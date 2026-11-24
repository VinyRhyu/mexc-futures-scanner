"""Parallel, READ-ONLY predictive-probability research over frozen MEXC M1 events.

Research phase 1: estimate P(TP before SL within 4h) using ONLY fields known
at the close of the second confirmed M1 and quote-time financial RR.

This is a *predictive filter on confirmed signals*, NOT yet an early-before-
breakout entry model. Data is previously inspected; results are exploratory.
No authenticated API, live orders, Telegram, config, cron, wallet or state.
No runtime package dependencies.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from pathlib import Path
from statistics import median

WINDOWS = {
    "2026-10-26T00:00:00+00:00": "TRAIN",
    "2026-10-31T00:00:00+00:00": "TRAIN",
    "2026-11-07T00:00:00+00:00": "TRAIN",
    "2026-11-14T00:00:00+00:00": "VALIDATION",
    "2026-11-15T20:00:00+00:00": "TEST",
}
VAL_START = datetime.fromisoformat("2026-11-14T00:00:00+00:00")
TEST_START = datetime.fromisoformat("2026-11-15T20:00:00+00:00")
# Every feature is measured at or before signal confirmation.
FEATURE_NAMES = (
    "projected_net_RR", "log10_turnover24_USDT",
    "M1_volume_vs_prev20", "M1_body_fraction_of_range",
    "M1_close_near_side_fraction", "M1_range_over_M15_ATR",
    "signed_1h_M1_extension_ATR", "signed_4h_M1_extension_ATR",
    "signed_2h_M15_extension_ATR", "h1_alignment", "is_long",
)
NUMERIC_FIELDS = (
    "projected_net_RR", "M1_volume_vs_prev20",
    "M1_body_fraction_of_range", "M1_close_near_side_fraction",
    "M1_range_over_M15_ATR", "signed_1h_M1_extension_ATR",
    "signed_4h_M1_extension_ATR", "signed_2h_M15_extension_ATR",
)
FUTURE_ONLY = {"outcome", "net_R", "net_USDT_fixed_paper", "exit_utc"}
OUTCOMES = {"ALVO", "STOP", "STOP_AMBIGUO", "TIME_4H"}
# Predeclared, not tuned on validation or test.
STEPS = 500
LEARNING_RATE = 0.1
L2 = 0.08
SAFETY_MARGIN_PROB = 0.03
MIN_TRAIN = 50
HORIZON_SECONDS = 4 * 3600


def parse_dt(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone-aware UTC timestamp required")
    result = result.astimezone(timezone.utc)
    if result.isoformat() != value.replace("Z", "+00:00"):
        raise ValueError("input timestamp must be canonical UTC")
    return result


def _finite(value, name):
    try:
        x = float(Decimal(str(value)))
    except (ValueError, ArithmeticError, TypeError) as exc:
        raise ValueError(f"invalid numeric feature {name}") from exc
    if not math.isfinite(x):
        raise ValueError(f"nonfinite numeric feature {name}")
    return x


def pretrade_features(row):
    """Fixed allowlist prevents accidental hindsight through export columns."""
    if FUTURE_ONLY.intersection(FEATURE_NAMES):
        raise AssertionError("feature contract contains future outcome")
    numeric = {k: _finite(row[k], k) for k in NUMERIC_FIELDS}
    turnover = _finite(row["turnover24_USDT"], "turnover24_USDT")
    if turnover <= 0 or numeric["projected_net_RR"] <= 0:
        raise ValueError("nonpositive turnover or financial RR")
    alignment = row["H1_alignment"]
    if alignment not in {"WITH_H1", "AGAINST_H1", "UNKNOWN_H1", "UNKNOWN"}:
        raise ValueError("unknown H1 structure alignment")
    if row["side"] not in {"LONG", "SHORT"}:
        raise ValueError("unknown direction")
    return (
        numeric["projected_net_RR"], math.log10(turnover),
        numeric["M1_volume_vs_prev20"],
        numeric["M1_body_fraction_of_range"],
        numeric["M1_close_near_side_fraction"],
        numeric["M1_range_over_M15_ATR"],
        numeric["signed_1h_M1_extension_ATR"],
        numeric["signed_4h_M1_extension_ATR"],
        numeric["signed_2h_M15_extension_ATR"],
        1.0 if alignment == "WITH_H1" else
        -1.0 if alignment == "AGAINST_H1" else 0.0,
        1.0 if row["side"] == "LONG" else 0.0,
    )


def load_frozen_events(inputs):
    files = sorted(Path(inputs).glob("**/one_usdt_viable_unique_events.csv"))
    if len(files) != len(WINDOWS):
        raise ValueError(f"expected 5 frozen source cohorts, found {len(files)}")
    periods = Counter()
    seen = set()
    rows = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"period", "signal_utc", "exit_utc", "side",
                        "symbol", "plan_id", "outcome", "net_R",
                        "net_USDT_fixed_paper", "turnover24_USDT",
                        "H1_alignment", *NUMERIC_FIELDS}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("missing predeclared frozen features / outcomes")
            local_periods=set()
            count=0
            for raw in reader:
                period=raw["period"]
                if period not in WINDOWS:
                    raise ValueError(f"unknown historical cohort {period}")
                local_periods.add(period)
                signal_at=parse_dt(raw["signal_utc"])
                exit_at=parse_dt(raw["exit_utc"])
                if not signal_at<=exit_at<=signal_at+__import__("datetime").timedelta(seconds=HORIZON_SECONDS+60):
                    raise ValueError("future label beyond declared horizon or before entry")
                if (period == "2026-11-14T00:00:00+00:00" and signal_at>=TEST_START) or (
                        period == "2026-11-15T20:00:00+00:00" and signal_at<TEST_START):
                    raise ValueError("boundary contamination")
                if period == "2026-11-07T00:00:00+00:00" and signal_at >= VAL_START:
                    raise ValueError("training signal extends beyond split")
                key=(raw["symbol"],raw["side"],raw["signal_utc"])
                if key in seen:
                    raise ValueError(f"duplicate market event {key}")
                seen.add(key)
                outcome=raw["outcome"]
                if outcome not in OUTCOMES:
                    raise ValueError(f"unknown result {outcome}")
                features=pretrade_features(raw)
                net_r=_finite(raw["net_R"],"net_R")
                net_usdt=_finite(raw["net_USDT_fixed_paper"],"net_USDT_fixed_paper")
                if outcome == "ALVO" and (net_r<=0 or net_usdt<=0):
                    raise ValueError("target result contradicts net profit")
                if outcome.startswith("STOP") and net_r>0:
                    raise ValueError("stop result contradicts net R")
                rows.append({
                    "symbol":raw["symbol"], "side":raw["side"],"plan_id":raw["plan_id"],
                    "signal_utc":raw["signal_utc"],"signal_at":signal_at,
                    "exit_utc":raw["exit_utc"],"exit_at":exit_at,
                    "period":period,"split":WINDOWS[period],
                    "features":features,"rr":features[0],
                    "outcome":outcome,"y":int(outcome=="ALVO"),
                    "net_r":net_r,"net_usdt_fixed_paper":net_usdt,
                })
                periods[period]+=1
                count+=1
            if count==0 or len(local_periods)!=1:
                raise ValueError(f"empty or mixed period in {path}")
    if set(periods)!=set(WINDOWS):
        raise ValueError("not all five known historical windows represented")
    rows.sort(key=lambda r:(r["signal_at"],r["symbol"],r["side"]))
    return rows,dict(periods)


def safe_sigmoid(value):
    x=max(-30.0,min(30.0,value))
    return 1/(1+math.exp(-x))


def fit_logistic(train):
    if len(train)<MIN_TRAIN:
        raise ValueError("insufficient training data")
    positives=sum(r["y"] for r in train)
    if positives==0 or positives==len(train):
        raise ValueError("need both target and non-target training labels")
    width=len(FEATURE_NAMES)
    means=[sum(r["features"][j] for r in train)/len(train) for j in range(width)]
    scales=[math.sqrt(sum((r["features"][j]-means[j])**2 for r in train)/len(train))
            for j in range(width)]
    scales=[max(x,1e-6) for x in scales]
    def standardized(row):
        return [max(-5.0,min(5.0,(value-means[j])/scales[j]))
                for j,value in enumerate(row["features"])]
    matrix=[standardized(r) for r in train]
    prior=(positives+1)/(len(train)+2)  # gentle smoothing; train only
    bias=math.log(prior/(1-prior))
    weights=[0.0]*width
    for _ in range(STEPS):
        gradients=[0.0]*width
        gb=0.0
        for z,row in zip(matrix,train):
            p=safe_sigmoid(bias+sum(w*v for w,v in zip(weights,z)))
            diff=p-row["y"]
            gb+=diff
            for j in range(width):
                gradients[j]+=diff*z[j]
        n=len(train)
        for j in range(width):
            weights[j]-=LEARNING_RATE*(gradients[j]/n+L2*weights[j])
        bias-=LEARNING_RATE*gb/n
    return {"bias":bias,"weights":weights,"means":means,"scales":scales,
            "training_prevalence":positives/len(train),
            "training_count":len(train),"features":list(FEATURE_NAMES),
            "steps":STEPS,"l2":L2,"learning_rate":LEARNING_RATE}


def probability(model, row):
    z=[max(-5,min(5,(v-model["means"][j])/model["scales"][j]))
       for j,v in enumerate(row["features"])]
    return safe_sigmoid(model["bias"]+
                        sum(w*v for w,v in zip(model["weights"],z)))


def metrics(rows, prior):
    n=len(rows)
    if n==0:
        return {"n":0,"targets":0,"brier":None,"prior_brier":None,
                "log_loss":None,"target_rate":None}
    eps=1e-12
    return {
        "n":n,"targets":sum(x["y"] for x in rows),
        "target_rate":sum(x["y"] for x in rows)/n,
        "brier":sum((x["p"]-x["y"])**2 for x in rows)/n,
        "prior_brier":sum((prior-x["y"])**2 for x in rows)/n,
        "log_loss":-sum(x["y"]*math.log(max(eps,x["p"]))+
                        (1-x["y"])*math.log(max(eps,1-x["p"]))
                        for x in rows)/n,
    }


def qualifies(row,variant):
    if variant=="CONFIRMED_ALL":
        return row["rr"]>=1.0
    if variant=="RR15_CONFIRMED":
        return row["rr"]>=1.5
    threshold=min(0.999,1/(row["rr"]+1)+SAFETY_MARGIN_PROB)
    if row["p"]<=threshold:
        return False
    if variant=="PREDICTED_POSITIVE_EXPECTANCY":
        return True
    if variant=="HYBRID_RR15_PREDICTED":
        return row["rr"]>=1.5
    raise ValueError("unknown comparator")


VARIANTS=("CONFIRMED_ALL","RR15_CONFIRMED",
          "PREDICTED_POSITIVE_EXPECTANCY","HYBRID_RR15_PREDICTED")


def one_slot_paper(rows,variant):
    """Causal one-position-at-a-time selection, fixed hypothetical trade sizing.

    Follows source simulated future exit only AFTER selecting a position.
    Does not compound capital or claim real order fills. Same rule across AB.
    """
    by_minute=defaultdict(list)
    for row in rows:
        if qualifies(row,variant):
            by_minute[row["signal_at"]].append(row)
    selected=[]
    busy_until=None
    for t in sorted(by_minute):
        if busy_until is not None and t<busy_until:
            continue
        choices=by_minute[t]
        # Predeclared ranking: RR for baselines; expected R for predictive.
        if variant in ("CONFIRMED_ALL","RR15_CONFIRMED"):
            key=lambda r:(-r["rr"],r["symbol"],r["side"])
        else:
            key=lambda r:(-(r["p"]*r["rr"]-(1-r["p"])),r["symbol"],r["side"])
        chosen=sorted(choices,key=key)[0]
        selected.append(chosen)
        busy_until=chosen["exit_at"]
    profits=[x["net_usdt_fixed_paper"] for x in selected]
    return {
        "selected":len(selected),
        "tp_first":sum(x["outcome"]=="ALVO" for x in selected),
        "sl_first":sum(x["outcome"].startswith("STOP") for x in selected),
        "time_exit":sum(x["outcome"]=="TIME_4H" for x in selected),
        "sum_simulated_fixed_size_net_r":round(sum(x["net_r"] for x in selected),6),
        "sum_simulated_fixed_size_net_usdt":round(sum(profits),8),
        "notes":"Not a compounded 1-USDT wallet: every operation retains original source fixed paper size",
        "trade_events":[{"signal_at":x["signal_utc"],"symbol":x["symbol"],
                         "side":x["side"],"plan_id":x["plan_id"],
                         "p":round(x["p"],6),"rr":round(x["rr"],6),
                         "result":x["outcome"],"net_usdt":x["net_usdt_fixed_paper"],
                         "exit_at":x["exit_utc"]} for x in selected],
    }


def run_experiment(rows,period_counts):
    train=[r for r in rows if r["split"]=="TRAIN" and r["exit_at"]<=VAL_START]
    validation=[r for r in rows if r["split"]=="VALIDATION"]
    test=[r for r in rows if r["split"]=="TEST"]
    if not train or not validation or not test:
        raise ValueError("all chronological partitions are required")
    if max(x["exit_at"] for x in train)>min(x["signal_at"] for x in validation):
        raise ValueError("training label reaches into validation")
    if max(x["exit_at"] for x in train)>min(x["signal_at"] for x in test):
        raise ValueError("training label reaches into test")
    model=fit_logistic(train)
    reports={}
    ledgers={}
    for name,sample in [("VALIDATION",validation),("TEST",test)]:
        scored=[{**row,"p":probability(model,row)} for row in sample]
        scored.sort(key=lambda r:(r["signal_at"],r["symbol"],r["side"]))
        reports[name]={
            "metrics":metrics(scored,model["training_prevalence"]),
            "portfolios":{k:{j:v for j,v in one_slot_paper(scored,k).items()
                              if j!="trade_events"} for k in VARIANTS},
        }
        ledgers[name]={k:one_slot_paper(scored,k)["trade_events"] for k in VARIANTS}
    result={
        "design":"Predict P(TP before SL within 4h) from confirmation-close features, not before first M1",
        "version":"predictive-research-v1-exploratory",
        "data_origin":"Five FROZEN breakout-quality artifacts from run 45280197720; never regenerate by selecting winners",
        "window_counts":period_counts,
        "counts":{"all":len(rows),"training_purged":len(train),
                  "validation":len(validation),"test":len(test),
                  "training_positives":sum(x["y"] for x in train)},
        "training_label_purge_cutoff_utc":VAL_START.isoformat(),
        "train_only_model":model,
        "predeclared_gate":"p > 1/(1+net_RR) + 0.03, no selected thresholds on validation/test",
        "scenario_costs":"Existing source 1-USDT fixed simulated MEXC fees and slippage, NOT live fill or compounded wallet",
        "limitations":[
            "No early entry before breakout: these features are known at second M1 confirmation only",
            "Data windows, 24 frozen coins and RR15 gates were previously inspected. TEST is retrospective, NOT untouched OOS",
            "Historical top50 membership unavailable; frozen current symbols cause survivorship bias",
            "Labels from completed M1 candles use stop-first conservative intrabar outcome, actual order fills unknown",
            "Net fixed-size paper PNL in source does not grow or shrink position with evolving balance",
            "Overlap/same-event duplicate removed; compare one-slot portfolios, not independent row-profit summation",
            "4h TIME exits are counted as no TP; no historical realized funding or exact market depth",
            "Model Brier must outperform train-prior benchmark; no inference of stable edge from a single week",
            "Pure predictor is only an event-scoring model; new early-event dataset is required to replace trend confirmations",
            "Do NOT activate signals, trade, raise leverage, change minimum RR or send predictive Telegram alerts",
        ],
        "reports":reports,
    }
    return result,ledgers


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    rows,periods=load_frozen_events(args.inputs)
    result,ledgers=run_experiment(rows,periods)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"walkforward_predictive_report.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (args.output/"walkforward_scored_signals.csv").open(
        "w",newline="",encoding="utf-8-sig") as handle:
        cols=("split","signal_utc","symbol","side","plan_id","outcome",
              "realized_net_r","model_p_tp","rr_pretrade","source_fixed_net_usdt")
        writer=csv.DictWriter(handle,fieldnames=cols)
        writer.writeheader()
        model=result["train_only_model"]
        for r in rows:
            if r["split"]=="TRAIN":
                continue
            writer.writerow({
                "split":r["split"],"signal_utc":r["signal_utc"],
                "symbol":r["symbol"],"side":r["side"],"plan_id":r["plan_id"],
                "outcome":r["outcome"],"realized_net_r":r["net_r"],
                "model_p_tp":round(probability(model,r),8),
                "rr_pretrade":r["rr"],
                "source_fixed_net_usdt":r["net_usdt_fixed_paper"],
            })
    (args.output/"walkforward_paper_trades.json").write_text(
        json.dumps(ledgers,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PREDICTIVE_WALKFORWARD="+json.dumps({
        "counts":result["counts"],
        "validation":result["reports"]["VALIDATION"],
        "test":result["reports"]["TEST"],
        "warning":"Research only; no OOS, no early entries, no live orders",
    },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
