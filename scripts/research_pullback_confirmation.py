"""V5f: fixed causal pullback and resumption diagnostic."""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
import numpy as np
from scripts.research_event_predictability import event,align_probabilities,CLASSES,PARTS,LOOKBACK,SEED,HORIZON
from scripts.research_event_baselines import pipeline,binary_metrics
from scripts.research_universe_transfer import sources
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2
from mexc_scanner.models import D
from scripts.research_pre_breakout_dataset import contiguous
from scripts.research_pre_breakout_model import FEATURES,net_r
from scripts.research_expected_net_return import COSTS
from scripts.research_amplitude_geometry import funding_charge
from scripts.research_universe_transfer import evaluate,stress_cost
from scripts.research_event_baselines import positive
def bounded_barrier(bars,t,a,side,end):
    # t is confirmation time; expiry remains original forecast time +240m.
    entry_t=t+60
    finish=t-DELAY+HORIZON
    seq=contiguous(bars,entry_t,finish) if finish<=end else None
    if seq is None:
        return {"outcome":"CENSORED"}
    sign=D(1) if side=="LONG" else D(-1)
    entry=seq[0].open
    stop,target=entry-sign*a,entry+sign*D(3)*a
    if min(stop,target)<=0:
        return {"outcome":"INVALID_GEOMETRY"}
    outcome,price,exit_t="TIMEOUT",seq[-1].close,seq[-1].end
    for c in seq:
        op=sign*(c.open-entry)/a
        if op<=-1:
            outcome,price,exit_t="SL",c.open,c.ts
            break
        if op>=D(3):
            outcome,price,exit_t="TP",target,c.ts
            break
        adv=sign*((c.low if sign>0 else c.high)-entry)/a
        fav=sign*((c.high if sign>0 else c.low)-entry)/a
        if adv<=-1:
            outcome,price,exit_t="SL",stop,c.end
            break
        if fav>=D(3):
            outcome,price,exit_t="TP",target,c.end
            break
    return {"outcome":outcome,"entry_ts":entry_t,"exit_ts":exit_t,"entry":str(entry),
            "exit":str(price),"stop":str(stop),"target":str(target),
            "gross_r":str(sign*(price-entry)/a)}



DELAY=900
MOVE=D("0.5")
GATE=.60

def confirmation(bars,t,a,anchor):
    c=t+DELAY
    upper,lower=anchor+3*a,anchor-3*a
    # Any target crossing before confirmation is known by then. No outcome-based filter.
    for ts in range(t,c,60):
        k=bars[ts]
        if k.high>=upper or k.low<=lower:
            return {"status":"already_expanded"}
    delta=(bars[c-60].close-anchor)/a
    if abs(delta)<MOVE:
        return {"status":"unconfirmed"}
    side="UP" if delta>0 else "DOWN"
    return {"status":"confirmed","side":side,"confirmation_t":c,"move_atr":float(delta)}

def remaining(bars,t,a,anchor,conf):
    # Outcome only, after one full minute delay from confirmation.
    c=conf["confirmation_t"]
    entry_t=c+60
    finish=t+HORIZON
    seq=[bars[ts] for ts in range(entry_t,finish,60)]
    entry=seq[0].open
    sign=D(1) if conf["side"]=="UP" else D(-1)
    fav=max(D(0),max(sign*((k.high if sign>0 else k.low)-entry)/a for k in seq))
    adv=max(D(0),max(-sign*((k.low if sign>0 else k.high)-entry)/a for k in seq))
    endret=sign*(seq[-1].close-entry)/a
    goal=anchor+sign*3*a
    room=sign*(goal-entry)/a
    # Include crossings during latency as missed original event, not hindsight exclusion.
    pre=bars[c]
    crossed=(pre.high>=anchor+3*a or pre.low<=anchor-3*a)
    return {"mfe":float(fav),"mae":float(adv),"end_ret":float(endret),
            "room":float(room),"latency_crossing":bool(crossed),
            "entry_ts":entry_t}

def stats(rows):
    confirmed=[r for r in rows if r["status"]=="confirmed"]
    directional=[r for r in confirmed if r["event"] in ("UP","DOWN")]
    correct=[r for r in confirmed if r["side"]==r["event"]]
    return {"n":len(rows),"event_rate":sum(r["event"]!="NONE" for r in rows)/len(rows) if rows else None,
            "statuses":dict(Counter(r["status"] for r in rows)),
            "confirmed":len(confirmed),"directional_events":len(directional),
            "direction_correct_all":len(correct)/len(confirmed) if confirmed else None,
            "direction_correct_conditional":len(correct)/len(directional) if directional else None,
            "latency_crossings":sum(r["latency_crossing"] for r in confirmed),
            "mfe_ge_1atr":sum(r["mfe"]>=1 for r in confirmed)/len(confirmed) if confirmed else None,
            "mfe_ge_2atr":sum(r["mfe"]>=2 for r in confirmed)/len(confirmed) if confirmed else None,
            "mfe_ge_3atr":sum(r["mfe"]>=3 for r in confirmed)/len(confirmed) if confirmed else None,
            **{k+"_median":float(np.median([r[k] for r in confirmed])) if confirmed else None for k in ("mfe","mae","end_ret","room")}}

