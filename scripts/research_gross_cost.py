"""V7c: matched gross-path prediction separated from causal cost estimation."""
from __future__ import annotations
import argparse,gzip,hashlib,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeRegressor,export_text
from sklearn.impute import SimpleImputer
from scripts.research_outcome_patterns import (LOOKBACK,NAMES,MIN_LEAF,MIN_CAL,MIN_DAYS,pattern_features,
    amplitude,describe,train_phase,qualifies)
from scripts.research_universe_transfer import sources,evaluate,stress_cost
from scripts.research_pre_breakout_dataset import load_raw,features
from scripts.research_amplitude_240 import inputs,split,MAX_LABEL,CUT1,CUT2,PARTS,SIDES
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_pre_breakout_model import net_r
from scripts.research_expected_net_return import COSTS,utc_day,prediction_metrics
from mexc_scanner.models import D

SYMBOLS=("ETH_USDT","SOL_USDT","LINK_USDT","HYPE_USDT","ORCA_USDT")
LAGS=(900,1800)
EXTRA=["oi_log_change_15m","oi_log_change_60m","lsr_taker_log1p","lsr_account_log1p",
       "top_lsr_size_log1p","top_lsr_account_log1p","taker_size_imbalance",
       "long_liq_per_oi","short_liq_per_oi"]
REQUIRED=("open_interest","lsr_taker","lsr_account","top_lsr_size","top_lsr_account",
          "long_taker_size","short_taker_size","long_liq_size","short_liq_size")

def load_gate(root,meta,symbol,start,end):
    m=meta["symbols"][symbol]
    if m["errors"] or m["conflicts"] or m["matched"]["pct"]!=100 or m["requested"]["pct"]!=100:
        raise ValueError("unqualified coverage "+symbol)
    c=m["catalog_fields"]
    if c["name"]!=symbol or c["type"]!="direct" or c["in_delisting"] or D(c["quanto_multiplier"])<=0:
        raise ValueError("current contract mismatch")
    blob=gzip.decompress((root/m["file"]).read_bytes())
    if hashlib.sha256(blob).hexdigest()!=m["sha256_uncompressed"]:
        raise ValueError("Gate checksum mismatch")
    rows={int(k):v for k,v in json.loads(blob).items()}
    left=(start+299)//300*300
    for t in range(left,end,300):
        r=rows[t]
        if any(k not in r for k in REQUIRED):
            raise ValueError("missing required field "+symbol)
    return rows

def gate_features(rows,t,lag):
    if lag not in LAGS or t%300:
        raise ValueError("invalid causal lag")
    k=t-lag
    if any(u not in rows for u in (k,k-900,k-3600)):
        return None
    r=rows[k]
    try:
        vals=[float(r[f]) for f in REQUIRED]
        oi,lt,la,ts,ta,buy,sell,ll,sl=vals
        prev=[float(rows[k-n]["open_interest"]) for n in (900,3600)]
    except (KeyError,ValueError,TypeError):
        return None
    if not all(math.isfinite(x) and x>=0 for x in vals+prev) or min(oi,*prev)<=0:
        return None
    # Ratios and quantities are exchange-local. No inference of net market OI direction.
    return [math.log(oi/prev[0]),math.log(oi/prev[1]),math.log1p(lt),math.log1p(la),
            math.log1p(ts),math.log1p(ta),(buy-sell)/(buy+sell) if buy+sell else 0.,
            ll/oi,sl/oi]

