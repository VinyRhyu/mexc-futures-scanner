"""Matched HYPE M1 vs M5 timing: frozen SL/TP at the same M5 WATCH.

PAPER RESEARCH ONLY. Preconditions, seven dates and acceptance test:
docs/hype-m1-fixed-watch-risk-preregistered-2026-11-20.md
No orders, alerts, Telegram, scanner main, or production changes.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, atr_before, iso
from scripts.audit_hype_m1_trend import (
    ONE_MS, SYMBOL, PERIODS, milli, local, m1_candles, contexts,
    watches, first_confirmation_m1,
)
from scripts.audit_hype_two_stage_1617 import confirmation, PARAMS

ARMS=("M5_FIXED","M1_FIXED","M1_FAST_FIXED")
MAX_HOLD=120


def frozen_watch_levels(five,w):
    """A fixed side, stop and target determined at M5 WATCH close only."""
    i=w["i"]
    if i<25:
        raise ValueError("Insufficient M5 warmup")
    a=atr_before(five,i)
    if a<=0:
        raise ValueError("Nonpositive ATR")
    recent=five[i-11:i+1]  # includes WATCH, excludes all future candles
    side=w["side"]
    c=float(five[i][4])
    stop=(min(float(x[3]) for x in recent)-.1*a if side=="LONG"
          else max(float(x[2]) for x in recent)+.1*a)
    r=(c-stop if side=="LONG" else stop-c)
    if r<=0:
        raise AssertionError("WATCH close on incorrect side of stop")
    target=c+1.8*r if side=="LONG" else c-1.8*r
    return {
        "stop":stop,"target":target,"reference":c,
        "reference_risk":r,"watch_side":side,
        "watch_at_ms":w["at_ms"],
        "watch_key":f'{w["at_ms"]}:{w["side"]}:{w["family"]}',
    }


def next_m1_index_at_close(minute, signal_ms, state):
    # First minute candle opening at signal_ms; only this is a plausible
    # next bar fill after the fully closed M1 or M5 confirm candle.
    import bisect
    i=bisect.bisect_left(state["m1e"],signal_ms+ONE_MS)
    if i>=len(minute) or int(minute[i][0])!=signal_ms:
        raise ValueError("No next M1 open exactly at signal close")
    return i


def fixed_execute(minute, state, sig, arm, levels):
    """Identical fixed TP/SL, same minute OHLC exit, window 120 M1."""
    close_at=milli(sig["signal_at"])
    i=next_m1_index_at_close(minute,close_at,state)
    if i+MAX_HOLD>len(minute):
        return None,"INCOMPLETE_EXIT_HORIZON"
    side=sig["side"]
    stop,target=levels["stop"],levels["target"]
    entry=float(minute[i][1])
    risk=(entry-stop if side=="LONG" else stop-entry)
    reward=(target-entry if side=="LONG" else entry-target)
    if risk<=0 or reward<=0:
        return None,"INVALID_ENTRY_RELATIVE_TO_FIXED_LEVELS"
    cost=2*entry*(PARAMS.taker_fee_each+PARAMS.slippage_each)
    rr=(reward-cost)/(risk+cost)
    if rr<1.2:
        return None,"RR_LT_1_2"
    result="TIME"
    exit_idx=i+MAX_HOLD-1
    exit_price=float(minute[exit_idx][4])
    for k in range(i,i+MAX_HOLD):
        hi,lo=float(minute[k][2]),float(minute[k][3])
        bad=(lo<=stop if side=="LONG" else hi>=stop)
        good=(hi>=target if side=="LONG" else lo<=target)
        if bad or good:
            result=("AMBIGUOUS_AS_SL" if bad and good else
                    "SL" if bad else "TP")
            exit_price=stop if bad else target
            exit_idx=k
            break
    gross=(exit_price-entry if side=="LONG" else entry-exit_price)
    net=(gross-cost)/(risk+cost)
    if result=="AMBIGUOUS_AS_SL":net=-1.0
    return {
        "arm":arm,"side":side,"watch_key":levels["watch_key"],
        "watch_at_ms":levels["watch_at_ms"],
        "signal_ms":close_at,"entry_ms":int(minute[i][0]),
        "exit_start_ms":int(minute[exit_idx][0]),
        "exit_end_ms":int(minute[exit_idx][0])+ONE_MS,
        "signal_at":iso(close_at),"entry_at":iso(int(minute[i][0])),
        "exit_at":iso(int(minute[exit_idx][0])),
        "entry":round(entry,6),"sl":round(stop,8),"tp":round(target,8),
        "result":result,"net_r":round(net,5),
        "rr_net_at_fill":round(rr,4),
        "fee_cost_pct_notional":round(100*2*(PARAMS.taker_fee_each+PARAMS.slippage_each),4),
        "watch_family":sig.get("watch_family",None),
        "confirmation_delay_min":(close_at-levels["watch_at_ms"])/ONE_MS,
    },None


def portfolio(trades):
    """One position at a time, held until EXACT end of minute exit bar."""
    s=sorted(trades,key=lambda t:(t["signal_ms"],-t["rr_net_at_fill"],
                    t["watch_key"]))
    chosen=[]
    held_until=-1
    bal=1.0
    peak=1.0
    maxdd=0.
    sumr=0.
    for t in s:
        if t["entry_ms"]<held_until:
            continue
        chosen.append(t)
        held_until=t["exit_end_ms"]
        bal*=1+.01*t["net_r"]
        peak=max(peak,bal)
        maxdd=max(maxdd,1-bal/peak)
        sumr+=t["net_r"]
    return chosen,{
        "n":len(chosen),"tp":sum(t["result"]=="TP" for t in chosen),
        "sl":sum(t["result"] in ("SL","AMBIGUOUS_AS_SL") for t in chosen),
        "time":sum(t["result"]=="TIME" for t in chosen),
        "roi_pct":round(100*(bal-1),3),
        "max_dd_pct":round(100*maxdd,3),
        "net_r":round(sumr,3),
    }


def evaluate(minute,m5,h,start,end):
    ws=watches(m5,start,end)  # frozen WATCH universe
    state=contexts(minute,m5,h)
    candidates={arm:[] for arm in ARMS}
    stage={arm:Counter() for arm in ARMS}
    perwatch={}
    latencies={arm:[] for arm in ARMS}
    for w in ws:
        levels=frozen_watch_levels(m5,w)
        perwatch[levels["watch_key"]]={"levels":levels,"arms":{}}
        for arm in ARMS:
            if arm=="M5_FIXED":
                sig=confirmation(m5,w,cutoff_ms=end)
            else:
                signalarm=("M1_M5_TREND" if arm=="M1_FIXED" else "M1_FAST")
                sig=first_confirmation_m1(minute,m5,h,w,signalarm,state,end)
            if sig is None:
                stage[arm]["no_confirmation"]+=1
                continue
            stage[arm]["confirmed"]+=1
            delay=(milli(sig["signal_at"])-w["at_ms"])/ONE_MS
            latencies[arm].append(delay)
            t,reason=fixed_execute(minute,state,sig,arm,levels)
            if t is None:
                stage[arm]["rejected_"+reason]+=1
                continue
            stage[arm]["eligible"]+=1
            perwatch[levels["watch_key"]]["arms"][arm]=t
            candidates[arm].append(t)

    for arm in ARMS:
        # Multiple WATCHs may confirm at the same moment. Refuse duplicates
        # even if they have different target/stops. Fixed family priority first.
        seen=set()
        uniq=[]
        for t in candidates[arm]:
            key=(t["signal_ms"],t["side"])
            if key in seen:
                stage[arm]["duplicate_same_signal_side"]+=1
                continue
            seen.add(key)
            uniq.append(t)
        candidates[arm]=uniq

    metrics={}
    selected={}
    n_days=(end-start)/(24*3600*1000)
    for arm in ARMS:
        selected[arm],p=portfolio(candidates[arm])
        metrics[arm]={
            **p,"eligible_unique":len(candidates[arm]),
            "watch_count":len(ws),
            "stage":dict(stage[arm]),
            "median_watch_to_signal_minutes":(
                median(latencies[arm]) if latencies[arm] else None),
            "trades_per_day":round(p["n"]/n_days,3),
            "first_8_selected":[{
                "watch_brt":local(t["watch_at_ms"]),"signal_brt":local(t["signal_ms"]),
                "side":t["side"],"family":t["watch_family"],
                "entry":t["entry"],"stop":t["sl"],"tp":t["tp"],
                "outcome":t["result"],"net_r":t["net_r"],
                "exit_candle_brt":local(t["exit_start_ms"])
            }for t in selected[arm][:8]],
        }
    # Different strategies choose different portfolios. Paired diagnostic
    # uses ONLY shared eligible WATCHs; NOT a tradable portfolio selection.
    pairs=[(v["arms"]["M5_FIXED"],v["arms"]["M1_FIXED"])
           for v in perwatch.values()
           if "M5_FIXED" in v["arms"] and "M1_FIXED" in v["arms"]]
    delta=[(m5t["signal_ms"]-m1t["signal_ms"])/ONE_MS for m5t,m1t in pairs]
    paired={
        "n":len(pairs),
        "m1_earlier_n":sum(d>0 for d in delta),
        "same_time_n":sum(d==0 for d in delta),
        "m1_later_n":sum(d<0 for d in delta),
        "median_m1_minutes_earlier":median(delta) if delta else None,
        "m5_paired_mean_R":round(sum(p[0]["net_r"] for p in pairs)/len(pairs),4) if pairs else None,
        "m1_paired_mean_R":round(sum(p[1]["net_r"] for p in pairs)/len(pairs),4) if pairs else None,
        "M1_better_paired_n":sum(b["net_r"]>a["net_r"] for a,b in pairs),
        "M5_better_paired_n":sum(a["net_r"]>b["net_r"] for a,b in pairs),
        "same_levels_verified":all(a["sl"]==b["sl"] and a["tp"]==b["tp"]
                                   for a,b in pairs),
    }
    if not paired["same_levels_verified"]:
        raise AssertionError("Matched cases must have identical target and stop")
    return {
        "watch_universe":len(ws),"models":metrics,"paired_diagnostic":paired,
        "warnings":[
            "All seven prior periods examined elsewhere; NOT clean out-of-sample.",
            "Matched paired-only outcomes are hindsight conditioned on BOTH signal eligibility.",
            "Entries on M1 next opening after M5/M1 close; no actual fills.",
            "Cost model excludes funding, real spread, order book and liquidation.",
            "Stop and target fixed at common original M5 WATCH; RR gate varies with entry price.",
        ],
    }


def run(window):
    first,last=PERIODS[window]
    start,end=milli(first),milli(last)
    future=end+2*HOUR_MS
    m5=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),int(future/1000))
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(future/1000))
    m1=m1_candles(SYMBOL,start-90*ONE_MS,future)
    if len(m1)!=3090 or len(m5)!=720 or len(h)!=210:
        raise ValueError(f"Incomplete data for {window}: M1={len(m1)} M5={len(m5)} H1={len(h)}")
    # Collector strict completeness guards; no silently filled missing dates.
    payload=evaluate(m1,m5,h,start,end)
    print("FIXED_WATCH_M1_REPORT "+json.dumps({
        "window":window,"start":first,"end_exclusive":last,
        "m1":len(m1),"m5":len(m5),"h1":len(h),
        "preregistered":"docs/hype-m1-fixed-watch-risk-preregistered-2026-11-20.md",
        "historical_reused":True,**payload,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--window",required=True,choices=tuple(PERIODS))
    run(p.parse_args().window)