def pullback_barrier(bars,t,a,side,finish,end):
    # t is the actual resumption decision; finish is the original forecast expiry.
    entry_t=t+60
    seq=contiguous(bars,entry_t,finish) if finish<=end else None
    if seq is None:
        return {"outcome":"CENSORED"}
    sign=D(1) if side=="LONG" else D(-1)
    entry=seq[0].open
    stop,target=entry-sign*a,entry+sign*D(3)*a
    if min(stop,target)<=0:
        return {"outcome":"INVALID_GEOMETRY"}
    outcome,price,exit_t="TIMEOUT",seq[-1].close,seq[-1].end
    for c in seq:
        op=sign*(c.open-entry)/a
        if op<=-1:
            outcome,price,exit_t="SL",c.open,c.ts
            break
        if op>=D(3):
            outcome,price,exit_t="TP",target,c.ts
            break
        adv=sign*((c.low if sign>0 else c.high)-entry)/a
        fav=sign*((c.high if sign>0 else c.low)-entry)/a
        if adv<=-1:
            outcome,price,exit_t="SL",stop,c.end
            break
        if fav>=D(3):
            outcome,price,exit_t="TP",target,c.end
            break
    return {"outcome":outcome,"entry_ts":entry_t,"exit_ts":exit_t,"entry":str(entry),
            "exit":str(price),"stop":str(stop),"target":str(target),
            "gross_r":str(sign*(price-entry)/a)}

from collections import defaultdict
from scripts.research_amplitude_frequency import select_daily

WAIT=3600
PULLBACK=D("0.5")
RESUME=D("0.25")
EXPECTED={"validation":(707,18,6.659280535307438,-1.1257038866753266),
          "test":(1152,18,-2.930079061836024,-9.755948144420449)}

def pullback_decision(bars,confirmation_t,anchor,atr,side):
    # Closed candles only. Track favorable peak in signed close space.
    # A pullback and a resumption must occur in distinct closed candles.
    sign=D(1) if side=="LONG" else D(-1)
    peak=D(0)
    trough=None
    ref=bars[confirmation_t-60].close
    upper,lower=anchor+3*atr,anchor-3*atr
    for ts in range(confirmation_t,confirmation_t+WAIT,60):
        c=bars[ts]
        # Original expansion/invalidation already occurred before entry signal.
        if c.high>=upper or c.low<=lower:
            return {"status":"original_excursion_before_trigger"}
        z=sign*(c.close-ref)/atr
        if trough is None:
            peak=max(peak,z)
            if peak-z>=PULLBACK:
                trough=z
        else:
            trough=min(trough,z)
            if z-trough>=RESUME:
                return {"status":"triggered","decision_t":c.end,
                        "pullback_depth_atr":float(peak-trough),
                        "resumption_atr":float(z-trough)}
    return {"status":"no_pullback" if trough is None else "no_resumption"}

def dedupe(candidates):
    # Many 5-minute forecasts can trigger on the same minute for the same side.
    # Resolve ties using only the original probability and forecast time.
    seen={}
    for r in sorted(candidates,key=lambda r:(r["t"],r["symbol"],r["side"],-r["rank"],r["forecast_t"])):
        seen.setdefault((r["t"],r["symbol"],r["side"]),r)
    return list(seen.values())

def overlap(rs):
    n=len(rs)
    return {"n":n,"outcomes":dict(Counter(r["label"]["outcome"] for r in rs)),
            "mean_gross_r":sum(float(r["label"]["gross_r"]) for r in rs)/n if n else None,
            "mean_base_r":sum(r["y"][0] for r in rs)/n if n else None,
            "mean_stress_r":sum(r["tier_net"] for r in rs)/n if n else None}

