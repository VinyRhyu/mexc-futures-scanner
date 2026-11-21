"""HYPE economic meta-label: predict net-R>0 of the ELIGIBLE executed trade.

Historical paper-only; no orders, Telegram, scanner main or production.
Protocol: docs/hype-economic-metalabel-preregistered-2026-11-21.md
"""
from __future__ import annotations
import bisect
import json
import math
from collections import Counter
from datetime import datetime

from scripts.audit_confluence_extended import candles
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, atr_before
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_two_stage_1617 import FAMILIES, watch_at, confirmation, execute
from scripts.audit_hype_meta_label_walkforward import (
    SEQUENCE, EVAL, BASELINE_GUARD, FEATURES as WATCH_FEATURES,
    epoch_ms, train_logit, probability, percentile80, financial,
)
from scripts.audit_hype_watch_crossperiod import PERIODS

SYMBOL="HYPE_USDT"
PURGE_MS=120*60_000
FEATURES=(
    "directional_ret30_pct",
    "directional_ret60_pct",
    "directional_m5_ema9_minus_ema21_pct",
    "directional_h1_close_minus_ema20_pct",
    "atr14_pct",
    "log1p_confirm_rvol",
    "directional_confirm_body_over_atr",
    "directional_beyond_24_m5_extreme_over_atr",
    "signal_close_to_stop_pct",
    "watch_to_confirm_minutes",
    "h1_aligned",
    "family_turn",
    "family_break",
)
if len(FEATURES)!=len(WATCH_FEATURES):
    raise AssertionError("Logistic helper assumes feature vector length 13")
MODELS=("ALL_ELIGIBLE","H1_VOL_SIMPLE","LOGIT_TOP20_TRAIN")


def features_at_confirmation(m,h,ind,confirm,watch):
    """Decision features exist by signal M5 close, before next candle open."""
    i=confirm["signal_index"]
    if i<45:
        raise ValueError("M5 warmup insufficient")
    t=epoch_ms(confirm["signal_at"])
    if t!=int(m[i][0])+FIVE_MS:
        raise AssertionError("Confirmation timestamp inconsistent")
    hi=bisect.bisect_right(ind["he"],t)-1
    if hi<25:
        raise ValueError("H1 warmup insufficient")
    side=1 if confirm["side"]=="LONG" else -1
    close=float(m[i][4])
    a=atr_before(m,i)
    if a<=0:raise ValueError("Nonpositive ATR")
    hcl=float(h[hi][4])
    hma=ind["h20"][hi]
    if hma is None or ind["m9"][i] is None or ind["m21"][i] is None:
        raise ValueError("Missing EMA")
    trend=side*(hcl-hma)
    stop=float(confirm["stop_raw"])
    dist=(close-stop if side==1 else stop-close)
    if dist<=0:
        raise ValueError("Stop invalid relative to confirmed close")
    past=m[i-24:i]
    level=(max(float(x[2]) for x in past) if side==1
           else min(float(x[3]) for x in past))
    breakthrough=side*(close-level)/a
    rvol=max(0.,float(confirm["relative_quote_volume"]))
    vals=(
        side*100*(close/float(m[i-6][4])-1),
        side*100*(close/float(m[i-12][4])-1),
        side*100*(ind["m9"][i]-ind["m21"][i])/close,
        side*100*(hcl-hma)/hcl,
        100*a/close,
        math.log1p(rvol),
        side*(float(m[i][4])-float(m[i][1]))/a,
        breakthrough,
        100*dist/close,
        (t-watch["at_ms"])/(60*1000),
        float(trend>0),
        float(watch["family"]=="TURN"),
        float(watch["family"]=="BREAK"),
    )
    if not all(math.isfinite(v) for v in vals):
        raise ValueError("Non-finite econ feature")
    return vals


