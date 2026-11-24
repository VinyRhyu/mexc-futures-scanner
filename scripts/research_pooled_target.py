"""V4a: train pooled model on all 52 assets, directly on 3 ATR exit, fixed chronological splits."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from scripts.research_universe_transfer import sources,evaluate,stress_cost
from scripts.research_pre_breakout_dataset import load_raw,features,WARM
from scripts.research_v3e_prospective import load_model,score,HASH
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_expected_net_return import COSTS,prediction_metrics
from scripts.research_pre_breakout_model import net_r
from mexc_scanner.models import D

ALPHA=10.
SIDES=("LONG","SHORT")
PARTS=("train","validation","test")

def expected(gross,notional,side,cost):
    g=min(float(gross),3.)
    sign=1 if side=="LONG" else -1
    return g-cost*max(0.,notional+sign*g/2.)

def run(raw,g,h,i,output):
    old=load_model()
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    times={part:[t for t in range((start+WARM+899)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end] for part in PARTS}
    # 15-minute training subsampling only, deterministic before outcomes; every 5min validation/test.
    times["train"]=[t for t in times["train"] if t%900==0]
    training={side:{"x":[],"y":[]} for side in SIDES}
    evaluation={side:{p:[] for p in PARTS[1:]} for side in SIDES}
    coverage={}
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("missing candles "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing causal features "+symbol)
                if not f["inside_prior_range"]:
                    continue
                x,notional=inputs(f,bars[t-60].close)
                a=D(f["atr15"])
                for side in SIDES:
                    l=barrier(bars,t,a,side,"3",end)
                    if l["outcome"]=="INVALID_GEOMETRY":
                        counts[part+"_invalid"]+=1
                        continue
                    if l["outcome"] not in ("TP","SL","TIMEOUT"):
                        raise ValueError("unexpected censored label")
                    counts[part+"_valid"]+=1
                    gross=float(l["gross_r"])
                    if part=="train":
                        training[side]["x"].append(x)
                        training[side]["y"].append(gross)
                        continue
                    atr=float(a)
                    fund=funding_charge(l,atr,.0005)
                    tier=stress_cost(bands.get(symbol))
                    evaluation[side][part].append({"t":t,"symbol":symbol,"side":side,
                        "x":x,"notional":notional,"label":l,"gross":gross,
                        "y":[net_r(l,atr,c) for c in COSTS],"funding":fund,
                        "tier_net":net_r(l,atr,tier)-fund,"tier_cost":tier,
                        "old_pred":score(x,notional,side,old)})
        coverage[symbol]=dict(counts)
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    report={"type":"V4A_POOLED_TARGET3","reference_model_sha256":HASH,
        "cutoffs":[CUT1,CUT2],"training_step_sec":900,"evaluation_step_sec":300,
        "alpha":ALPHA,"coverage":coverage,"training":{},"prediction":{},"results":{},
        "limitations":["Already inspected historical dates; not independent temporal validation.",
            "All 52 selected using historical coverage and current catalog; survivor/liquidity selection bias.",
            "Training uses 15-minute grid; evaluation uses original 5-minute grid.",
            "Funding stress and tier fees are hypothetical, not actual execution.",
            "Forecast targets gross realized R for 3 ATR, cost deducted using causal notional proxy.",
            "No funding in gate; stress only after selection; no hyperparameter tuning or PRD changes."]}
    candidates={p:{"frozen_6":[],"frozen_52":[],"pooled_common":[],"pooled_tier":[]} for p in PARTS[1:]}
    for side in SIDES:
        train=training[side]
        model=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),StandardScaler(),Ridge(alpha=ALPHA))
        model.fit(np.asarray(train["x"]),np.asarray(train["y"]))
        baseline=float(np.mean(train["y"]))
        report["training"][side]={"n":len(train["y"]),"mean_gross_r":baseline}
        report["prediction"][side]={}
        for part,rows in evaluation[side].items():
            predictions=model.predict(np.asarray([r["x"] for r in rows]))
            report["prediction"][side][part]=prediction_metrics([r["gross"] for r in rows],predictions.tolist(),baseline)
            for r,gross in zip(rows,predictions):
                oldp=r["old_pred"]
                if min(oldp)>0:
                    c={**r,"rank":oldp[1]}
                    candidates[part]["frozen_52"].append(c)
                    if r["symbol"] in groups["6"]:
                        candidates[part]["frozen_6"].append(c)
                base=expected(gross,r["notional"],side,COSTS[0])
                common=expected(gross,r["notional"],side,COSTS[1])
                tier=expected(gross,r["notional"],side,r["tier_cost"])
                if min(base,common)>0:
                    candidates[part]["pooled_common"].append({**r,"rank":common})
                if min(base,tier)>0:
                    candidates[part]["pooled_tier"].append({**r,"rank":tier})
    for part,tt in ((p,times[p]) for p in PARTS[1:]):
        report["results"][part]={name:{"cap3":evaluate(v,tt,3),"uncapped":evaluate(v,tt,None)}
                                  for name,v in candidates[part].items()}
        # Match previously verified comparator exactly, including full portfolio selection.
        checks={"validation":{"frozen_6":(12,1.6526712730962987),"frozen_52":(18,4.866561273825133)},
                "test":{"frozen_6":(16,4.756236536451358),"frozen_52":(18,-14.264460103453345)}}
        for key,(n,v) in checks[part].items():
            q=report["results"][part][key]["cap3"]["finance"]
            if q["trades"]!=n or abs(q["0.0016"]["total_net_r"]-v)>1e-8:
                raise ValueError("frozen comparator mismatch: "+part+" "+key)
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("raw","g","h","i","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.g,a.h,a.i,a.output)
