"""Frozen v4: one-M5 confirmation after false resistance breakout (SHORT).

Paper research only. Compare F (original) versus F_confirm_1bar using same MEXC
historical data and costs; see docs/confluence-v4-preregistered.md.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import Counter
from datetime import datetime, timezone

from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, SYMBOLS, candidate_f, execute, iso, metrics,
    replay_structural,
)

WINDOWS = {
    "U": ("2026-07-17T11:00:00+00:00", "2026-08-28T11:00:00+00:00"),
    "V": ("2026-08-28T11:00:00+00:00", "2026-10-09T11:00:00+00:00"),
    "W": ("2026-10-09T11:00:00+00:00", "2026-11-20T11:00:00+00:00"),
}


def confirmation_at(five, hourly, confirm_index: int, hour_ends=None):
    """Only M5 candles through *confirm_index* and completed H1 bars.

    Returns a signal formed when confirmation bar closes. In particular this
    function never evaluates a future confirmation bar at sweep detection time.
    """
    sweep_index = confirm_index - 1
    if sweep_index < 25 or confirm_index >= len(five):
        return None
    origin = candidate_f(five, hourly, sweep_index, hour_ends)
    if origin is None:
        return None
    candle = five[confirm_index]
    sweep = five[sweep_index]
    if (float(candle[4]) >= float(sweep[3])
            or float(candle[4]) >= float(candle[1])
            or float(candle[2]) >= float(origin["stop_raw"])):
        return None
    return {
        "signal_at": iso(candle[0] + FIVE_MS),
        "signal_index": confirm_index,
        "signal_ms": candle[0] + FIVE_MS,
        "stop_raw": origin["stop_raw"],  # frozen before confirmation
        "volume_ratio": origin["volume_ratio"],
        "origin_sweep_at": origin["signal_at"],
        "origin_index": sweep_index,
        "atr": origin["atr"],
        "level": origin["level"],
    }


def replay_confirm(five, hourly):
    ends = [h[0] + HOUR_MS for h in hourly]
    starts = [b[0] for b in five]
    next_allowed = 26
    eligible = 0
    all_confirmed = 0
    trades = []
    paired = []
    for i in range(26, len(five) - 25):
        candidate = confirmation_at(five, hourly, i, ends)
        if candidate is None:
            continue
        all_confirmed += 1
        if i < next_allowed:
            continue
        eligible += 1
        trade = execute(five, candidate, max_hold=24)
        if trade is None:
            continue
        original = candidate_f(five, hourly, i-1, ends)
        earlier = execute(five, original, max_hold=24)
        paired.append({
            "origin_sweep_at": candidate["origin_sweep_at"],
            "confirmation_at": candidate["signal_at"],
            "original_F_outcome": earlier["result"] if earlier else None,
            "confirmed_outcome": trade["result"],
            "original_F_net_R": earlier["net_r"] if earlier else None,
            "confirmed_net_R": trade["net_r"],
        })
        trades.append(trade)
        exit_ms = int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000)
        next_allowed = bisect.bisect_right(starts, exit_ms)
    return {"trades": trades, "confirmations_observed": all_confirmed,
            "confirmations_eligible": eligible, "paired": paired}


def run(window: str):
    lo, hi = WINDOWS[window]
    start = int(datetime.fromisoformat(lo).timestamp())
    end = int(datetime.fromisoformat(hi).timestamp())
    mid = start+21*86400
    midpoint = datetime.fromtimestamp(mid, timezone.utc).isoformat()
    all_trades = {"F_original": [], "F_confirm_1bar": []}
    obs = {}
    failures = []
    print("V4_PREDECLARED "+json.dumps({"window":window,"start":lo,"split":midpoint,
        "end":hi,"assets":SYMBOLS,"hypothesis":"docs/confluence-v4-preregistered.md"}),flush=True)
    for base in SYMBOLS:
        sym=base+"_USDT"
        try:
            h = candles(sym, "Min60", start-160*3600, end)
            five = candles(sym, "Min5", start-30*300, end)
            orig = replay_structural(five, h, "F_sweep_rejection")
            conf = replay_confirm(five, h)
            orig=[{**t,"symbol":sym} for t in orig if lo <= t["signal_at"] < hi]
            good=[{**t,"symbol":sym} for t in conf["trades"] if lo <= t["signal_at"] < hi]
            all_trades["F_original"].extend(orig)
            all_trades["F_confirm_1bar"].extend(good)
            obs[sym]={"M5":len(five),"H1":len(h),"F_trades":len(orig),
                      "confirmed_trades":len(good),
                      "confirmed_observed":conf["confirmations_observed"],
                      "confirmed_eligible":conf["confirmations_eligible"],
                      "paired":conf["paired"]}
            print("V4_ASSET "+json.dumps({"symbol":sym,"M5":len(five),"H1":len(h),
                 "original_F":len(orig),"confirmed":len(good)}),flush=True)
        except Exception as exc:
            failures.append({"symbol":sym,"error":f"{type(exc).__name__}: {str(exc)[:200]}"})
            print("V4_SOURCE_ERROR "+json.dumps(failures[-1]),flush=True)
    if failures:
        print("V4_INCOMPLETE_COVERAGE "+json.dumps({"window":window,"failures":failures}),flush=True)
        raise RuntimeError(f"Refusing incomplete {window}: {len(failures)} unavailable symbols")

    out={}
    for name, trades in all_trades.items():
        early=metrics(trades,lo,midpoint)
        late=metrics(trades,midpoint,hi)
        full=metrics(trades,lo,hi)
        out[name]={"early21":early,"late21":late,"full42":full}
        print("V4_VARIANT "+json.dumps({"window":window,"name":name,"results":out[name],
             "per_asset":{s:sum(t["symbol"]==s+"_USDT" for t in trades) for s in SYMBOLS}
             },sort_keys=True),flush=True)
    pairs=[p for x in obs.values() for p in x["paired"]
           if lo <= p["confirmation_at"] < hi]
    comparable=[p for p in pairs if p["original_F_outcome"] is not None]
    print("V4_COMPARISON "+json.dumps({"window":window,"comparison":out,
          "observed_confirmations":sum(x["confirmed_observed"] for x in obs.values()),
          "eligible_confirmations":sum(x["confirmed_eligible"] for x in obs.values()),
          "paired_origin_outcomes":dict(Counter(x["original_F_outcome"] or "NO_ORIGINAL_TRADE" for x in pairs)),
          "paired_confirm_outcomes":dict(Counter(x["confirmed_outcome"] for x in pairs)),
          "paired_comparable_events":len(comparable),
          "paired_comparable_original_net_R":round(sum(x["original_F_net_R"] if x["original_F_net_R"] is not None else -1 for x in comparable),4),
          "paired_comparable_confirm_net_R":round(sum(x["confirmed_net_R"] if x["confirmed_net_R"] is not None else -1 for x in comparable),4),
          "paired_original_absent":sum(x["original_F_outcome"] is None for x in pairs),
          "note":"Only events executable under BOTH entry rules form valid pairs; strategy portfolios can differ due to overlapping positions",
          "historical_not_prospective":True},sort_keys=True),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window",choices=tuple(WINDOWS),required=True)
    args=p.parse_args()
    run(args.window)


if __name__=="__main__":
    main()
