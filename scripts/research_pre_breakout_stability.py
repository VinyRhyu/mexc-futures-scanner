"""E3b: post-hoc stability audit of frozen E3 predictions, no refit or threshold tuning."""
from __future__ import annotations
import argparse
import csv
import gzip
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score

DAY = 86400
SEED = 20261124
REPLICATES = 1000

def load(path):
    with gzip.open(path,"rt",newline="") as f:
        for r in csv.DictReader(f):
            yield dict(symbol=r["symbol"],side=r["side"],partition=r["partition"],
                       t=int(r["asof_utc"]),y=int(r["actual_tp"]),
                       p=float(r["p_tp"]),base=float(r["constant_p"]))

def metrics(rows):
    y=np.asarray([r["y"] for r in rows])
    p=np.asarray([r["p"] for r in rows])
    b=np.asarray([r["base"] for r in rows])
    return {"n":len(rows),"tp_rate":float(y.mean()),"mean_p":float(p.mean()),
            "auc":float(roc_auc_score(y,p)) if len(np.unique(y))==2 else None,
            "brier":float(np.mean((p-y)**2)),
            "baseline_brier":float(np.mean((b-y)**2)),
            "brier_gain":float(np.mean((b-y)**2-(p-y)**2))}

def group(rows,key):
    result=defaultdict(list)
    for r in rows:
        result[key(r)].append(r)
    return dict(result)

def day(t):
    return datetime.fromtimestamp(t,timezone.utc).date().isoformat()

def calibration(rows):
    # Fixed bins, not selected for performance; low counts remain visible.
    out=[]
    for lo,hi in zip((0,.05,.10,.15,.20,.30,.50),(.05,.10,.15,.20,.30,.50,1.000001)):
        sample=[r for r in rows if lo<=r["p"]<hi]
        out.append({"lo":lo,"hi":min(hi,1),"n":len(sample),
                    "mean_p":float(np.mean([r["p"] for r in sample])) if sample else None,
                    "tp_rate":float(np.mean([r["y"] for r in sample])) if sample else None})
    return out

def bootstrap(rows,block_seconds,replicates=REPLICATES):
    # All assets in each block sampled jointly; preserve cross-asset correlation.
    # Nonoverlapping anchored time blocks; small number of blocks limits inference.
    start=min(r["t"] for r in rows)
    blocks=list(group(rows,lambda r:(r["t"]-start)//block_seconds).values())
    rng=np.random.default_rng(SEED)
    aucs,gains=[],[]
    for _ in range(replicates):
        sample=[r for i in rng.integers(0,len(blocks),size=len(blocks)) for r in blocks[i]]
        m=metrics(sample)
        if m["auc"] is not None:
            aucs.append(m["auc"])
        gains.append(m["brier_gain"])
    def ci(vals):
        return [float(x) for x in np.quantile(vals,[.025,.975])] if vals else None
    return {"block_hours":block_seconds/3600,"blocks":len(blocks),
            "replicates":replicates,"auc_valid_replicates":len(aucs),
            "auc_percentile_95":ci(aucs),"brier_gain_percentile_95":ci(gains)}

def audit(rows,replicates=REPLICATES):
    report={"source_run":45434889849,"type":"exploratory_posthoc_stability",
            "limitations":["Already-inspected retrospective partitions; not confirmatory inference.",
                           "Short windows and few temporal blocks yield unstable intervals.",
                           "Block bootstrap approximates dependence, not proof of independence or persistent edge.",
                           "No threshold changes, no retraining, no finance inference.",
                           "Calibration bins fixed for diagnosis only."],"results":{}}
    for side in ("LONG","SHORT"):
        report["results"][side]={}
        for part in ("validation","test"):
            sample=[r for r in rows if r["side"]==side and r["partition"]==part]
            if not sample:
                raise ValueError("missing partition")
            report["results"][side][part]={
                "overall":metrics(sample),
                "by_symbol":{k:metrics(v) for k,v in sorted(group(sample,lambda r:r["symbol"]).items())},
                "by_day_utc":{k:metrics(v) for k,v in sorted(group(sample,lambda r:day(r["t"])).items())},
                "leave_one_symbol_out":{s:metrics([r for r in sample if r["symbol"]!=s])
                                         for s in sorted({r["symbol"] for r in sample})},
                "calibration":calibration(sample),
                "bootstrap":[bootstrap(sample,secs,replicates) for secs in (21600,86400,172800)]}
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=audit(list(load(a.input/"predictions.csv.gz")))
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"summary.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2),flush=True)
