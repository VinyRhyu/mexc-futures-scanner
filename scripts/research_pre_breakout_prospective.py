"""Locked SHORT prospective evaluation; no fitting, order routing or notifications."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from scripts.research_pre_breakout_coverage import collect, SYMBOLS
from scripts.research_pre_breakout_dataset import features, label
from scripts.research_pre_breakout_model import metrics, net_r, FEATURES
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D

START=int(datetime.fromisoformat("2026-11-25T00:00:00+00:00").timestamp())
END=int(datetime.fromisoformat("2026-12-09T00:00:00+00:00").timestamp())
FREEZE=int(datetime.fromisoformat("2026-11-24T16:36:50+00:00").timestamp())
HASH="b02b0e2e30a441b9719d071e8d2cb214b99e19f9445a0485b556625ea09224d1"
MODEL=Path("config/research/predict-v2-frozen-short.json")
DAY=86400
SEED=20261124

def load_model(path=MODEL):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=HASH:
        raise ValueError("frozen model digest differs")
    m=json.loads(raw)
    if tuple(m["feature_order"])!=FEATURES or m["gate"]!=.5 or m["side"]!="SHORT" or m["horizon_min"]!=30:
        raise ValueError("model contract differs")
    if not FREEZE<START or END-START!=14*DAY:
        raise ValueError("invalid prospective window")
    return m

def probability(f,m):
    z=m["intercept"]
    for k,med,mean,scale,coef in zip(m["feature_order"],m["median"],m["mean"],m["scale"],m["coef"]):
        x=med if f[k] is None else float(f[k])
        if not math.isfinite(x) or not scale>0:
            raise ValueError("invalid feature or scale")
        z+=coef*(x-mean)/scale
    return 1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z))

def require_closed(now):
    if now<END+31*60+10:
        raise ValueError("prospective window and final outcome tail are not closed")

def replay(client,m):
    require_closed(client.server_time())
    left,right=START-2*DAY,END+31*60
    expected=(right-left)//60
    universe={}
    for symbol in SYMBOLS:
        bars,failures,_=collect(client,symbol,left,right)
        if failures or len(bars)!=expected or any(t not in bars for t in range(left,right,60)):
            raise ValueError("incomplete prospective M1 coverage: "+symbol)
        universe[symbol]=bars
    out=[]
    for t in range(START,END,300):
        for symbol,bars in universe.items():
            f=features(bars,universe["BTC_USDT"],t)
            if f is None:
                raise ValueError("unexpected missing prospective features")
            if not f["inside_prior_range"]:
                continue
            p=probability(f,m)
            a=D(f["atr15"])
            l=label(bars,t,a,"SHORT",30,right)
            if l["outcome"] not in ("TP","SL","TIMEOUT"):
                raise ValueError("unexpected invalid prospective label")
            out.append({"t":t,"symbol":symbol,"score":p,"y":int(l["outcome"]=="TP"),
                        "atr":float(a),"label":l})
    return out

def trades(rows,m):
    out=[]
    available=-1
    for r in sorted(rows,key=lambda r:(r["t"],-r["score"],r["symbol"])):
        if r["score"]<m["gate"] or r["t"]<available:
            continue
        available=int(r["label"]["exit_ts"])+60
        out.append({**r,"net":{str(c):net_r(r["label"],r["atr"],c) for c in m["costs"]}})
    return out

def financial(trades_,cost):
    # Resample whole UTC dates, including zero-trade dates, preserving cross-asset dependence.
    day_totals=np.zeros(14)
    day_counts=np.zeros(14)
    values=[]
    for r in trades_:
        value=r["net"][str(cost)]
        idx=(r["t"]-START)//DAY
        day_totals[idx]+=value
        day_counts[idx]+=1
        values.append(value)
    rng=np.random.default_rng(SEED)
    ci=[]
    for _ in range(2000):
        ids=rng.integers(0,14,14)
        n=day_counts[ids].sum()
        if n:
            ci.append(float(day_totals[ids].sum()/n))
    pnl=peak=dd=0.
    for v in values:
        pnl+=v
        peak=max(peak,pnl)
        dd=max(dd,peak-pnl)
    return {"trades":len(values),"active_days":int((day_counts>0).sum()),"net_r":pnl,
            "mean_r":pnl/len(values) if values else None,"drawdown_r":dd,
            "mean_r_day_bootstrap_95":np.quantile(ci,[.025,.975]).tolist() if ci else None,
            "valid_bootstrap_replicates":len(ci)}

def probability_audit(rows,m):
    from scripts.research_pre_breakout_stability import bootstrap
    sample=[{"t":r["t"],"y":r["y"],"p":r["score"],"base":m["constant_p"]} for r in rows]
    y=[r["y"] for r in rows]
    return {"model":metrics(y,[r["score"] for r in rows]),
            "constant":metrics(y,np.full(len(y),m["constant_p"])),
            "blocks_24h":bootstrap(sample,DAY,1000)}

def run(output):
    m=load_model()
    observations=replay(MexcClient(),m)
    if not observations:
        raise ValueError("no evaluable observations")
    selected=trades(observations,m)
    prob=probability_audit(observations,m)
    finance={str(c):financial(selected,c) for c in m["costs"]}
    b=prob["blocks_24h"]["brier_gain_percentile_95"]
    a=prob["blocks_24h"]["auc_percentile_95"]
    adequate=len(selected)>=30 and all(v["active_days"]>=10 for v in finance.values())
    passed=adequate and a is not None and a[0]>.5 and b is not None and b[0]>0 and all(
        v["mean_r_day_bootstrap_95"] is not None and v["mean_r_day_bootstrap_95"][0]>0 for v in finance.values())
    result={"start":START,"end_exclusive":END,"model_hash":HASH,"n":len(observations),
            "probability":prob,"finance":finance,"decision":"REVIEW_ONLY" if passed else
            "INCONCLUSIVE_SAMPLE" if not adequate else "NOT_VALIDATED",
            "limitations":["Prospective offline replay; no real fills, historical tick, funding or liquidation.",
                           "Geometric cohort only; not matched PRD replay.",
                           "Daily bootstrap descriptive; fourteen dates not independent proof.",
                           "No capital deployment or automatic promotion."]}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    with (output/"predictions.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["t","symbol","score","y","outcome","gross_r"])
        w.writeheader()
        for r in observations:
            w.writerow({**{k:r[k] for k in ("t","symbol","score","y")},
                        "outcome":r["label"]["outcome"],"gross_r":r["label"]["gross_r"]})
    print(json.dumps(result,indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--preflight",action="store_true")
    p.add_argument("--output",type=Path,default=Path("reports/predict-v2-prospective"))
    a=p.parse_args()
    if a.preflight:
        m=load_model()
        print(json.dumps({"status":"FROZEN_MODEL_VERIFIED","model_hash":HASH,"start":START,"end":END}))
    else:
        run(a.output)
