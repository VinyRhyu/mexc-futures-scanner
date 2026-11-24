"""V3b: matched 30/60m horizon experiment with causal amplitude/cost decomposition."""
import argparse
import json
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from scripts.research_pre_breakout_dataset import load_raw
from scripts.research_pre_breakout_model import rows, net_r, FEATURES
from scripts.research_expected_net_return import portfolio_stats, prediction_metrics, utc_day, COSTS, CUT1, CUT2

HORIZONS=(30,60)
MAX_LABEL=3660
EMBARGO=3600
ALPHA=10.
SIDES=("LONG","SHORT")
PARTS=("train","validation","test")

def split(t):
    if t+MAX_LABEL<=CUT1:
        return "train"
    if t>=CUT1+EMBARGO and t+MAX_LABEL<=CUT2:
        return "validation"
    if t>=CUT2+EMBARGO:
        return "test"
    return None

def inputs(f,last_close):
    atr=float(f["atr15"])
    close=float(last_close)
    if atr<=0 or close<=0:
        raise ValueError("invalid causal geometry")
    ratio=atr/close
    return [float(f[k]) if f[k] not in ("",None) else np.nan for k in FEATURES]+[ratio],close/atr

def predicted_net(gross,notional_r,side):
    # TP limits favorable gross R to 1.5 by construction. No favorable lower bound.
    gross=min(float(gross),1.5)
    sign=1 if side=="LONG" else -1
    # Approximate round-trip notional using last closed price, not future entry.
    turn=max(0.,notional_r+sign*gross/2)
    return [gross-c*turn for c in COSTS]

def run(raw,dataset,output):
    meta=json.loads((raw/"coverage.json").read_text())
    fs={}
    for symbol,m in meta["symbols"].items():
        bars=load_raw(raw/m["raw_file"],m["sha256_uncompressed"])
        for f in rows(dataset/"features.csv.gz"):
            if f["symbol"]!=symbol or f["inside_prior_range"]!="1":
                continue
            t=int(f["asof_utc"])
            if not split(t):
                continue
            c=bars[t-60]
            if c.end!=t:
                raise ValueError("future or misaligned price")
            x,notional=inputs(f,c.close)
            fs[(symbol,t)]={"x":x,"notional":notional,"atr":float(f["atr15"])}
    labels={}
    for l in rows(dataset/"labels.csv.gz"):
        h=int(l["horizon"])
        k=(l["symbol"],int(l["asof_utc"]))
        if h in HORIZONS and k in fs and l["outcome"] in ("TP","SL","TIMEOUT"):
            labels.setdefault((*k,l["side"]),{})[h]=l
    data={s:{p:[] for p in PARTS} for s in SIDES}
    for (symbol,t,side),ll in labels.items():
        if set(ll)!=set(HORIZONS):
            continue
        f=fs[(symbol,t)]
        data[side][split(t)].append({"symbol":symbol,"side":side,"t":t,**f,"labels":ll})
    report={"type":"V3B_MATCHED_HORIZONS","horizons":HORIZONS,"cutoffs":[CUT1,CUT2],
            "purge_seconds":MAX_LABEL,"embargo_seconds":EMBARGO,
            "model":"ridge gross R alpha 10; causal notional/ATR cost proxy",
            "features":[*FEATURES,"atr_over_last_closed_price"],"cohort":{},"results":{},
            "limitations":["Post-hoc research on previously inspected dates; no independent test.",
                "Matched evaluable labels exclude missing outcomes; same timestamps per horizon.",
                "Cost prediction uses last closed price, not guaranteed entry; realized costs use actual simulated fills.",
                "Fixed 1 ATR stop and 1.5 ATR TP; higher horizon does not widen price barriers.",
                "No real execution, funding, tick/lot, liquidation or exact PRD replay."]}
    for s in SIDES:
        report["cohort"][s]={p:len(data[s][p]) for p in PARTS}
    for h in HORIZONS:
        result={"prediction":{},"finance":{}}
        decisions={p:[] for p in PARTS[1:]}
        for side in SIDES:
            train=data[side]["train"]
            y=[float(r["labels"][h]["gross_r"]) for r in train]
            base=[float(np.mean([net_r(r["labels"][h],r["atr"],c) for r in train])) for c in COSTS]
            pipe=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
                               StandardScaler(),Ridge(alpha=ALPHA))
            pipe.fit(np.asarray([r["x"] for r in train]),y)
            result["prediction"][side]={}
            for p in PARTS[1:]:
                sample=data[side][p]
                g=pipe.predict(np.asarray([r["x"] for r in sample]))
                evaluated=[]
                for r,pred in zip(sample,g):
                    l=r["labels"][h]
                    expected=predicted_net(pred,r["notional"],side)
                    actual=[net_r(l,r["atr"],c) for c in COSTS]
                    evaluated.append({**r,"label":l,"y":actual,"pred":expected,
                                      "rank":expected[1],"gross":float(l["gross_r"])})
                decisions[p].extend(evaluated)
                result["prediction"][side][p]={str(c):prediction_metrics(
                    [r["y"][i] for r in evaluated],[r["pred"][i] for r in evaluated],base[i])
                    for i,c in enumerate(COSTS)}
        for p,sample in decisions.items():
            days=sorted({utc_day(r["t"]) for r in sample})
            variants={"geometric":[dict(r,rank=.10736509052557568 if r["side"]=="SHORT" else .10465811214624714) for r in sample],
                      "causal_atr_ge_1pct":[dict(r,rank=1/r["notional"]) for r in sample if 1/r["notional"]>=.01],
                      "model_net_positive":[r for r in sample if min(r["pred"])>0]}
            result["finance"][p]={}
            for name,candidates in variants.items():
                stats,actual=portfolio_stats(candidates,days)
                stats["gross_r"]=sum(r["gross"] for r in actual)
                stats["outcomes"]={k:sum(r["label"]["outcome"]==k for r in actual) for k in ("TP","SL","TIMEOUT")}
                result["finance"][p][name]=stats
        report["results"][str(h)]=result
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","dataset","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.dataset,a.output)
