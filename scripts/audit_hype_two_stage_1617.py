"""HYPE 16/17 Nov: two-stage causal WATCH -> CONFIRM -> PAPER ENTRY study.

Pre-registered: docs/hype-16-17-two-stage-preregistered.md
Only the two user-selected dates generate watches and entries. Next day's bars
are fetched solely to close/score the late entries and watches. NEVER trade live.
"""
from __future__ import annotations

import bisect
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, atr_before, iso, replay_structural
from scripts.audit_confluence_pilot import Parameters
from scripts.audit_hype_eight_moves_20261120 import EVENTS, ms, clock
from scripts.audit_hype_three_regimes import ema, context

SYMBOL="HYPE_USDT"
FAMILIES=("TURN","BREAK","DRIFT")
PRIORITY={family:i for i,family in enumerate(FAMILIES)}
START=ms(16,0,0)
END=ms(18,0,0)                 # exclusive new-watch/entry cutoff
DATA_END=ms(18,2,0)           # future bars ONLY for verification
PARAMS=Parameters()


def watch_at(m,i,indicator):
    """At close of M5[i], evaluate all 3 modes without future bars."""
    if i<45 or i>=len(m):
        return []
    bar=m[i]
    op,hi,lo,close=map(float,bar[1:5])
    atr=atr_before(m,i)
    if atr<=0:
        return []
    prev=m[i-12:i]
    vol=float(bar[6])/max(1e-12,median(float(c[6]) for c in prev))
    m9=indicator["ema9"][i]
    m21=indicator["ema21"][i]
    last9=indicator["ema9"][i-1]
    last21=indicator["ema21"][i-1]
    old9=indicator["ema9"][i-4]
    if any(x is None for x in (m9,m21,last9,last21,old9)):
        return []
    c6=float(m[i-6][4])
    high6=max(float(c[2]) for c in m[i-6:i])
    low6=min(float(c[3]) for c in m[i-6:i])
    res=[]
    for side in ("LONG","SHORT"):
        directional=(close-op if side=="LONG" else op-close)
        delta=(close/c6-1) if side=="LONG" else (1-close/c6)
        cross=(last9<=last21 and m9>m21 if side=="LONG"
               else last9>=last21 and m9<m21)
        breakout=(close>high6 if side=="LONG" else close<low6)
        aligned=(m9>m21 and m9>old9 and close>m9 if side=="LONG"
                 else m9<m21 and m9<old9 and close<m9)
        flags={
            "TURN": cross and directional>=.25*atr and vol>=.8,
            "BREAK": breakout and directional>=.35*atr and vol>=.8,
            "DRIFT": aligned and delta>=.0035 and vol>=.55,
        }
        for fam in FAMILIES:
            if flags[fam]:
                res.append({"i":i,"family":fam,"side":side,
                            "at_ms":int(m[i][0])+FIVE_MS,
                            "close":close,"volume_x":round(vol,5),
                            "atr":atr,"change_30m_pct":round(100*delta,4)})
    return res


def score_direction(m,i,side):
    """Ex post ONLY, first 1.25% favorable move before 0.75% adverse in 90m."""
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
            return False
        if good:
            return True
    return False


def confirmation(m,watch,cutoff_ms=None):
    """Separate phase, starts AFTER the WATCH candle, waits up to six M5."""
    wi=watch["i"]
    side=watch["side"]
    if cutoff_ms is None:
        cutoff_ms=END
    for i in range(wi+1,min(len(m)-1,wi+7)):
        at=int(m[i][0])+FIVE_MS
        if at>=cutoff_ms:   # no confirmations outside this research window
            break
        atr=atr_before(m,i)
        if atr<=0:
            continue
        c=m[i]
        op,close=float(c[1]),float(c[4])
        past6=m[i-6:i]
        past12=m[i-12:i]
        rv=float(c[6])/max(1e-12,median(float(x[6]) for x in past12))
        body=close-op if side=="LONG" else op-close
        broke=(close>max(float(x[2]) for x in past6) if side=="LONG"
               else close<min(float(x[3]) for x in past6))
        if body<.40*atr or rv<1.0 or not broke:
            continue
        stop=(min(float(x[3]) for x in past12)-.1*atr if side=="LONG"
              else max(float(x[2]) for x in past12)+.1*atr)
        return {"signal_index":i,"signal_at":iso(at),"side":side,
                "stop_raw":stop,"relative_quote_volume":round(rv,6),
                "watch_ms":watch["at_ms"],"family":watch["family"],
                "watch_i":wi,"confirmation_ms":at}
    return None


