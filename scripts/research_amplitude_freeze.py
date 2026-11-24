"""V3e: freeze the original 240m entrance gate and candidate 3 ATR exit."""
import argparse
import json
import hashlib
from pathlib import Path
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from scripts.research_pre_breakout_dataset import load_raw, label, contiguous
from mexc_scanner.models import D
from collections import Counter
from scripts.research_pre_breakout_model import rows, net_r, FEATURES
from scripts.research_expected_net_return import portfolio_stats, prediction_metrics, utc_day, COSTS, CUT1, CUT2

HORIZONS=(30,60,240)
MAX_LABEL=14460
EMBARGO=14460
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


TARGETS=("1.5","2","3")
FUNDING_RATES=(0.,.0001,.0005)

def barrier(bars,t,a,side,mult,end):
    # Same one-minute delay, 240m cap, conservative OHLC ambiguity and gaps.
    entry_t=t+60
    finish=entry_t+14400
    seq=contiguous(bars,entry_t,finish) if finish<=end else None
    if seq is None:
        return {"outcome":"CENSORED"}
    sign=D(1) if side=="LONG" else D(-1)
    entry=seq[0].open
    stop,target=entry-sign*a,entry+sign*D(mult)*a
    if min(stop,target)<=0:
        return {"outcome":"INVALID_GEOMETRY"}
    outcome,price,exit_t="TIMEOUT",seq[-1].close,seq[-1].end
    for c in seq:
        op=sign*(c.open-entry)/a
        if op<=-1:
            outcome,price,exit_t="SL",c.open,c.ts
            break
        if op>=D(mult):
            outcome,price,exit_t="TP",target,c.ts
            break
        adv=sign*((c.low if sign>0 else c.high)-entry)/a
        fav=sign*((c.high if sign>0 else c.low)-entry)/a
        if adv<=-1:
            outcome,price,exit_t="SL",stop,c.end
            break
        if fav>=D(mult):
            outcome,price,exit_t="TP",target,c.end
            break
    return {"outcome":outcome,"entry_ts":entry_t,"exit_ts":exit_t,"entry":str(entry),
            "exit":str(price),"stop":str(stop),"target":str(target),
            "gross_r":str(sign*(price-entry)/a)}

def funding_charge(l,atr,rate):
    # Hypothetical adverse charge at each 4h UTC boundary, entry < boundary <= exit.
    # Entry notional proxy; not historical funding or actual exchange schedule.
    crossings=int(l["exit_ts"])//14400-int(l["entry_ts"])//14400
    return crossings*rate*float(l["entry"])/atr

def geometry_report(candidates,raw_bars,end,days,base_actual):
    out={}
    for mult in TARGETS:
        sample=[]
        for r in candidates:
            l=barrier(raw_bars[r["symbol"]],r["t"],D(r["atr_exact"]),r["side"],mult,end)
            if l["outcome"] not in ("TP","SL","TIMEOUT"):
                raise ValueError("incomplete or invalid alternate geometry")
            if mult=="1.5":
                for field in ("outcome","entry_ts","exit_ts","entry","exit","stop","target","gross_r"):
                    if str(l[field])!=str(r["label"][field]):
                        raise ValueError("original geometry mismatch "+field)
            sample.append({**r,"label":l,"gross":float(l["gross_r"]),
                           "y":[net_r(l,r["atr"],c) for c in COSTS]})
        stats,actual=portfolio_stats(sample,days)
        k=lambda r:(r["symbol"],r["t"],r["side"])
        index={k(r):r for r in sample}
        paired=[index[k(r)] for r in base_actual]
        stats["gross_r"]=sum(r["gross"] for r in actual)
        stats["outcomes"]=dict(Counter(r["label"]["outcome"] for r in actual))
        stats["funding_sensitivity"]={}
        for rate in FUNDING_RATES:
            charged=[{**r,"y":[v-funding_charge(r["label"],r["atr"],rate) for v in r["y"]]} for r in sample]
            fstats,selected_=portfolio_stats(charged,days)
            if [k(r) for r in selected_]!=[k(r) for r in actual]:
                raise ValueError("funding stress changed frozen selection")
            stats["funding_sensitivity"][str(rate)]=fstats
        stats["paired_original_entries_not_portfolio"]={"n":len(paired),
            "net_r":{str(c):sum(r["y"][i] for r in paired) for i,c in enumerate(COSTS)},
            "outcomes":dict(Counter(r["label"]["outcome"] for r in paired))}
        out[mult]=stats
    return out

