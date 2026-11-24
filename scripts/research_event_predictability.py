"""V5a: event predictability audit, independent of trading exits and costs."""
from __future__ import annotations
import argparse
import json
import math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score,average_precision_score,log_loss
from scripts.research_universe_transfer import sources
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2
from scripts.research_expected_net_return import utc_day
from scripts.research_pre_breakout_model import FEATURES
from mexc_scanner.models import D

CLASSES=("AMBIGUOUS","DOWN","NONE","UP")
PARTS=("train","validation","test")
HORIZON=14400
LOOKBACK=86400
SEED=20261124
CONTEXT_NAMES=[f"{s}_ret_{h}h" for s in ("asset","btc","relative") for h in (1,4,12,24)]+[f"{s}_{k}_{h}h" for s in ("asset","btc") for h in (4,12,24) for k in ("rv","position","range")]

def event(bars,t,anchor,atr):
    # Anchor is last known close. No fill, SL, TP or costs. First excursion only.
    if atr<=0:
        raise ValueError("nonpositive ATR")
    upper,lower=anchor+3*atr,anchor-3*atr
    for ts in range(t,t+HORIZON,60):
        c=bars[ts]
        # At the open the order is known; inside an OHLC bar it is not.
        if c.open>=upper:
            return "UP",ts
        if c.open<=lower:
            return "DOWN",ts
        u,d=c.high>=upper,c.low<=lower
        if u and d:
            return "AMBIGUOUS",c.end
        if u or d:
            return ("UP" if u else "DOWN"),c.end
    return "NONE",t+HORIZON

def context(bars,btc,t):
    # Closes sampled at 15min spacing ending at t; no future observations.
    a=np.array([float(bars[t-60-j*900].close) for j in range(96,-1,-1)])
    b=np.array([float(btc[t-60-j*900].close) for j in range(96,-1,-1)])
    if np.any(a<=0) or np.any(b<=0):
        raise ValueError("invalid close")
    returns=[[float(s[-1]/s[-1-h*4]-1) for h in (1,4,12,24)] for s in (a,b)]
    out=returns[0]+returns[1]+[x-y for x,y in zip(*returns)]
    for s in (a,b):
        for h in (4,12,24):
            v=s[-(h*4+1):]
            lo,hi=float(np.min(v)),float(np.max(v))
            out.extend([float(np.std(np.diff(np.log(v)))),float((v[-1]-lo)/(hi-lo)) if hi>lo else np.nan,float(hi/lo-1)])
    return out

def auc(y,p):
    return float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None

def ap(y,p):
    return float(average_precision_score(y,p)) if len(np.unique(y))==2 else None

def metrics(y,p):
    y=np.asarray(y)
    p=np.asarray(p)
    index=np.array([CLASSES.index(k) for k in y])
    one=np.eye(len(CLASSES))[index]
    pe=1-p[:,CLASSES.index("NONE")]
    ye=(y!="NONE").astype(int)
    mask=np.isin(y,("UP","DOWN"))
    pd=p[mask,CLASSES.index("UP")]/np.maximum(1e-15,p[mask,CLASSES.index("UP")]+p[mask,CLASSES.index("DOWN")])
    yd=(y[mask]=="UP").astype(int)
    return {"n":len(y),"class_counts":dict(Counter(y.tolist())),
            "log_loss":float(log_loss(y,p,labels=list(CLASSES))),
            "multiclass_brier":float(np.mean(np.sum((p-one)**2,axis=1))),
            "event_auc":auc(ye,pe),"event_ap":ap(ye,pe),"event_brier":float(np.mean((pe-ye)**2)),
            "direction_n":int(mask.sum()),"direction_auc":auc(yd,pd) if len(yd) else None,
            "direction_brier":float(np.mean((pd-yd)**2)) if len(yd) else None}