def eligible_rows(name):
    first,last=PERIODS[name]
    start,end=epoch_ms(first),epoch_ms(last)
    m=candles(SYMBOL,"Min5",int((start-120*FIVE_MS)/1000),
              int((end+2*HOUR_MS)/1000))
    h=candles(SYMBOL,"Min60",int((start-160*HOUR_MS)/1000),int(end/1000))
    if any(int(b[0])-int(a[0])!=FIVE_MS for a,b in zip(m,m[1:])):
        raise ValueError("Incomplete M5")
    if any(int(b[0])-int(a[0])!=HOUR_MS for a,b in zip(h,h[1:])):
        raise ValueError("Incomplete H1")
    ind={
        "m9":ema([float(x[4]) for x in m],9),
        "m21":ema([float(x[4]) for x in m],21),
        "h20":ema([float(x[4]) for x in h],20),
        "he":[int(x[0])+HOUR_MS for x in h],
    }
    watches=[]
    family_last={}
    for i in range(45,len(m)):
        t=int(m[i][0])+FIVE_MS
        if t<start:continue
        if t>=end:break
        for w in watch_at(m,i,{"ema9":ind["m9"],"ema21":ind["m21"]}):
            key=(w["family"],w["side"])
            if t-family_last.get(key,-10**18)<30*60_000:continue
            family_last[key]=t
            watches.append(w)
    watches.sort(key=lambda x:(x["at_ms"],FAMILIES.index(x["family"])))
    union=[]
    last_side={}
    for w in watches:
        t=w["at_ms"]
        if t-last_side.get(w["side"],-10**18)<30*60_000:continue
        union.append(w)
        last_side[w["side"]]=t

    rows=[]
    seen=set()
    status=Counter()
    for w in union:
        c=confirmation(m,w,cutoff_ms=end)
        if c is None:
            status["no_confirmation"]+=1
            continue
        status["confirmed"]+=1
        t=execute(m,c)
        if t is None:
            status["risk_rejected"]+=1
            continue
        dedup=(t["signal_at"],t["side"])
        if dedup in seen:
            status["duplicate_confirm"]+=1
            continue
        seen.add(dedup)
        feats=features_at_confirmation(m,h,ind,c,w)
        t={**t,"watch_family":w["family"]}
        rows.append({
            "window":name,"at_ms":w["at_ms"],
            "signal_ms":epoch_ms(c["signal_at"]),
            "label_end_ms":epoch_ms(t["exit_at"])+FIVE_MS,
            "features":feats,
            "label":int(t["net_r"]>0),
            "net_r":t["net_r"],
            "side":t["side"],"family":w["family"],
            "relative_vol":c["relative_quote_volume"],
            "h1_aligned":bool(feats[10]),
            "trade":t,
        })
        status["eligible_unique"]+=1
    rows.sort(key=lambda r:(r["signal_ms"],r["at_ms"]))
    print("ECON_META_SOURCE "+json.dumps({
        "period":name,"m5":len(m),"h1":len(h),
        "watches":len(union),"eligible":len(rows),
        "positive_net_R":sum(x["label"] for x in rows),
        "stage":dict(status),
        "mean_net_R_all_eligible":round(sum(x["net_r"] for x in rows)/len(rows),5),
        "source":"MEXC closed 5m/1h candles, NOT actual fills",
    },sort_keys=True),flush=True)
    return rows,len(union)


def result(rows):
    # The financial() helper follows EXACT frozen M5 executor selection.
    # Returns only paper portfolio trades, 1 position at a time.
    f=financial(rows)
    n=len(rows)
    positives=sum(x["label"] for x in rows)
    return {
        "eligible_events":n,
        "economic_label_precision_pct":round(100*positives/n,3) if n else None,
        "economic_label_positive_events":positives,
        "mean_net_R_all_eligible":round(sum(x["net_r"] for x in rows)/n,5) if n else None,
        "portfolio":f,
    }


