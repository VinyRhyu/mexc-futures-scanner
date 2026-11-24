"""V3 post-hoc audit of frozen trades: separate gross edge from linear costs.
No new model, threshold, filtering, or counterfactual position selection.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scripts.research_pre_breakout_model import rows
from scripts.research_expected_net_return import utc_day, COSTS

def key(r):
    return (r["symbol"],int(r.get("asof_utc",r.get("t"))),r["side"])

def enrich(trade,label,feature):
    if int(trade["exit_ts"])!=int(label["exit_ts"]):
        raise ValueError("exit mismatch")
    entry,exit_,a=float(label["entry"]),float(label["exit"]),float(feature["atr15"])
    gross=float(label["gross_r"])
    turnover=(entry+exit_)/(2*a)
    base,adverse=[gross-c*turnover for c in COSTS]
    if not np.allclose([base,adverse],[float(trade["net_r_base_cost"]),float(trade["net_r_adverse_cost"])],rtol=0,atol=1e-9):
        raise ValueError("cost identity mismatch")
    return {**trade,"gross":gross,"turnover_r":turnover,"base":base,"adverse":adverse,
            "atr_fraction":a/entry,"minutes":(int(label["exit_ts"])-int(label["entry_ts"]))/60,
            "outcome":label["outcome"],"day":utc_day(int(trade["t"]))}

def summarize(sample):
    n=len(sample)
    gross=sum(r["gross"] for r in sample)
    turnover=sum(r["turnover_r"] for r in sample)
    base=sum(r["base"] for r in sample)
    adverse=sum(r["adverse"] for r in sample)
    return {"trades":n,"outcomes":dict(Counter(r["outcome"] for r in sample)),
            "gross_r":gross,"base_cost_r":gross-base,"adverse_cost_r":gross-adverse,
            "net_base_r":base,"net_adverse_r":adverse,
            "mean_gross_r":gross/n if n else None,
            "mean_net_base_r":base/n if n else None,
            "break_even_cost_pct":100*gross/turnover if turnover and gross>0 else None,
            "median_atr_pct":100*float(np.median([r["atr_fraction"] for r in sample])) if n else None,
            "median_duration_min":float(np.median([r["minutes"] for r in sample])) if n else None,
            "gross_positive_fraction":sum(r["gross"]>0 for r in sample)/n if n else None}

def grouped(sample,fn):
    groups=defaultdict(list)
    for r in sample:
        groups[fn(r)].append(r)
    return {k:summarize(v) for k,v in sorted(groups.items())}

def run(dataset,v3,output):
    trades=list(rows(v3/"trades.csv.gz"))
    keys={key(r) for r in trades}
    labels={key(l):l for l in rows(dataset/"labels.csv.gz") if l["horizon"]=="30" and key(l) in keys}
    fkeys={(k[0],k[1]) for k in keys}
    features={(f["symbol"],int(f["asof_utc"])):f for f in rows(dataset/"features.csv.gz")
              if (f["symbol"],int(f["asof_utc"])) in fkeys}
    audited=[enrich(r,labels[key(r)],features[key(r)[:2]]) for r in trades]
    result={"source_run":45442069393,"type":"frozen_trade_cost_attribution",
            "limitations":["Same trades at every cost; no alternative fills or selection.",
                "Break-even cost is retrospective hypothetical, not achievable fee or target.",
                "Subgroups descriptive only; no tuning or inference of independent edge.",
                "ATR, costs and gross R inherit E2 simulation assumptions; no actual funding or liquidation."],
            "partitions":{}}
    for part in ("validation","test"):
        sample=[r for r in audited if r["partition"]==part]
        focus=[r for r in sample if r["strategy"]=="v3_expected_net_positive"]
        if len(focus)!=(91 if part=="validation" else 129):
            raise ValueError("frozen trade count mismatch")
        result["partitions"][part]={"all_strategies":grouped(sample,lambda r:r["strategy"]),
            "v3_by_direction":grouped(focus,lambda r:r["side"]),
            "v3_by_symbol":grouped(focus,lambda r:r["symbol"]),
            "v3_by_day":grouped(focus,lambda r:r["day"]),
            "v3_by_outcome":grouped(focus,lambda r:r["outcome"]),
            "v3_by_atr_pct":grouped(focus,lambda r:"<0.25%" if r["atr_fraction"]<.0025 else
              "0.25-0.5%" if r["atr_fraction"]<.005 else "0.5-1%" if r["atr_fraction"]<.01 else ">=1%")}
    output.mkdir(parents=True,exist_ok=True)
    (output/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("dataset","v3","output"):
        p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    run(a.dataset,a.v3,a.output)
