"""Prospective V3e replay; frozen scores only, no orders or daily quota."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D
from scripts.research_pre_breakout_coverage import collect,save_raw,SYMBOLS
from scripts.research_pre_breakout_dataset import features
from scripts.research_amplitude_240 import inputs,predicted_net
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_expected_net_return import selected,portfolio_stats,utc_day,COSTS
from scripts.research_pre_breakout_model import FEATURES,net_r

START=int(datetime.fromisoformat("2026-12-09T00:00:00+00:00").timestamp())
END=int(datetime.fromisoformat("2026-12-23T00:00:00+00:00").timestamp())
TAIL=14460
DAY=86400
HASH="7a364216c887f25fb1c0a140da0ac67670476a3ff8c496d023163b07b3747524"
MODEL=Path("config/research/predict-v3e-frozen.json")
LOCAL=ZoneInfo("America/Sao_Paulo")

def load_model():
    raw=MODEL.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=HASH:
        raise ValueError("frozen digest differs")
    m=json.loads(raw)
    if (m["feature_order"]!=[*FEATURES,"atr_over_last_closed_price"]
        or m["horizon_min"]!=240 or m["execution_target_atr"]!=3 or m["stop_atr"]!=1
        or m["forecast_target_atr"]!=1.5 or m["gate"]!=0
        or m["entry_delay_sec"]!=60 or tuple(m["costs"])!=COSTS
        or set(m["symbols"])!=set(SYMBOLS) or set(m["models"])!={"LONG","SHORT"}
        or m["window_start"]!="2026-12-09T00:00:00Z"
        or m["window_end_exclusive"]!="2026-12-23T00:00:00Z"):
        raise ValueError("frozen contract differs")
    return m

def score(x,notional,side,m):
    params=m["models"][side]
    z=float(params["intercept"])
    for v,med,mean,scale,coef in zip(x,params["median"],params["mean"],params["scale"],params["coef"],strict=True):
        v=med if math.isnan(v) else v
        if not math.isfinite(v) or scale<=0:
            raise ValueError("invalid feature")
        z+=(v-mean)/scale*coef
    return predicted_net(z,notional,side)

def require_closed(now):
    if now<END+TAIL+10:
        raise ValueError("reserved window or outcome tail not closed")

def local_day(t):
    return datetime.fromtimestamp(t,LOCAL).date().isoformat()

def frequency(candidates,actual):
    eligible=Counter(local_day(r["t"]) for r in candidates)
    slots=Counter(local_day(t) for t in {r["t"] for r in candidates})
    executed=Counter(local_day(r["t"]) for r in actual)
    days=[]
    d=datetime.fromtimestamp(START,LOCAL).date()
    last=datetime.fromtimestamp(END-1,LOCAL).date()
    while d<=last:
        k=d.isoformat()
        left=int(datetime.combine(d,datetime.min.time(),LOCAL).timestamp())
        right=int(datetime.combine(d+timedelta(days=1),datetime.min.time(),LOCAL).timestamp())
        days.append({"date":k,"complete":START<=left and right<=END,
                     "eligible_directional":eligible[k],"eligible_decision_slots":slots[k],"executed":executed[k]})
        d+=timedelta(days=1)
    full=[d["executed"] for d in days if d["complete"]]
    return {"timezone":"America/Sao_Paulo","daily":days,"complete_days":len(full),
            "zero":sum(n==0 for n in full),"one":sum(n==1 for n in full),
            "two_or_more":sum(n>=2 for n in full),"two_to_four":sum(2<=n<=4 for n in full),
            "above_four":sum(n>4 for n in full),"mean":float(np.mean(full)),"median":float(np.median(full)),
            "target_met_every_complete_day":all(n>=2 for n in full)}

def run(output):
    m=load_model()
    client=MexcClient()
    require_closed(client.server_time())
    output.mkdir(parents=True,exist_ok=True)
    left,right=START-2*DAY,END+TAIL
    bars={}
    coverage={}
    for s in SYMBOLS:
        b,failures,dupes=collect(client,s,left,right)
        if failures or len(b)!=(right-left)//60 or any(t not in b for t in range(left,right,60)):
            raise ValueError("incomplete prospective M1 coverage: "+s)
        bars[s]=b
        coverage[s]={"n":len(b),"duplicates":dupes,"sha256_uncompressed":save_raw(output/(s+".jsonl.gz"),b)}
    candidates=[]
    evaluated=0
    for t in range(START,END,300):
        for symbol,b in bars.items():
            f=features(b,bars["BTC_USDT"],t)
            if f is None:
                raise ValueError("unexpected missing causal features")
            if not f["inside_prior_range"]:
                continue
            x,notional=inputs(f,b[t-60].close)
            for side in ("LONG","SHORT"):
                evaluated+=1
                p=score(x,notional,side,m)
                if min(p)<=0:
                    continue
                a=D(f["atr15"])
                l=barrier(b,t,a,side,"3",right)
                if l["outcome"] not in ("TP","SL","TIMEOUT"):
                    raise ValueError("invalid prospective label")
                candidates.append({"t":t,"symbol":symbol,"side":side,"rank":p[1],"pred":p,
                                   "atr":float(a),"label":l,"y":[net_r(l,float(a),c) for c in COSTS]})
    days=[utc_day(t) for t in range(START,END,DAY)]
    finance,actual=portfolio_stats(candidates,days)
    stress=[{**r,"y":[v-funding_charge(r["label"],r["atr"],.0005) for v in r["y"]]} for r in candidates]
    stressed,actual_stress=portfolio_stats(stress,days)
    key=lambda r:(r["t"],r["symbol"],r["side"])
    if [key(r) for r in actual]!=[key(r) for r in actual_stress]:
        raise ValueError("funding changed selection")
    freq=frequency(candidates,actual)
    base=finance["0.0016"]
    adverse=stressed["0.0024"]
    sufficient=len(actual)>=30 and base["active_days"]>=10
    positive=all(q["mean_r_day_bootstrap_95"] is not None and q["mean_r_day_bootstrap_95"][0]>0 for q in (base,adverse))
    decision="REVIEW_ONLY" if sufficient and positive and freq["target_met_every_complete_day"] else (
        "INCONCLUSIVE_SAMPLE" if not sufficient else "NOT_VALIDATED" if not positive else "FREQUENCY_INADEQUATE")
    result={"type":"V3E_PROSPECTIVE","model_sha256":HASH,"start":START,"end_exclusive":END,
            "coverage":coverage,"evaluated_directional":evaluated,"finance":finance,"adverse_funding":adverse,
            "frequency":freq,"decision":decision,"abstention_net_r":0,
            "limitations":["Prospective offline replay, not live fills or confirmed PRD signals.",
                "Forecast trained for 1.5 ATR exits; actual target 3 ATR.",
                "Hypothetical costs and adverse funding at 4h boundaries; no actual rates, mark prices, ticks, lots or liquidation.",
                "Daily counts based on decision timestamps; partial local dates reported separately.",
                "Small time-block sample; no automatic promotion."]}
    (output/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    with (output/"trades.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["t","symbol","side","outcome","entry_ts","exit_ts","entry","exit","gross_r","net_base_r","net_adverse_r","net_adverse_funding_r"])
        w.writeheader()
        for r,z in zip(actual,actual_stress):
            l=r["label"]
            w.writerow({**{k:r[k] for k in ("t","symbol","side")},**{k:l[k] for k in ("outcome","entry_ts","exit_ts","entry","exit","gross_r")},
                        "net_base_r":r["y"][0],"net_adverse_r":r["y"][1],"net_adverse_funding_r":z["y"][1]})
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--preflight",action="store_true")
    p.add_argument("--output",type=Path,default=Path("reports/predict-v3e-prospective"))
    a=p.parse_args()
    if a.preflight:
        load_model()
        print(json.dumps({"status":"VERIFIED","sha256":HASH,"start":START,"end":END}))
    else:
        run(a.output)
