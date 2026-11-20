"""Three frozen HYPE futures families: causal reversal / impulse / gradual trend.

RESEARCH ONLY, no API trading/Telegram/production.
Pre-registered: docs/hype-three-regimes-preregistered-2026-11-20.md
All chosen historical windows were already inspected in prior experiments.
"""
from __future__ import annotations
import argparse
import bisect
import json
from collections import Counter
from datetime import datetime, timezone
from statistics import median
from zoneinfo import ZoneInfo

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, atr_before, iso, replay_structural,
)
from scripts.audit_brkt_momentum import execute as execute_both_sides
from scripts.audit_smc_liquidity_fvg import WINDOWS, portfolio_metrics
from scripts.audit_hype_eight_moves_20261120 import EVENTS, ms, clock

SYMBOL="HYPE_USDT"
BRT=ZoneInfo("America/Sao_Paulo")
FAMILIES=("REVERSAL","IMPULSE","GRADUAL")
PRIORITY={name:i for i,name in enumerate(FAMILIES)}
WEEK=("2026-11-16T03:00:00+00:00","2026-11-20T22:10:00+00:00")
WINDOWS5={**WINDOWS,"WK":WEEK}


def ema(values,period):
    """EMA initialized using SMA only after entire period is closed."""
    out=[None]*len(values)
    if len(values)<period:
        return out
    e=sum(values[:period])/period
    out[period-1]=e
    factor=2/(period+1)
    for i in range(period,len(values)):
        e=(values[i]-e)*factor+e
        out[i]=e
    return out


def context(five,hourly):
    hends=[int(c[0])+HOUR_MS for c in hourly]
    mends=[int(c[0])+FIVE_MS for c in five]
    hc=[float(c[4]) for c in hourly]
    mc=[float(c[4]) for c in five]
    return {"he":hends,"me":mends,"hc":hc,"mc":mc,
            "h20":ema(hc,20),"h50":ema(hc,50),
            "m20":ema(mc,20),"m50":ema(mc,50)}


