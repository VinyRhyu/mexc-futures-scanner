"""Pilot confluence SHORT signal with causal 5m / 1h inputs. Paper only.

Original experimental implementation. Rules were selected after inspecting the TAO
event on 2026-11-19 and are NOT out-of-sample validated. This module does not
send Telegram notifications or place orders.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.request import urlopen


@dataclass(frozen=True)
class Parameters:
    rel_volume_min: float = 1.2
    recent_high_tolerance: float = 0.004  # 0.4% near prior high
    alert_rejection: float = 0.002  # close at least 0.2% below prior high
    atr_range_max: float = 2.0
    stop_buffer: float = 0.0001  # 1bp of entry
    rr_gross: float = 1.5
    min_rr_net: float = 1.0
    taker_fee_each: float = 0.0006  # simulation only, not verified user fee
    slippage_each: float = 0.0002  # simulation only
    max_hold_bars: int = 12  # 60 minutes
    prealert_cooldown_bars: int = 12


def _ema_last(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError("Insufficient EMA history")
    k = 2.0 / (period + 1)
    value = sum(values[:period]) / period
    for x in values[period:]:
        value = x * k + value * (1.0 - k)
    return value


def _iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


def validate_source(data: dict) -> tuple[list, list]:
    if not data.get("closed_candles_only"):
        raise ValueError("Use a verified closed-candles-only snapshot")
    c = data.get("candles", {})
    five, hourly = c.get("5m", []), c.get("1h", [])
    if len(five) < 34 or len(hourly) < 22:
        raise ValueError("Insufficient 5m or 1h candle history")
    for name, rows, step in [("5m", five, 300_000), ("1h", hourly, 3_600_000)]:
        if any(len(x) < 7 for x in rows):
            raise ValueError(f"{name} must contain time, OHLC and quote volume")
        if any(b[0] - a[0] != step for a, b in zip(rows, rows[1:])):
            raise ValueError(f"Gap or non-monotonic timestamps in {name}")
        if any(x[2] < max(x[1], x[4]) or x[3] > min(x[1], x[4]) for x in rows):
            raise ValueError(f"Malformed OHLC in {name}")
    return five, hourly


def scan_at(five: list, hourly: list, index: int, p: Parameters = Parameters()) -> dict:
    """Return only conditions observable when five[index] CLOSES.

    The source array may contain future candles, but this function never reads
    five[index+1:] or any 1h candle whose close is after the decision time.
    It does not consume the future entry open or future TP/SL candles.
    """
    if index < 20 or index >= len(five):
        return {"prealert": False, "trigger": False, "reason": "warmup_or_index"}
    bar = five[index]
    decision_ms = bar[0] + 300_000
    known_hours = [h for h in hourly if h[0] + 3_600_000 <= decision_ms]
    if len(known_hours) < 21:
        return {"prealert": False, "trigger": False, "reason": "hourly_warmup"}
    ema = _ema_last([float(h[4]) for h in known_hours], 20)
    h1_close, prev_h1_close = float(known_hours[-1][4]), float(known_hours[-2][4])
    trend = h1_close < ema and h1_close < prev_h1_close
    previous20 = five[index-20:index]
    last6 = five[index-6:index]
    prior3 = five[index-3:index]
    level = max(float(x[2]) for x in previous20)
    last_high = max(float(x[2]) for x in last6)
    failed_high = last_high >= level * (1-p.recent_high_tolerance)
    red = float(bar[4]) < float(bar[1])
    prealert = (trend and failed_high and red and
                float(bar[4]) < level * (1-p.alert_rejection))

    prior12 = five[index-12:index]
    base = median(float(x[6]) for x in prior12)
    ratio = float(bar[6])/base if base > 0 else 0
    trs = []
    for k in range(index-14,index):
        x, prev = five[k], five[k-1]
        trs.append(max(float(x[2])-float(x[3]),
                       abs(float(x[2])-float(prev[4])),
                       abs(float(x[3])-float(prev[4]))))
    atr = sum(trs)/len(trs)
    this_tr = max(float(bar[2])-float(bar[3]),
                  abs(float(bar[2])-float(five[index-1][4])),
                  abs(float(bar[3])-float(five[index-1][4])))
    close_below_lows = float(bar[4]) < min(float(x[3]) for x in prior3)
    trigger = (prealert and close_below_lows and ratio >= p.rel_volume_min
               and atr > 0 and this_tr <= p.atr_range_max * atr)
    return {
        "prealert": bool(prealert), "trigger": bool(trigger),
        "decision_at": _iso(decision_ms), "h1_close": h1_close,
        "h1_ema20": round(ema, 8), "prior_resistance": level,
        "relative_quote_volume": round(ratio, 4),
        "breaks_prior_three_lows": bool(close_below_lows),
        "range_to_prior_atr": round(this_tr / atr, 4) if atr > 0 else None,
    }


def replay(data: dict, p: Parameters = Parameters(), gate=None) -> dict:
    five, hourly = validate_source(data)
    prealerts, trades, skipped = [], [], []
    next_eligible = 20
    last_alert_index = -p.prealert_cooldown_bars - 1
    for i in range(20, len(five)-p.max_hold_bars):
        check = scan_at(five, hourly, i, p)
        if check.get("prealert") and i-last_alert_index >= p.prealert_cooldown_bars:
            prealerts.append({"at": check["decision_at"], "close": five[i][4],
                              "prior_resistance": check["prior_resistance"]})
            last_alert_index = i
        if i < next_eligible or not check.get("trigger"):
            continue
        # Gate is evaluated at signal close, before consulting the next M5 bar.
        # A rejected plan does not consume a 60-minute trading slot.
        if gate is not None and not gate(check, five, hourly, i):
            skipped.append({"at": check["decision_at"], "reason": "regime_gate"})
            continue

        # Next-bar open is a SIMULATED fill, not part of the causal signal.
        entry = float(five[i+1][1])
        stop = max(float(x[2]) for x in five[i-6:i+1]) + p.stop_buffer * entry
        risk = stop-entry
        if risk <= 0:
            skipped.append({"at": check["decision_at"], "reason": "invalid_stop"})
            continue
        target = entry-p.rr_gross*risk
        cost = 2*entry*(p.taker_fee_each+p.slippage_each)
        net_rr = (entry-target-cost)/(risk+cost)
        if net_rr < p.min_rr_net:
            skipped.append({"at": check["decision_at"], "reason": "net_rr_below_min",
                            "net_rr": round(net_rr, 4)})
            continue

        result = "TIME"
        exit_price = float(five[i+p.max_hold_bars][4])
        exit_index = i+p.max_hold_bars
        for k in range(i+1, i+p.max_hold_bars+1):
            candle = five[k]
            stop_touched = float(candle[2]) >= stop
            target_touched = float(candle[3]) <= target
            if stop_touched and target_touched:
                result, exit_price, exit_index = "AMBIGUOUS", None, k
                break
            if stop_touched:
                result, exit_price, exit_index = "SL", stop, k
                break
            if target_touched:
                result, exit_price, exit_index = "TP", target, k
                break
        gross_r = (entry-exit_price)/risk if exit_price is not None else None
        net_r = (entry-exit_price-cost)/(risk+cost) if exit_price is not None else None
        trades.append({
            "signal_at": check["decision_at"], "entry_at": _iso(five[i+1][0]),
            "entry": entry, "stop": round(stop, 8), "target": round(target, 8),
            "gross_rr": p.rr_gross, "net_rr_ex_ante": round(net_rr, 4),
            "relative_quote_volume": check["relative_quote_volume"],
            "result": result, "exit_at": _iso(five[exit_index][0]),
            "exit_price": exit_price,
            "gross_r": round(gross_r, 4) if gross_r is not None else None,
            "net_r": round(net_r, 4) if net_r is not None else None,
            "note": "Hypothetical next-open fill, no order-book simulation",
        })
        next_eligible = exit_index+1
    return {
        "source": data.get("venue"), "snapshot_collected_utc": data.get("collected_utc"),
        "symbol": data.get("symbol"), "hypothesis_selected_after_tao": True,
        "parameters": asdict(p), "prealerts": prealerts, "trades": trades,
        "skipped": skipped,
        "outcomes": {v: sum(t["result"] == v for t in trades)
                     for v in ("TP", "SL", "TIME", "AMBIGUOUS")},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline SHORT confluence pilot; no trading")
    arg = ap.add_mutually_exclusive_group(required=True)
    arg.add_argument("--input", type=Path, help="Local closed-candle snapshot JSON")
    arg.add_argument("--url", help="Public JSON snapshot URL")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    if args.url:
        with urlopen(args.url, timeout=20) as response:
            source = json.load(response)
    else:
        source = json.loads(args.input.read_text(encoding="utf-8"))
    report = replay(source)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