def run(raw,dataset,output):
    meta=json.loads((raw/"coverage.json").read_text())
    fs={}
    raw_bars={}
    audit=Counter()
    for symbol,m in meta["symbols"].items():
        bars=load_raw(raw/m["raw_file"],m["sha256_uncompressed"])
        raw_bars[symbol]=bars
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
            fs[(symbol,t)]={"x":x,"notional":notional,"atr":float(f["atr15"]),"atr_exact":f["atr15"]}
    labels={}
    for l in rows(dataset/"labels.csv.gz"):
        h=int(l["horizon"])
        k=(l["symbol"],int(l["asof_utc"]))
        if h in HORIZONS and k in fs and l["outcome"] in ("TP","SL","TIMEOUT"):
            labels.setdefault((*k,l["side"]),{})[h]=l
    data={s:{p:[] for p in PARTS} for s in SIDES}
    for (symbol,t,side),ll in labels.items():
        if set(ll)!={30,60}:
            continue
        f=fs[(symbol,t)]
        bars=raw_bars[symbol]
        for h in (30,60):
            replay=label(bars,t,D(f["atr_exact"]),side,h,meta["end_exclusive"])
            for field in ("outcome","entry_ts","exit_ts","entry","exit","stop","target","gross_r"):
                if str(replay.get(field))!=ll[h][field]:
                    raise ValueError(f"prior label mismatch {symbol} {t} {side} {h} {field}")
            audit[f"verified_{h}"]+=1
        extended=label(bars,t,D(f["atr_exact"]),side,240,meta["end_exclusive"])
        if extended["outcome"] not in ("TP","SL","TIMEOUT"):
            audit["excluded_240"]+=1
            continue
        ll[240]=extended
        for h in (30,60):
            if ll[h]["outcome"]!="TIMEOUT" and (ll[h]["outcome"]!=extended["outcome"] or int(ll[h]["exit_ts"])!=extended["exit_ts"] or D(ll[h]["exit"])!=D(extended["exit"])):
                raise ValueError("earlier barrier exit changed with horizon")
            if ll[h]["outcome"]=="TIMEOUT":
                audit[f"{h}_timeout_to_{extended['outcome']}"]+=1
        data[side][split(t)].append({"symbol":symbol,"side":side,"t":t,**f,"labels":ll})
    report={"type":"V3E_FREEZE_CANDIDATE","label_audit":dict(audit),"horizons":HORIZONS,"cutoffs":[CUT1,CUT2],
            "purge_seconds":MAX_LABEL,"embargo_seconds":EMBARGO,
            "model":"ridge gross R alpha 10; causal notional/ATR cost proxy",
            "features":[*FEATURES,"atr_over_last_closed_price"],"cohort":{},"results":{},
            "limitations":["Post-hoc research on previously inspected dates; no independent test.",
                "Matched evaluable labels exclude missing outcomes; same timestamps per horizon.",
                "Cost prediction uses last closed price, not guaranteed entry; realized costs use actual simulated fills.",
                "Fixed 1 ATR stop and 1.5 ATR TP; higher horizon does not widen price barriers.",
                "Frozen 30m gate preserves candidate scores, but realized occupancy can change executed entries.",
                "Alternative targets are post-hoc diagnostic only; frozen 1.5 ATR gate not retrained.",
                "Funding is hypothetical adverse 4h-boundary stress using entry notional; not actual rates or schedules.",
                "No real execution, historical tick/lot, liquidation or exact PRD replay."]}
    for s in SIDES:
        report["cohort"][s]={p:len(data[s][p]) for p in PARTS}
    frozen={"version":"V3E_240_FIXED_GATE_3ATR","source_run":45446894380,
            "feature_order":[*FEATURES,"atr_over_last_closed_price"],"costs":COSTS,
            "gate":0.,"forecast_target_atr":1.5,"execution_target_atr":3.,"stop_atr":1.,
            "horizon_min":240,"entry_delay_sec":60,"cutoffs":[CUT1,CUT2],"alpha":ALPHA,
            "symbols":sorted(raw_bars),"models":{},"window_start":"2026-12-09T00:00:00Z",
            "window_end_exclusive":"2026-12-23T00:00:00Z"}
    for h in (240,):
        result={"prediction":{},"finance":{}}
        decisions={p:[] for p in PARTS[1:]}
        for side in SIDES:
            train=data[side]["train"]
            y=[float(r["labels"][h]["gross_r"]) for r in train]
            base=[float(np.mean([net_r(r["labels"][h],r["atr"],c) for r in train])) for c in COSTS]
            pipe=make_pipeline(SimpleImputer(strategy="median",keep_empty_features=True),
                               StandardScaler(),Ridge(alpha=ALPHA))
            pipe.fit(np.asarray([r["x"] for r in train]),y)
            if len(train)!=28210:
                raise ValueError("training count differs from V3c")
            imputer,scaler,ridge=[obj for _,obj in pipe.steps]
            frozen["models"][side]={"train_n":len(train),"median":imputer.statistics_.tolist(),
                "mean":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
                "coef":ridge.coef_.tolist(),"intercept":float(ridge.intercept_),"constant_net_r":base}
            result["prediction"][side]={}
            for p in PARTS[1:]:
                sample=data[side][p]
                X=np.asarray([r["x"] for r in sample])
                g=pipe.predict(X)
                fm=frozen["models"][side]
                reconstructed=((np.where(np.isnan(X),fm["median"],X)-fm["mean"])/fm["scale"])@np.asarray(fm["coef"])+fm["intercept"]
                if float(np.max(np.abs(g-reconstructed)))>1e-10:
                    raise ValueError("exported coefficients do not reproduce predictions")
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
                if name=="model_net_positive":
                    expected_n,expected_r=(24,1.5554463317562268) if p=="validation" else (60,-.2691497558629614)
                    if len(actual)!=expected_n or abs(stats["0.0016"]["total_net_r"]-expected_r)>1e-8:
                        raise ValueError("V3c fixed gate not reproduced")
                    geometry=geometry_report(candidates,raw_bars,meta["end_exclusive"],days,actual)
                    candidate=geometry["3"]
                    n,r=(18,.6562278018556729) if p=="validation" else (39,5.899315915626597)
                    if candidate["trades"]!=n or abs(candidate["0.0016"]["total_net_r"]-r)>1e-8:
                        raise ValueError("V3d candidate not reproduced")
                    result.setdefault("geometry",{})[p]=geometry
        report["results"][str(h)]=result
    output.mkdir(parents=True,exist_ok=True)
    raw_model=json.dumps(frozen,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    (output/"frozen-v3e.json").write_bytes(raw_model)
    report["model_sha256"]=hashlib.sha256(raw_model).hexdigest()
    (output/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False))
    print("FROZEN_V3E_JSON="+raw_model.decode(),flush=True)
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("raw","dataset","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    run(a.raw,a.dataset,a.output)
