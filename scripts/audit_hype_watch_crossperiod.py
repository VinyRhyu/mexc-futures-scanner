"""Paper robustness test of UNCHANGED HYPE WATCH and ENTRY rules on other dates.

Four chronological disjoint periods before 16 Nov; historical not untouched.
Frozen protocol: docs/hype-watch-crossperiod-preregistered-2026-11-20.md.
No orders, main, Telegram, or scanner production changes.
"""
from __future__ import annotations
import argparse
import bisect
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS,HOUR_MS,iso
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_two_stage_1617 import (
    FAMILIES, PARAMS, watch_at, score_direction, confirmation,
    execute, group_summary,
)
from scripts.audit_smc_liquidity_fvg import WINDOWS
from scripts.audit_hype_eight_moves_20261120 import ms,clock

SYMBOL="HYPE_USDT"
PERIODS={
    "T": WINDOWS["T"],
    "U": WINDOWS["U"],
    "V": WINDOWS["V"],
    "W0": (WINDOWS["W"][0],"2026-11-16T03:00:00+00:00"),
}
NINETY_MIN=18
DELTA_MS=5*60_000


def date_ms(dt):
    return int(datetime.fromisoformat(dt).timestamp()*1000)


def gap_checked(m,h):
    if any(int(b[0])-int(a[0])!=FIVE_MS for a,b in zip(m,m[1:])):
        raise ValueError("M5 history incomplete")
    if any(int(b[0])-int(a[0])!=HOUR_MS for a,b in zip(h,h[1:])):
        raise ValueError("H1 history incomplete")


def hit_delay(m,i,side):
    """Ex-post score used ONLY in evaluation. None when bad/no follow-through."""
    if i+18>=len(m):
        return None
    price=float(m[i][4])
    good=price*(1.0125 if side=="LONG" else 0.9875)
    bad=price*(.9925 if side=="LONG" else 1.0075)
    for k in range(i+1,i+19):
        hi,lo=float(m[k][2]),float(m[k][3])
        touched_bad=(lo<=bad if side=="LONG" else hi>=bad)
        touched_good=(hi>=good if side=="LONG" else lo<=good)
        if touched_bad:
            return None
        if touched_good:
            return (k-i)*5
    return None


def cohort(w):
    return {
        "total":len(w),
        "success":sum(t["hit"] for t in w),
        "fail_or_time":sum(not t["hit"] for t in w),
        "precision_pct":round(100*sum(t["hit"] for t in w)/len(w),3) if w else None,
        "success_delay_median_minutes":median([t["delay"] for t in w if t.get("delay") is not None]) if any(x.get("delay") is not None for x in w) else None,
    }


