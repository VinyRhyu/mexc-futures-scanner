"""V7a: outcome-first discovery of interpretable economic patterns."""
from __future__ import annotations
import argparse,json
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeRegressor,export_text
from sklearn.impute import SimpleImputer
from scripts.research_universe_transfer import sources,evaluate,stress_cost
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2,EMBARGO,PARTS,SIDES
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_pre_breakout_model import FEATURES,net_r
from scripts.research_expected_net_return import COSTS,utc_day,prediction_metrics
from mexc_scanner.models import D

LOOKBACK=86400
LEVELS=(.01,.02,.03,.05)
WINDOWS=(5,15,30,60)
NAMES=[*FEATURES,"atr_over_last_closed_price","inside_prior_range"]+[f"{k}_{n}" for n in WINDOWS for k in ("volume_ratio","range_atr","close_location","signed_volume_proxy","path_efficiency")]
MIN_LEAF=500
MIN_CAL=100
MIN_DAYS=3

def pattern_features(bars,t,a):
    # Price/volume OHLC proxy only, not actual aggressor flow.
    out=[]
    for n in WINDOWS:
        seq=[bars[u] for u in range(t-n*60,t,60)]
        prev=[bars[u] for u in range(t-2*n*60,t-n*60,60)]
        if seq[-1].end!=t:
            raise ValueError("unclosed input")
        volume=sum(c.volume for c in seq)
        earlier=sum(c.volume for c in prev)
        hi=max(c.high for c in seq);lo=min(c.low for c in seq)
        signed=sum(c.volume*(D(1) if c.close>c.open else D(-1) if c.close<c.open else D(0)) for c in seq)
        path=sum(abs(c.close-c.open) for c in seq)
        out.extend([float(volume/earlier) if earlier else np.nan,float((hi-lo)/a),
                    float((seq[-1].close-lo)/(hi-lo)) if hi>lo else np.nan,
                    float(signed/volume) if volume else np.nan,
                    float((seq[-1].close-seq[0].open)/path) if path else np.nan])
    return out

def amplitude(bars,t,side):
    # Entry-open reference, future extrema for descriptive labels only.
    entry=bars[t+60].open
    seq=[bars[u] for u in range(t+60,t+MAX_LABEL,60)]
    return float(max(D(0),max(c.high for c in seq)/entry-1)) if side=="LONG" else float(max(D(0),1-min(c.low for c in seq)/entry))

def describe(rs):
    n=len(rs)
    return {"n":n,"days":len({utc_day(r["t"]) for r in rs}),
            "mean_gross_r":float(np.mean([float(r["label"]["gross_r"]) for r in rs])) if n else None,
            "mean_base_r":float(np.mean([r["y"][0] for r in rs])) if n else None,
            "mean_stress_r":float(np.mean([r["tier_net"] for r in rs])) if n else None,
            "positive_stress_fraction":sum(r["tier_net"]>0 for r in rs)/n if n else None,
            "outcomes":dict(Counter(r["label"]["outcome"] for r in rs)),
            "amplitude_counts":{str(p):sum(r["amplitude"]>=p for r in rs) for p in LEVELS}}

def train_phase(t,boundary):
    if t+MAX_LABEL<=boundary:
        return "discovery"
    if t>=boundary+EMBARGO:
        return "calibration"
    return None

def qualifies(fit,cal):
    return fit["n"]>=MIN_LEAF and cal["n"]>=MIN_CAL and cal["days"]>=MIN_DAYS and fit["mean_stress_r"]>0 and cal["mean_stress_r"]>0

