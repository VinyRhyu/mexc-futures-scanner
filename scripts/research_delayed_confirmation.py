"""V5c: fixed causal delayed confirmation diagnostic; no trade strategy."""
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
                data[part].append(r)
                counts[part]+=1
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    if [len(data[p]) for p in PARTS]!=[79260,77796,77336]:
        raise ValueError("V5a cohort mismatch")
    model=pipeline()
    model.fit(np.asarray([r["x"] for r in data["train"]]),np.asarray([r["event"] for r in data["train"]]))
    report={"type":"V5C_DELAYED_CONFIRMATION","cutoffs":[CUT1,CUT2],"delay_sec":DELAY,
            "confirmation_move_atr":str(MOVE),"event_gate":GATE,"horizon_sec":HORIZON,
            "results":{},"limitations":["V5b may still be pending; diagnostic uses exact V5a original features, not a selected V5b model.",
                "Fixed researcher-chosen 15min and 0.5 ATR confirmation, event probability >=0.60, no parameter search.",
                "All candidates overlapping, no position or daily quota, no PNL, costs, SL, TP execution or recommendations.",
                "Directional correctness conditional on ex-post observed directional events is descriptive only; unconditional also reported.",
                "MFE/MAE are extrema after delayed entry, not achievable returns; order of extrema not inferred.",
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
        report["results"][part]={"reference_occurrence":met,"all":stats(rows),
                                "p_ge_0.60":stats(selected),
                                "by_side":{s:stats([r for r in selected if r.get("side")==s]) for s in ("UP","DOWN")}}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