def run(wname):
    first,last=PERIODS[wname]
    start,end=date_ms(first),date_ms(last)
    days=(end-start)/86_400_000
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(end/1000))
    m=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),int((end+2*HOUR_MS)/1000))
    gap_checked(m,h)
    if int(m[-1][0])+FIVE_MS != end+2*HOUR_MS:
        raise ValueError("Expected two-hour scoring buffer")
    indicators={
        "ema9":ema([float(c[4]) for c in m],9),
        "ema21":ema([float(c[4]) for c in m],21),
    }
    hends=[int(b[0])+HOUR_MS for b in h]
    hcloses=[float(b[4]) for b in h]
    h20=ema(hcloses,20)
    baseline=[]
    individual=defaultdict(list)
    last_family={}
    for i in range(45,len(m)):
        at=int(m[i][0])+FIVE_MS
        if at<start:continue
        if at>=end:break
        # Both directions on EVERY 5-minute close: comparison denominator.
        for side in ("LONG","SHORT"):
            hit=score_direction(m,i,side)
            if hit is None:
                raise ValueError("Insufficient future evaluation horizon")
            baseline.append({"side":side,"hit":hit})
        for w in watch_at(m,i,indicators):
            key=w["family"],w["side"]
            if at-last_family.get(key,-10**18)<30*60_000:continue
            last_family[key]=at
            hit=score_direction(m,i,w["side"])
            delay=hit_delay(m,i,w["side"])
            if hit is not (delay is not None):
                raise AssertionError("Diagnostic score and delay disagree")
            h_index=bisect.bisect_right(hends,at)-1
            if h_index<20 or h20[h_index] is None:
                raise RuntimeError("Incomplete H1 EMA20 warmup")
            bias="LONG" if hcloses[h_index]>h20[h_index] else "SHORT"
            w.update(hit=hit,delay=delay,h1_bias=bias)
            individual[w["family"]].append(w)

    # Deterministic same union 30min cooldown by direction used 16/17.
    all_watches=sorted((w for g in individual.values() for w in g),
                       key=lambda t:(t["at_ms"],FAMILIES.index(t["family"])))
    union=[]
    last_side={}
    for w in all_watches:
        side=w["side"]
        if w["at_ms"]-last_side.get(side,-10**18)<30*60_000:continue
        union.append(w)
        last_side[side]=w["at_ms"]

    # Frozen staged confirmation and RR gate. Evaluation labels NEVER enter.
    phase=Counter()
    qualified=[]
    confirmation_keys=set()
    watch_to_trade={}
    for w in union:
        c=confirmation(m,w,cutoff_ms=end)
        if c is None:
            phase["watch_only"]+=1
            continue
        phase["confirmed"]+=1
        key=(c["confirmation_ms"],c["side"])
        if key in confirmation_keys:
            phase["duplicate_confirmation"]+=1
            continue
        confirmation_keys.add(key)
        trade=execute(m,c)
        if trade is None:
            phase["rr_or_stop_rejected"]+=1
            continue
        qualified.append(trade)
        phase["qualified"]+=1
        watch_to_trade[(trade["signal_at"],trade["watch_ms"])]=w

    p=select_portfolio(qualified)
    chosen=p["chosen"]
    outcomes=Counter(t["result"] for t in chosen)
    sides=Counter()
    by_entry_map=defaultdict(list)
    for t in qualified:
        by_entry_map[(t["signal_at"],t["exit_at"])].append(t)
    selected_examples=[]
    for x in chosen:
        t=by_entry_map[(x["signal_at"],x["exit_at"])][0]
        sides[t["side"]]+=1
        if len(selected_examples)<5 or t["net_r"]>1.0:
            selected_examples.append({
                "side":t["side"],"watch":clock(t["watch_ms"]),
                "confirmed":clock(date_ms(t["signal_at"])),
                "entry":t["entry"],"sl":t["stop"],"tp":t["target"],
                "result":t["result"],"net_r":t["net_r"],
            })
    baseline_overall=cohort(baseline)
    un=cohort(union)
    aligned=[w for w in union if w["h1_bias"]==w["side"]]
    opposed=[w for w in union if w["h1_bias"]!=w["side"]]
    per_family={k:cohort(individual.get(k,[])) for k in FAMILIES}
    per_side={s:cohort([w for w in union if w["side"]==s]) for s in ("LONG","SHORT")}
    # The original five cases are excluded from *all* these windows.
    out={
        "period":wname,"start_utc":first,"end_utc":last,
        "days":round(days,3),"source":"MEXC HYPE_USDT futures M5/H1 closed candles",
        "m5_total_with_warmup_future":len(m),"h1_with_warmup":len(h),
        "base_rate":baseline_overall,
        "baseline_LONG":cohort([x for x in baseline if x["side"]=="LONG"]),
        "baseline_SHORT":cohort([x for x in baseline if x["side"]=="SHORT"]),
        "union_watch":un,
        "union_sides":per_side,
        "families":per_family,
        "h1_alignment_diagnostic":{
            "aligned":cohort(aligned),"opposed":cohort(opposed),
            "fraction_alerts_kept_pct":round(100*len(aligned)/len(union),3) if union else None,
            "fraction_successful_union_alerts_kept_pct":round(
                100*sum(w["hit"] for w in aligned)/sum(w["hit"] for w in union),3)
                if any(w["hit"] for w in union) else None,
        },
        "alert_precision_lift_pp":round(
            un["precision_pct"]-baseline_overall["precision_pct"],3),
        "watches_per_day":round(len(union)/days,3),
        "phase_counts":dict(phase),
        "eligible_total":len(qualified),
        "portfolio":{
            "selected":len(chosen),"TP":outcomes["TP"],"SL":outcomes["SL"],
            "TIME":outcomes["TIME"],
            "ambiguous":outcomes["AMBIGUOUS_AS_SL"],
            "roi_pct":p["return_pct_at_1pct_risk"],
            "drawdown_pct":p["max_drawdown_pct_at_1pct_risk"],
            "net_r":p["net_R_sum"],"trades_per_day":round(len(chosen)/days,3),
            "sides":dict(sides),
        },
        "sample_selected_trades":selected_examples[:9],
        "limitations":[
            "Historical dates already examined with different strategies, NOT untouched holdout.",
            "No parameter change from 16/17. Entry conditions unrelated to future scoring labels.",
            "H1 alignment group is diagnostic only, not an approved filter.",
            "Position score assumes next-bar fills and fixed taker/slippage; no funding.",
            "Base-rate M5/side points are correlated and not independent trials.",
        ]
    }
    print("HYPE_WATCH_CROSS_RESULT "+json.dumps(out,sort_keys=True),flush=True)


if __name__=="__main__":
    pa=argparse.ArgumentParser()
    pa.add_argument("--window",required=True,choices=tuple(PERIODS))
    args=pa.parse_args()
    run(args.window)
