"""Extended evaluation of frozen confluence pilot, MEXC public futures candles only.
Research/paper, no Telegram, no order execution, no changes to scanner runtime.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from scripts.audit_confluence_pilot import Parameters, replay

BASE = "https://api.mexc.com"
PERIOD = {"Min5": 300, "Min60": 3600}

def candles(symbol: str, interval: str, start: int, end: int):
    tf = PERIOD[interval]
    start -= start % tf
    end -= end % tf
    expected = list(range(start, end, tf))
    results = {}
    for lo in range(start, end, tf * 1400):
        hi = min(end - tf, lo + (1400 - 1) * tf)
        url = f"{BASE}/api/v1/contract/kline/{symbol}?" + urlencode(
            {"interval": interval, "start": lo, "end": hi})
        data = None
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={"User-Agent": "ResearchPaperOnly/1.0"}), timeout=18) as resp:
                    data = json.load(resp)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        if not isinstance(data, dict) or not data.get("success") or int(data.get("code", -1)) != 0:
            raise ValueError(f"{symbol} {interval}: invalid API response {str(data)[:140]}")
        d = data.get("data") or {}
        keys = ("time", "open", "high", "low", "close", "vol", "amount")
        if any(k not in d for k in keys) or len({len(d[k]) for k in keys}) != 1:
            raise ValueError(f"{symbol} {interval}: missing/inconsistent candle columns")
        for x in zip(*(d[k] for k in keys)):
            ts = int(x[0])
            row = [ts * 1000] + [float(v) for v in x[1:]]
            if ts in results and results[ts] != row:
                raise ValueError(f"{symbol} {interval}: conflicting duplicate timestamp")
            results[ts] = row
        time.sleep(0.08)
    if set(results) != set(expected):
        missing = sorted(set(expected) - set(results))
        raise ValueError(f"{symbol} {interval}: incomplete history {len(results)}/{len(expected)}; missing={missing[:3]}")
    rows = [results[t] for t in expected]
    if any(r[2] < max(r[1], r[4]) or r[3] > min(r[1], r[4])
           or not all(math.isfinite(v) for v in r[1:]) for r in rows):
        raise ValueError(f"{symbol} {interval}: malformed OHLC/volume")
    return rows

def select_portfolio(trades):
    """One position at a time; tiebreaker uses ONLY known relative volume."""
    ordered = sorted(trades, key=lambda t: (t["signal_at"], -t["relative_quote_volume"], t["symbol"]))
    balance, peak, dd, total, held_until = 1.0, 1.0, 0.0, 0.0, ""
    chosen = []
    for t in ordered:
        if held_until and t["signal_at"] < held_until:
            continue
        net_r = t["net_r"] if t["net_r"] is not None else -1.0
        balance *= 1 + .01 * net_r
        peak = max(peak, balance)
        dd = max(dd, 1 - balance / peak)
        total += net_r
        held_until = (datetime.fromisoformat(t["exit_at"]) + timedelta(minutes=5)).isoformat()
        chosen.append({"symbol": t["symbol"], "signal_at": t["signal_at"],
                       "exit_at": t["exit_at"], "result": t["result"], "net_r": net_r})
    return {"n": len(chosen), "net_R_sum": round(total, 3),
            "return_pct_at_1pct_risk": round((balance - 1) * 100, 3),
            "max_drawdown_pct_at_1pct_risk": round(dd * 100, 3),
            "chosen": chosen}

def summary(results, days, end):
    trades = [dict(t, symbol=x["symbol"]) for x in results
              if x["status"] == "ok" for t in x["trades"]]
    by_symbol = [{"symbol": x["symbol"], "n": len(x["trades"]), "prealerts": x["prealerts"],
                  "outcomes": dict(Counter(t["result"] for t in x["trades"])),
                  "sum_net_R": round(sum(t["net_r"] if t["net_r"] is not None else -1
                                         for t in x["trades"]), 3)}
                 for x in results if x["status"] == "ok"]
    days_map = defaultdict(list)
    for t in trades:
        days_map[t["signal_at"][:10]].append(t)
    by_day = [{"day": day, "n": len(ts), "outcomes": dict(Counter(t["result"] for t in ts)),
               "sum_net_R": round(sum(t["net_r"] if t["net_r"] is not None else -1 for t in ts), 3)}
              for day, ts in sorted(days_map.items())]
    return {"source": "MEXC PUBLIC FUTURES MARKET; historical candles not actual executions",
            "model": "H1/M5 short confluence, fitted after observing TAO 19 Nov",
            "days": days, "end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat(),
            "ok_assets": len(by_symbol),
            "skipped": [{k: v for k, v in r.items() if k != "trades"}
                        for r in results if r["status"] != "ok"],
            "total_signals": len(trades), "outcomes": dict(Counter(t["result"] for t in trades)),
            "net_R_sum_independent_signals_not_portfolio": round(
                sum(t["net_r"] if t["net_r"] is not None else -1 for t in trades), 3),
            "per_symbol": by_symbol, "per_day": by_day,
            "one_at_a_time": select_portfolio(trades),
            "assumed_taker_fee_per_side": Parameters().taker_fee_each,
            "assumed_slippage_per_side": Parameters().slippage_each,
            "warnings": ["No actual fills, funding, min lot or liquidation",
                         "Do not treat correlated signals as independent",
                         "Rule selected after viewing TAO; not a prospective test"]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=21)
    p.add_argument("--symbols", nargs="+",
                   default=["TAO", "SOL", "AVAX", "ENA", "DOT", "ZEC", "HYPE", "AAVE", "BTC", "ETH"])
    p.add_argument("--end", default="2026-11-20T11:00:00+00:00")
    args = p.parse_args()
    if not 5 <= args.days <= 45:
        p.error("days must be 5..45")
    end = int(datetime.fromisoformat(args.end.replace("Z", "+00:00")).timestamp())
    start = end - args.days * 86400
    results = []
    print(f"START MEXC {args.days} days; assets {len(args.symbols)}; END {args.end}", flush=True)
    for a in args.symbols:
        sym = a if a.endswith("_USDT") else a + "_USDT"
        try:
            h = candles(sym, "Min60", start - 36 * 3600, end)
            m = candles(sym, "Min5", start - 24 * 300, end)
            data = {"venue": "mexc_swap", "collected_utc": args.end,
                    "closed_candles_only": True, "symbol": sym,
                    "candles": {"5m": m, "1h": h}}
            result = replay(data)
            threshold = datetime.fromtimestamp(start, timezone.utc).isoformat()
            ts = [t for t in result["trades"] if t["signal_at"] >= threshold]
            prealerts = sum(x["at"] >= threshold for x in result["prealerts"])
            results.append({"symbol": sym, "status": "ok", "trades": ts, "prealerts": prealerts})
            print(f"ASSET {sym} candles M5={len(m)} H1={len(h)} candidates={len(ts)} "
                  f"outcomes={dict(Counter(t['result'] for t in ts))}", flush=True)
        except Exception as exc:
            results.append({"symbol": sym, "status": "source_error",
                            "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
            print(f"ASSET {sym}: SOURCE ERROR {type(exc).__name__} {str(exc)[:180]}", flush=True)
    report = summary(results, args.days, end)
    print("=== EXTENDED VALIDATION SUMMARY JSON ===", flush=True)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
    if report["ok_assets"] < 5:
        print("INSUFFICIENT COVERAGE: no conclusion", flush=True)
        sys.exit(2)

if __name__ == "__main__":
    main()
