"""V4: fixed factorial horizon/amplitude research on frozen M1 history.
Compare six geometries on identical decision timestamps, no live orders or tuning.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from mexc_scanner.models import D
from scripts.research_pre_breakout_dataset import load_raw, contiguous, label
from scripts.research_pre_breakout_model import rows, net_r, FEATURES
from scripts.research_expected_net_return import vector, portfolio_stats, prediction_metrics, passes_gate, utc_day

CUT1,CUT2=1794450600,1794964500
HORIZONS=(30,60,120)
STOP_MULTIPLIERS=(1,2)
PRIMARY=(120,2)
COSTS=(.0016,.0024)
PARTS=("train","validation","test")
SIDES=("LONG","SHORT")
MAX_LABEL_TIME=121*60
EMBARGO=120*60

def partition(t):
    if t+MAX_LABEL_TIME<=CUT1:
        return "train"
    if t>=CUT1+EMBARGO and t+MAX_LABEL_TIME<=CUT2:
        return "validation"
    if t>=CUT2+EMBARGO:
        return "test"
    return None

def common_cohort(raw,dataset):
    meta=json.loads((raw/"coverage.json").read_text())
    end=meta["end_exclusive"]
    universe={s:load_raw(raw/m["raw_file"],m["sha256_uncompressed"]) for s,m in meta["symbols"].items()}
    sample={p:[] for p in PARTS}
    excluded=Counter()
    for f in rows(dataset/"features.csv.gz"):
        if f["inside_prior_range"]!="1":
            excluded["outside_geometric_range"]+=1
            continue
        t=int(f["asof_utc"])
        part=partition(t)
        if not part:
            excluded["purged_or_embargoed"]+=1
            continue
        bars=universe[f["symbol"]]
        # Historical coverage only, shared across all six configurations.
        if t+MAX_LABEL_TIME>end or contiguous(bars,t+60,t+MAX_LABEL_TIME) is None:
            excluded["incomplete_maximum_horizon"]+=1
            continue
        a=D(f["atr15"])
        if a<=0:
            raise ValueError("invalid ATR")
        # A nonpositive stop/target is not economically meaningful. Fail explicitly.
        entry=bars[t+60].open
        if entry<=3*a:
            raise ValueError("invalid common geometry; no silent cohort change")
        sample[part].append({"t":t,"symbol":f["symbol"],"x":vector(f),"a":a})
    return universe,end,sample,dict(excluded)

def outcome(bars,row,side,horizon,mult,end):
    risk=row["a"]*D(mult)
    l=label(bars,row["t"],risk,side,horizon,end)
    if l["outcome"] not in ("TP","SL","TIMEOUT"):
        raise ValueError("common cohort yielded censored or invalid label")
    return {**row,"side":side,"label":l,"atr":float(risk),
            "gross":float(l["gross_r"]),"y":[net_r(l,float(risk),c) for c in COSTS]}

def run_geometry(universe,end,sample,horizon,mult):
    report={"horizon_min":horizon,"stop_atr":mult,"target_atr":1.5*mult,"primary":(horizon,mult)==PRIMARY,
            "model":{},"finance":{},"outcomes":{}}
    decisions={p:[] for p in PARTS[1:]}
    prediction_rows=[]
    for side in SIDES:
        train=[outcome(universe[r["symbol"]],r,side,horizon,mult,end) for r in sample["train"]]
        X=np.asarray([r["x"] for r in train])
        Y=np.asarray([r["y"] for r in train])
        base=Y.mean(axis=0)
        pipe=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
                           StandardScaler(),Ridge(alpha=10.0))
        pipe.fit(X,Y)
        report["model"][side]={"train_n":len(train),"train_mean_net_r":base.tolist()}
        for part in PARTS[1:]:
            evaluable=[outcome(universe[r["symbol"]],r,side,horizon,mult,end) for r in sample[part]]
            if not evaluable:
                raise ValueError("empty evaluation split")
            pred=pipe.predict(np.asarray([r["x"] for r in evaluable]))
            report["model"][side][part]={str(c):prediction_metrics([r["y"][i] for r in evaluable],pred[:,i],base[i]) for i,c in enumerate(COSTS)}
            report["outcomes"][side+"_"+part]=dict(Counter(r["label"]["outcome"] for r in evaluable))
            for r,p in zip(evaluable,pred):
                r["pred"]=p.tolist()
                r["base"]=base.tolist()
                decisions[part].append(r)
                prediction_rows.append({"horizon":horizon,"stop_atr":mult,"partition":part,
                    "symbol":r["symbol"],"t":r["t"],"side":side,"pred_base":p[0],"pred_adverse":p[1],
                    "net_base":r["y"][0],"net_adverse":r["y"][1],"gross_r":r["gross"],
                    "outcome":r["label"]["outcome"]})
    trade_rows=[]
    for part,all_rows in decisions.items():
        days=sorted({utc_day(r["t"]) for r in all_rows})
        # Fixed training means as tie-breakers; do not use future outcomes.
        variants={
            "unfiltered":[dict(r,rank=r["base"][1]) for r in all_rows],
            "constant_positive":[dict(r,rank=r["base"][1]) for r in all_rows if passes_gate(r["base"])],
            "expected_positive":[dict(r,rank=r["pred"][1]) for r in all_rows if passes_gate(r["pred"])]}
        report["finance"][part]={}
        for name,candidates in variants.items():
            stats,actual=portfolio_stats(candidates,days)
            gross=sum(r["gross"] for r in actual)
            stats["gross_r"]=gross
            stats["mean_gross_r"]=gross/len(actual) if actual else None
            stats["base_cost_r"]=gross-stats[str(COSTS[0])]["total_net_r"]
            stats["adverse_cost_r"]=gross-stats[str(COSTS[1])]["total_net_r"]
            stats["outcomes"]=dict(Counter(r["label"]["outcome"] for r in actual))
            report["finance"][part][name]=stats
            for r in actual:
                trade_rows.append({"horizon":horizon,"stop_atr":mult,"partition":part,
                    "strategy":name,"symbol":r["symbol"],"t":r["t"],"side":r["side"],
                    "exit_ts":r["label"]["exit_ts"],"outcome":r["label"]["outcome"],
                    "gross_r":r["gross"],"net_base":r["y"][0],"net_adverse":r["y"][1]})
    return report,prediction_rows,trade_rows

def save_csv(path,items):
    if items:
        with gzip.open(path,"wt",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(items[0]))
            w.writeheader()
            w.writerows(items)

def run(raw,dataset,output):
    universe,end,sample,excluded=common_cohort(raw,dataset)
    report={"type":"V4_AMPLITUDE_HORIZON_FACTORIAL","source_runs":[45432136926,45434595239],
            "cutoffs":[CUT1,CUT2],"purge_seconds":MAX_LABEL_TIME,"embargo_seconds":EMBARGO,
            "common_decision_rows":{k:len(v) for k,v in sample.items()},"excluded":excluded,
            "primary":{"horizon":120,"stop_atr":2,"target_atr":3},
            "costs":COSTS,"configurations":{},
            "limitations":["Previously inspected history, exploratory only; no best-variant selection for deployment.",
                "Fixed six assets, geometric cohort not exact PRD state; common retrospective complete-data requirement.",
                "Different stops normalize each position to equal initial risk R; not equal notional size.",
                "Same decision timestamps, but each geometry independently reallocates one position; returns not additive.",
                "Same delayed entry, conservative stop-first/gap and timeout rules as E2; no actual fills, funding, tick, lot or liquidation.",
                "Costs are hypothetical; daily bootstrap descriptive, very few days; longer holds can increase exposure.",
                "No retraining on validation/test and no V2 future-window use."]}
    output.mkdir(parents=True,exist_ok=True)
    for horizon in HORIZONS:
        for mult in STOP_MULTIPLIERS:
            name=f"{horizon}m_stop{mult}atr"
            result,pred,trade=run_geometry(universe,end,sample,horizon,mult)
            report["configurations"][name]=result
            save_csv(output/(name+"-predictions.csv.gz"),pred)
            save_csv(output/(name+"-trades.csv.gz"),trade)
            print(json.dumps({"configuration":name,"finance":result["finance"]},allow_nan=False),flush=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("raw","dataset","output"):
        p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.dataset,a.output)
