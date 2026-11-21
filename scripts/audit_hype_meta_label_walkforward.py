"""HYPE triple-barrier WATCH meta-label experiment with causal expanding walk-forward.

No actual orders, chat alerts, or changes to scanner production.
Pre-registration: docs/hype-meta-label-walkforward-preregistered-2026-11-20.md
Methodological inspiration: mlfinpy labeling and time-series CV; this stdlib
implementation is intentionally independent, not a claim to run MLfin.py.
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
from collections import Counter
from datetime import datetime
from statistics import median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, atr_before
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_two_stage_1617 import (
    FAMILIES, watch_at, confirmation, execute,
)
from scripts.audit_hype_watch_crossperiod import PERIODS

SYMBOL="HYPE_USDT"
SEQUENCE=("T","U","V","W0")
EVAL=("U","V","W0")
COST=0.0016
HORIZON_MS=90*60_000
FEATURES=(
    "oriented_ret30_pct","oriented_ret60_pct",
    "oriented_m5_ema9_21_diff_pct",
    "oriented_h1_close_ema20_pct",
    "oriented_h1_ema20_slope3_pct",
    "m5_atr14_pct","ln1p_rvol","oriented_body_atr",
    "oriented_beyond_prev24_atr","h1_alignment",
    "family_turn","family_break","family_drift",
)
MODELS=("BASE","H1_SIMPLE","LOGIT_META_TOP20")
BASELINE_GUARD={
    "U":{"watch":1389,"selected":311,"roi_pct":-36.532},
    "V":{"watch":1358,"selected":339,"roi_pct":-35.793},
    "W0":{"watch":1236,"selected":286,"roi_pct":-18.432},
}


def epoch_ms(s):
    return int(datetime.fromisoformat(s).timestamp()*1000)


def triple_barrier(m,i,side):
    """Label at completed WATCH candle; future used for LABEL ONLY."""
    if i+18>=len(m):
        raise ValueError("Insufficient horizon for label")
    p=float(m[i][4])
    profit=p*(1.0125 if side=="LONG" else .9875)
    bad=p*(.9925 if side=="LONG" else 1.0075)
    for k in range(i+1,i+19):
        hi,lo=float(m[k][2]),float(m[k][3])
        wrong=(lo<=bad if side=="LONG" else hi>=bad)
        right=(hi>=profit if side=="LONG" else lo<=profit)
        if wrong:
            return 0,int(m[k][0])+FIVE_MS,"ADVERSE"
        if right:
            return 1,int(m[k][0])+FIVE_MS,"FAVORABLE"
    return 0,int(m[i+18][0])+FIVE_MS,"TIME"


def watch_features(m,h,i,w,state):
    """Only M5 candles [0..i], H1 with COMPLETION <= WATCH close."""
    t=w["at_ms"]
    hi=bisect.bisect_right(state["he"],t)-1
    if hi<25:
        raise ValueError("Incomplete H1 indicator warmup")
    close=float(m[i][4])
    side=1 if w["side"]=="LONG" else -1
    a=atr_before(m,i)
    if a<=0:
        raise ValueError("ATR invalid")
    hclose=float(h[hi][4])
    h20=state["h20"][hi]
    h20_3=state["h20"][hi-3]
    m9=state["m9"][i]
    m21=state["m21"][i]
    if any(x is None for x in (h20,h20_3,m9,m21)):
        raise ValueError("Missing EMA")
    v=max(0.,float(w["volume_x"]))
    past24=m[i-24:i]
    ext=(max(float(c[2]) for c in past24) if side==1
         else min(float(c[3]) for c in past24))
    beyond=((close-ext)/a if side==1 else (ext-close)/a)
    ret30=side*100*(close/float(m[i-6][4])-1)
    ret60=side*100*(close/float(m[i-12][4])-1)
    hdir=(1 if hclose>h20 else -1)
    body=(float(m[i][4])-float(m[i][1]))*side/a
    feat=(
        ret30,ret60,
        side*100*(m9-m21)/close,
        side*100*(hclose-h20)/hclose,
        side*100*(h20-h20_3)/hclose,
        100*a/close,math.log1p(v),body,beyond,
        1.0 if side==hdir else 0.0,
        float(w["family"]=="TURN"),
        float(w["family"]=="BREAK"),
        float(w["family"]=="DRIFT"),
    )
    if not all(math.isfinite(x) for x in feat):
        raise ValueError("Non-finite feature")
    return feat


def events_for_window(name):
    first,last=PERIODS[name]
    start,end=epoch_ms(first),epoch_ms(last)
    m=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),
              int((end+2*HOUR_MS)/1000))
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(end/1000))
    if any(int(b[0])-int(a[0])!=FIVE_MS for a,b in zip(m,m[1:])):
        raise ValueError("M5 missing")
    if any(int(b[0])-int(a[0])!=HOUR_MS for a,b in zip(h,h[1:])):
        raise ValueError("H1 missing")
    state={
        "m9":ema([float(c[4]) for c in m],9),
        "m21":ema([float(c[4]) for c in m],21),
        "h20":ema([float(c[4]) for c in h],20),
        "he":[int(c[0])+HOUR_MS for c in h],
    }
    family_last={}
    intermediate=[]
    for i in range(45,len(m)):
        now=int(m[i][0])+FIVE_MS
        if now<start:continue
        if now>=end:break
        for w in watch_at(m,i,{"ema9":state["m9"],"ema21":state["m21"]}):
            k=w["family"],w["side"]
            if now-family_last.get(k,-10**18)<30*60_000:
                continue
            family_last[k]=now
            intermediate.append(w)
    intermediate.sort(key=lambda x:(x["at_ms"],FAMILIES.index(x["family"])))
    union=[]
    last_side={}
    for w in intermediate:
        s=w["side"]
        if w["at_ms"]-last_side.get(s,-10**18)<30*60_000:
            continue
        union.append(w)
        last_side[s]=w["at_ms"]
    rows=[]
    for w in union:
        i=w["i"]
        label,label_end,why=triple_barrier(m,i,w["side"])
        feat=watch_features(m,h,i,w,state)
        c=confirmation(m,w,cutoff_ms=end)
        trade=execute(m,c) if c is not None else None
        if trade is not None:
            trade={**trade,"watch_family":w["family"]}
        rows.append({
            "window":name,"at_ms":w["at_ms"],"label":label,
            "label_end_ms":label_end,"label_cause":why,
            "features":feat,"side":w["side"],"family":w["family"],
            "relative_vol":w["volume_x"],"h1_aligned":feat[9]==1.0,
            "trade":trade,
            "watch_key":str(w["at_ms"])+":"+w["side"]+":"+w["family"],
        })
    print("ML_PERIOD_SOURCE "+json.dumps({
        "window":name,"m5_candles":len(m),"h1_candles":len(h),
        "watch_count":len(rows),"label_positive":sum(x["label"] for x in rows),
        "labels":dict(Counter(x["label_cause"] for x in rows)),
        "first_utc":first,"last_utc":last,
    },sort_keys=True),flush=True)
    return rows


def fit_standardizer(train):
    d=len(FEATURES)
    mu=[sum(r["features"][k] for r in train)/len(train) for k in range(d)]
    sd=[math.sqrt(sum((r["features"][k]-mu[k])**2 for r in train)/
                  len(train)) for k in range(d)]
    sd=[v if v>1e-8 else 1. for v in sd]
    return mu,sd


def standardize(feat,mu,sd):
    return tuple(max(-5.,min(5.,(v-m)/s)) for v,m,s in zip(feat,mu,sd))


def sigmoid(z):
    if z>30:return 1.-1e-13
    if z< -30:return 1e-13
    return 1./(1.+math.exp(-z))


def train_logit(train):
    """Fixed L2=.02, LR=.15, 140 fullbatch epochs. Train-only scaling."""
    if len(train)<100:
        raise ValueError("Insufficient train samples")
    mu,sd=fit_standardizer(train)
    x=[standardize(r["features"],mu,sd) for r in train]
    y=[float(r["label"]) for r in train]
    p=max(1e-5,min(1.-1e-5,sum(y)/len(y)))
    b=math.log(p/(1-p))
    coef=[0.]*len(FEATURES)
    lr=.15
    lam=.02
    for epoch in range(140):
        grad_b=0.
        grad=[0.]*len(FEATURES)
        for v,target in zip(x,y):
            pred=sigmoid(b+sum(c*t for c,t in zip(coef,v)))
            delta=pred-target
            grad_b+=delta
            for k,a in enumerate(v):
                grad[k]+=delta*a
        b-=lr*grad_b/len(y)
        for k in range(len(coef)):
            coef[k]-=lr*(grad[k]/len(y)+lam*coef[k])
    return {
        "mu":mu,"sd":sd,"coef":coef,"intercept":b,
        "train_rate":p,"train_n":len(train),
    }


def probability(model,row):
    x=standardize(row["features"],model["mu"],model["sd"])
    return sigmoid(model["intercept"]+
                   sum(c*v for c,v in zip(model["coef"],x)))


def percentile80(values):
    vals=sorted(values)
    if not vals:
        raise ValueError("No probabilities")
    return vals[int(.8*(len(vals)-1))]


def evaluate_watch(rows):
    return {
        "n":len(rows),"positive":sum(r["label"] for r in rows),
        "precision_pct":round(100*sum(r["label"] for r in rows)/len(rows),3)
        if rows else None,
        "alerts_per_day":round(len(rows)/((epoch_ms(PERIODS[rows[0]["window"]][1])-
            epoch_ms(PERIODS[rows[0]["window"]][0]))/(24*3600*1000)),3)
            if rows else 0.,
    }


def financial(rows):
    """Dedup first eligible signal by signal time+side, then one-at-a-time."""
    raw=sorted((r for r in rows if r["trade"] is not None),
               key=lambda z:(z["at_ms"],FAMILIES.index(z["family"])))
    seen=set()
    unique=[]
    for r in raw:
        t=r["trade"]
        key=(t["signal_at"],r["side"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(t)
    p=select_portfolio(unique)
    return {
        "eligible":len(unique),"selected":p["n"],
        "TP":sum(x["result"]=="TP" for x in p["chosen"]),
        "SL":sum(x["result"] in ("SL","AMBIGUOUS_AS_SL") for x in p["chosen"]),
        "TIME":sum(x["result"]=="TIME" for x in p["chosen"]),
        "roi_pct":p["return_pct_at_1pct_risk"],
        "max_dd_pct":p["max_drawdown_pct_at_1pct_risk"],
        "net_R":p["net_R_sum"],
        "first_3":[{"at":t["signal_at"],"result":t["result"],"net_R":t["net_r"]}
                   for t in p["chosen"][:3]],
    }


def fold(train,test,fold_name):
    test_start=epoch_ms(PERIODS[fold_name][0])
    purge_start=test_start-HORIZON_MS
    train=[r for r in train if r["at_ms"]+HORIZON_MS<test_start]
    if not train:
        raise ValueError("Empty purged train")
    if not all(r["at_ms"]+HORIZON_MS<test_start for r in train):
        raise AssertionError("TRAIN label crosses test start")
    model=train_logit(train)
    train_probs=[probability(model,r) for r in train]
    test_probs=[probability(model,r) for r in test]
    threshold=percentile80(train_probs)
    buckets={
        "BASE":list(test),
        "H1_SIMPLE":[r for r in test if r["h1_aligned"] and r["relative_vol"]>=1.2],
        "LOGIT_META_TOP20":[r for r,p in zip(test,test_probs) if p>=threshold],
    }
    baseline_guard=BASELINE_GUARD[fold_name]
    bg=evaluate_watch(buckets["BASE"])
    bfin=financial(buckets["BASE"])
    if bg["n"]!=baseline_guard["watch"] or bfin["selected"]!=baseline_guard["selected"] or bfin["roi_pct"]!=baseline_guard["roi_pct"]:
        raise AssertionError("Baseline mismatch, must stop before interpreting classifiers: "+
                             str({"watch":bg["n"],"fin":bfin,"expected":baseline_guard}))
    p_train=model["train_rate"]
    brier=sum((p-y["label"])**2 for p,y in zip(test_probs,test))/len(test)
    brier_constant=sum((p_train-y["label"])**2 for y in test)/len(test)
    z={
        "test_window":fold_name,"training_windows":sorted(set(r["window"] for r in train)),
        "train_n":len(train),"train_label_rate_pct":round(100*p_train,3),
        "test_n":len(test),"test_label_rate_pct":round(100*sum(r["label"] for r in test)/len(test),3),
        "purge_minutes":90,
        "train_last_event_utc":datetime.fromtimestamp(
            max(r["at_ms"] for r in train)/1000).isoformat(),
        "train_probability_80pct_threshold":round(threshold,5),
        "logit_brier":round(brier,6),"constant_train_rate_brier":round(brier_constant,6),
        "brier_skill_pct":round(100*(1-brier/brier_constant),3),
        "feature_coefficients":{n:round(c,4) for n,c in zip(FEATURES,model["coef"])},
        "models":{},
    }
    for name,items in buckets.items():
        watch=evaluate_watch(items)
        fin=bfin if name=="BASE" else financial(items)
        positives_all=sum(x["label"] for x in test)
        z["models"][name]={
            "watch":watch,"watch_recall_pct":round(
                100*sum(x["label"] for x in items)/positives_all,3)
                if positives_all else None,
            "finance":fin,
            "return_delta_vs_base_pp":round(fin["roi_pct"]-bfin["roi_pct"],3),
            "trades_per_day":round(fin["selected"]/(
                (epoch_ms(PERIODS[fold_name][1])-test_start)/(24*3600*1000)),3),
        }
    return z


def run():
    data={}
    for w in SEQUENCE:
        data[w]=events_for_window(w)
    folds=[]
    for idx,w in enumerate(EVAL,1):
        past=[r for s in SEQUENCE[:idx] for r in data[s]]
        report=fold(past,data[w],w)
        print("ML_META_FOLD "+json.dumps(report,sort_keys=True),flush=True)
        folds.append(report)
    out={"folds":len(folds),"conditions":"HYPE M5 WATCH labels, expanding walk-forward purged 90m",
         "historical_reused":True,"models":{}}
    for m in MODELS:
        segments=[f["models"][m] for f in folds]
        out["models"][m]={
            "watches":sum(x["watch"]["n"] for x in segments),
            "watch_success":sum(x["watch"]["positive"] for x in segments),
            "selected":sum(x["finance"]["selected"] for x in segments),
            "TP":sum(x["finance"]["TP"] for x in segments),
            "SL":sum(x["finance"]["SL"] for x in segments),
            "TIME":sum(x["finance"]["TIME"] for x in segments),
            "positive_folds":sum(x["finance"]["roi_pct"]>0 for x in segments),
            "roi_compound_pct":round(
                100*(math.prod(1+x["finance"]["roi_pct"]/100 for x in segments)-1),3),
            "roi_by_fold":{f["test_window"]:x["finance"]["roi_pct"]
                          for f,x in zip(folds,segments)},
            "mdd_max_any_fold_pct":max(x["finance"]["max_dd_pct"] for x in segments),
            "trades_per_day":round(sum(x["finance"]["selected"] for x in segments)/
                                   sum((epoch_ms(PERIODS[f["test_window"]][1])-
                                        epoch_ms(PERIODS[f["test_window"]][0]))/
                                       (24*3600*1000) for f in folds),3),
        }
    out["logit_brier_positive_folds"]=sum(f["brier_skill_pct"]>0 for f in folds)
    out["data_not_available"]=["historical order-book imbalance","real bid-ask spread",
                               "real fills and slippage","funding charges"]
    out["warnings"]=[
        "Previously inspected prices; expanding walkforward avoids temporal training leakage but not historical model-selection bias.",
        "Labels are ex-post 1.25pct/0.75pct/90min WATCH labels; real trade TP/SL remain different.",
        "Baseline is the frozen original M5 WATCH confirmation strategy, not an account ledger.",
        "Costs assumed taker 0.06pct plus 0.02pct slippage each side; funding omitted.",
        "H1_SIMPLE rule and LOGIT threshold were chosen before results, never fitted on test.",
    ]
    print("ML_META_SUMMARY "+json.dumps(out,sort_keys=True),flush=True)


if __name__=="__main__":
    run()