def fit_variant(data,times,name):
    index={"price_only":None,"gate_lag15":900,"gate_lag30":1800}[name]
    names=NAMES if index is None else NAMES+EXTRA
    def matrix(rs):
        return np.asarray([r["x"] if index is None else r["x"]+r["extra"][index] for r in rs])
    result={"sides":{},"portfolios":{}}
    eligible={p:[] for p in PARTS[1:]}
    for side,parts in data.items():
        fit=parts["discovery"];cal=parts["calibration"]
        imputer=SimpleImputer(strategy="median",keep_empty_features=True)
        X=imputer.fit_transform(matrix(fit))
        y=np.array([r["tier_net"] for r in fit])
        tree=DecisionTreeRegressor(max_depth=3,min_samples_leaf=MIN_LEAF,random_state=20261124)
        tree.fit(X,y)
        leaf={}
        for phase,rs in parts.items():
            lx=tree.apply(imputer.transform(matrix(rs)))
            for r,k in zip(rs,lx):
                leaf.setdefault(int(k),{}).setdefault(phase,[]).append(r)
        leaves={};accepted={}
        for k,ph in sorted(leaf.items()):
            stats={p:describe(ph.get(p,[])) for p in parts}
            ok=qualifies(stats["discovery"],stats["calibration"])
            leaves[str(k)]={"accepted":ok,"statistics":stats}
            if ok:
                accepted[k]=stats["calibration"]["mean_stress_r"]
        q={"rules":export_text(tree,feature_names=names,decimals=6),"leaves":leaves,
           "accepted_leaves":accepted,"prediction":{}}
        prior=float(np.mean([r["tier_net"] for r in cal]))
        for p in PARTS[1:]:
            rs=parts[p]
            xx=imputer.transform(matrix(rs))
            ids=tree.apply(xx);pred=tree.predict(xx)
            q["prediction"][p]=prediction_metrics([r["tier_net"] for r in rs],pred,prior)
            for r,k in zip(rs,ids):
                if int(k) in accepted:
                    eligible[p].append({**r,"rank":accepted[int(k)],"leaf":int(k)})
        result["sides"][side]=q
    for p in PARTS[1:]:
        result["portfolios"][p]={}
        for side in ("BOTH",*SIDES):
            rs=[r for r in eligible[p] if side=="BOTH" or r["side"]==side]
            result["portfolios"][p][side]={"eligible":describe(rs),"cap3":evaluate(rs,times[p],3)}
    return result

def expected_net(gross,notional,side,rate):
    # Only last closed price/ATR, fitted gross estimate, fixed rate and side.
    # One adverse funding boundary reserved for a holding window of <=240m.
    g=min(3.,float(gross))
    if notional<=0 or rate<0 or side not in SIDES or not math.isfinite(g+notional+rate):
        raise ValueError("invalid prediction geometry")
    turn=max(0.,notional+(g/2 if side=="LONG" else -g/2))
    return g-rate*turn-.0005*notional