def run_fold(train,test,test_name,test_watches):
    start=epoch_ms(PERIODS[test_name][0])
    train=[r for r in train
           if r["label_end_ms"]+PURGE_MS<start]
    if not train:
        raise ValueError("Empty eligible training set")
    if any(r["label_end_ms"]+PURGE_MS>=start for r in train):
        raise AssertionError("Purge failed")
    model=train_logit(train)
    probs_train=[probability(model,r) for r in train]
    probs_test=[probability(model,r) for r in test]
    threshold=percentile80(probs_train)

    buckets={
        "ALL_ELIGIBLE":test,
        "H1_VOL_SIMPLE":[r for r in test
                         if r["h1_aligned"] and r["relative_vol"]>=1.2],
        "LOGIT_TOP20_TRAIN":[r for r,p in zip(test,probs_test)
                             if p>=threshold],
    }
    baseline=result(test)
    guard=BASELINE_GUARD[test_name]
    if (test_watches!=guard["watch"] or
        baseline["portfolio"]["selected"]!=guard["selected"] or
        baseline["portfolio"]["roi_pct"]!=guard["roi_pct"]):
        raise AssertionError("BASELINE REGRESSION mismatch: "+
                             str({"name":test_name,"watches":test_watches,
                                  "baseline":baseline["portfolio"],
                                  "expected":guard}))
    overall_positives=sum(r["label"] for r in test)
    train_prevalence=model["train_rate"]
    brier=sum((p-r["label"])**2 for p,r in zip(probs_test,test))/len(test)
    brier_baseline=sum((train_prevalence-r["label"])**2 for r in test)/len(test)
    fold={
        "test":test_name,"train_from":sorted(set(r["window"] for r in train)),
        "train_n":len(train),"train_positive_rate_pct":round(100*train_prevalence,3),
        "test_eligible":len(test),
        "test_positive_rate_pct":round(100*overall_positives/len(test),3),
        "threshold_train_percentile80":round(threshold,5),
        "purge_min_after_label_end":120,
        "brier_logit":round(brier,6),
        "brier_train_constant":round(brier_baseline,6),
        "brier_skill_pct":round(100*(1-brier/brier_baseline),3),
        "feature_coefficients":{
            n:round(c,5) for n,c in zip(FEATURES,model["coef"])
        },
        "models":{},
    }
    days=(epoch_ms(PERIODS[test_name][1])-start)/(24*3600*1000)
    for modelname,items in buckets.items():
        stats=baseline if modelname=="ALL_ELIGIBLE" else result(items)
        positive=sum(r["label"] for r in items)
        fold["models"][modelname]={
            **stats,
            "recall_positive_pct":round(100*positive/overall_positives,3)
                if overall_positives else None,
            "trades_per_day":round(stats["portfolio"]["selected"]/days,3),
            "roi_delta_vs_all_pp":round(
                stats["portfolio"]["roi_pct"]-baseline["portfolio"]["roi_pct"],3),
        }
    print("ECON_META_FOLD "+json.dumps(fold,sort_keys=True),flush=True)
    return fold


def run():
    history={}
    watches={}
    for w in SEQUENCE:
        history[w],watches[w]=eligible_rows(w)
    folds=[]
    for i,w in enumerate(EVAL,1):
        train=[row for name in SEQUENCE[:i] for row in history[name]]
        folds.append(run_fold(train,history[w],w,watches[w]))
    summary={"folds":len(folds),"models":{},
             "historical_already_examined":True,
             "classification_target":"net_R > 0 of actual original eligible trade",
             "warnings":[
                 "No genuinely unseen holdout: research historical and subject to model-selection bias.",
                 "Train examples can overlap economically; purge between train and test by exit plus 120m.",
                 "The 1-bar next open is replayed, not guaranteed fill.",
                 "Profitability label differs from expected R; positive rate can coexist with negative ROI.",
                 "Spread/order book/funding/minimum order/liquidation not modeled.",
                 "No actual orders or Telegram.",
             ]}
    for modelname in MODELS:
        vals=[f["models"][modelname] for f in folds]
        pp=[v["portfolio"] for v in vals]
        rois=[p["roi_pct"] for p in pp]
        summary["models"][modelname]={
            "eligible":sum(v["eligible_events"] for v in vals),
            "selected":sum(p["selected"] for p in pp),
            "economic_positive_events":sum(v["economic_label_positive_events"] for v in vals),
            "TP":sum(p["TP"] for p in pp),
            "SL":sum(p["SL"] for p in pp),
            "TIME":sum(p["TIME"] for p in pp),
            "roi_by_fold":{f["test"]:v["portfolio"]["roi_pct"] for f,v in zip(folds,vals)},
            "positive_folds":sum(x>0 for x in rois),
            "roi_compounded_pct":round(100*(math.prod(1+x/100 for x in rois)-1),3),
            "mdd_max_any_fold_pct":max(p["max_dd_pct"] for p in pp),
            "trades_per_day":round(
                sum(p["selected"] for p in pp) /
                sum((epoch_ms(PERIODS[f["test"]][1])-epoch_ms(PERIODS[f["test"]][0]))/
                    (24*3600*1000) for f in folds),3),
        }
    summary["brier_skill_positive_folds"]=sum(f["brier_skill_pct"]>0 for f in folds)
    print("ECON_META_SUMMARY "+json.dumps(summary,sort_keys=True),flush=True)


if __name__=="__main__":
    run()
