"""HYPE user-marked eight movements: causal checkpoints and broad-week signal counter.

Exploratory hindsight-anchored diagnosis; zero orders or production changes.
Rules pre-registered at docs/hype-eight-moves-preregistered-2026-11-20.md.
"""
from __future__ import annotations
import bisect
import json
from collections import Counter
from datetime import datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_pilot import Parameters, _ema_last
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, atr_before, candidate_f, iso

BRT=ZoneInfo("America/Sao_Paulo")
SYMBOL="HYPE_USDT"
START=(2026,11,16,0,0)
END=(2026,11,20,19,10)
EVENTS=(
    ("16-short", 16,8,0,16,10,0,"SHORT"),
    ("16-reversal",16,10,0,16,12,15,"LONG"),
    ("16-slow-long",16,12,15,16,19,0,"LONG"),
    ("17-short-early",17,2,30,17,6,15,"SHORT"),
    ("17-short-midday",17,11,15,17,12,30,"SHORT"),
    ("18-short",18,10,15,18,13,0,"SHORT"),
    ("19-long",19,0,0,19,8,30,"LONG"),
    ("20-short",20,8,0,20,12,30,"SHORT"),
)
PARAM=Parameters()


def ms(day,hour,minute):
    return int(datetime(2026,11,day,hour,minute,tzinfo=BRT).timestamp()*1000)


def clock(ts):
    return datetime.fromtimestamp(ts/1000,BRT).strftime("%d/%m %H:%M")


def checkpoint(five,hourly,ends_m,ends_h,at_ms):
    i=bisect.bisect_right(ends_m,at_ms)-1
    h=bisect.bisect_right(ends_h,at_ms)-1
    if i<26 or h<50:
        return None
    bar=five[i]
    cl=float(bar[4])
    op=float(bar[1])
    a=atr_before(five,i)
    past12=five[i-12:i]
    prior_hi=max(float(c[2]) for c in past12)
    prior_lo=min(float(c[3]) for c in past12)
    base=median(float(c[6]) for c in past12)
    hcls=[float(c[4]) for c in hourly[:h+1]]
    ema20=_ema_last(hcls,20)
    ema50=_ema_last(hcls,50)
    prev20=_ema_last(hcls[:-1],20)
    trend="above" if hcls[-1]>ema20 else "below" if hcls[-1]<ema20 else "equal"
    return {
        "time":clock(at_ms),"m5_close":round(cl,5),
        "h1_last_completed":clock(ends_h[h]),
        "h1_close":round(hcls[-1],5),"h1_ema20":round(ema20,5),
        "h1_ema50":round(ema50,5),
        "h1_relative_to_ema20":trend,
        "h1_ema20_slope":("rising" if ema20>prev20 else "falling"),
        "h1_bias_short":bool(hcls[-1]<ema20),
        "h1_bias_long":bool(hcls[-1]>ema20),
        "m5_return_last60_pct":round(100*(cl/float(five[i-12][4])-1),3),
        "atr14_m5_pct":round(100*a/cl,3),
        "m5_last_bar_volume_x":round(float(bar[6])/max(base,1e-12),3),
        "m5_close_breaks_prev60m_high":cl>prior_hi,
        "m5_close_breaks_prev60m_low":cl<prior_lo,
        "m5_body_direction": "LONG" if cl>op else "SHORT" if cl<op else "DOJI",
        "m5_body_atr":round(abs(cl-op)/a,3) if a else 0,
    }


def raw_momentum(five,i):
    """Fixed causal descriptive marker; NO H1 filter, no hindsight extents."""
    if i<26:
        return None
    bar=five[i]
    atr=atr_before(five,i)
    if atr<=0:
        return None
    op,close=float(bar[1]),float(bar[4])
    prev=five[i-12:i]
    rel_vol=float(bar[6])/max(1e-12,median(float(c[6]) for c in prev))
    if rel_vol<1.2 or abs(close-op)<0.5*atr:
        return None
    high=max(float(c[2]) for c in prev)
    low=min(float(c[3]) for c in prev)
    side=("LONG" if close>high and close>op else
          "SHORT" if close<low and close<op else None)
    if side is None:
        return None
    return {
        "i":i,"side":side,"signal_ms":int(bar[0])+FIVE_MS,
        "atr":atr,"volume_x":rel_vol,"prior_high":high,"prior_low":low,
        "signal_close":close,
    }


