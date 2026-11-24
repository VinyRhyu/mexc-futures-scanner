"""V5b: isolate movement and direction predictability against stronger baselines."""
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

def align_probabilities(probabilities,observed_classes):
    # A class absent from training has no fitted probability, not an invented sample.
    if len(set(observed_classes))!=len(observed_classes) or not set(observed_classes)<=set(CLASSES):
        raise ValueError("invalid observed class mapping")
    raw=np.asarray(probabilities,dtype=float)
    if raw.ndim!=2 or raw.shape[1]!=len(observed_classes) or not np.all(np.isfinite(raw)) or np.any(raw<0) or not np.allclose(raw.sum(axis=1),1.):
        raise ValueError("invalid class probabilities")
    aligned=np.zeros((len(raw),len(CLASSES)))
    for j,c in enumerate(observed_classes):
        aligned[:,CLASSES.index(c)]=raw[:,j]
    return aligned

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

def binary_metrics(y,p):
    y=np.asarray(y,dtype=int)
    p=np.clip(np.asarray(p,dtype=float),1e-15,1-1e-15)
    if len(y)==0 or len(y)!=len(p):
        raise ValueError("invalid binary sample")
    return {"n":len(y),"prevalence":float(np.mean(y)),"pred_mean":float(np.mean(p)),
            "auc":auc(y,p),"ap":ap(y,p),"brier":float(np.mean((y-p)**2)),
            "log_loss":float(-np.mean(y*np.log(p)+(1-y)*np.log1p(-p)))}

def binary_gain(y,p,base,days):
    # Convert to two outcome log probabilities, reuse paired whole-day bootstrap.
    y=np.asarray(y,dtype=int)
    p=np.asarray(p,dtype=float)
    base=np.asarray(base,dtype=float)
    pp=np.zeros((len(y),len(CLASSES)))
    bb=np.zeros_like(pp)
    pp[:,CLASSES.index("UP")]=p
    pp[:,CLASSES.index("NONE")]=1-p
    bb[:,CLASSES.index("UP")]=base
    bb[:,CLASSES.index("NONE")]=1-base
    return day_gain(np.where(y,"UP","NONE"),pp,bb,days)

def symbol_prior(y,symbols):
    return {s:float(np.mean(y[symbols==s])) for s in sorted(set(symbols))}

def pipeline():
    return make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),
                         LogisticRegression(C=1.,max_iter=1000,solver="lbfgs",random_state=SEED))

def positive(model,x):
    return model.predict_proba(x)[:,list(model.classes_).index(1)]

