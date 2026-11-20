"""Pre-registered SHORT SMC-R: sweep of prior M5 liquidity -> bearish 3-candle FVG.

Original research implementation (not copied from upstream). Signals are causal:
only data from completed M5 and H1 candles enter entry decisions.
No exchange orders, Telegram notifications or production changes.

Frozen specification: docs/smc-liquidity-fvg-preregistered-2026-11-20.md.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import Counter
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, SYMBOLS, atr_before, iso, replay_structural,
)
from scripts.audit_confluence_pilot import Parameters

WINDOWS = {
    "T": ("2026-06-05T11:00:00+00:00", "2026-07-17T11:00:00+00:00"),
    "U": ("2026-07-17T11:00:00+00:00", "2026-08-28T11:00:00+00:00"),
    "V": ("2026-08-28T11:00:00+00:00", "2026-10-09T11:00:00+00:00"),
    "W": ("2026-10-09T11:00:00+00:00", "2026-11-20T11:00:00+00:00"),
}


def h1_states(hourly):
    """Build causal EMA20 and H1-close state, one state per COMPLETED H1 candle."""
    completed = [int(row[0]) + HOUR_MS for row in hourly]
    if any(a >= b for a, b in zip(completed, completed[1:])):
        raise ValueError("H1 order not strict")
    flags = []
    ema = None
    opening = []
    for i, h in enumerate(hourly):
        close = float(h[4])
        if i < 19:
            opening.append(close)
            if i == 19:
                ema = sum(opening) / 20.0
        else:
            ema = close * (2.0 / 21.0) + ema * (19.0 / 21.0)
        flags.append(i >= 19 and close < ema)
    return completed, flags


def h1_is_down(ms, ends, flags):
    index = bisect.bisect_right(ends, ms) - 1
    return index >= 19 and flags[index]


def detect_sweep(five, index):
    """Only closes/volumes through index; level from 36 candles BEFORE index."""
    if index < 37 or index >= len(five):
        return None
    bar = five[index]
    atr = atr_before(five, index)
    if atr <= 0:
        return None
    high = float(bar[2])
    low = float(bar[3])
    close = float(bar[4])
    op = float(bar[1])
    level = max(float(x[2]) for x in five[index-36:index])
    span = high-low
    wick = high-max(op, close)
    quote_vols = [float(x[6]) for x in five[index-12:index]]
    rv = float(bar[6]) / max(1e-12, median(quote_vols))
    if (span <= 0 or high < level + 0.1 * atr or close >= level
            or wick < 0.25 * span or rv < 1.0):
        return None
    return {"sweep_index": index, "sweep_ms": int(bar[0]) + FIVE_MS,
            "high": high, "low": low, "level": level, "atr": atr,
            "volume_ratio": rv}


def detect_signal_at(five, hourly, index, h1_end_states=None):
    """A confirmed SHORT signal exists ONLY on close of five[index].

    FVG is three-candle pattern high[i] < low[i-2], and a qualifying sweep
    must have happened from i-4 to i-2. NO bar after index is inspected.
    """
    if index < 39 or index >= len(five):
        return None
    ends, flags = h1_end_states if h1_end_states is not None else h1_states(hourly)
    decision_ms = int(five[index][0]) + FIVE_MS
    if not h1_is_down(decision_ms, ends, flags):
        return None

    bar = five[index]
    close = float(bar[4])
    op = float(bar[1])
    high = float(bar[2])
    rv = float(bar[6]) / max(
        1e-12, median(float(x[6]) for x in five[index-12:index]))
    if close >= op or rv < 1.2:
        return None

    for j in range(index - 4, index - 1):
        origin = detect_sweep(five, j)
        if origin is None or not h1_is_down(origin["sweep_ms"], ends, flags):
            continue
        atr = origin["atr"]
        gap = float(five[index-2][3]) - high
        if (gap < .05 * atr or
                op - close < .6 * atr or
                close >= origin["low"]):
            continue
        return {
            "signal_ms": decision_ms,
            "signal_at": iso(decision_ms),
            "signal_index": index,
            "sweep_index": j,
            "sweep_at": iso(origin["sweep_ms"]),
            "stop_raw": origin["high"] + .1 * atr,
            "volume_ratio": rv,
            "liquidity_level": origin["level"],
            "fvg_upper": float(five[index-2][3]),
            "fvg_lower": high,
            "gap_atr": gap / atr,
            "atr": atr,
        }
    return None


def execute_short(five, setup, *, gross_rr=2.0, hold_bars=24,
                  params=Parameters()):
    """Simulate execution AFTER signal close; candle high/low order is unknown."""
    i = setup["signal_index"]
    if i + hold_bars >= len(five):
        return None
    entry = float(five[i+1][1])
    stop = float(setup["stop_raw"])
    risk = stop - entry
    if risk <= 0:
        return None
    target = entry - gross_rr * risk
    cost = 2.0 * entry * (params.taker_fee_each + params.slippage_each)
    rr_net = (gross_rr * risk - cost) / (risk + cost)
    if rr_net < 1.2:
        return None

    state = "TIME"
    exit_price = float(five[i+hold_bars][4])
    end_index = i + hold_bars
    for k in range(i+1, i+hold_bars+1):
        high, low = float(five[k][2]), float(five[k][3])
        sl = high >= stop
        tp = low <= target
        if sl or tp:
            state = "AMBIGUOUS" if sl and tp else "SL" if sl else "TP"
            exit_price = None if sl and tp else stop if sl else target
            end_index = k
            break
    net_r = ((entry-exit_price-cost) / (risk + cost)
             if exit_price is not None else None)
    return {
        "signal_at": setup["signal_at"],
        "sweep_at": setup["sweep_at"],
        "entry_at": iso(int(five[i+1][0])),
        "exit_at": iso(int(five[end_index][0])),
        "result": state, "entry": round(entry,8),
        "stop": round(stop,8), "target": round(target,8),
        "net_r": round(net_r,5) if net_r is not None else None,
        "relative_quote_volume": round(setup["volume_ratio"],5),
        "net_rr_ex_ante": round(rr_net,5),
        "fvg_gap_atr": round(setup["gap_atr"],4),
    }


def replay_smc(five, hourly):
    ends_flags = h1_states(hourly)
    trades = []
    starts = [int(row[0]) for row in five]
    next_index = 40
    diagnostics = Counter()
    for i in range(40, len(five)-25):
        if i < next_index:
            continue
        setup = detect_signal_at(five, hourly, i, ends_flags)
        if setup is None:
            continue
        diagnostics["confirmed_structural_fvg"] += 1
        trade = execute_short(five, setup)
        if trade is None:
            diagnostics["rejected_net_rr_or_bad_stop"] += 1
            continue
        trades.append(trade)
        end_ms = int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000)
        next_index = bisect.bisect_right(starts, end_ms)
        diagnostics["executed_paper"] += 1
    return trades, dict(diagnostics)


def portfolio_metrics(trades, first, last):
    pool = [t for t in trades if first <= t["signal_at"] < last]
    chosen = select_portfolio(pool)
    filtered = chosen["chosen"]
    outcomes = dict(Counter(t["result"] for t in filtered))
    n_days = (datetime.fromisoformat(last)-datetime.fromisoformat(first)).total_seconds()/86400
    return {
        "candidates": len(pool),
        "selected": chosen["n"],
        "outcomes": outcomes,
        "portfolio_net_R": chosen["net_R_sum"],
        "portfolio_roi_pct_at_1pct_risk": chosen["return_pct_at_1pct_risk"],
        "portfolio_max_drawdown_pct": chosen["max_drawdown_pct_at_1pct_risk"],
        "signals_per_day": round(chosen["n"]/n_days,4),
        "net_R_per_trade": round(chosen["net_R_sum"]/chosen["n"],4) if chosen["n"] else None,
        "by_symbol": dict(Counter(t["symbol"] for t in filtered)),
    }


def run(window):
    start_iso, end_iso = WINDOWS[window]
    start = int(datetime.fromisoformat(start_iso).timestamp())
    end = int(datetime.fromisoformat(end_iso).timestamp())
    split_iso = datetime.fromtimestamp(start+21*86400,timezone.utc).isoformat()
    record = {"window":window,"dates":[start_iso,split_iso,end_iso],
              "symbols":SYMBOLS, "model":"SMC-R SHORT causal", "baseline":"F unchanged",
              "params":"docs/smc-liquidity-fvg-preregistered-2026-11-20.md"}
    print("SMC_RUN "+json.dumps(record,sort_keys=True),flush=True)
    combined = {"F_original":[], "SMC_R": []}
    errors = []
    diagnostics = {}
    for symbol in SYMBOLS:
        contract = symbol+"_USDT"
        try:
            # H1 warmup >=24 bars and M5 warmup >40 bars, with continuous data.
            h = candles(contract,"Min60",start-80*3600,end)
            m = candles(contract,"Min5",start-52*300,end)
            base = replay_structural(m,h,"F_sweep_rejection")
            challenger, diag = replay_smc(m,h)
            for label, rows in (("F_original",base),("SMC_R",challenger)):
                combined[label].extend({**row,"symbol":contract} for row in rows
                                       if start_iso <= row["signal_at"] < end_iso)
            diagnostics[contract]=diag
            print("SMC_ASSET "+json.dumps({
                "window":window, "symbol":contract, "M5":len(m),"H1":len(h),
                "F":len(base),"SMC":len(challenger),"diagnostics":diag
            },sort_keys=True),flush=True)
        except Exception as exc:
            errors.append({"symbol":contract,
                           "error":f"{type(exc).__name__}: {str(exc)[:180]}"})
            print("SMC_DATA_FAIL "+json.dumps({"window":window,**errors[-1]}),flush=True)
    if errors:
        print("SMC_INCOMPLETE "+json.dumps({"window":window,"failed":errors}),flush=True)
        raise RuntimeError(f"Refusing partial {window}: {len(errors)} unavailable symbols")

    for label, trades in combined.items():
        report = {
            "early21":portfolio_metrics(trades,start_iso,split_iso),
            "late21":portfolio_metrics(trades,split_iso,end_iso),
            "full42":portfolio_metrics(trades,start_iso,end_iso),
        }
        print("SMC_VARIANT "+json.dumps({
            "window":window,"model":label,"results":report,
            "per_symbol_candidate_count":dict(Counter(t["symbol"] for t in trades)),
            "historical_not_prospective":True,
        },sort_keys=True),flush=True)

    print("SMC_DONE "+json.dumps({
        "window":window,"symbols_complete":len(SYMBOLS),
        "model_diagnostics":diagnostics,
        "not_live_executable":True,
    },sort_keys=True),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--window",required=True,choices=tuple(WINDOWS))
    args=parser.parse_args()
    run(args.window)


if __name__ == "__main__":
    main()