def hypothetical(five,setup, cutoff_ms=None):
    i=setup["i"]
    if i+24>=len(five):
        return {"status":"NOT_ENOUGH_CANDLES"}
    side=setup["side"]
    entry=float(five[i+1][1])
    stop=(setup["prior_high"]+0.1*setup["atr"] if side=="SHORT"
          else setup["prior_low"]-0.1*setup["atr"])
    risk=stop-entry if side=="SHORT" else entry-stop
    if risk<=0:
        return {"status":"INVALID_RISK"}
    target=entry-1.8*risk if side=="SHORT" else entry+1.8*risk
    cost=2*entry*(PARAM.taker_fee_each+PARAM.slippage_each)
    rr=(1.8*risk-cost)/(risk+cost)
    outcome="TIME"
    exit_idx=i+24
    exit_price=float(five[exit_idx][4])
    for k in range(i+1,i+25):
        hi,lo=float(five[k][2]),float(five[k][3])
        bad=(hi>=stop if side=="SHORT" else lo<=stop)
        good=(lo<=target if side=="SHORT" else hi>=target)
        if bad or good:
            outcome="AMBIGUOUS" if bad and good else "SL" if bad else "TP"
            exit_price=stop if bad else target
            exit_idx=k
            break
    net_r=((entry-exit_price-cost)/(risk+cost) if side=="SHORT" else
           (exit_price-entry-cost)/(risk+cost))
    return {
        "status":"QUALIFIES_NET_RR" if rr>=1.2 else "BLOCKED_NET_RR",
        "entry_brt":clock(int(five[i+1][0])),"entry":round(entry,5),
        "stop":round(stop,5),"tp":round(target,5),"risk_pct":round(100*risk/entry,3),
        "rr_net_ex_ante":round(rr,3),
        "exit_brt_candle_start":clock(int(five[exit_idx][0])),
        "exit_brt_candle_end":clock(int(five[exit_idx][0])+FIVE_MS),
        "outcome_if_taken":outcome,
        "net_R_if_taken":round(net_r,4) if outcome!="AMBIGUOUS" else -1.0,
    }