def maybe_setup(five,hourly,i,family,state,side):
    """Return signal only using <= i M5 and fully closed H1 candles."""
    if i<60 or i>=len(five):
        return None
    at=int(five[i][0])+FIVE_MS
    h=bisect.bisect_right(state["he"],at)-1
    if h<51:
        return None
    h20,h50=state["h20"][h],state["h50"][h]
    if h20 is None or h50 is None:
        return None
    h20_prev=state["h20"][h-1]
    if h20_prev is None:
        return None
    hc=state["hc"][h]
    atr=atr_before(five,i)
    if atr<=0:
        return None
    bar=five[i]
    op,high,low,close=map(float,bar[1:5])
    body=(close-op if side=="LONG" else op-close)
    past12=five[i-12:i]
    vol=float(bar[6])/max(1e-12,median(float(c[6]) for c in past12))
    signal=None

    if family=="IMPULSE":
        trend=(hc>h20>h50 and h20>h20_prev if side=="LONG"
               else hc<h20<h50 and h20<h20_prev)
        if not trend or body<0.70*atr or vol<1.2:
            return None
        level=(max(float(c[2]) for c in past12) if side=="LONG"
               else min(float(c[3]) for c in past12))
        if (close<=level if side=="LONG" else close>=level):
            return None
        last6=five[i-6:i]
        stop=(min(float(c[3]) for c in last6)-0.1*atr if side=="LONG"
              else max(float(c[2]) for c in last6)+0.1*atr)
        signal={"stop_raw":stop,"reason":"H1 trend + M5 12bar close breakout"}

    elif family=="REVERSAL":
        against=(hc<h20 if side=="LONG" else hc>h20)
        if not against or body<0.25*atr:
            return None
        # First matching most recent sweep (fully closed before confirmation).
        for j in range(i-1,i-4,-1):
            s=five[j]
            if j<39:
                continue
            aj=atr_before(five,j)
            if aj<=0:
                continue
            so,sh,sl,sc=map(float,s[1:5])
            span=sh-sl
            if span<=0:
                continue
            past24=five[j-24:j]
            level=(min(float(c[3]) for c in past24) if side=="LONG"
                   else max(float(c[2]) for c in past24))
            sv=float(s[6])/max(1e-12,median(float(c[6]) for c in five[j-12:j]))
            wick=(min(so,sc)-sl if side=="LONG" else sh-max(so,sc))
            sweep=(sl<level-.1*aj and sc>level if side=="LONG"
                   else sh>level+.1*aj and sc<level)
            reclaim=(close>(sh+sl)/2 if side=="LONG" else close<(sh+sl)/2)
            if sweep and wick>=0.35*span and sv>=1.2 and reclaim:
                stop=sl-.1*aj if side=="LONG" else sh+.1*aj
                signal={"stop_raw":stop,"reason":"M5 sweep/reclaim + confirmation",
                        "sweep_at":iso(int(s[0])+FIVE_MS)}
                break

    elif family=="GRADUAL":
        trend=(h20>h50 and h20>h20_prev if side=="LONG"
               else h20<h50 and h20<h20_prev)
        m20=state["m20"][i]
        m50=state["m50"][i]
        prior_m20=state["m20"][i-1]
        earlier_m20=state["m20"][i-6]
        if not trend or any(v is None for v in (m20,m50,prior_m20,earlier_m20)):
            return None
        mtrend=(m20>m50 and m20>earlier_m20 if side=="LONG"
                else m20<m50 and m20<earlier_m20)
        if not mtrend or body<0.25*atr or vol<0.70:
            return None
        prev=five[i-1]
        prevhigh,prevlow,prevclose=map(float,(prev[2],prev[3],prev[4]))
        touched=(prevlow<=prior_m20 if side=="LONG" else prevhigh>=prior_m20)
        near=abs(prevclose-prior_m20)<=.60*atr
        confirmed=(close>prevhigh and close>m20 if side=="LONG"
                   else close<prevlow and close<m20)
        if not (touched and near and confirmed):
            return None
        last6=five[i-6:i]
        stop=(min(float(c[3]) for c in last6)-.1*atr if side=="LONG"
              else max(float(c[2]) for c in last6)+.1*atr)
        signal={"stop_raw":stop,"reason":"EMA H1 M5 aligned; pullback EMA20 then break"}
    else:
        raise ValueError(f"Unknown family {family}")

    if not signal:
        return None
    return {**signal,"signal_index":i,"signal_at":iso(at),
            "relative_quote_volume":round(vol,6),"side":side,
            "family":family,"atr":round(atr,8)}


def tag_trade(t,family):
    return {**t,"symbol":SYMBOL,"family":family}


def choose_union(trades):
    """One global position, fixed deterministic event priority by family."""
    s=sorted(trades,key=lambda t:(t["signal_at"],PRIORITY[t["family"]],
                                -t["relative_quote_volume"],t["side"]))
    dedup=[]
    used=set()
    for t in s:
        if t["signal_at"] in used:
            continue
        dedup.append(t)
        used.add(t["signal_at"])
    # select_portfolio uses signal, volume, symbol as sorting keys; dedup preserves priority.
    return dedup


def gather(five,hourly,first,last):
    state=context(five,hourly)
    valid={family:[] for family in FAMILIES}
    counts={family:Counter() for family in FAMILIES}
    all_raw=[]
    for i in range(60,len(five)-25):
        t=int(five[i][0])+FIVE_MS
        if t < int(datetime.fromisoformat(first).timestamp()*1000):
            continue
        if t >= int(datetime.fromisoformat(last).timestamp()*1000):
            break
        for family in FAMILIES:
            for side in ("LONG","SHORT"):
                setup=maybe_setup(five,hourly,i,family,state,side)
                if setup is None:
                    continue
                counts[family]["raw_"+side]+=1
                trade=execute_both_sides(five,setup)
                if trade is None:
                    counts[family]["rr_or_stop_rejected"]+=1
                    continue
                row=tag_trade(trade,family)
                valid[family].append(row)
                all_raw.append(row)
                counts[family]["eligible_"+side]+=1
    return valid,counts,choose_union(all_raw)


