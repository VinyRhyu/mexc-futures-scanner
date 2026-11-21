"""Research-only F/G SHORT reversal setups, pre-registered before earlier 42-day test.

No orders, Telegram, live scanner changes, auto-optimization, or future data at decision.
See docs/confluence-v3-preregistered.md for the frozen hypotheses.
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
import time
from collections import Counter
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_pilot import Parameters, replay as replay_baseline, _ema_last

FIVE_MS = 300_000
HOUR_MS = 3_600_000
SYMBOLS = ("TAO", "SOL", "AVAX", "ENA", "DOT", "ZEC", "HYPE", "AAVE", "BTC", "ETH")
VARIANTS = ("A_baseline", "F_sweep_rejection", "G_break_retest")


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def true_range(c, previous_close):
    return max(float(c[2]) - float(c[3]), abs(float(c[2]) - previous_close),
               abs(float(c[3]) - previous_close))


def atr_before(five, i):
    return sum(true_range(five[k], float(five[k - 1][4]))
               for k in range(i - 14, i)) / 14


def h1_bias_below_ema_at(hourly, decision_ms, hour_ends=None):
    """No current H1 bar allowed; >=20 closed H1 required."""
    if hour_ends is None:
        hour_ends = [x[0] + HOUR_MS for x in hourly]
    count = bisect.bisect_right(hour_ends, decision_ms)
    if count < 20:
        return False
    closes = [float(x[4]) for x in hourly[:count]]
    return closes[-1] < _ema_last(closes, 20)


def candidate_f(five, hourly, index, ends=None):
    """Only candles <= five[index] and closed H1 candles."""
    if index < 25 or index >= len(five):
        return None
    c = five[index]
    at = c[0] + FIVE_MS
    if not h1_bias_below_ema_at(hourly, at, ends):
        return None
    atr = atr_before(five, index)
    if atr <= 0:
        return None
    prior = five[index - 24:index]
    resistance = max(float(x[2]) for x in prior)
    hi, lo, op, close = map(float, (c[2], c[3], c[1], c[4]))
    width = hi - lo
    if width <= 0 or not .8 * atr <= true_range(c, float(five[index-1][4])) <= 3*atr:
        return None
    wick = hi - max(op, close)
    rel_volume = float(c[6]) / max(1e-12, median(float(x[6]) for x in five[index-12:index]))
    if (hi < resistance + .1*atr or close >= resistance or close >= op
            or wick < .4*width or rel_volume < 1.5):
        return None
    return {"signal_at": iso(at), "signal_index": index, "signal_ms": at,
            "stop_raw": hi + .1*atr, "volume_ratio": rel_volume,
            "level": resistance, "atr": atr}


def candidate_g(five, hourly, index, ends=None, through_index=None):
    """Find a break and its first qualifying retest among KNOWN closed candles.

    In a replay, set through_index to the current candle index. This prevents
    a future retest from influencing decisions at the break candle.
    """
    last_known = min(len(five)-1, through_index if through_index is not None else len(five)-1)
    if index < 25 or index + 1 > last_known:
        return None
    c = five[index]
    at = c[0] + FIVE_MS
    if not h1_bias_below_ema_at(hourly, at, ends):
        return None
    atr = atr_before(five, index)
    if atr <= 0:
        return None
    support = min(float(x[3]) for x in five[index-12:index])
    op, close = float(c[1]), float(c[4])
    rel_volume = float(c[6]) / max(1e-12, median(float(x[6]) for x in five[index-12:index]))
    if (close >= support or close >= op or op - close < .6*atr or rel_volume < 1.5):
        return None
    for j in range(index+1, min(index+4, last_known+1)):
        r = five[j]
        reject = (float(r[2]) >= support*.999
                  and support-1.2*atr <= float(r[4]) < support
                  and float(r[4]) < float(r[1]))
        if reject:
            return {"signal_at": iso(r[0]+FIVE_MS), "signal_index": j,
                    "signal_ms": r[0]+FIVE_MS,
                    "stop_raw": max(float(x[2]) for x in five[index:j+1]) + .1*atr,
                    "volume_ratio": rel_volume, "level": support, "atr": atr}
    return None


def execute(five, candidate, param=Parameters(), max_hold=24):
    """Simulated NEXT BAR open; no fill guarantee, never used to create signal."""
    i = candidate["signal_index"]
    if i+max_hold >= len(five):
        return None
    entry = float(five[i+1][1])
    stop = candidate["stop_raw"]
    risk = stop - entry
    if risk <= 0:
        return None
    target = entry-1.8*risk
    # Two-sided hypothetical taker/slippage costs, as in baseline.
    cost = 2*entry*(param.taker_fee_each+param.slippage_each)
    rr_net = (entry-target-cost)/(risk+cost)
    if rr_net < 1.2:
        return None
    result, exit_price, end_index = "TIME", float(five[i+max_hold][4]), i+max_hold
    for k in range(i+1,i+max_hold+1):
        c=five[k]
        bad = float(c[2]) >= stop
        good = float(c[3]) <= target
        if bad or good:
            result = "AMBIGUOUS" if bad and good else "SL" if bad else "TP"
            exit_price = None if bad and good else stop if bad else target
            end_index = k
            break
    net_r = (entry-exit_price-cost)/(risk+cost) if exit_price is not None else None
    return {"signal_at": candidate["signal_at"], "entry_at": iso(five[i+1][0]),
            "exit_at": iso(five[end_index][0]),
            "result": result, "entry": round(entry,8), "stop": round(stop,8),
            "target": round(target,8), "net_r": round(net_r, 5) if net_r is not None else None,
            "relative_quote_volume": round(candidate["volume_ratio"], 5),
            "net_rr_ex_ante": round(rr_net,5)}


def replay_structural(five, hourly, variant, param=Parameters()):
    assert variant in ("F_sweep_rejection", "G_break_retest")
    ends=[x[0]+HOUR_MS for x in hourly]
    next_allowed_index=25
    trades=[]
    for i in range(25,len(five)-25):
        if i < next_allowed_index:
            continue
        if variant == "F_sweep_rejection":
            candidate = candidate_f(five,hourly,i,ends)
        else:
            # At close of bar i, check only break events up to three candles
            # ago; do not look at any retest that closes after bar i.
            candidate = None
            for break_index in range(max(25,i-3),i):
                possible = candidate_g(five,hourly,break_index,ends,through_index=i)
                if possible is not None and possible["signal_index"] == i:
                    candidate = possible
                    break
        if candidate is None:
            continue
        trade=execute(five,candidate,param,24)
        if trade is None:
            continue
        trades.append(trade)
        end_ms = int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000)
        # If a G candidate i has retest at j, guard all bars until that exit.
        next_allowed_index = max(candidate["signal_index"]+1,
                                 bisect.bisect_right([x[0] for x in five], end_ms))
    return trades


def metrics(trades, low, high):
    pool = [t for t in trades if low <= t["signal_at"] < high]
    p = select_portfolio(pool)
    return {"candidates":len(pool), "selected":p["n"],
            "TP":sum(t["result"]=="TP" for t in p["chosen"]),
            "SL":sum(t["result"]=="SL" for t in p["chosen"]),
            "TIME":sum(t["result"]=="TIME" for t in p["chosen"]),
            "net_R":p["net_R_sum"], "roi_pct":p["return_pct_at_1pct_risk"],
            "max_dd_pct":p["max_drawdown_pct_at_1pct_risk"],
            "trades_day":round(p["n"] / ((datetime.fromisoformat(high) -
                                        datetime.fromisoformat(low)).total_seconds()/86400), 3)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--days",type=int,default=42)
    parser.add_argument("--end",default="2026-10-09T11:00:00+00:00")
    args=parser.parse_args()
    if args.days != 42 or args.end != "2026-10-09T11:00:00+00:00":
        parser.error("V3 pre-registered date window is frozen")
    end=int(datetime.fromisoformat(args.end).timestamp())
    start=end - 42*86400
    mid=start+21*86400
    starts=[iso(t*1000) for t in (start,mid,end)]
    results={v:[] for v in VARIANTS}
    errors=[]
    print("V3_FROZEN_TEST " + json.dumps({"periods":starts,"symbols":SYMBOLS,
                                         "doc":"docs/confluence-v3-preregistered.md"}),flush=True)
    for s in SYMBOLS:
        sym=s+"_USDT"
        try:
            h = candles(sym,"Min60",start-160*3600,end)
            m = candles(sym,"Min5",start-30*300,end)
            data={"venue":"mexc_swap","collected_utc":args.end,
                  "symbol":sym,"closed_candles_only":True,
                  "candles":{"5m":m,"1h":h}}
            base=replay_baseline(data)
            variants={"A_baseline":base["trades"],
                      "F_sweep_rejection":replay_structural(m,h,"F_sweep_rejection"),
                      "G_break_retest":replay_structural(m,h,"G_break_retest")}
            for name,trades in variants.items():
                results[name].extend({**t,"symbol":sym} for t in trades
                                     if starts[0] <= t["signal_at"] < starts[-1])
            print("V3_ASSET "+json.dumps({"symbol":sym,"M5":len(m),"H1":len(h),
                    "candidates":{n:len(t) for n,t in variants.items()}}),flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"reason":f"{type(exc).__name__}: {str(exc)[:200]}"})
            print("V3_SOURCE_ERROR "+json.dumps(errors[-1]),flush=True)
    if errors:
        raise RuntimeError("Refusing incomplete V3 evaluation: "+repr(errors))
    for name,trades in results.items():
        reports={k:metrics(trades,lo,hi) for k,lo,hi in
                 [("early21",starts[0],starts[1]),("late21",starts[1],starts[2]),
                  ("full42",starts[0],starts[2])]}
        m=reports["full42"]
        ok=(all(reports[k]["roi_pct"]>0 for k in ("early21","late21"))
            and m["selected"]>=30 and m["trades_day"]<=3
            and m["max_dd_pct"]<=10
            and m["roi_pct"] > metrics(results["A_baseline"],starts[0],starts[2])["roi_pct"])
        print("V3_VARIANT "+json.dumps({"name":name,"windows":reports,
              "advance":ok,"per_symbol":{s:sum(t["symbol"]==s+"_USDT" for t in trades)
                                         for s in SYMBOLS},
              "historical_not_prospective":True},sort_keys=True),flush=True)


if __name__=="__main__":
    main()
