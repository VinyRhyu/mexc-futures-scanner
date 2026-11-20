"""Frozen HYPE two-stage WATCH→CONFIRM rules transferred to four full weeks.

The detectors and execution rules are IMPORTED intact from the earlier
16–17/11 evaluation. The only mutable global is the *window boundary*
used to prevent new confirmation after a period's end.

PAPER RESEARCH. NO LIVE ORDERS / TELEGRAM / PRODUCTION.
Pre-registration: docs/hype-watch-transfer-preregistered-2026-11-20.md
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, iso
from scripts.audit_hype_three_regimes import ema, context
from scripts.audit_hype_two_stage_1617 import (
    watch_at, score_direction, confirmation, execute, group_summary
)
from scripts import audit_hype_two_stage_1617 as original

SYMBOL="HYPE_USDT"
TZ=ZoneInfo("America/Sao_Paulo")
PERIODS={
    "P1":("2026-10-19T00:00:00-03:00","2026-10-26T00:00:00-03:00"),
    "P2":("2026-10-26T00:00:00-03:00","2026-11-02T00:00:00-03:00"),
    "P3":("2026-11-02T00:00:00-03:00","2026-11-09T00:00:00-03:00"),
    "P4":("2026-11-09T00:00:00-03:00","2026-11-16T00:00:00-03:00"),
    "REF":("2026-11-16T00:00:00-03:00","2026-11-18T00:00:00-03:00"),
}
REGRESSION={"alerts":73, "positive":18, "eligible":32, "selected":17,
            "TP":1,"SL":6,"TIME":10,"net_R_sum":-3.202,"roi_pct":-3.204}


def local(ms):
    return datetime.fromtimestamp(ms/1000,TZ).strftime("%Y-%m-%d %H:%M")


def at_ms(iso_s):
    return int(datetime.fromisoformat(iso_s).timestamp()*1000)


def first_target_minutes(m,i,side):
    """Ex-post-only delay to target in the unchanged label (bad bar wins)."""
    if i+18>=len(m):
        return None
    price=float(m[i][4])
    target=(price*1.0125 if side=="LONG" else price*.9875)
    adverse=(price*.9925 if side=="LONG" else price*1.0075)
    for k in range(i+1,i+19):
        hi,lo=float(m[k][2]),float(m[k][3])
        bad=(lo<=adverse if side=="LONG" else hi>=adverse)
        good=(hi>=target if side=="LONG" else lo<=target)
        if bad:
            return None
        if good:
            return (k-i)*5
    return None


def metrics_by_day(watches,chosen,start,end):
    out=[]
    for d in range(int((end-start)//(24*3600*1000))):
        lo=start+d*24*3600*1000
        hi=lo+24*3600*1000
        ws=[w for w in watches if lo<=w["at_ms"]<hi]
        ts=[t for t in chosen if lo<=at_ms(t["signal_at"])<hi]
        g=group_summary(ws)
        out.append({"day":local(lo)[:10],"watches":len(ws),
                    "watch_hits":g["positive"],"watch_rate_pct":g["rate_pct"],
                    "chosen_trades":len(ts),"trade_outcomes":dict(Counter(
                        t["result"] for t in ts)),"chosen_net_R":round(
                        sum(t["net_r"] for t in ts),3)})
    return out


def check_regression(report):
    p=report["portfolio"]
    values={
        "alerts":report["union"]["n"],
        "positive":report["union"]["positive"],
        "eligible":report["eligible_total"],
        "selected":p["n"],
        "TP":p["outcomes"].get("TP",0),
        "SL":p["outcomes"].get("SL",0),
        "TIME":p["outcomes"].get("TIME",0),
        "net_R_sum":p["net_R_sum"],
        "roi_pct":p["return_pct_at_1pct_risk"]
    }
    if values!=REGRESSION:
        raise AssertionError(f"REF regression changed: got {values}, expected {REGRESSION}")
    return values


def evaluate(m,h,start,end,window):
    # No modifications to watch, confirm, execution rules or thresholds.
    # This global only ensures each confirmation ends before window END.
    original.END=end
    complete_m=[int(c[0])+FIVE_MS for c in m]
    complete_h=[int(c[0])+HOUR_MS for c in h]
    if any(b-a!=FIVE_MS for a,b in zip(complete_m,complete_m[1:])):
        raise ValueError(f"{window} missing 5m bars")
    if any(b-a!=HOUR_MS for a,b in zip(complete_h,complete_h[1:])):
        raise ValueError(f"{window} missing 1h bars")
    if complete_m[-1]<end+2*HOUR_MS:
        raise ValueError(f"{window} too few future candles to score late events")
    assert start%HOUR_MS==0 and end%HOUR_MS==0
    state={"ema9":ema([float(c[4]) for c in m],9),
           "ema21":ema([float(c[4]) for c in m],21)}
    hstate=context(m,h)

    checks=[]
    last_alert={}
    by_fam=defaultdict(list)
    watches=[]
    for i in range(45,len(m)):
        at=complete_m[i]
        if not start<=at<end:
            continue
        for side in ("LONG","SHORT"):
            hit=score_direction(m,i,side)
            if hit is None:
                raise AssertionError("Missing 90-minute score horizon")
            checks.append({"i":i,"side":side,"hit":hit,"at_ms":at})

        for w in watch_at(m,i,state):
            key=(w["family"],w["side"])
            if at-last_alert.get(key,-10**17)<30*60*1000:
                continue
            last_alert[key]=at
            w["hit"]=score_direction(m,i,w["side"])
            delay=first_target_minutes(m,i,w["side"])
            if bool(delay is not None)!=bool(w["hit"]):
                raise AssertionError("Score/delay mismatch")
            w["minutes_to_target"]=delay
            hi=__import__("bisect").bisect_right(hstate["he"],at)-1
            w["h1_bias"]=(
                "LONG" if hstate["hc"][hi]>hstate["h20"][hi] else "SHORT"
            ) if hi>=20 and hstate["h20"][hi] is not None else None
            watches.append(w)
            by_fam[w["family"]].append(w)

    priority=sorted(watches,key=lambda w:(w["at_ms"],
                    ["TURN","BREAK","DRIFT"].index(w["family"])))
    union=[]
    last_side={}
    for w in priority:
        side=w["side"]
        if w["at_ms"]-last_side.get(side,-10**17)<30*60*1000:
            continue
        union.append(w)
        last_side[side]=w["at_ms"]

    phase=Counter()
    qualified=[]
    audit=[]
    seen_confirmations=set()
    for w in union:
        c=confirmation(m,w)
        if c is None:
            phase["watch_only"]+=1
            audit.append({"watch_at":local(w["at_ms"]),"family":w["family"],
                          "side":w["side"],"status":"WATCH_ONLY"})
            continue
        phase["confirmed"]+=1
        key=(c["confirmation_ms"],c["side"])
        if key in seen_confirmations:
            phase["duplicate_confirmation"]+=1
            continue
        seen_confirmations.add(key)
        t=execute(m,c)
        if t is None:
            phase["rr_or_stop_rejected"]+=1
            audit.append({"watch_at":local(w["at_ms"]),"family":w["family"],
                          "side":w["side"],"status":"BLOCKED_RISK"})
            continue
        phase["qualified"]+=1
        qualified.append(t)
        audit.append({"watch_at":local(w["at_ms"]),"family":w["family"],
                      "side":w["side"],"confirm_at":local(c["confirmation_ms"]),
                      "status":"PAPER_ELIGIBLE","entry":t["entry"],"tp":t["target"],
                      "sl":t["stop"],"result":t["result"],"net_r":t["net_r"]})

    portfolio=select_portfolio(qualified)
    by_trade=defaultdict(list)
    for t in qualified:
        by_trade[(t["signal_at"],t["exit_at"],t["result"],t["net_r"])].append(t)
    chosen=[]
    for p in portfolio["chosen"]:
        matches=by_trade[(p["signal_at"],p["exit_at"],p["result"],p["net_r"])]
        if not matches:
            raise AssertionError("Selected portfolio trade not mapped")
        chosen.append(matches[0])
    base=group_summary(checks)
    base_long=group_summary([x for x in checks if x["side"]=="LONG"])
    base_short=group_summary([x for x in checks if x["side"]=="SHORT"])
    uni=group_summary(union)
    cl=Counter(w["side"] for w in union)
    weighted=(cl["LONG"]*base_long["positive"]/base_long["n"]+
              cl["SHORT"]*base_short["positive"]/base_short["n"])*100/max(1,len(union))
    found=[w["minutes_to_target"] for w in union if w["hit"]]
    follow=[w for w in union if w["hit"] and w["minutes_to_target"]<=30]
    total_days=(end-start)/(24*3600*1000)
    res={
        "window":window,"start_brt":local(start),"end_exclusive_brt":local(end),
        "n_closed_m5":sum(start<=v<end for v in complete_m),
        "base_all":base,"base_long":base_long,"base_short":base_short,
        "union":uni,"union_by_side":dict(cl),
        "base_weighted_same_side_mix_pct":round(weighted,3),
        "lift_vs_side_weighted_base_pp":round(uni["rate_pct"]-weighted,3),
        "union_rate_per_day":round(uni["n"]/total_days,3),
        "union_time_to_target_median_minutes":median(found) if found else None,
        "union_target_hit_within_30min":len(follow),
        "watch_family":{family:{
            "total":group_summary(by_fam[family]),
            "LONG":group_summary([w for w in by_fam[family] if w["side"]=="LONG"]),
            "SHORT":group_summary([w for w in by_fam[family] if w["side"]=="SHORT"])
        } for family in ("TURN","BREAK","DRIFT")},
        "phase":dict(phase),
        "eligible_total":len(qualified),
        "portfolio":{**{k:v for k,v in portfolio.items() if k!="chosen"},
                     "outcomes":dict(Counter(t["result"] for t in chosen)),
                     "trades_per_day":round(portfolio["n"]/total_days,3)},
        "days":metrics_by_day(union,chosen,start,end),
        "selected_first_12":[{
            "watch_brt":local(t["watch_ms"]),
            "signal_brt":local(at_ms(t["signal_at"])),
            "side":t["side"],"family":t["watch_family"],
            "entry":t["entry"],"sl":t["stop"],"tp":t["target"],
            "result":t["result"],"net_r":t["net_r"],
            "exit_candle_brt":local(at_ms(t["exit_at"]))
        } for t in chosen[:12]],
        "caveats":[
            "Previously inspected history: NOT independent out-of-sample.",
            "Future M5 used for labels and exits ONLY, not for candidate decisions.",
            "No actual fills, funding, dynamic spread or liquidation.",
            "No changes to frozen watch, confirm, entry thresholds.",
        ]
    }
    if window=="REF":
        res["reference_regression_verified"]=check_regression(res)
    return res


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window",choices=tuple(PERIODS),required=True)
    args=p.parse_args()
    first,last=PERIODS[args.window]
    start,end=at_ms(first),at_ms(last)
    data_end=end+2*HOUR_MS
    # Strict continuity/quality validation is performed by the shared collector.
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(data_end/1000))
    m=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),int(data_end/1000))
    print("WATCH_TRANSFER_SOURCE "+json.dumps({
        "window":args.window,"symbol":SYMBOL,
        "m5_total":len(m),"h1_total":len(h),
        "period_start":first,"period_end_exclusive":last,
        "post_end_eval_only_hours":2,
        "preregistered":"docs/hype-watch-transfer-preregistered-2026-11-20.md",
        "same_original_rules":True,"historical_previously_inspected":True
    },sort_keys=True),flush=True)
    r=evaluate(m,h,start,end,args.window)
    print("WATCH_TRANSFER_REPORT "+json.dumps(r,sort_keys=True),flush=True)


if __name__=="__main__":
    main()