def run(raw,g,h,i,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    boundary=((min(times["train"])+int((CUT1-min(times["train"]))*0.7))//900)*900
    data={side:{p:[] for p in ("discovery","calibration","validation","test")} for side in SIDES}
    invalid=Counter()
    for symbol,(p,m) in loc.items():
        bars=btc if symbol=="BTC_USDT" else load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        if any(t not in bars for t in range(start,end,60)):
            raise ValueError("incomplete raw coverage "+symbol)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                phase=train_phase(t,boundary) if part=="train" else part
                if phase is None:
                    continue
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing causal features")
                a=D(f["atr15"])
                x,_=inputs(f,bars[t-60].close)
                x=x+[f["inside_prior_range"]]+pattern_features(bars,t,a)
                for side in SIDES:
                    l=barrier(bars,t,a,side,"3",end)
                    if l["outcome"]=="INVALID_GEOMETRY":
                        invalid[phase]+=1;continue
                    if l["outcome"] not in ("SL","TP","TIMEOUT"):
                        raise ValueError("censored label")
                    fund=funding_charge(l,float(a),.0005)
                    r={"t":t,"symbol":symbol,"side":side,"x":x,"label":l,
                       "amplitude":amplitude(bars,t,side),
                       "y":[net_r(l,float(a),c) for c in COSTS],"funding":fund,
                       "tier_net":net_r(l,float(a),stress_cost(bands.get(symbol)))-fund}
                    data[side][phase].append(r);counts[phase]+=1
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    report={"type":"V7A_OUTCOME_FIRST_PATTERNS","cutoffs":[boundary,CUT1,CUT2],"features":NAMES,
            "settings":{"depth":3,"minimum_discovery_leaf":MIN_LEAF,"minimum_calibration_leaf":MIN_CAL,"minimum_calibration_days":MIN_DAYS},
            "invalid_geometry":dict(invalid),"sides":{},"portfolios":{},
            "limitations":["Same previously inspected dates, exploratory only; no independent evidence.",
                "Full grid including outside prior range, outcomes on both sides including failures; amplitude after entry does not imply TP before SL.",
                "Fixed shallow regression trees fit only discovery block to adverse net R, separate sides. Calibration block independently gates leaves with positive mean adverse net R. No tuning using validation/test.",
                "One-minute latency, 240min from fill, SL1 ATR TP3 ATR, adverse hypothetical costs and funding; no actual liquidation/ticks/fills.",
                "OHLC signed volume proxy is not CVD. Overlapping rows and correlated symbols, calibration mean positivity not statistical proof.",
                "Three trades maximum per Sao Paulo day, no forced minimum. Scores are calibration leaf means, not calibrated trade probabilities."]}
    eligible={p:[] for p in PARTS[1:]}
    for side,parts in data.items():
        fit=parts["discovery"];cal=parts["calibration"]
        imputer=SimpleImputer(strategy="median",keep_empty_features=True)
        X=imputer.fit_transform(np.array([r["x"] for r in fit]))
        y=np.array([r["tier_net"] for r in fit])
        tree=DecisionTreeRegressor(max_depth=3,min_samples_leaf=MIN_LEAF,random_state=20261124)
        tree.fit(X,y)
        leaf={}
        for phase,rs in parts.items():
            lx=tree.apply(imputer.transform(np.asarray([r["x"] for r in rs])))
            for r,k in zip(rs,lx):
                leaf.setdefault(int(k),{}).setdefault(phase,[]).append(r)
        leaves={}
        accepted={}
        for k,ph in sorted(leaf.items()):
            stats={p:describe(ph.get(p,[])) for p in parts}
            ok=qualifies(stats["discovery"],stats["calibration"])
            leaves[str(k)]={"accepted":ok,"statistics":stats}
            if ok:
                accepted[k]=stats["calibration"]["mean_stress_r"]
        result={"cohorts":{p:describe(rs) for p,rs in parts.items()},
                "rules":export_text(tree,feature_names=NAMES,decimals=6),"leaves":leaves,"accepted_leaves":accepted,"prediction":{}}
        prior=float(np.mean([r["tier_net"] for r in cal]))
        for p in PARTS[1:]:
            rs=parts[p]
            xx=imputer.transform(np.asarray([r["x"] for r in rs]))
            ids=tree.apply(xx)
            pred=tree.predict(xx)
            result["prediction"][p]=prediction_metrics([r["tier_net"] for r in rs],pred,prior)
            for r,k in zip(rs,ids):
                if int(k) in accepted:
                    eligible[p].append({**r,"rank":accepted[int(k)],"leaf":int(k)})
        report["sides"][side]=result
    for p in PARTS[1:]:
        report["portfolios"][p]={}
        for side in ("BOTH",*SIDES):
            rs=[r for r in eligible[p] if side=="BOTH" or r["side"]==side]
            report["portfolios"][p][side]={"eligible":describe(rs),"cap3":evaluate(rs,times[p],3)}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","g","h","i","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.raw,a.g,a.h,a.i,a.output)