def decomposed(data,times,name):
    index={"price_only":None,"gate_lag15":900,"gate_lag30":1800}[name]
    names=NAMES if index is None else NAMES+EXTRA
    def matrix(rs):
        return np.asarray([r["x"] if index is None else r["x"]+r["extra"][index] for r in rs])
    result={"sides":{},"portfolios":{}}
    eligible={p:[] for p in PARTS[1:]}
    for side,parts in data.items():
        fit=parts["discovery"];cal=parts["calibration"]
        imputer=SimpleImputer(strategy="median",keep_empty_features=True)
        X=imputer.fit_transform(matrix(fit))
        tree=DecisionTreeRegressor(max_depth=3,min_samples_leaf=MIN_LEAF,random_state=20261124)
        tree.fit(X,np.asarray([float(r["label"]["gross_r"]) for r in fit]))
        leaf={}; all_predictions={}
        for phase,rs in parts.items():
            xx=imputer.transform(matrix(rs))
            ids=tree.apply(xx);gross=tree.predict(xx)
            net=[expected_net(g,r["notional"],side,r["rate"]) for r,g in zip(rs,gross)]
            all_predictions[phase]=(ids,gross,net)
            for r,k,p in zip(rs,ids,net):
                # Estimate strictly from features and tree. Outcome used only for diagnostics/gating historical blocks.
                q=leaf.setdefault(int(k),{}).setdefault(phase,{"all":[],"positive_estimate":[]})
                q["all"].append(r)
                if p>0:
                    q["positive_estimate"].append(r)
        leaves={};accepted={}
        for k,ph in sorted(leaf.items()):
            stats={p:{z:describe(ph.get(p,{}).get(z,[])) for z in ("all","positive_estimate")} for p in parts}
            ok=qualifies(stats["discovery"]["positive_estimate"],stats["calibration"]["positive_estimate"])
            leaves[str(k)]={"accepted":ok,"statistics":stats}
            if ok:
                accepted[k]=stats["calibration"]["positive_estimate"]["mean_stress_r"]
        q={"rules":export_text(tree,feature_names=names,decimals=6),"leaves":leaves,
           "accepted_leaves":accepted,"prediction":{},"diagnostics":{}}
        gross_prior=float(np.mean([float(r["label"]["gross_r"]) for r in cal]))
        net_prior=float(np.mean([r["tier_net"] for r in cal]))
        for p,rs in parts.items():
            ids,gross,net=all_predictions[p]
            actual_gross=np.asarray([float(r["label"]["gross_r"]) for r in rs])
            actual_net=np.asarray([r["tier_net"] for r in rs])
            predicted_cost=np.asarray(gross)-np.asarray(net)
            actual_cost=actual_gross-actual_net
            positive=[r for r,v in zip(rs,net) if v>0]
            q["diagnostics"][p]={"all":describe(rs),"positive_estimate":describe(positive),
                "cost_mae":float(np.mean(np.abs(predicted_cost-actual_cost))),
                "mean_estimated_cost":float(np.mean(predicted_cost)),
                "mean_actual_cost":float(np.mean(actual_cost)),
                "cost_vs_gross_variance_ratio":float(np.var(actual_cost)/np.var(actual_gross)) if np.var(actual_gross)>0 else None}
            if p in PARTS[1:]:
                q["prediction"][p]={"gross":prediction_metrics(actual_gross,gross,gross_prior),
                    "net":prediction_metrics(actual_net,net,net_prior)}
                for r,k,v in zip(rs,ids,net):
                    if int(k) in accepted and v>0:
                        eligible[p].append({**r,"rank":min(accepted[int(k)],v),"leaf":int(k)})
        result["sides"][side]=q
    for p in PARTS[1:]:
        result["portfolios"][p]={}
        for side in ("BOTH",*SIDES):
            rs=[r for r in eligible[p] if side=="BOTH" or r["side"]==side]
            result["portfolios"][p][side]={"eligible":describe(rs),"cap3":evaluate(rs,times[p],3)}
    return result