def case_diagnostics(trades):
    outcomes=[]
    for label,sd,sh,sm,ed,eh,em,side in EVENTS:
        a,b=ms(sd,sh,sm),ms(ed,eh,em)
        before=min(a+60*60*1000,b)
        item={"case":label,"expected_direction":side,
              "start":clock(a),"end":clock(b),"families":{}}
        for family in FAMILIES:
            match=[t for t in trades[family]
                   if t["side"]==side and a<int(datetime.fromisoformat(t["signal_at"]).timestamp()*1000)<=b]
            early=[t for t in match if int(datetime.fromisoformat(t["signal_at"]).timestamp()*1000)<=before]
            def small(x):
                if x is None:
                    return None
                return {"signal_at":datetime.fromisoformat(x["signal_at"]).astimezone(BRT).strftime("%d/%m %H:%M"),
                        "entry":x["entry"],"stop":x["stop"],"tp":x["target"],
                        "outcome":x["result"],"net_r":x["net_r"],
                        "side":x["side"],"exit_at_utc":x["exit_at"]}
            item["families"][family]={"signals_in_window":len(match),
                    "first_in_60m":small(early[0]) if early else None,
                    "first_in_full_window":small(match[0]) if match else None}
        outcomes.append(item)
    return outcomes


def run(window):
    first,last=WINDOWS5[window]
    start=int(datetime.fromisoformat(first).timestamp())
    end=int(datetime.fromisoformat(last).timestamp())
    h=candles(SYMBOL,"Min60",start-160*3600,end-end%3600)
    m=candles(SYMBOL,"Min5",start-120*300,end)
    print("REGIME_START "+json.dumps({
        "window":window,"date_start":first,"date_end":last,
        "symbol":SYMBOL,"h1":len(h),"m5":len(m),
        "spec":"docs/hype-three-regimes-preregistered-2026-11-20.md",
        "already_inspected_history":True},sort_keys=True),flush=True)
    candidates,counts,union=gather(m,h,first,last)
    baselines=replay_structural(m,h,"F_sweep_rejection")
    models={**candidates,
            "UNION_ALL_THREE":union,
            "F_original":[tag_trade(t,"F_original") for t in baselines
                          if first<=t["signal_at"]<last]}
    for family in FAMILIES:
        # Separate paper accounts for each direction are compared, never added as one portfolio.
        for side in ("LONG","SHORT"):
            models[family+"_"+side]=[t for t in candidates[family] if t["side"]==side]
    for model,trades in models.items():
        result=portfolio_metrics(trades,first,last)
        print("REGIME_RESULT "+json.dumps({
            "window":window,"model":model,"metrics":result,
            "outcomes_direction":dict(Counter(t["side"] for t in
                select_portfolio(trades)["chosen"])) if False else
                dict(Counter(t["side"] for t in trades)),
            "source":"MEXC historical candles, not real fills"
        },sort_keys=True),flush=True)
    print("REGIME_COUNTS "+json.dumps({
        "window":window,"counters":{k:dict(v) for k,v in counts.items()},
        "eligible_by_family":{k:len(v) for k,v in candidates.items()},
        "union_candidates":len(union)},sort_keys=True),flush=True)
    if window=="WK":
        for c in case_diagnostics(candidates):
            print("REGIME_CASE "+json.dumps(c,sort_keys=True),flush=True)
    print("REGIME_DONE "+json.dumps({"window":window,"models":len(models)}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--window",required=True,choices=tuple(WINDOWS5))
    run(p.parse_args().window)
