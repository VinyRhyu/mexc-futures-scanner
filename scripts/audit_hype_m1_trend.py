"""Causal M1 entry experiment for HYPE after frozen M5 WATCH.

Paper historical replay only, no orders/production/Telegram.
Frozen protocol: docs/hype-m1-trend-preregistered-2026-11-20.md
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
import time
from collections import Counter,defaultdict
from datetime import datetime
from statistics import median
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

from scripts.audit_confluence_extended import candles,select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS,HOUR_MS,iso
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_two_stage_1617 import watch_at,confirmation,execute
from scripts import audit_hype_two_stage_1617 as frozen

ONE_MS=60_000
BRT=ZoneInfo("America/Sao_Paulo")
SYMBOL="HYPE_USDT"
FAMILIES=("TURN","BREAK","DRIFT")
ARM=("M5_ORIGINAL","M1_FAST","M1_M5_TREND","M1_H1_TREND")
PERIODS={
 "OCT05":("2026-10-05T00:00:00-03:00","2026-10-07T00:00:00-03:00"),
 "OCT12":("2026-10-12T00:00:00-03:00","2026-10-14T00:00:00-03:00"),
 "OCT19":("2026-10-19T00:00:00-03:00","2026-10-21T00:00:00-03:00"),
 "OCT26":("2026-10-26T00:00:00-03:00","2026-10-28T00:00:00-03:00"),
 "REF":("2026-11-16T00:00:00-03:00","2026-11-18T00:00:00-03:00"),
 "CMP":("2026-11-09T00:00:00-03:00","2026-11-11T00:00:00-03:00"),
 "CMP2":("2026-11-02T00:00:00-03:00","2026-11-04T00:00:00-03:00"),
}
REF_REGRESSION={"watch_count":73,"M5_original_eligible":32,
                "M5_original_selected":17,"M5_original_roi":-3.204}


def milli(dt):
    return int(datetime.fromisoformat(dt).timestamp()*1000)


def local(v):
    return datetime.fromtimestamp(v/1000,BRT).strftime("%d/%m %H:%M")


def m1_candles(symbol,lo_ms,hi_ms):
    """Same strict public MEXC OHLC collector semantics, paginated <=1400 M1."""
    start=lo_ms//ONE_MS*60
    end=hi_ms//ONE_MS*60
    expected=range(start,end,60)
    got={}
    for page in range(start,end,1400*60):
        through=min(end-60,page+1399*60)
        url=("https://api.mexc.com/api/v1/contract/kline/"+symbol+"?"+
             urlencode({"interval":"Min1","start":page,"end":through}))
        for attempt in range(3):
            try:
                with urlopen(Request(url,headers={
                    "User-Agent":"ResearchPaperOnly/1.0"
                }),timeout=22) as resp:
                    data=json.load(resp)
                break
            except Exception:
                if attempt==2:
                    raise
                time.sleep(1+attempt)
        if not (isinstance(data,dict) and data.get("success") and data.get("code")==0):
            raise ValueError("MEXC Min1 response rejected: "+str(data)[:180])
        o=data.get("data") or {}
        keys=("time","open","high","low","close","vol","amount")
        if any(k not in o for k in keys) or len({len(o[k]) for k in keys})!=1:
            raise ValueError("Invalid MEXC Min1 OHLC columns")
        for fields in zip(*(o[k] for k in keys)):
            t=int(fields[0])
            row=[t*1000]+[float(v) for v in fields[1:]]
            if t in got and got[t]!=row:
                raise ValueError("Conflicting Min1 duplicate candle")
            got[t]=row
        time.sleep(.08)
    if set(got)!=set(expected):
        missing=sorted(set(expected)-set(got))
        raise ValueError(f"Unavailable Min1 historical data {len(got)}/{len(expected)}; first missing {missing[:5]}")
    rows=[got[t] for t in expected]
    for c in rows:
        if c[2]<max(c[1],c[4]) or c[3]>min(c[1],c[4]) or not all(
            math.isfinite(x) for x in c[1:]):
            raise ValueError("Malformed Min1 candle")
    return rows


def atr_m1_pre(m,i):
    if i<15:
        return None
    return sum(max(float(m[k][2])-float(m[k][3]),
        abs(float(m[k][2])-float(m[k-1][4])),
        abs(float(m[k][3])-float(m[k-1][4])))
        for k in range(i-14,i))/14


def contexts(m1,m5,h):
    return {
        "m1e":[int(c[0])+ONE_MS for c in m1],
        "m5e":[int(c[0])+FIVE_MS for c in m5],
        "he":[int(c[0])+HOUR_MS for c in h],
        "m1e9":ema([float(c[4]) for c in m1],9),
        "m5e9":ema([float(c[4]) for c in m5],9),
        "m5e21":ema([float(c[4]) for c in m5],21),
        "h20":ema([float(c[4]) for c in h],20),
    }


def candidate_minute(m1,m5,h,i,side,arm,state):
    """Only completed one-minute and already-closed M5/H1 candles."""
    if i<16:
        return None
    t=state["m1e"][i]
    row=m1[i]
    op,hi,lo,cl=map(float,row[1:5])
    atr=atr_m1_pre(m1,i)
    if atr is None or atr<=0:
        return None
    last5=m1[i-5:i]
    last10=m1[i-10:i]
    v=float(row[6])/max(1e-12,median(float(c[6]) for c in last10))
    body=cl-op if side=="LONG" else op-cl
    if body<.35*atr or v<1.0:
        return None
    border=max(float(c[2]) for c in last5) if side=="LONG" else min(float(c[3]) for c in last5)
    if (cl<=border if side=="LONG" else cl>=border):
        return None
    ma=state["m1e9"][i]
    ma3=state["m1e9"][i-3]
    if ma is None or ma3 is None:
        return None
    aligned=(cl>ma and ma>ma3 if side=="LONG"
             else cl<ma and ma<ma3)
    if not aligned:
        return None

    if arm in ("M1_M5_TREND","M1_H1_TREND"):
        ix=bisect.bisect_right(state["m5e"],t)-1
        if ix<23:
            return None
        e9=state["m5e9"][ix]
        e21=state["m5e21"][ix]
        eprev=state["m5e9"][ix-2]
        trend=(e9>e21 and e9>eprev if side=="LONG"
               else e9<e21 and e9<eprev)
        if not trend:
            return None

    if arm=="M1_H1_TREND":
        ix=bisect.bisect_right(state["he"],t)-1
        if ix<20 or state["h20"][ix] is None:
            return None
        hclose=float(h[ix][4])
        hma=state["h20"][ix]
        if not (hclose>hma if side=="LONG" else hclose<hma):
            return None
    return {
        "signal_index":i,"signal_at":iso(t),"side":side,"arm":arm,
        "relative_quote_volume":round(v,6),"atr":atr,
        "stop_raw":(
            min(float(c[3]) for c in m1[i-15:i])-.15*atr
            if side=="LONG"
            else max(float(c[2]) for c in m1[i-15:i])+.15*atr
        ),
    }


def first_confirmation_m1(m1,m5,h,w,arm,state,end):
    lo=w["at_ms"]
    until=min(end,lo+30*ONE_MS)
    # A signal at close t is permitted after watch and before cutoff.
    p=bisect.bisect_right(state["m1e"],lo)
    while p<len(m1) and state["m1e"][p]<=until:
        t=state["m1e"][p]
        if t>=end:
            break
        s=candidate_minute(m1,m5,h,p,w["side"],arm,state)
        if s is not None:
            return {**s,"watch_ms":lo,"watch_family":w["family"]}
        p+=1
    return None


def execute_m1(m,setup):
    i=setup["signal_index"]
    if i+120>=len(m):
        return None
    entry=float(m[i+1][1])
    stop=setup["stop_raw"]
    side=setup["side"]
    risk=entry-stop if side=="LONG" else stop-entry
    if risk<=0:
        return None
    cost=2*entry*(frozen.PARAMS.taker_fee_each+frozen.PARAMS.slippage_each)
    rr=(1.8*risk-cost)/(risk+cost)
    if rr<1.2:
        return None
    tp=entry+1.8*risk if side=="LONG" else entry-1.8*risk
    result="TIME"
    exit_idx=i+120
    exit_price=float(m[exit_idx][4])
    for k in range(i+1,i+121):
        hi,lo=float(m[k][2]),float(m[k][3])
        bad=lo<=stop if side=="LONG" else hi>=stop
        good=hi>=tp if side=="LONG" else lo<=tp
        if bad or good:
            result=("AMBIGUOUS_AS_SL" if bad and good else
                    "SL" if bad else "TP")
            exit_price=stop if bad else tp
            exit_idx=k
            break
    net_r=(((exit_price-entry) if side=="LONG" else (entry-exit_price))-cost)/(risk+cost)
    if result=="AMBIGUOUS_AS_SL":
        net_r=-1.0
    return {
        "symbol":SYMBOL,"signal_at":setup["signal_at"],
        "entry_at":iso(int(m[i+1][0])),"exit_at":iso(int(m[exit_idx][0])),
        "result":result,"side":side,"entry":round(entry,6),
        "stop":round(stop,6),"target":round(tp,6),
        "net_r":round(net_r,5),"net_rr_ex_ante":round(rr,5),
        "relative_quote_volume":setup["relative_quote_volume"],
        "watch_ms":setup["watch_ms"],"watch_family":setup["watch_family"],
        "arm":setup["arm"],
    }


def watches(m5,start,end):
    ind={
        "ema9":ema([float(c[4]) for c in m5],9),
        "ema21":ema([float(c[4]) for c in m5],21)
    }
    by_family_last={}
    out=[]
    for i in range(45,len(m5)):
        at=int(m5[i][0])+FIVE_MS
        if not start<=at<end:
            continue
        for w in watch_at(m5,i,ind):
            k=(w["family"],w["side"])
            if at-by_family_last.get(k,-10**17)<30*ONE_MS:
                continue
            by_family_last[k]=at
            out.append(w)
    out.sort(key=lambda x:(x["at_ms"],FAMILIES.index(x["family"])))
    union=[]
    by_side_last={}
    for w in out:
        if w["at_ms"]-by_side_last.get(w["side"],-10**17)<30*ONE_MS:
            continue
        union.append(w)
        by_side_last[w["side"]]=w["at_ms"]
    return union


def simulate(m1,m5,h,start,end):
    ws=watches(m5,start,end)
    state=contexts(m1,m5,h)
    portfolios={}
    signals={}
    for arm in ARM:
        candidate=[]
        stage=Counter()
        latency=[]
        for w in ws:
            if arm=="M5_ORIGINAL":
                s=confirmation(m5,w,cutoff_ms=end)
                if s is not None:
                    t=execute(m5,s)
                    if t is not None:
                        t={**t,"arm":arm}
            else:
                s=first_confirmation_m1(m1,m5,h,w,arm,state,end)
                t=execute_m1(m1,s) if s is not None else None
            if s is None:
                stage["watch_only"]+=1
                continue
            stage["confirmed"]+=1
            latency.append((int(datetime.fromisoformat(s["signal_at"]).timestamp()*1000)-w["at_ms"])/ONE_MS)
            if t is None:
                stage["risk_rejected"]+=1
                continue
            stage["eligible"]+=1
            candidate.append(t)
        # Frozen original deduplicates confirmation (signal ms, side) to avoid
        # counting repeated watches that confirm on the same candle.
        unique=set()
        eligible=[]
        for t in candidate:
            k=(t["signal_at"],t["side"])
            if k in unique:
                stage["duplicate_confirmation"]+=1
                continue
            unique.add(k)
            eligible.append(t)
        p=select_portfolio(eligible)
        m={(t["signal_at"],t["exit_at"],t["net_r"]):t for t in eligible}
        chosen=[m[(t["signal_at"],t["exit_at"],t["net_r"])] for t in p["chosen"]]
        portfolios[arm]={
            "stage":dict(stage),"eligible_unique":len(eligible),
            "selected":p["n"],"tp":sum(t["result"]=="TP" for t in chosen),
            "sl":sum(t["result"] in ("SL","AMBIGUOUS_AS_SL") for t in chosen),
            "time":sum(t["result"]=="TIME" for t in chosen),
            "net_r":p["net_R_sum"],"roi_pct":p["return_pct_at_1pct_risk"],
            "drawdown_pct":p["max_drawdown_pct_at_1pct_risk"],
            "median_watch_to_signal_minutes":median(latency) if latency else None,
            "trades_per_day":round(p["n"]/((end-start)/(24*60*ONE_MS)),3),
        }
        signals[arm]=[{
            "watch":local(t["watch_ms"]),"confirmation":local(int(datetime.fromisoformat(t["signal_at"]).timestamp()*1000)),
            "side":t["side"],"family":t["watch_family"],"entry":t["entry"],
            "tp":t["target"],"sl":t["stop"],"result":t["result"],
            "net_r":t["net_r"],"exit_candle":local(int(datetime.fromisoformat(t["exit_at"]).timestamp()*1000)),
        } for t in chosen]
    return ws,portfolios,signals


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window",required=True,choices=tuple(PERIODS))
    args=p.parse_args()
    first,last=PERIODS[args.window]
    start,end=milli(first),milli(last)
    future=end+2*HOUR_MS
    m5=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),int(future/1000))
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(future/1000))
    minute=m1_candles(SYMBOL,start-90*ONE_MS,future)
    if len(minute)<3000:
        raise AssertionError("M1 incomplete two-day window")
    print("M1_PILOT_SOURCE "+json.dumps({
        "symbol":SYMBOL,"window":args.window,"start":first,
        "end":last,"min1":len(minute),"min5":len(m5),"h1":len(h),
        "first_closed_m1":local(int(minute[0][0])+ONE_MS),
        "last_closed_m1":local(int(minute[-1][0])+ONE_MS),
        "all_complete":True,"historical_reused":True,
        "cost_nominal_roundtrip":2*(frozen.PARAMS.taker_fee_each+frozen.PARAMS.slippage_each)
    },sort_keys=True),flush=True)
    ws,portfolio,trades=simulate(minute,m5,h,start,end)
    if args.window=="REF":
        found={"watch_count":len(ws),
               "M5_original_eligible":portfolio["M5_ORIGINAL"]["eligible_unique"],
               "M5_original_selected":portfolio["M5_ORIGINAL"]["selected"],
               "M5_original_roi":portfolio["M5_ORIGINAL"]["roi_pct"]}
        if found!=REF_REGRESSION:
            raise AssertionError(f"M5 REF comparison not reproducible: {found}; expected {REF_REGRESSION}")
    print("M1_PILOT_REPORT "+json.dumps({
        "window":args.window,"watches":len(ws),
        "watch_sides":dict(Counter(w["side"] for w in ws)),
        "portfolios":portfolio,
        "trades":trades if args.window=="REF" else {k:v[:8] for k,v in trades.items()},
        "warnings":[
            "No actual orders; M1 OHLC bars not tick-level precision.",
            "Fast confirmation and its M1 stop are a package; not same stop as M5 baseline.",
            "Reused historical data: not independent or prospective.",
            "One-at-a-time portfolio per strategy, not combined.",
            "No funding, real slippage or real order-book spread."
        ]
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()