def pullback_audit(rows,reference,loc,btc,bands,end,times,part):
    n,k,net,stress=EXPECTED[part]
    baseline=evaluate(reference,times,3)
    if len(reference)!=n or baseline["finance"]["trades"]!=k or abs(baseline["finance"]["0.0016"]["total_net_r"]-net)>1e-8 or abs(baseline["tier_adverse_funding"]["total_net_r"]-stress)>1e-8:
        raise ValueError("V5d reference mismatch")
    by_symbol=defaultdict(list)
    for r in rows:
        if r.get("vol_probability",0)>=GATE and "trade" in r:
            by_symbol[r["symbol"]].append(r)
    delayed=[]
    paired=[]
    status=Counter()
    by_side_status=defaultdict(Counter)
    improvements=[]
    waits=[]
    for symbol,rs in sorted(by_symbol.items()):
        p,m=loc[symbol]
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        for r in rs:
            old=r["trade"]
            a=D(r["audit_atr"])
            side=old["side"]
            conf=old["t"]
            anchor=bars[r["t"]-60].close
            q=pullback_decision(bars,conf,anchor,a,side)
            status[q["status"]]+=1
            by_side_status[side][q["status"]]+=1
            if q["status"]!="triggered":
                continue
            t=q["decision_t"]
            l=pullback_barrier(bars,t,a,side,r["t"]+HORIZON,end)
            if l["outcome"]=="INVALID_GEOMETRY":
                status["invalid_geometry"]+=1
                continue
            if l["outcome"] not in ("SL","TP","TIMEOUT"):
                raise ValueError("unexpected delayed outcome")
            fund=funding_charge(l,float(a),.0005)
            tr={"t":t,"forecast_t":r["t"],"symbol":symbol,"side":side,
                "rank":r["vol_probability"],"label":l,
                "y":[net_r(l,float(a),c) for c in COSTS],
                "funding":fund,"tier_net":net_r(l,float(a),stress_cost(bands.get(symbol)))-fund}
            delayed.append(tr)
            paired.append(old)
            sign=1 if side=="LONG" else -1
            improvements.append(sign*float((D(old["label"]["entry"])-D(l["entry"]))/a))
            waits.append((t-conf)/60)
    unique=dedupe(delayed)
    # Use the common observation calendar, extended through the last possible trigger.
    # No outcome-based inclusion; dates are fixed by the forecast grid and WAIT.
    calendar=list(range(min(times),max(times)+WAIT+60,60))
    result={"status":dict(status),"by_side_status":{s:dict(v) for s,v in by_side_status.items()},
            "baseline_all":overlap(reference),"pullback_all_forecasts":overlap(delayed),
            "pullback_unique_triggers":overlap(unique),
            "paired_immediate_not_portfolio":overlap(paired),
            "paired_pullback_not_portfolio":overlap(delayed),
            "median_entry_improvement_atr":float(np.median(improvements)) if improvements else None,
            "fraction_better_entry":sum(v>0 for v in improvements)/len(improvements) if improvements else None,
            "median_wait_minutes":float(np.median(waits)) if waits else None,
            "portfolios":{}}
    for s in ("BOTH","LONG","SHORT"):
        a=[r for r in reference if s=="BOTH" or r["side"]==s]
        b=[r for r in unique if s=="BOTH" or r["side"]==s]
        result["portfolios"][s]={"immediate":evaluate(a,calendar,3),"pullback":evaluate(b,calendar,3),
                                 "immediate_overlap":overlap(a),"pullback_overlap":overlap(b)}
    return result