def run():
    start=ms(16,0,0)
    end=ms(20,19,10)
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int((end-end%HOUR_MS)/1000))
    m=candles(SYMBOL,"Min5",int((start-55*FIVE_MS)/1000),int(end/1000))
    ends_m=[int(x[0])+FIVE_MS for x in m]
    ends_h=[int(x[0])+HOUR_MS for x in h]
    if ends_m[-1]!=end:
        raise ValueError(f"Unexpected M5 end {clock(ends_m[-1])}")
    if any(b-a!=FIVE_MS for a,b in zip(ends_m,ends_m[1:])):
        raise ValueError("M5 gaps")
    if any(b-a!=HOUR_MS for a,b in zip(ends_h,ends_h[1:])):
        raise ValueError("H1 gaps")
    print("HYPE_EVENTS_SOURCE "+json.dumps({
        "symbol":SYMBOL,"source":"MEXC futures contract M5 & H1",
        "week_first_brt":clock(start),"week_last_closed_brt":clock(end),
        "M5_total":len(m),"H1_total":len(h),
        "candidate_rules":"fixed pre-registered 12-M5 close breakout + 0.5 ATR body + 1.2x quote volume",
        "fees_per_side":PARAM.taker_fee_each,"slippage_per_side":PARAM.slippage_each,
        "NOT_out_of_sample":True},sort_keys=True),flush=True)
    candidate=[]
    for i in range(26,len(m)):
        event_ms=ends_m[i]
        if not start<=event_ms<end:
            continue
        x=raw_momentum(m,i)
        if x is not None:
            candidate.append(x)
    per_event_early=set()
    observed=[]
    for label,sd,sh,sm,ed,eh,em,side in EVENTS:
        a,b=ms(sd,sh,sm),ms(ed,eh,em)
        if a>=b:
            raise ValueError(f"Invalid case {label}")
        at_start=bisect.bisect_left([int(c[0]) for c in m],a)
        at_end=bisect.bisect_left([int(c[0]) for c in m],b)
        assert m[at_start][0]==a and int(m[at_end][0])==b
        segment=m[at_start:at_end]
        op=float(segment[0][1])
        close=float(segment[-1][4])
        lo=min(float(c[3]) for c in segment)
        hi=max(float(c[2]) for c in segment)
        hi_bar=next(c for c in segment if float(c[2])==hi)
        lo_bar=next(c for c in segment if float(c[3])==lo)
        move=100*(close/op-1)
        maxfav=100*((hi/op-1) if side=="LONG" else (1-lo/op))
        maxadv=100*((1-lo/op) if side=="LONG" else (hi/op-1))
        checkpoints={}
        for name,offset in (("minus15",-15),("start",0),("plus15",15),
                            ("plus30",30),("plus60",60)):
            t=a+offset*60_000
            if t>b:continue
            checkpoints[name]=checkpoint(m,h,ends_m,ends_h,t)
        early=[x for x in candidate
               if x["side"]==side and a<x["signal_ms"]<=min(a+60*60_000,b)]
        event_candidate=early[0] if early else None
        if event_candidate:
            per_event_early.add(event_candidate["i"])
        fixed_window_candidates=[x for x in candidate
                                 if a<x["signal_ms"]<=b and x["side"]==side]
        opposite=[x for x in candidate if a<x["signal_ms"]<=b and x["side"]!=side]
        h1_begin=checkpoints["start"]
        result={
            "name":label,"side_as_marked":side,
            "window_start_brt":clock(a),"window_end_brt":clock(b),
            "duration_minutes":int((b-a)/60000),
            "open_at_start":round(op,5),"close_at_end":round(close,5),
            "signed_price_change_pct":round(move,3),
            "side_aligned_end_change_pct":round(move if side=="LONG" else -move,3),
            "high":round(hi,5),"high_5min_candle_brt":clock(int(hi_bar[0])),
            "low":round(lo,5),"low_5min_candle_brt":clock(int(lo_bar[0])),
            "max_favorable_intrawindow_pct":round(maxfav,3),
            "max_adverse_intrawindow_pct":round(maxadv,3),
            "early_same_side_raw_markers":len(early),
            "same_side_markers_whole_window":len(fixed_window_candidates),
            "first_same_side_marker_in_full_window_brt":(
                clock(fixed_window_candidates[0]["signal_ms"])
                if fixed_window_candidates else None),
            "first_same_side_marker_delay_minutes":(
                int((fixed_window_candidates[0]["signal_ms"]-a)/60000)
                if fixed_window_candidates else None),
            "opposite_side_markers_whole_window":len(opposite),
            "checkpoints":checkpoints,
            "first_early_marker":({
                "confirmed_brt":clock(event_candidate["signal_ms"]),
                "side":event_candidate["side"],
                "volume_x":round(event_candidate["volume_x"],3),
                "h1_favorable":checkpoint(m,h,ends_m,ends_h,event_candidate["signal_ms"])["h1_bias_"+side.lower()],
                "diagnostic_hypothetical":hypothetical(m,event_candidate)
            } if event_candidate else None),
            "F_frozen_is_short_only":True,
        }
        observed.append(result)
        print("HYPE_EVENTS_CASE "+json.dumps(result,sort_keys=True),flush=True)
    # Hindsight marker coverage is NOT win rate; count off-event alerts.
    same_side_in_marked=0
    within_any=0
    for x in candidate:
        for label,sd,sh,sm,ed,eh,em,side in EVENTS:
            if ms(sd,sh,sm)<x["signal_ms"]<=ms(ed,eh,em):
                within_any+=1
                if x["side"]==side:
                    same_side_in_marked+=1
                break
    # Frozen F candidate count weekly (including blocked RR)
    f_candidates=[]
    for i in range(25,len(m)):
        if start<=ends_m[i]<end:
            c=candidate_f(m,h,i)
            if c is not None:
                entry=float(m[i+1][1]) if i+1<len(m) else None
                risk=c["stop_raw"]-entry if entry is not None else None
                if risk is None or risk<=0:
                    rr=None
                else:
                    cost=2*entry*(PARAM.taker_fee_each+PARAM.slippage_each)
                    rr=(1.8*risk-cost)/(risk+cost)
                f_candidates.append({"at_brt":clock(ends_m[i]),
                                     "rr_net":round(rr,3) if rr is not None else None,
                                     "approved":bool(rr is not None and rr>=1.2)})
    # Evaluate hypothetical isolated raw momentum events across the whole
    # week (to avoid only describing hand-picked successful intervals).
    qualified=[]
    reject=Counter()
    for x in candidate:
        result=hypothetical(m,x)
        if result["status"]!="QUALIFIES_NET_RR":
            reject[result["status"]]+=1
            continue
        qualified.append({
            "symbol":SYMBOL,"signal_at":iso(x["signal_ms"]),
            "exit_at":iso(int(datetime.strptime(result["exit_brt_candle_start"],
                     "%d/%m %H:%M").replace(year=2026,tzinfo=BRT).timestamp()*1000)),
            "relative_quote_volume":x["volume_x"],
            "result":result["outcome_if_taken"],
            "net_r":result["net_R_if_taken"],
        })
    selected=select_portfolio(qualified)
    chosen=selected["chosen"]
    print("HYPE_EVENTS_SUMMARY "+json.dumps({
        "cases":len(observed),
        "markers_total_week":len(candidate),
        "markers_by_side":dict(Counter(x["side"] for x in candidate)),
        "markers_inside_any_user_selected_window":within_any,
        "markers_same_direction_inside_selected_windows":same_side_in_marked,
        "markers_outside_user_windows":len(candidate)-within_any,
        "early_cases_with_marker":sum(x["first_early_marker"] is not None for x in observed),
        "early_cases_without_marker":sum(x["first_early_marker"] is None for x in observed),
        "full_week_hypothetical":{
            "qualified_raw_signal_count":len(qualified),
            "rejected":dict(reject),
            "one_position_portfolio":{
                **{k:v for k,v in selected.items() if k!="chosen"},
                "outcomes":dict(Counter(x["result"] for x in chosen)),
            },
        },
        "f_original_candidates":f_candidates,
        "warnings":[
            "Movements selected with hindsight, so early markers are NOT prospective success evidence.",
            "Direction LONG/SHORT specified by user, not inferred by algorithm from future.",
            "The unanchored full-week marker sample contains false/losing signals too.",
            "Hypothetical entries and stop/TP are diagnostic, NOT validated strategy.",
            "Only completed H1/M5 candles enter features and signal decisions.",
            "Fee taker 0.06% and slippage 0.02% per side modeled; excludes funding.",
        ],
    },sort_keys=True),flush=True)

if __name__=="__main__":
    run()
