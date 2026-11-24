"""V6d: separate occurrence and conditional direction on matched V6b data."""
from __future__ import annotations
import argparse,bisect,gzip,hashlib,json
from pathlib import Path
import numpy as np
from scripts.research_event_predictability import event,PARTS,LOOKBACK,align_probabilities,metrics,day_gain,CLASSES
from scripts.research_event_baselines import pipeline,positive,binary_metrics,binary_gain,symbol_prior
from scripts.research_pre_breakout_model import FEATURES
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

def matrices(x,z):
    names=[*FEATURES,"atr_over_last_closed_price"]
    vi=[names.index(k) for k in ("rv15","rv60","rv_ratio","range_atr","atr_over_last_closed_price")]
    return {"price":x,"volatility":x[:,vi],"basis":z[:,:9],"funding":z[:,9:],
            "basis_funding":z,"price_basis":np.column_stack([x,z[:,:9]]),
            "price_funding":np.column_stack([x,z[:,9:]]),"price_all":np.column_stack([x,z])}

def separate(data):
    tr=data["train"]; y=np.asarray(tr["y"]); sy=np.asarray(tr["symbol"])
    train_m=matrices(np.asarray(tr["x"]),np.asarray(tr["z"]))
    report={}
    for task in ("occurrence","direction"):
        mask=np.ones(len(y),dtype=bool) if task=="occurrence" else np.isin(y,("UP","DOWN"))
        yy=(y[mask]!="NONE").astype(int) if task=="occurrence" else (y[mask]=="UP").astype(int)
        pri=float(yy.mean()); sp=symbol_prior(yy,sy[mask])
        models={}
        for name,xx in train_m.items():
            m=pipeline();m.fit(xx[mask],yy);models[name]=m
        report[task]={}
        for part in PARTS[1:]:
            d=data[part]; y0=np.asarray(d["y"]); sy0=np.asarray(d["symbol"])
            keep=np.ones(len(y0),dtype=bool) if task=="occurrence" else np.isin(y0,("UP","DOWN"))
            actual=(y0[keep]!="NONE").astype(int) if task=="occurrence" else (y0[keep]=="UP").astype(int)
            days=np.asarray(d["day"])[keep]; symbols=sy0[keep]
            mm=matrices(np.asarray(d["x"]),np.asarray(d["z"]))
            preds={"constant":np.full(len(actual),pri),"symbol_prior":np.array([sp.get(k,pri) for k in symbols])}
            preds.update({k:positive(m,mm[k][keep]) for k,m in models.items()})
            result={}
            for name,p in preds.items():
                result[name]={"metrics":binary_metrics(actual,p),
                    "gain_vs_price":binary_gain(actual,p,preds["price"],days),
                    "gain_vs_symbol_prior":binary_gain(actual,p,preds["symbol_prior"],days),
                    "by_symbol":{k:binary_metrics(actual[symbols==k],p[symbols==k]) for k in sorted(set(symbols))},
                    "by_day":{k:binary_metrics(actual[days==k],p[days==k]) for k in sorted(set(days))}}
            report[task][part]=result
    return report

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
    report={"type":"V6D_SEPARATE_BASIS_FUNDING","cutoffs":[CUT1,CUT2],"coverage":coverage,
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
    if [len(data[k]["y"]) for k in PARTS]!=[9188,9041,9081]:
        raise ValueError("V6b cohort differs")
    expected={"validation":(.5852628426130428,.47882073094657207),"test":(.6647276489929368,.6432800730332598)}
    for part,(a,b) in expected.items():
        r=report["results"][part]
        if abs(r["price_only"]["metrics"]["event_auc"]-a)>1e-8 or abs(r["basis_funding_only"]["metrics"]["direction_auc"]-b)>1e-8:
            raise ValueError("V6b reference differs")
    report["separate"]=separate(data)
    report["limitations"].extend(["Separate direction trained/evaluated only on realized UP/DOWN events; not an actionable gate or trade hit rate.",
        "Fixed feature groups, no tuning; multiple descriptive comparisons with reused dates."])
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    compact={**report,"separate":{task:{part:{name:{k:v for k,v in z.items() if k not in ("by_symbol","by_day")} for name,z in q.items()} for part,q in p.items()} for task,p in report["separate"].items()}}
    print(json.dumps(compact,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","source","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.raw,a.source,a.output)