def run(raw,g,h,i,gate,output):
    loc,groups,bands,start,end=sources(raw,g,h,i)
    p,m=loc["BTC_USDT"]
    btc=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
    meta=json.loads((gate/"summary.json").read_text())
    if meta["type"]!="V6F_GATE_STATS_COVERAGE" or meta["matched"]!=[(start+299)//300*300,end]:
        raise ValueError("Gate reference mismatch")
    times={part:[t for t in range((start+LOOKBACK+60+299)//300*300,end,300)
                 if split(t)==part and t+MAX_LABEL<=end and (part!="train" or t%900==0)] for part in PARTS}
    boundary=((min(times["train"])+int((CUT1-min(times["train"]))*0.7))//900)*900
    data={side:{p:[] for p in ("discovery","calibration","validation","test")} for side in SIDES}
    coverage={}
    for symbol in SYMBOLS:
        p,m=loc[symbol]
        bars=load_raw(p/m["raw_file"],m["sha256_uncompressed"])
        rows=load_gate(gate,meta,symbol,start,end)
        counts=Counter()
        for part,tt in times.items():
            for t in tt:
                phase=train_phase(t,boundary) if part=="train" else part
                if phase is None:
                    continue
                counts[phase+"_decisions"]+=1
                extras={lag:gate_features(rows,t,lag) for lag in LAGS}
                if any(v is None for v in extras.values()):
                    counts[phase+"_missing"]+=1;continue
                f=features(bars,btc,t)
                if f is None:
                    raise ValueError("missing causal features")
                a=D(f["atr15"])
                x,notional=inputs(f,bars[t-60].close)
                x=x+[f["inside_prior_range"]]+pattern_features(bars,t,a)
                for side in SIDES:
                    l=barrier(bars,t,a,side,"3",end)
                    if l["outcome"]=="INVALID_GEOMETRY":
                        counts[phase+"_invalid"]+=1;continue
                    if l["outcome"] not in ("SL","TP","TIMEOUT"):
                        raise ValueError("censored")
                    fund=funding_charge(l,float(a),.0005)
                    r={"t":t,"symbol":symbol,"side":side,"x":x,"extra":extras,"label":l,
                       "notional":notional,"rate":stress_cost(bands.get(symbol)),
                       "amplitude":amplitude(bars,t,side),"y":[net_r(l,float(a),c) for c in COSTS],
                       "funding":fund,"tier_net":net_r(l,float(a),stress_cost(bands.get(symbol)))-fund}
                    data[side][phase].append(r);counts[phase+"_matched_directional"]+=1
        coverage[symbol]=dict(counts)
        print(json.dumps({"symbol":symbol,"counts":dict(counts)}),flush=True)
    report={"type":"V7C_DECOMPOSED_GROSS_COST","cutoffs":[boundary,CUT1,CUT2],"symbols":SYMBOLS,
            "coverage":coverage,"gate_features":EXTRA,"lags_seconds":LAGS,
            "cohorts":{side:{p:describe(rs) for p,rs in q.items()} for side,q in data.items()},
            "variants":{},"limitations":["Five common assets, identical matched decisions and outcome labels across variants.",
              "Gate historical timestamp is documented only as stat timestamp; assume at most one 5min interval plus delay. 15min primary and 30min sensitivity do not prove publication time or immutability.",
              "BTC excluded due conflicting historical records; MEXC BTC price context retained. Current contract metadata does not establish historical contract identity or rights.",
              "Gate variables are exchange-local, not MEXC OI or CVD; no future backfill. Missing cases removed equally.",
              "Fixed V7a discovery/calibration gates, no tuning, same reused dates, only exploratory results. No production or trading."]}
    for name in ("price_only","gate_lag15","gate_lag30"):
        report["variants"][name]=fit_variant(data,times,name)
    expected={"discovery":5745,"calibration":2335,"validation":8080,"test":8080}
    for side in SIDES:
        if {p:len(rs) for p,rs in data[side].items()}!=expected:
            raise ValueError("V7b cohort mismatch")
    checks={"price_only":(2.277321877944603,2.5283924500588038),
            "gate_lag15":(2.277321877944604,2.563659450067127),
            "gate_lag30":(2.277321877944604,2.5339202600225734)}
    for name,(a,b) in checks.items():
        v=report["variants"][name]
        if abs(v["sides"]["LONG"]["prediction"]["validation"]["mse"]-a)>1e-8 or abs(v["sides"]["SHORT"]["prediction"]["test"]["mse"]-b)>1e-8:
            raise ValueError("V7b direct reference mismatch")
        if any(q["accepted_leaves"] for q in v["sides"].values()):
            raise ValueError("V7b reference accepted leaf mismatch")
    for name in checks:
        report["variants"]["gross_"+name]=decomposed(data,times,name)
    report["limitations"].extend(["Gross trees target realized first-passage gross R, not excursion alone.",
        "Cost proxy uses last closed price/ATR and predicted gross to estimate round-trip notional, plus one adverse 4h funding boundary; actual exit and entry never used in prediction.",
        "Fixed positive predicted net gate; leaf qualifies on positive realized adverse net means and original support in discovery and calibration subsets only. No test tuning.",
        "Same five assets and reused dates; no independent confirmation. Cost and direction are not assumed statistically independent."])
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    compact={**report,"variants":{k:{"sides":{s:{a:b for a,b in q.items() if a!="leaves"} for s,q in v["sides"].items()},"portfolios":v["portfolios"]} for k,v in report["variants"].items()}}
    print(json.dumps(compact,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","g","h","i","gate","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();run(a.raw,a.g,a.h,a.i,a.gate,a.output)
