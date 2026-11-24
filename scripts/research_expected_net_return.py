"""PREDICT V3: exploratory conditional expected net R, using frozen E2/E3 data.
No live orders, refitting on validation/test, threshold optimization, or PRD changes.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from scripts.research_pre_breakout_model import rows, FEATURES, partition, net_r

CUT1,CUT2=1794450600,1794964500
COSTS=(.0016,.0024)
SIDES=("LONG","SHORT")
PARTS=("train","validation","test")
ALPHA=10.0
GATE=0.0
DAY=86400
SEED=20261124

def key(r):
    return (r["symbol"],r["asof_utc"])

def vector(f):
    return [float(f[k]) if f[k] not in ("",None) else np.nan for k in FEATURES]

def target(l,atr):
    # Only a supervised outcome, never part of the input vector.
    return [net_r(l,atr,c) for c in COSTS]

def selected(candidates):
    """One position across both sides; ranking only uses information at decision."""
    available=-1
    out=[]
    for r in sorted(candidates,key=lambda r:(r["t"],-r["rank"],r["symbol"],r["side"])):
        if r["t"]<available:
            continue
        available=int(r["label"]["exit_ts"])+60
        out.append(r)
    return out

def passes_gate(pred):
    return all(float(x)>GATE for x in pred)

def utc_day(t):
    return datetime.fromtimestamp(t,timezone.utc).date().isoformat()

def block_ci(total,count,replicates=1000):
    if not np.sum(count):
        return None
    rng=np.random.default_rng(SEED)
    estimates=[]
    for _ in range(replicates):
        ids=rng.integers(0,len(total),len(total))
        n=np.sum(count[ids])
        if n:
            estimates.append(float(np.sum(total[ids])/n))
    return np.quantile(estimates,[.025,.975]).tolist() if estimates else None

def portfolio_stats(candidates,part_days):
    actual=selected(candidates)
    result={"eligible":len(candidates),"trades":len(actual),
            "side_counts":dict(Counter(r["side"] for r in actual))}
    for i,c in enumerate(COSTS):
        vals=[r["y"][i] for r in actual]
        pnl=peak=dd=0.
        for v in vals:
            pnl+=v
            peak=max(peak,pnl)
            dd=max(dd,peak-pnl)
        positive=sum(v for v in vals if v>0)
        negative=-sum(v for v in vals if v<0)
        daily=np.zeros(len(part_days))
        count=np.zeros(len(part_days))
        day_idx={d:j for j,d in enumerate(part_days)}
        for r,v in zip(actual,vals):
            j=day_idx[utc_day(r["t"])]
            daily[j]+=v
            count[j]+=1
        result[str(c)]={"total_net_r":pnl,"mean_net_r":pnl/len(vals) if vals else None,
                        "win_rate":sum(v>0 for v in vals)/len(vals) if vals else None,
                        "profit_factor":positive/negative if negative else None,
                        "max_drawdown_r":dd,"active_days":int((count>0).sum()),
                        "mean_r_day_bootstrap_95":block_ci(daily,count)}
    return result,actual

def prediction_metrics(y,p,baseline):
    y=np.asarray(y)
    p=np.asarray(p)
    base=np.full(len(y),baseline)
    return {"n":len(y),"actual_mean":float(np.mean(y)),"pred_mean":float(np.mean(p)),
            "mae":float(np.mean(np.abs(y-p))),"baseline_mae":float(np.mean(np.abs(y-base))),
            "mse":float(np.mean((y-p)**2)),"baseline_mse":float(np.mean((y-base)**2)),
            "correlation":float(np.corrcoef(y,p)[0,1]) if np.std(y)>0 and np.std(p)>0 else None}

def calibration(sample,i):
    edges=(-float("inf"),-.5,-.2,0,.2,.5,float("inf"))
    out=[]
    for lo,hi in zip(edges,edges[1:]):
        group=[r for r in sample if lo<=r["pred"][i]<hi]
        out.append({"lo":lo if np.isfinite(lo) else None,"hi":hi if np.isfinite(hi) else None,
                    "n":len(group),"pred_mean":float(np.mean([r["pred"][i] for r in group])) if group else None,
                    "actual_mean":float(np.mean([r["y"][i] for r in group])) if group else None})
    return out

def run(dataset,previous,output):
    features={key(f):f for f in rows(dataset/"features.csv.gz") if f["inside_prior_range"]=="1"}
    old={(r["symbol"],r["asof_utc"],r["side"]):r for r in rows(previous/"predictions.csv.gz")}
    data={s:{p:[] for p in PARTS} for s in SIDES}
    for l in rows(dataset/"labels.csv.gz"):
        if l["horizon"]!="30" or l["outcome"] not in ("TP","SL","TIMEOUT"):
            continue
        f=features.get(key(l))
        if f is None:
            continue
        t=int(l["asof_utc"])
        part=partition(t,CUT1,CUT2)
        if part is None:
            continue
        a=float(f["atr15"])
        if a<=0:
            raise ValueError("invalid ATR")
        side=l["side"]
        old_p=None
        if part!="train":
            prior=old[(l["symbol"],l["asof_utc"],side)]
            if prior["partition"]!=part or prior["outcome"]!=l["outcome"]:
                raise ValueError("E3 cohort mismatch")
            old_p=float(prior["p_tp"])
        data[side][part].append({"t":t,"symbol":l["symbol"],"side":side,
            "x":vector(f),"y":target(l,a),"label":l,"atr":a,"p_tp":old_p,
            "compression":f["rv_ratio"]!="" and float(f["rv_ratio"])<=.7 and
                (float(f["range_position"])>=.5 if side=="LONG" else float(f["range_position"])<.5)})
    report={"type":"V3_EXPECTED_NET_R_EXPLORATORY","source_runs":[45434595239,45434889849],
            "cutoffs":[CUT1,CUT2],"features":FEATURES,"alpha":ALPHA,"gate":GATE,"costs":COSTS,
            "model":{},"finance":{},"limitations":[
                "The historical validation/test periods were already inspected in V2; no confirmatory claims.",
                "Net R is fixed initial risk, not actual wallet return; fees/slippage/spread hypothetical.",
                "One position, exact E2/E3 evaluable cohort, future-censored rows excluded.",
                "No actual funding, liquidation, historical contract eligibility, lot/tick or exact PRD replay.",
                "Daily bootstrap descriptive with few dates and overlapping labels.",
                "A positive fitted expectation does not establish profitability. No parameter search."]}
    decisions={p:[] for p in PARTS[1:]}
    predictions=[]
    for side in SIDES:
        train=data[side]["train"]
        if len(train)!=28445:
            raise ValueError("training cohort differs from E3")
        X=np.asarray([r["x"] for r in train])
        Y=np.asarray([r["y"] for r in train])
        base=Y.mean(axis=0)
        # Each cost target estimated jointly as separate linear response columns.
        pipe=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
                           StandardScaler(),Ridge(alpha=ALPHA))
        pipe.fit(X,Y)
        report["model"][side]={"train_n":len(train),"train_mean_net_r":base.tolist()}
        for part,n_expected in (("validation",9471),("test",9536)):
            sample=data[side][part]
            if len(sample)!=n_expected:
                raise ValueError("evaluation cohort differs from E3")
            P=pipe.predict(np.asarray([r["x"] for r in sample]))
            for r,p in zip(sample,P):
                r["pred"]=p.tolist()
                r["base"]=base.tolist()
                decisions[part].append(r)
                predictions.append({"t":r["t"],"symbol":r["symbol"],"side":side,"partition":part,
                                    "pred_base_cost":p[0],"pred_adverse_cost":p[1],
                                    "actual_base_cost":r["y"][0],"actual_adverse_cost":r["y"][1],
                                    "p_tp_v2":r["p_tp"],"outcome":r["label"]["outcome"]})
            report["model"][side][part]={str(c):{
                **prediction_metrics([r["y"][i] for r in sample],P[:,i],base[i]),
                "calibration":calibration(sample,i)} for i,c in enumerate(COSTS)}
    all_trades=[]
    for part,sample in decisions.items():
        days=sorted({utc_day(r["t"]) for r in sample})
        variants={
            "all_geometric":[dict(r,rank=.10465811214624714 if r["side"]=="LONG" else .10736509052557568) for r in sample],
            "compression":[dict(r,rank=.10465811214624714 if r["side"]=="LONG" else .10736509052557568) for r in sample if r["compression"]],
            "v2_p_ge_0_5":[dict(r,rank=r["p_tp"]) for r in sample if r["p_tp"]>=.5],
            "constant_net_positive":[dict(r,rank=r["base"][1]) for r in sample if passes_gate(r["base"])],
            "v3_expected_net_positive":[dict(r,rank=r["pred"][1]) for r in sample if passes_gate(r["pred"])]}
        report["finance"][part]={}
        for name,candidates in variants.items():
            stats,actual=portfolio_stats(candidates,days)
            report["finance"][part][name]=stats
            for r in actual:
                all_trades.append({"partition":part,"strategy":name,"t":r["t"],"symbol":r["symbol"],
                                  "side":r["side"],"exit_ts":r["label"]["exit_ts"],
                                  "net_r_base_cost":r["y"][0],"net_r_adverse_cost":r["y"][1],
                                  "pred_base_cost":r["pred"][0],"pred_adverse_cost":r["pred"][1]})
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    for name,items in (("predictions",predictions),("trades",all_trades)):
        if items:
            with gzip.open(output/(name+".csv.gz"),"wt",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(items[0]))
                w.writeheader()
                w.writerows(items)
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("dataset","previous","output"):
        p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    run(a.dataset,a.previous,a.output)