def day_gain(y,p,base,days):
    # Paired daily resampling; retains all correlated symbols and overlapping events in each UTC day.
    idx=np.array([CLASSES.index(k) for k in y])
    gain=np.log(np.maximum(p[np.arange(len(y)),idx],1e-15))-np.log(np.maximum(base[np.arange(len(y)),idx],1e-15))
    days=np.asarray(days)
    unique=sorted(set(days))
    totals=np.array([gain[days==d].sum() for d in unique])
    counts=np.array([(days==d).sum() for d in unique])
    rng=np.random.default_rng(SEED)
    ix=rng.integers(0,len(unique),(2000,len(unique)))
    vals=totals[ix].sum(axis=1)/counts[ix].sum(axis=1)
    return {"days":len(unique),"mean_log_loss_gain":float(np.mean(gain)),"ci95":np.quantile(vals,[.025,.975]).tolist(),
            "daily":{d:float(t/n) for d,t,n in zip(unique,totals,counts)}}

def run(raw,g,h,i,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    data={part:{"x":[],"y":[],"day":[],"symbol":[]} for part in PARTS}
    audit={}
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("missing reference candle "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing features")
                # Pre-expansion proxy shared with V4a, not a confirmed breakout.
                if not f["inside_prior_range"]:
                    continue
                anchor=bars[t-60].close
                x,_=inputs(f,anchor)
                label,_=event(bars,t,anchor,D(f["atr15"]))
                q=data[part]
                q["x"].append(x+context(bars,btc,t))
                q["y"].append(label)
                q["day"].append(utc_day(t))
                q["symbol"].append(symbol)
                counts[part+"_"+label]+=1
        audit[symbol]=dict(counts)
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    width=len(FEATURES)+1
    train=data["train"]
    X=np.asarray(train["x"])
    y=np.asarray(train["y"])
    counts=Counter(y.tolist())
    if set(counts)!=set(CLASSES):
        raise ValueError("training lacks event class")
    prior=np.asarray([counts[k]/len(y) for k in CLASSES])
    report={"type":"V5A_EVENT_PREDICTABILITY","cutoffs":[CUT1,CUT2],"horizon_minutes":240,
            "excursion_atr":3,"classes":CLASSES,"training_counts":dict(counts),
            "training_step_seconds":900,"evaluation_step_seconds":300,
            "feature_order":[*FEATURES,"atr_over_last_closed_price",*CONTEXT_NAMES],
            "coverage":audit,"results":{},"limitations":[
                "Event labels use future candles only for outcomes; no trade execution, PNL or stop.",
                "First excursion relative to causal anchor; both barriers in same minute ambiguous unless open establishes order.",
                "Directional metrics conditional on known direction after the fact; not standalone trading performance.",
                "Existing inside-range proxy, fixed 52 assets, current-selection hindsight and previously examined dates.",
                "Overlapping outcomes and correlated assets; day bootstrap descriptive with few dates.",
                "No hyperparameter tuning or model selection for production. No independent temporal confirmation."]}
    for name,k in (("existing_features",width),("extended_context",X.shape[1])):
        model=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),
                            LogisticRegression(C=1.,max_iter=1000,solver="lbfgs",random_state=SEED))
        model.fit(X[:,:k],y)
        order=[list(model.classes_).index(c) for c in CLASSES]
        report["results"][name]={}
        for part in PARTS[1:]:
            q=data[part]
            xx=np.asarray(q["x"])[:,:k]
            yy=np.asarray(q["y"])
            pp=model.predict_proba(xx)[:,order]
            base=np.tile(prior,(len(yy),1))
            sy=np.asarray(q["symbol"])
            report["results"][name][part]={"model":metrics(yy,pp),"constant_train_prior":metrics(yy,base),
                "paired_day_log_loss_gain":day_gain(yy,pp,base,q["day"]),
                "by_symbol":{s:metrics(yy[sy==s],pp[sy==s]) for s in sorted(set(sy))}}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    # Full per-symbol metrics in artifact; compact workflow log.
    print(json.dumps({**report,"results":{n:{p:{k:v for k,v in q.items() if k!="by_symbol"} for p,q in r.items()} for n,r in report["results"].items()}},indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
