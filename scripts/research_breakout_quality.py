"""Causal breakdown of ALL eligible M1 breakout events; research only.

Exploratory, PREDECLARED gates from the earlier 12-trade case study. They are
not optimized here, and the retrospective periods are NOT a blind validation.
No production writes, network access, alerts or order placement in this module.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from statistics import median
import csv
import json
from pathlib import Path

from mexc_scanner.models import D, jsonable
from scripts.research_entry_context import pick_portfolio
from scripts.research_financial_diagnostics import dedupe_scenario, event_id
from scripts.research_financial_diagnostics import summarize_selected

MONEY_KEYS = ("wallet_1usdt", "wallet_1usdt_mid", "wallet_1usdt_stress")
# These are PRE-REGISTERED exploratory comparisons, NOT winners chosen on outcomes.
GATES = ("BASE", "RR15", "RR15_VOL2", "RR15_EXT2H", "RR15_VOL2_EXT2H")
FEATURES = (
    "M1_volume_vs_prev20", "M1_body_fraction_of_range",
    "M1_close_near_side_fraction", "M1_range_over_M15_ATR",
    "signed_1h_M1_extension_ATR", "signed_4h_M1_extension_ATR",
    "signed_2h_M15_extension_ATR",
)

BUCKETS = {
    "M1_volume_vs_prev20": (("below_1x", None, D("1")), ("1_to_2x", D("1"), D("2")),
                             ("2_to_4x", D("2"), D("4")), ("at_least_4x", D("4"), None)),
    "signed_4h_M1_extension_ATR": (("negative", None, D("0")),
                                  ("0_to_2", D("0"), D("2")),
                                  ("2_to_4", D("2"), D("4")),
                                  ("at_least_4", D("4"), None)),
    "signed_2h_M15_extension_ATR": (("negative", None, D("0")),
                                   ("0_to_1_5", D("0"), D("1.5")),
                                   ("1_5_to_3", D("1.5"), D("3")),
                                   ("at_least_3", D("3"), None)),
    "M1_body_fraction_of_range": (("below_0_3", None, D("0.3")),
                                  ("0_3_to_0_6", D("0.3"), D("0.6")),
                                  ("at_least_0_6", D("0.6"), None)),
    "M1_range_over_M15_ATR": (("below_0_1", None, D("0.1")),
                              ("0_1_to_0_25", D("0.1"), D("0.25")),
                              ("at_least_0_25", D("0.25"), None)),
}


def gate(row, key, name):
    """Entry-time projected financial RR and CLOSED-candle predictors only."""
    if name not in GATES:
        raise ValueError("Unknown or unregistered quality gate")
    if row[key]["status"] != "FILLED_SIMULATED":
        return False
    if name == "BASE":
        return True
    ratio=row[key].get("net_rr")
    if ratio is None:
        raise ValueError("missing projected RR at entry; fail closed")
    if D(ratio) < D("1.5"):
        return False
    if name == "RR15":
        return True
    f=row["exante_features"]
    if f["asof_utc"] != row["signal_at"]:
        raise ValueError("feature time must be the signal confirmation")
    if "VOL2" in name and (f.get("M1_volume_vs_prev20") is None or
                            D(f["M1_volume_vs_prev20"]) < D("2")):
        return False
    if "EXT2H" in name and (f.get("signed_2h_M15_extension_ATR") is None or
                             D(f["signed_2h_M15_extension_ATR"]) > D("1.5")):
        return False
    return True


def select_portfolio(rows, key, rule):
    """Reallocate the one-slot portfolio after each causal entry gate."""
    eligible=[r for r in rows if gate(r, key, rule)]
    return pick_portfolio(eligible,"BASE",key=key)


def numerical_summary(rows, key):
    if not rows:
        return {"n":0,"wins":0,"total_net_R":"0","mean_net_R":None,
                "median_net_R":None,"positive_rate":None}
    vals=[D(r[key]["net_r"]) for r in rows]
    winners=sum(x>0 for x in vals)
    return {
        "n":len(rows),"wins":winners,
        "total_net_R":str(sum(vals,D(0))),
        "mean_net_R":str(sum(vals,D(0))/len(vals)),
        "median_net_R":str(median(vals)),
        "positive_rate":str(D(winners)/len(vals)),
    }


def bucket(value, groups):
    if value is None:
        return "UNKNOWN"
    x=D(value)
    for name,lower,upper in groups:
        if (lower is None or x>=lower) and (upper is None or x<upper):
            return name
    raise ValueError("nonfinite/out-of-range bucket")


def h1_alignment(row):
    h1=row["exante_features"]["H1_structure"]
    side=row["side"]
    if h1 not in ("ALTA","BAIXA"):
        return "NO_CONFIRMED_H1_TREND"
    return "WITH_H1" if (h1=="ALTA" and side=="LONG") or (
        h1=="BAIXA" and side=="SHORT") else "AGAINST_H1"


def strata(rows,key):
    """Descriptive overlapping events, not independent simulated trades."""
    result={}
    for feature, definitions in BUCKETS.items():
        values=defaultdict(list)
        for r in rows:
            val=r["exante_features"].get(feature)
            values[bucket(val,definitions)].append(r)
        result[feature]={k:numerical_summary(v,key) for k,v in sorted(values.items())}
    for label, f in (("side",lambda r:r["side"]),
                     ("H1_alignment",h1_alignment),
                     ("symbol",lambda r:r["symbol"]),
                     ("projected_RR",lambda r:bucket(r[key].get("net_rr"), (
                          ("1_to_1_5",None,D("1.5")),
                          ("1_5_to_2",D("1.5"),D("2")),
                          ("at_least_2",D("2"),None))))):
        groups=defaultdict(list)
        for r in rows:
            groups[f(r)].append(r)
        result[label]={k:numerical_summary(v,key) for k,v in sorted(groups.items())}
    return result


def one_slot_context(rows,key):
    """Analyze outcomes AFTER selecting baseline trades (distinct from candidates)."""
    if not rows:
        return {"features":{}}
    features={}
    wins=[r for r in rows if D(r[key]["net_r"])>0]
    losses=[r for r in rows if D(r[key]["net_r"])<=0]
    for f in FEATURES:
        def compute(arr):
            vs=[D(r["exante_features"][f]) for r in arr
                if r["exante_features"].get(f) is not None]
            return str(median(vs)) if vs else None
        features[f]={"median_winners":compute(wins),"median_nonwinners":compute(losses),
                     "n_winners_with_feature":sum(r["exante_features"].get(f) is not None for r in wins),
                     "n_nonwinners_with_feature":sum(r["exante_features"].get(f) is not None for r in losses)}
    return {"n_winners":len(wins),"n_nonwinners":len(losses),
            "features":features}


def analyze_quality(all_signals, period):
    """Quality audit requires complete source candles, caller owns completeness."""
    eligible=[r for r in all_signals if r["historical_group"]=="core_liquidity"]
    for row in eligible:
        f=row["exante_features"]
        if f["asof_utc"] != row["signal_at"]:
            raise ValueError("causal feature stamp differs from signal")
        for k in MONEY_KEYS:
            if k not in row:
                raise ValueError("missing frozen cost variant")
    result={
        "window_start":period,
        "raw_technical_5m_plans":len(eligible),
        "predeclared_rules":list(GATES),
        "feature_bins_predeclared":BUCKETS,
        "scenario_result":{},
        "methodology":"Events unique by asset/side/signal minute; independently selected one-slot portfolios",
        "limits":[
            "These 5 historical windows have already influenced earlier scanner research",
            "Current 24-symbol snapshot is NOT historical top50; survivorship bias",
            "Simulated synthetic bid/ask/spread, no historical order book, funding or real fills",
            "Unique events may overlap in time and are NOT independent trades",
            "Bucket cohorts are retrospective diagnostics, not validated filters",
            "Thresholds 2x volume, 1.5 ATR in 2h, RR1.5 were informed by previous 12 trades; selection bias",
            "No strategy changes or permission for production implied",
        ],
    }
    base_rows_for_export=[]
    for key in MONEY_KEYS:
        unique,dupes=dedupe_scenario(eligible,key)
        selected={name:select_portfolio(unique,key,name) for name in GATES}
        base=selected["BASE"]
        base_ids={event_id(r) for r in base}
        summary={
            "raw_filled_plans":sum(r[key]["status"]=="FILLED_SIMULATED" for r in eligible),
            "unique_viable_events":len(unique),
            "duplicate_viable_plan_records":dupes,
            "one_slot":{},
            "all_unique_viable_events_including_overlaps":{
                "counts":numerical_summary(unique,key),
                "stratified":strata(unique,key),
            },
            "BASE_one_slot_context":one_slot_context(base,key),
            "BASE_one_slot_strata":strata(base,key),
        }
        for name,rows in selected.items():
            stats=summarize_selected(rows,key)
            ids={event_id(r) for r in rows}
            stats["removed_from_BASE"]=len(base_ids-ids)
            stats["new_from_reallocation"]=len(ids-base_ids)
            stats["removed_BASE_winners"]=sum(
                D(r[key]["net_r"])>0 for r in base if event_id(r) not in ids)
            stats["removed_BASE_nonwinners"]=sum(
                D(r[key]["net_r"])<=0 for r in base if event_id(r) not in ids)
            stats["quote_eligible_unique"]=sum(gate(r,key,name) for r in unique)
            summary["one_slot"][name]=stats
        result["scenario_result"][key]=summary
        if key=="wallet_1usdt":
            for r in unique:
                v=r[key]
                flags={f"selected_{rule}":event_id(r) in {event_id(x) for x in picks}
                       for rule,picks in selected.items()}
                base_rows_for_export.append({
                    "period":period,"symbol":r["symbol"],"side":r["side"],
                    "signal_utc":r["signal_at"],"plan_id":r["plan_id"],
                    "projected_net_RR":v.get("net_rr"),
                    "entry_utc":v.get("entry_at"),"exit_utc":v.get("exit_at"),
                    "estimated_entry":v.get("entry_fill_estimate"),
                    "stop":r["stop"],"target":r["target"],
                    "outcome":v["outcome"],"net_R":v["net_r"],
                    "net_USDT_fixed_paper":v.get("net_usdt"),
                    "turnover24_USDT":r["turnover24"],
                    "H1_alignment":h1_alignment(r),
                    **r["exante_features"],**flags
                })
    return jsonable(result),base_rows_for_export


def save_quality(result,ledger,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/"breakout_quality_summary.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    columns=[
        "period","signal_utc","symbol","side","plan_id","projected_net_RR",
        "entry_utc","estimated_entry","stop","target","exit_utc",
        "outcome","net_R","net_USDT_fixed_paper","turnover24_USDT",
        *FEATURES,"H1_structure","H1_alignment","A_late","B_against_H1",
        *(f"selected_{name}" for name in GATES),
    ]
    with (outdir/"one_usdt_viable_unique_events.csv").open(
        "w",newline="",encoding="utf-8-sig") as fh:
        writer=csv.DictWriter(fh,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ledger)
    return outdir