def execute(m,setup):
    """Next-bar open and conservative same-bar fill priority for paper only."""
    i=setup["signal_index"]
    if i+24>=len(m):
        return None
    entry=float(m[i+1][1])
    side=setup["side"]
    stop=setup["stop_raw"]
    risk=(entry-stop if side=="LONG" else stop-entry)
    if risk<=0:
        return None
    cost=2*entry*(PARAMS.taker_fee_each+PARAMS.slippage_each)
    rr=(1.8*risk-cost)/(risk+cost)
    if rr<1.2:
        return None
    target=(entry+1.8*risk if side=="LONG" else entry-1.8*risk)
    result="TIME"
    ix=i+24
    exit_price=float(m[ix][4])
    for k in range(i+1,i+25):
        hi,lo=float(m[k][2]),float(m[k][3])
        bad=lo<=stop if side=="LONG" else hi>=stop
        good=hi>=target if side=="LONG" else lo<=target
        if bad or good:
            result="AMBIGUOUS_AS_SL" if bad and good else "SL" if bad else "TP"
            ix=k
            exit_price=stop if bad else target
            break
    profit=((exit_price-entry) if side=="LONG" else (entry-exit_price))
    net_r=(profit-cost)/(risk+cost)
    if result=="AMBIGUOUS_AS_SL":
        net_r=-1.0
    return {"signal_at":setup["signal_at"],"entry_at":iso(int(m[i+1][0])),
            "exit_at":iso(int(m[ix][0])),"symbol":SYMBOL,
            "side":side,"result":result,
            "entry":round(entry,6),"stop":round(stop,6),
            "target":round(target,6),"net_r":round(net_r,5),
            "net_rr_ex_ante":round(rr,4),"relative_quote_volume":setup["relative_quote_volume"],
            "watch_ms":setup["watch_ms"],"watch_family":setup["family"]}


def group_summary(rows):
    return {"n":len(rows),"positive":sum(x["hit"] for x in rows),
            "false_or_no_followthrough":sum(not x["hit"] for x in rows),
            "rate_pct":round(100*sum(x["hit"] for x in rows)/len(rows),2) if rows else None}