def baseline_audit(data,width):
    train=data["train"]
    X=np.asarray(train["x"])[:,:width]
    y=np.asarray(train["y"])
    sy=np.asarray(train["symbol"])
    names=[*FEATURES,"atr_over_last_closed_price"]
    vol_idx=[names.index(k) for k in ("rv15","rv60","rv_ratio","range_atr","atr_over_last_closed_price")]
    # Separate occurrence model and conditional direction model. No event outcome supplied at prediction.
    ye=(y!="NONE").astype(int)
    dm=np.isin(y,("UP","DOWN"))
    yd=(y[dm]=="UP").astype(int)
    if set(np.unique(ye))!={0,1} or set(np.unique(yd))!={0,1}:
        raise ValueError("missing primary binary class")
    priore,priord=float(ye.mean()),float(yd.mean())
    se,sd=symbol_prior(ye,sy),symbol_prior(yd,sy[dm])
    ev,full,direction=pipeline(),pipeline(),pipeline()
    ev.fit(X[:,vol_idx],ye)
    full.fit(X,ye)
    direction.fit(X[dm],yd)
    original=pipeline()
    original.fit(X,y)
    result={"volatility_features":[names[j] for j in vol_idx],
            "train_occurrence_prior":priore,"train_direction_prior":priord,
            "train_symbol_occurrence_prior":se,"train_symbol_direction_prior":sd,"parts":{}}
    for part in PARTS[1:]:
        q=data[part]
        xx=np.asarray(q["x"])[:,:width]
        yy=np.asarray(q["y"])
        ss=np.asarray(q["symbol"])
        days=np.asarray(q["day"])
        ey=(yy!="NONE").astype(int)
        mask=np.isin(yy,("UP","DOWN"))
        dy=(yy[mask]=="UP").astype(int)
        pp=align_probabilities(original.predict_proba(xx),list(original.classes_))
        pm=metrics(yy,pp)
        target=(.6005279571949154,.541316639858392) if part=="test" else (.5870439166518046,.5578397664566601)
        if max(abs(pm["event_auc"]-target[0]),abs(pm["direction_auc"]-target[1]))>1e-8:
            raise ValueError("V5a benchmark differs")
        eprior=np.full(len(ey),priore)
        esym=np.array([se.get(s,priore) for s in ss])
        dprior=np.full(len(dy),priord)
        dsym=np.array([sd.get(s,priord) for s in ss[mask]])
        event_preds={"constant":eprior,"symbol_prior":esym,
                     "volatility_only":positive(ev,xx[:,vol_idx]),
                     "binary_full":positive(full,xx),"v5a_multiclass":1-pp[:,CLASSES.index("NONE")]}
        dpp=pp[mask,CLASSES.index("UP")]/np.maximum(1e-15,pp[mask,CLASSES.index("UP")]+pp[mask,CLASSES.index("DOWN")])
        direction_preds={"constant":dprior,"symbol_prior":dsym,
                         "binary_full":positive(direction,xx[mask]),"v5a_multiclass":dpp}
        out={}
        for name,labels,preds,base,dd,assets in (("occurrence",ey,event_preds,esym,days,ss),
                  ("conditional_direction",dy,direction_preds,dsym,days[mask],ss[mask])):
            out[name]={}
            for variant,p in preds.items():
                per_symbol=[binary_metrics(labels[assets==s],p[assets==s]) for s in sorted(set(assets))]
                aucs=[v["auc"] for v in per_symbol if v["auc"] is not None]
                out[name][variant]={**binary_metrics(labels,p),
                    "macro_symbol_auc":float(np.mean(aucs)) if aucs else None,
                    "symbols_with_auc":len(aucs),
                    "gain_vs_symbol_prior":binary_gain(labels,p,base,dd)}
        result["parts"][part]=out
    return result

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
                q["x"].append(x)
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
    if not {"UP","DOWN","NONE"}<=set(counts) or not set(counts)<=set(CLASSES):
        raise ValueError("training lacks a primary event class")
    missing_classes=[k for k in CLASSES if k not in counts]
    prior=np.asarray([counts[k]/len(y) for k in CLASSES])
    report={"type":"V5B_BASELINE_DECOMPOSITION","cutoffs":[CUT1,CUT2],"horizon_minutes":240,
            "excursion_atr":3,"classes":CLASSES,"training_counts":{k:counts[k] for k in CLASSES},
            "absent_training_classes":missing_classes,
            "training_step_seconds":900,"evaluation_step_seconds":300,
            "feature_order":[*FEATURES,"atr_over_last_closed_price"],
            "coverage":audit,"results":{},"limitations":[
                "Event labels use future candles only for outcomes; no trade execution, PNL or stop.",
                "First excursion relative to causal anchor; both barriers in same minute ambiguous unless open establishes order.",
                "Directional metrics conditional on known direction after the fact; not standalone trading performance.",
                "Existing inside-range proxy, fixed 52 assets, current-selection hindsight and previously examined dates.",
                "Overlapping outcomes and correlated assets; day bootstrap descriptive with few dates.",
                "No hyperparameter tuning or model selection for production. No independent temporal confirmation.",
                "An unobserved optional AMBIGUOUS class receives zero probability in both model and train prior. Future appearances are counted, not discarded; log loss uses numerical clipping. No synthetic labels."]}
    expected_counts={"train":79260,"validation":77796,"test":77336}
    if any(len(data[p]["y"])!=n for p,n in expected_counts.items()):
        raise ValueError("V5a cohort mismatch")
    report["results"]=baseline_audit(data,width)
    report["limitations"].extend(["Volatility-only and per-symbol empirical priors are fixed diagnostic baselines, not new trading rules.",
        "Conditional direction is evaluated only on actual directional events, not an actionable forecast gate.",
        "Macro AUC averages within-symbol discrimination; pooled AUC can reflect differences between assets.",
        "No independent temporal holdout; no threshold or trade optimization."])
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    # Full per-symbol metrics in artifact; compact workflow log.
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
