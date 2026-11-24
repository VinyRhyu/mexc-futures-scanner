"""E3 exploratory 30m geometric-cohort model, not PRD replay or live trading."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZON=30
EMBARGO=3600
MAX_LABEL_TIME=1860
THRESHOLD=0.5
COSTS=(0.0016,0.0024)
FEATURES=("range_atr","range_position","rv15","rv60","rv_ratio","relative_volume",
          "body_atr","upper_wick_atr","lower_wick_atr")+tuple(
              f"{prefix}_{n}" for n in (1,5,15,30,60) for prefix in ("ret","btc_ret","rel_btc"))


def rows(path):
    with gzip.open(path,"rt",newline="") as f:
        yield from csv.DictReader(f)


def partition(t,cut1,cut2):
    if t+MAX_LABEL_TIME<=cut1:
        return "train"
    if cut1+EMBARGO<=t and t+MAX_LABEL_TIME<=cut2:
        return "validation"
    if t>=cut2+EMBARGO:
        return "test"
    return None


def net_r(label,atr,cost):
    # Round-trip notional assumption: half the cost at each fill.
    return float(label["gross_r"])-cost/2*(float(label["entry"])+float(label["exit"]))/atr


def metrics(y,p):
    return {"n":len(y),"tp_rate":float(np.mean(y)),
            "mean_p":float(np.mean(p)),
            "brier":float(brier_score_loss(y,p)),
            "log_loss":float(log_loss(y,p,labels=[0,1])),
            "auc":float(roc_auc_score(y,p)) if len(set(y))==2 else None}


def portfolio(candidates,cost):
    # Fixed risk per trade, one position across all symbols and both sides.
    # Must be free at decision time; conservative extra minute after exit.
    available=-1
    result=[]
    for r in sorted(candidates,key=lambda x:(x["t"],-x["score"],x["symbol"],x["side"])):
        if r["t"]<available:
            continue
        available=int(r["label"]["exit_ts"])+60
        result.append(net_r(r["label"],r["atr"],cost))
    pnl=peak=dd=0.0
    for r in result:
        pnl+=r
        peak=max(peak,pnl)
        dd=max(dd,peak-pnl)
    win=sum(r for r in result if r>0)
    loss=-sum(r for r in result if r<0)
    return {"trades":len(result),"total_net_r":pnl,"mean_net_r":pnl/len(result) if result else None,
            "profit_factor":win/loss if loss else None,"max_drawdown_r":dd,
            "win_rate":sum(r>0 for r in result)/len(result) if result else None}


def run(source,output):
    # Time range from complete features, before filtering by label or outcome.
    feature_rows=list(rows(source/"features.csv.gz"))
    times=[int(r["asof_utc"]) for r in feature_rows]
    start,end=min(times),max(times)+300
    cut1=start+int((end-start)*.6)//300*300
    cut2=start+int((end-start)*.8)//300*300
    features={(r["symbol"],r["asof_utc"]):r for r in feature_rows if r["inside_prior_range"]=="1"}
    if not features:
        raise ValueError("empty geometric cohort")
    data={s:{p:[] for p in ("train","validation","test")} for s in ("LONG","SHORT")}
    excluded=Counter()
    for l in rows(source/"labels.csv.gz"):
        if int(l["horizon"])!=HORIZON:
            continue
        f=features.get((l["symbol"],l["asof_utc"]))
        if f is None:
            continue
        t=int(l["asof_utc"])
        part=partition(t,cut1,cut2)
        if not part or l["outcome"] not in ("TP","SL","TIMEOUT"):
            excluded["purged_or_censored"]+=1
            continue
        a=float(f["atr15"])
        if a<=0:
            raise ValueError("invalid ATR")
        vals=[float(f[k]) if f[k] not in ("",None) else np.nan for k in FEATURES]
        data[l["side"]][part].append({"symbol":l["symbol"],"side":l["side"],"t":t,
                                      "x":vals,"y":int(l["outcome"]=="TP"),"atr":a,
                                      "label":l,"compression":f["rv_ratio"]!="" and
                                      float(f["rv_ratio"])<=0.7 and
                                      (float(f["range_position"])>=.5 if l["side"]=="LONG"
                                       else float(f["range_position"])<.5)})
    report={"source_run":45434595239,"range":[start,end],"cutoffs":[cut1,cut2],
            "embargo_seconds":EMBARGO,"horizon_min":HORIZON,"cohort":"inside prior range geometric proxy",
            "excluded":dict(excluded),"threshold":THRESHOLD,"features":FEATURES,
            "probability":{},"finance":{},"limitations":[
            "Retrospective exploratory split; no prospective holdout or independent rows.",
            "Fixed six assets; historical eligibility and exact PRD state not reconstructed.",
            "P(TP first by 30m); timeout and stop are non-TP; not a forecast of arbitrary price direction.",
            "Fixed 0.5 gate and compression ratio 0.7 chosen before seeing results, not optimized.",
            "Round-trip costs 0.16% and 0.24% hypothetical, not verified personal fees or historical fills.",
            "Fixed risk in R; no lot, liquidation, funding, tick, capital compounding, or matched PRD replay.",
            "Censored labels excluded; model quality is conditional on evaluable snapshots."]}
    prediction_rows=[]
    decisions={p:[] for p in ("validation","test")}
    for side,parts in data.items():
        train=parts["train"]
        if not train or len(set(r["y"] for r in train))!=2:
            raise ValueError("insufficient training classes")
        model=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
                            StandardScaler(),LogisticRegression(C=1.0,max_iter=1000,random_state=0))
        model.fit(np.array([r["x"] for r in train]),[r["y"] for r in train])
        base=float(np.mean([r["y"] for r in train]))
        report["probability"][side]={"train_n":len(train),"train_tp_rate":base}
        for part in ("validation","test"):
            sample=parts[part]
            if not sample:
                raise ValueError("empty evaluation split")
            y=[r["y"] for r in sample]
            p=model.predict_proba(np.array([r["x"] for r in sample]))[:,1]
            report["probability"][side][part]={"model":metrics(y,p),"constant":metrics(y,np.full(len(y),base))}
            for r,prob in zip(sample,p):
                r["score"]=float(prob)
                r["base"]=base
                decisions[part].append(r)
                prediction_rows.append({"symbol":r["symbol"],"side":side,"asof_utc":r["t"],
                                        "partition":part,"p_tp":float(prob),"constant_p":base,
                                        "actual_tp":r["y"],"outcome":r["label"]["outcome"]})
    for part,sample in decisions.items():
        variants={"all_geometric":[dict(r,score=r["base"]) for r in sample],
                  "compression":[dict(r,score=r["base"]) for r in sample if r["compression"]],
                  "model_p_ge_0_5":[r for r in sample if r["score"]>=THRESHOLD]}
        report["finance"][part]={k:{"eligible":len(v),**{str(c):portfolio(v,c) for c in COSTS}}
                                 for k,v in variants.items()}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2))
    with gzip.open(output/"predictions.csv.gz","wt",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(prediction_rows[0]))
        w.writeheader()
        w.writerows(prediction_rows)
    print(json.dumps(report,indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    run(a.input,a.output)
