"""V6b: matched MEXC basis/funding incremental predictability, no trading."""
from __future__ import annotations
import argparse,bisect,gzip,hashlib,json
from pathlib import Path
import numpy as np
from scripts.research_event_predictability import event,PARTS,LOOKBACK,align_probabilities,metrics,day_gain,CLASSES
from scripts.research_event_baselines import pipeline,positive,binary_metrics
from scripts.research_pre_breakout_coverage import SYMBOLS
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2
from scripts.research_expected_net_return import utc_day
from mexc_scanner.models import D

PRICE_LAG=600
FUND_LAG=300
EXTRA=[f"{k}_{lag}" for lag in (0,900,3600) for k in ("trade_index","fair_index","trade_fair")]+["funding_last","funding_change","funding_age_hours"]

def read_verified(root,meta):
    data=gzip.decompress((root/meta["file"]).read_bytes())
    if hashlib.sha256(data).hexdigest()!=meta["sha256_uncompressed"]:
        raise ValueError("source checksum mismatch")
    return {int(k):v for k,v in json.loads(data).items()}

def extra(bars,index,fair,funding,ft,t):
    out=[]
    for lag in (0,900,3600):
        k=t-PRICE_LAG-lag
        if k not in index or k not in fair or k+240 not in bars:
            return None
        traded=float(bars[k+240].close)
        i=float(index[k][3]); f=float(fair[k][3])
        if min(traded,i,f)<=0:
            raise ValueError("nonpositive price")
        out.extend([traded/i-1,f/i-1,traded/f-1])
    j=bisect.bisect_right(ft,t-FUND_LAG)-1
    if j<1:
        return None
    now=ft[j]
    a=float(funding[now]["rate"]); b=float(funding[ft[j-1]]["rate"])
    # Fail stale prior settlement rather than carry an unknown gap indefinitely.
    cycle=funding[now]["cycle_hours"]
    if cycle is None or t-now>cycle*3600+FUND_LAG:
        return None
    return out+[a,a-b,(t-now)/3600]

def run(raw,source,output):
    m=json.loads((raw/"coverage.json").read_text())
    v=json.loads((source/"summary.json").read_text())
    if v["type"]!="V6A_PUBLIC_SOURCE_COVERAGE" or set(v["symbols"])!=set(SYMBOLS):
        raise ValueError("unexpected source")
    start,end=v["matched_min5"]
    p=m["symbols"]["BTC_USDT"]
    btc=load_raw(raw/p["raw_file"],p["sha256_uncompressed"])
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    data={p:{"x":[],"z":[],"y":[],"day":[],"symbol":[]} for p in PARTS}
    coverage={}
    for symbol in SYMBOLS:
        p=m["symbols"][symbol]
        bars=btc if symbol=="BTC_USDT" else load_raw(raw/p["raw_file"],p["sha256_uncompressed"])
        q=v["symbols"][symbol]
        index=read_verified(source,q["index_price"]);fair=read_verified(source,q["fair_price"])
        funding=read_verified(source,q["funding"]);ft=sorted(funding)
        counts={}
        for part,tt in times.items():
            n=missing=0
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing M1 features")
                if not f["inside_prior_range"]:
                    continue
                n+=1
                z=extra(bars,index,fair,funding,ft,t)
                if z is None:
                    missing+=1;continue
                anchor=bars[t-60].close
                x,_=inputs(f,anchor)
                y,_=event(bars,t,anchor,D(f["atr15"]))
                d=data[part]
                d["x"].append(x);d["z"].append(z);d["y"].append(y)
                d["day"].append(utc_day(t));d["symbol"].append(symbol)
            counts[part]={"eligible":n,"missing_extra":missing,"matched":n-missing}
        coverage[symbol]=counts
        print(json.dumps({"symbol":symbol,"coverage":counts}),flush=True)
    train=data["train"];x=np.asarray(train["x"]);z=np.asarray(train["z"]);y=np.asarray(train["y"])
    if not {"UP","DOWN","NONE"}<=set(y):
        raise ValueError("missing primary classes")
    prior=np.array([np.mean(y==k) for k in CLASSES])
    models={}
    for name,xx in (("price_only",x),("price_plus_basis_funding",np.column_stack([x,z])),("basis_funding_only",z)):
        model=pipeline();model.fit(xx,y);models[name]=model
    report={"type":"V6B_MATCHED_BASIS_FUNDING","cutoffs":[CUT1,CUT2],"coverage":coverage,
            "feature_order":EXTRA,"price_lag_seconds":PRICE_LAG,"funding_lag_seconds":FUND_LAG,
            "train_n":len(y),"results":{},"limitations":["Six fixed symbols, same previously explored dates; no independent validation.",
                "Historical archive publication lag not recorded; conservative extra 5min after price candle close and funding settlement, not proof of live availability.",
                "Matched complete cases only; missing and stale funding counted, no future backfill.",
                "Model predicts original +/-3 ATR event, not actual trading profit; overlapping observations and few days."]}
    for part in PARTS[1:]:
        d=data[part];xx=np.asarray(d["x"]);zz=np.asarray(d["z"]);yy=np.asarray(d["y"])
        preds={}
        for name,arr in (("price_only",xx),("price_plus_basis_funding",np.column_stack([xx,zz])),("basis_funding_only",zz)):
            model=models[name];preds[name]=align_probabilities(model.predict_proba(arr),list(model.classes_))
        base=preds["price_only"]
        result={"constant":metrics(yy,np.tile(prior,(len(yy),1)))}
        for name,p in preds.items():
            result[name]={"metrics":metrics(yy,p),"gain_vs_price_only":day_gain(yy,p,base,d["day"])}
        report["results"][part]=result
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","source","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.raw,a.source,a.output)