def report():
    h=candles(SYMBOL,"Min60",int((START-160*HOUR_MS)/1000),int(DATA_END/1000))
    m=candles(SYMBOL,"Min5",int((START-120*FIVE_MS)/1000),int(DATA_END/1000))
    if any(int(b[0])-int(a[0])!=FIVE_MS for a,b in zip(m,m[1:])):
        raise ValueError("Gap in M5 candles")
    if any(int(b[0])-int(a[0])!=HOUR_MS for a,b in zip(h,h[1:])):
        raise ValueError("Gap in H1 candles")
    ix=dict((int(x[0])+FIVE_MS,i) for i,x in enumerate(m))
    state={"ema9":ema([float(c[4]) for c in m],9),
           "ema21":ema([float(c[4]) for c in m],21)}
    hstate=context(m,h)
    all_checks=[]
    by_fam=defaultdict(list)
    last_alert={}
    watches=[]
    for i in range(45,len(m)):
        at=int(m[i][0])+FIVE_MS
        if at<START or at>=END:
            continue
        for side in ("LONG","SHORT"):
            hit=score_direction(m,i,side)
            if hit is not None:
                all_checks.append({"i":i,"side":side,"hit":hit,"at_ms":at})
        for w in watch_at(m,i,state):
            key=(w["family"],w["side"])
            if at-last_alert.get(key,-10**17)<30*60*1000:
                continue
            last_alert[key]=at
            w["hit"]=score_direction(m,i,w["side"])
            w["h1_bias"]=None
            hi=bisect.bisect_right(hstate["he"],at)-1
            if hi>=20:
                w["h1_bias"]=("LONG" if hstate["hc"][hi]>hstate["h20"][hi]
                              else "SHORT")
            watches.append(w)
            by_fam[w["family"]].append(w)

    # Merge concurrent family watches and suppress repeated alerts of same
    # direction within 30 minutes in one chronological stream.
    priority=sorted(watches,key=lambda x:(x["at_ms"],["TURN","BREAK","DRIFT"].index(x["family"])))
    union=[]
    last_side={}
    for w in priority:
        side=w["side"]
        if w["at_ms"]-last_side.get(side,-10**17)<30*60*1000:
            continue
        union.append(w)
        last_side[side]=w["at_ms"]

    # Confirmation -> eligibility separated from warning detection.
    phase=Counter()
    audit=[]
    qualified=[]
    seen_confirmations=set()
    for w in union:
        c=confirmation(m,w)
        if c is None:
            phase["watch_only"]+=1
            audit.append({"watch":clock(w["at_ms"]),"family":w["family"],
                          "side":w["side"],"score_hit":w["hit"],
                          "status":"WATCH_ONLY"})
            continue
        phase["confirmed"]+=1
        key=(c["confirmation_ms"],c["side"])
        if key in seen_confirmations:
            phase["duplicate_confirmation"]+=1
            continue
        seen_confirmations.add(key)
        trade=execute(m,c)
        if trade is None:
            phase["rr_or_stop_rejected"]+=1
            audit.append({"watch":clock(w["at_ms"]),"family":w["family"],
                          "side":w["side"],"score_hit":w["hit"],
                          "confirm":clock(c["confirmation_ms"]),
                          "status":"BLOCKED_ENTRY_RISK"})
            continue
        qualified.append(trade)
        phase["qualified"]+=1
        audit.append({"watch":clock(w["at_ms"]),"family":w["family"],
                      "side":w["side"],"score_hit":w["hit"],
                      "confirm":clock(c["confirmation_ms"]),
                      "status":"PAPER_ELIGIBLE","entry":trade["entry"],"sl":trade["stop"],
                      "tp":trade["target"],"result":trade["result"],
                      "net_r":trade["net_r"],"exit":clock(
                          int(datetime.fromisoformat(trade["exit_at"]).timestamp()*1000))})

    p=select_portfolio(qualified)
    chosen=[]
    by_sig=defaultdict(list)
    for t in qualified:
        by_sig[(t["signal_at"],t["exit_at"],t["result"])].append(t)
    for t in p["chosen"]:
        z=by_sig[(t["signal_at"],t["exit_at"],t["result"])][0]
        chosen.append({"alert":clock(z["watch_ms"]),"confirm":clock(
            int(datetime.fromisoformat(z["signal_at"]).timestamp()*1000)),
            "entry_at":clock(int(datetime.fromisoformat(z["entry_at"]).timestamp()*1000)),
            "side":z["side"],"family":z["watch_family"],
            "entry":z["entry"],"SL":z["stop"],"TP":z["target"],
            "result":z["result"],"exit_candle":clock(
                int(datetime.fromisoformat(z["exit_at"]).timestamp()*1000)),
            "R_net":z["net_r"]})
    labels=(("16-short",16,8,0,16,10,0,"SHORT"),
            ("16-reversal",16,10,0,16,12,15,"LONG"),
            ("16-slow-long",16,12,15,16,19,0,"LONG"),
            ("17-short-early",17,2,30,17,6,15,"SHORT"),
            ("17-short-midday",17,11,15,17,12,30,"SHORT"))
    cases=[]
    for label,sd,sh,sm,ed,eh,em,side in labels:
        a,b=ms(sd,sh,sm),ms(ed,eh,em)
        hits=[w for w in union if w["side"]==side and a<w["at_ms"]<=b]
        early=[w for w in hits if w["at_ms"]<=min(b,a+60*60*1000)]
        eligible=[t for t in qualified
                  if t["side"]==side and
                  a<int(datetime.fromisoformat(t["signal_at"]).timestamp()*1000)<=b]
        cases.append({"name":label,"side":side,"start":clock(a),"end":clock(b),
                      "early_warning":clock(early[0]["at_ms"]) if early else None,
                      "first_warning":clock(hits[0]["at_ms"]) if hits else None,
                      "warnings_in_window":len(hits),
                      "first_eligible_confirm":clock(int(
                          datetime.fromisoformat(eligible[0]["signal_at"]).timestamp()*1000))
                          if eligible else None,
                      "eligible_confirmed":len(eligible)})
    print("HYPE_1617_SOURCE "+json.dumps({
        "symbol":SYMBOL,"analyzed_days":["2026-11-16","2026-11-17"],
        "cutoff_brt":clock(END),"late_exit_data_end":clock(DATA_END),
        "M5":len(m),"H1":len(h),"warmup_complete":True,
        "spec":"docs/hype-16-17-two-stage-preregistered.md"},sort_keys=True),flush=True)
    for case in cases:
        print("HYPE_1617_CASE "+json.dumps(case,sort_keys=True),flush=True)
    for x in chosen:
        print("HYPE_1617_TRADE "+json.dumps(x,sort_keys=True),flush=True)
    per_day={}
    for day in (16,17):
        start_d=ms(day,0,0)
        end_d=ms(day+1,0,0)
        per_day[str(day)]={
            "watches":len([w for w in union if start_d<=w["at_ms"]<end_d]),
            "eligible":len([t for t in qualified
                          if start_d<=int(datetime.fromisoformat(t["signal_at"]).timestamp()*1000)<end_d]),
            "selected":len([t for t in chosen if t["confirm"].startswith(f"{day:02d}/")]),
            "score_precision":group_summary([w for w in union
                                            if start_d<=w["at_ms"]<end_d]),
        }
    result={
        "two_days_only":True,
        "base_rate_both_directions":group_summary(all_checks),
        "base_rate_long":group_summary([x for x in all_checks if x["side"]=="LONG"]),
        "base_rate_short":group_summary([x for x in all_checks if x["side"]=="SHORT"]),
        "per_family":{family:{
            "all":group_summary(by_fam[family]),
            "LONG":group_summary([x for x in by_fam[family] if x["side"]=="LONG"]),
            "SHORT":group_summary([x for x in by_fam[family] if x["side"]=="SHORT"]),
        } for family in FAMILIES},
        "union_score":group_summary(union),
        "union_sides":dict(Counter(x["side"] for x in union)),
        "union_alerts":len(union),
        "phase_counts":dict(phase),
        "eligible_total":len(qualified),
        "selected_global_one_at_a_time":{
            **{k:v for k,v in p.items() if k!="chosen"},
            "outcomes":dict(Counter(t["result"] for t in chosen)),
            "mean_net_r":round(sum(t["R_net"] for t in chosen)/len(chosen),5)
                           if chosen else None,
        },
        "per_day":per_day,
        "first_25_alerts":audit[:25],
        "case_count":len(cases),
        "warnings":[
            "Two days and annotated cases selected retrospectively: NOT out-of-sample.",
            "90m direction label is future information used for evaluation ONLY.",
            "Watch alert is NOT an entry; confirmation + RR gate are separate.",
            "Cost assumes taker 0.06%, slippage 0.02% per side; no funding/fills.",
            "Ambiguous TP and SL candles treated conservatively as stop.",
            "Selected global portfolio is paper; no actual trades.",
        ]
    }
    print("HYPE_1617_SUMMARY "+json.dumps(result,sort_keys=True),flush=True)


if __name__=="__main__":
    report()