def run(raw,g,h,i,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    data={p:[] for p in PARTS}
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("missing candle "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing features")
                if not f["inside_prior_range"]:
                    continue
                a=D(f["atr15"])
                anchor=bars[t-60].close
                x,_=inputs(f,anchor)
                y,_=event(bars,t,anchor,a)
                r={"x":x,"event":y,"symbol":symbol,"t":t}
                if part!="train":
                    conf=confirmation(bars,t,a,anchor)
                    r.update(conf)
                    if conf["status"]=="confirmed":
                        r.update(remaining(bars,t,a,anchor,conf))
                        side="LONG" if conf["side"]=="UP" else "SHORT"
                        l=bounded_barrier(bars,conf["confirmation_t"],a,side,end)
                        if l["outcome"]=="CENSORED":
                            raise ValueError("incomplete delayed outcome")
                        if l["outcome"]!="INVALID_GEOMETRY":
                            atr=float(a)
                            fund=funding_charge(l,atr,.0005)
                            r["audit_atr"]=str(a)
                            r["trade"]={"t":conf["confirmation_t"],"symbol":symbol,"side":side,
                                "label":l,"y":[net_r(l,atr,c) for c in COSTS],
                                "funding":fund,"tier_net":net_r(l,atr,stress_cost(bands.get(symbol)))-fund}
                data[part].append(r)
                counts[part]+=1
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    if [len(data[p]) for p in PARTS]!=[79260,77796,77336]:
        raise ValueError("V5a cohort mismatch")
    model=pipeline()
    model.fit(np.asarray([r["x"] for r in data["train"]]),np.asarray([r["event"] for r in data["train"]]))
    names=[*FEATURES,"atr_over_last_closed_price"]
    vi=[names.index(k) for k in ("rv15","rv60","rv_ratio","range_atr","atr_over_last_closed_price")]
    vol=pipeline()
    vol.fit(np.asarray([r["x"] for r in data["train"]])[:,vi],
            np.asarray([r["event"]!="NONE" for r in data["train"]],dtype=int))
    report={"type":"V5F_CAUSAL_PULLBACK","cutoffs":[CUT1,CUT2],"delay_sec":DELAY,
            "confirmation_move_atr":str(MOVE),"event_gate":GATE,"horizon_sec":HORIZON,
            "results":{},"limitations":["Compare original V5a and V5b volatility probabilities, plus no gate with volatility ranking.",
                "Fixed researcher-chosen 15min and 0.5 ATR confirmation, event probability >=0.60, no parameter search.",
                "Overlapping candidate statistics separate from chronological single-position max3 portfolios.",
                "SL1 ATR TP3 ATR based on original causal ATR, expiry at original t+240m, entry at confirmation+60s. SL-first intrabar, gap-stop at open. Costs/funding hypothetical.",
                "Directional correctness conditional on ex-post observed directional events is descriptive only; unconditional also reported.",
                "No selection based on future latency crossings or future realized outcome; invalid nonpositive barrier geometry counted. No actual fills, liquidation or recommendations.",
                "Same examined dates, current asset-selection bias, no independent confirmation."]}
    for part in PARTS[1:]:
        rows=data[part]
        p=align_probabilities(model.predict_proba(np.asarray([r["x"] for r in rows])),list(model.classes_))
        prob=1-p[:,CLASSES.index("NONE")]
        met=binary_metrics([r["event"]!="NONE" for r in rows],prob)
        expected=.5870439166518046 if part=="validation" else .6005279571949154
        if abs(met["auc"]-expected)>1e-8:
            raise ValueError("V5a event AUC mismatch")
        for r,v in zip(rows,prob):
            r["event_probability"]=float(v)
        selected=[r for r in rows if r["event_probability"]>=GATE]
        vp=positive(vol,np.asarray([r["x"] for r in rows])[:,vi])
        vm=binary_metrics([r["event"]!="NONE" for r in rows],vp)
        expected_vol=.5923385341549485 if part=="validation" else .6094123723225107
        if abs(vm["auc"]-expected_vol)>1e-8:
            raise ValueError("V5b volatility AUC mismatch")
        expected_confirmed=(3650,1861) if part=="validation" else (3552,1901)
        if (len(selected),sum(r["status"]=="confirmed" for r in selected))!=expected_confirmed:
            raise ValueError("V5c cohort mismatch")
        variants={"no_gate_vol_rank":[],"original_gate":[],"volatility_gate":[]}
        invalid=0
        for r,v in zip(rows,vp):
            r["vol_probability"]=float(v)
            if r["status"]!="confirmed":
                continue
            if "trade" not in r:
                invalid+=1
                continue
            variants["no_gate_vol_rank"].append({**r["trade"],"rank":float(v)})
            if r["event_probability"]>=GATE:
                variants["original_gate"].append({**r["trade"],"rank":r["event_probability"]})
            if v>=GATE:
                variants["volatility_gate"].append({**r["trade"],"rank":float(v)})
        result={"original_occurrence":met,"volatility_occurrence":vm,"invalid_geometry":invalid,
                "v5c_reference":stats(selected),"variants":{}}
        for name,rs in variants.items():
            n=len(rs)
            result["variants"][name]={"overlapping":{"n":n,
                "outcomes":dict(Counter(r["label"]["outcome"] for r in rs)),
                "mean_gross_r":sum(float(r["label"]["gross_r"]) for r in rs)/n if n else None,
                "mean_tier_stress_r":sum(r["tier_net"] for r in rs)/n if n else None},
                "portfolio_cap3":evaluate(rs,[t+DELAY for t in times[part]],3)}
        result["pullback_audit"]=pullback_audit(rows,variants["volatility_gate"],loc,btc,bands,end,[t+DELAY for t in times[part]],part)
        report["results"][part]=result
    report["pullback_settings"]={"wait_minutes":60,"pullback_atr":str(PULLBACK),"resume_atr":str(RESUME),"cancel_on_original_excursion":True}
    report["limitations"].extend(["Fixed researcher-selected 0.5 ATR pullback and 0.25 ATR resumption, max 60min; not optimized.",
        "Signed closed candle prices only; resumption must occur on a later candle. Original +/-3 ATR excursion cancels a pending setup.",
        "One minute latency from actual decision; original forecast expiry unchanged, new target/stop same ATR distances from new fill.",
        "Same symbol/side/minute trigger deduplication by original score then forecast time; different direction portfolios separate diagnostics.",
        "Paired subset uses future knowledge of whether a trigger occurred, descriptive only; not a deployable immediate-entry filter. No fresh holdout."])
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
