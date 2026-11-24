"""Freeze original SHORT fit and diagnose frozen historical score buckets.
No refit on validation/test; no gate selection; no prospective data used.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from scripts.research_pre_breakout_model import rows, FEATURES, partition, net_r, portfolio, metrics

CUT1,CUT2=1794450600,1794964500
BINS=(0,.05,.10,.15,.20,.30,.50,1.000001)
COSTS=(.0016,.0024)

def key(r):
    return (r["symbol"],r["asof_utc"])

def vector(f):
    return [float(f[k]) if f[k] not in ("",None) else np.nan for k in FEATURES]

def freeze(dataset,predictions,output):
    features={key(f):f for f in rows(dataset/"features.csv.gz") if f["inside_prior_range"]=="1"}
    labels={key(l):l for l in rows(dataset/"labels.csv.gz")
            if l["side"]=="SHORT" and l["horizon"]=="30" and l["outcome"] in ("TP","SL","TIMEOUT") and key(l) in features}
    train=[k for k in labels if partition(int(k[1]),CUT1,CUT2)=="train"]
    y=[int(labels[k]["outcome"]=="TP") for k in train]
    if len(train)!=28445:
        raise ValueError("training sample differs from E3")
    pipe=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),
                       LogisticRegression(C=1.0,max_iter=1000,random_state=0))
    pipe.fit(np.asarray([vector(features[k]) for k in train]),y)
    imputer,scaler,model=pipe.steps[0][1],pipe.steps[1][1],pipe.steps[2][1]
    pred=[r for r in rows(predictions/"predictions.csv.gz") if r["side"]=="SHORT"]
    p=pipe.predict_proba(np.asarray([vector(features[key(r)]) for r in pred]))[:,1]
    error=float(np.max(np.abs(p-np.asarray([float(r["p_tp"]) for r in pred]))))
    if error>1e-9:
        raise ValueError("frozen model does not reproduce original E3 predictions")
    frozen={"feature_order":FEATURES,"median":imputer.statistics_.tolist(),
            "mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
            "coef":model.coef_[0].tolist(),"intercept":float(model.intercept_[0]),
            "train_n":len(train),"constant_p":float(np.mean(y)),"cutoffs":[CUT1,CUT2],
            "side":"SHORT","horizon_min":30,"gate":.5,"costs":COSTS,
            "source_run":45434889849,"max_reproduction_error":error}
    raw=json.dumps(frozen,sort_keys=True,allow_nan=False,separators=(",",":")).encode()
    output.mkdir(parents=True,exist_ok=True)
    (output/"frozen-short.json").write_bytes(raw)
    result={"model_sha256":hashlib.sha256(raw).hexdigest(),"max_reproduction_error":error,
            "historical_diagnostics":{},"limitations":["Post-hoc buckets, not trading rules.",
                "Independent row means overlap; bucket portfolios are separate alternatives, not additive.",
                "Only evaluable snapshots; costs hypothetical; no exact PRD replay."]}
    for part in ("validation","test"):
        sample=[r for r in pred if r["partition"]==part]
        buckets=[]
        for lo,hi in zip(BINS,BINS[1:]):
            group=[r for r in sample if lo<=float(r["p_tp"])<hi]
            candidates=[{"t":int(r["asof_utc"]),"score":float(r["p_tp"]),"symbol":r["symbol"],
                         "side":"SHORT","label":labels[key(r)],"atr":float(features[key(r)]["atr15"])} for r in group]
            buckets.append({"lo":lo,"hi":min(1,hi),"n":len(group),
                "outcomes":dict(Counter(r["outcome"] for r in group)),
                "mean_net_r_overlapping":{str(c):float(np.mean([net_r(r["label"],r["atr"],c) for r in candidates])) if candidates else None for c in COSTS},
                "isolated_bucket_portfolio":{str(c):portfolio(candidates,c) for c in COSTS}})
        no21=[r for r in sample if not 1795219200<=int(r["asof_utc"])<1795305600]
        result["historical_diagnostics"][part]={"buckets":buckets,
            "excluding_nov21":metrics([int(r["actual_tp"]) for r in no21],[float(r["p_tp"]) for r in no21])}
    (output/"diagnostics.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)
    print("FROZEN_MODEL_JSON="+raw.decode(),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("dataset","predictions","output"):
        p.add_argument("--"+arg,type=Path,required=True)
    a=p.parse_args()
    freeze(a.dataset,a.predictions,a.output)
