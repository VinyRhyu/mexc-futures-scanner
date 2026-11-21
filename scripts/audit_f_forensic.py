"""Causal forensic diagnostic of the frozen F_sweep_rejection strategy.

Analysis is DESCRIPTIVE/RETROSPECTIVE. It does not optimize or approve filters.
Frozen protocol: docs/f-forensic-preregistered-2026-11-20.md.
Historical MEXC public candles only, no orders, no Telegram, no main changes.
"""
from __future__ import annotations
import argparse
import bisect
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, median

from scripts.audit_confluence_extended import candles, select_portfolio
from scripts.audit_confluence_v3 import (
    FIVE_MS, HOUR_MS, SYMBOLS, atr_before, candidate_f,
    replay_structural, iso,
)
from scripts.audit_confluence_pilot import _ema_last, Parameters
from scripts.audit_smc_liquidity_fvg import WINDOWS

FEATURES = (
    "vol_ratio", "atr_pct", "stop_pct", "wick_frac", "sweep_atr",
    "range_atr", "body_frac", "m5_return_60m_pct", "m5_return_120m_pct",
    "h1_below_ema20_pct", "h1_return_3h_pct",
    "relative_stop_to_atr", "utc_hour", "entry_gap_atr",
    "cost_fraction_of_risk_pct", "atr_change_14bar_pct",
)

EXPECTED = {
    "T": {"n":24,"TP":8,"SL":12,"TIME":4},
    "U": {"n":10,"TP":2,"SL":6,"TIME":2},
    "V": {"n":27,"TP":9,"SL":15,"TIME":3},
    "W": {"n":20,"TP":7,"SL":10,"TIME":3},
}


def finite(x):
    return isinstance(x,(float,int)) and math.isfinite(x)


def compute_features(five, hourly, trade, index=None):
    """Features at the F candle close; entry-dependent fields at NEXT M5 open.

    Do not use any bars after the signal except entry OPEN for stop distance
    and cost-related attributes, which are known only when the entry occurs.
    """
    if index is None:
        by_at={iso(int(c[0])+FIVE_MS):k for k,c in enumerate(five)}
        index=by_at[trade["signal_at"]]
    setup=candidate_f(five,hourly,index)
    if setup is None or setup["signal_at"]!=trade["signal_at"]:
        raise ValueError("F replay/diagnostic mismatch: candidate not causal")
    c=five[index]
    open_,high,low,close=map(float, (c[1],c[2],c[3],c[4]))
    width=high-low
    atr=setup["atr"]
    entry=float(five[index+1][1])
    stop=float(setup["stop_raw"])
    risk=stop-entry
    if width<=0 or atr<=0 or entry<=0 or risk<=0:
        raise ValueError("Malformed F trade geometry")
    decision_ms=int(c[0])+FIVE_MS
    completed=bisect.bisect_right([int(h[0])+HOUR_MS for h in hourly],decision_ms)
    if completed<24:
        raise ValueError("Insufficient closed hourly candles")
    hcloses=[float(h[4]) for h in hourly[:completed]]
    h1ema=_ema_last(hcloses,20)
    h1close=hcloses[-1]
    previous_close=float(five[index-1][4])
    atr_prev=(atr_before(five,index-14) if index>=29 else float("nan"))
    out={
        "vol_ratio":float(setup["volume_ratio"]),
        "atr_pct":100*atr/close,
        "stop_pct":100*risk/entry,
        "wick_frac":(high-max(open_,close))/width,
        "sweep_atr":(high-float(setup["level"]))/atr,
        "range_atr":width/atr,
        "body_frac":(open_-close)/width,
        "m5_return_60m_pct":100*(close/float(five[index-12][4])-1),
        "m5_return_120m_pct":100*(close/float(five[index-24][4])-1),
        "h1_below_ema20_pct":100*(h1ema-h1close)/h1close,
        "h1_return_3h_pct":100*(h1close/hcloses[-4]-1),
        "relative_stop_to_atr":risk/atr,
        "utc_hour":datetime.fromisoformat(trade["signal_at"]).hour,
        "entry_gap_atr":(entry-close)/atr,
        "cost_fraction_of_risk_pct":100*2*entry*
            (Parameters().taker_fee_each+Parameters().slippage_each)/risk,
        "atr_change_14bar_pct":100*(atr/atr_prev-1) if atr_prev>0 else None,
    }
    if any(not finite(v) for v in out.values() if v is not None):
        raise ValueError("Invalid ex-ante feature vector")
    return out


def outcome_summary(rows):
    balance=1.0
    for row in rows:
        balance *= 1.0 + 0.01 * (row["net_r"] if row["net_r"] is not None else -1.0)
    n=len(rows)
    return {
        "n":n,
        "TP":sum(r["result"]=="TP" for r in rows),
        "SL":sum(r["result"]=="SL" for r in rows),
        "TIME":sum(r["result"]=="TIME" for r in rows),
        "AMBIGUOUS":sum(r["result"]=="AMBIGUOUS" for r in rows),
        "sum_net_R":round(sum((r["net_r"] if r["net_r"] is not None else -1) for r in rows),4),
        "mean_net_R":round(mean((r["net_r"] if r["net_r"] is not None else -1) for r in rows),5) if n else None,
        "portfolio_compound_pct_at_1pct_risk":round(100*(balance-1),3),
    }


def auc_tp_vs_sl(rows, feat):
    """Nonparametric descriptive rank statistic. Not a causal probability."""
    positive=[r["features"][feat] for r in rows if r["result"]=="TP" and r["features"][feat] is not None]
    negative=[r["features"][feat] for r in rows if r["result"]=="SL" and r["features"][feat] is not None]
    if not positive or not negative:
        return None
    wins=sum(1 if x>y else .5 if x==y else 0 for x in positive for y in negative)
    return round(wins/(len(positive)*len(negative)),4)


def distribution(rows,feat):
    cohorts={}
    for label in ("TP","SL","TIME"):
        values=[r["features"][feat] for r in rows
                if r["result"]==label and r["features"][feat] is not None]
        cohorts[label]={"n":len(values), "median":round(median(values),5),
                        "mean":round(mean(values),5)} if values else {"n":0}
    return cohorts


def group_statistics(rows,feat,threshold):
    """Post-hoc association ONLY. NOT a strategy backtest with freed slots."""
    groups={"low":[],"high":[]}
    for row in rows:
        v=row["features"][feat]
        if v is not None:
            groups["high" if v>=threshold else "low"].append(row)
    result={}
    for name,subset in groups.items():
        by_window={w:outcome_summary([r for r in subset if r["window"]==w])
                   for w in WINDOWS}
        result[name]={"summary":outcome_summary(subset),"by_window":by_window}
    return result


def analyze(rows):
    full=outcome_summary(rows)
    assert full["n"]==81 and (full["TP"],full["SL"],full["TIME"])==(26,43,12),full
    by_window={w:outcome_summary([r for r in rows if r["window"]==w])
               for w in WINDOWS}
    for w,ex in EXPECTED.items():
        actual=by_window[w]
        if any(actual[k]!=v for k,v in ex.items()):
            raise RuntimeError(f"Unexpected F portfolio mismatch {w}: {actual} != {ex}")
    by_asset={s:outcome_summary([r for r in rows if r["symbol"]==s+"_USDT"])
              for s in SYMBOLS}
    variables={}
    for feat in FEATURES:
        vals=[r["features"][feat] for r in rows if r["features"][feat] is not None]
        threshold=median(vals) if vals else None
        variables[feat]={
            "overall_median":round(threshold,6) if threshold is not None else None,
            "tp_vs_sl_auc":auc_tp_vs_sl(rows,feat),
            "by_outcome":distribution(rows,feat),
            "exploratory_split_ge_population_median":(
                group_statistics(rows,feat,threshold) if threshold is not None else {}),
            "per_window_tp_sl_medians":{
                w:{
                    y:(round(median([r["features"][feat] for r in rows
                         if r["window"]==w and r["result"]==y and
                         r["features"][feat] is not None]),5)
                       if any(r["window"]==w and r["result"]==y and
                              r["features"][feat] is not None for r in rows) else None)
                    for y in ("TP","SL")
                } for w in WINDOWS
            },
        }
    ranking=sorted(FEATURES,key=lambda f:
                   abs((variables[f]["tp_vs_sl_auc"] or .5)-.5), reverse=True)
    return {
        "study":"F_forensic_causal_descriptive_NO_filter_approval",
        "warnings":[
            "Selected portfolio has only 81 trades; 26 TP vs 43 SL. All four windows used before. NOT independent.",
            "AUC and median splits inspect labels in-sample: do NOT use them as live trading thresholds.",
            "Associations confounded by calendar regime and correlated assets; no statistical causation established.",
            "Conditioned subset summaries do not rerun the portfolio when skipped positions free time.",
            "Stop_pct, entry_gap_atr, cost_fraction_of_risk_pct observed at next candle opening, not at M5 close.",
            "Taker and slippage hypothetical, no historical order book/funding/liquidation/actual fills.",
        ],
        "whole_portfolio":full,
        "per_window":by_window,
        "per_symbol":by_asset,
        "ranked_features_by_descriptive_auc_distance_from_0_5":ranking,
        "variables":variables,
    }


def run(window):
    first,last=WINDOWS[window]
    start=int(datetime.fromisoformat(first).timestamp())
    end=int(datetime.fromisoformat(last).timestamp())
    print("F_FORENSIC_START "+json.dumps({
        "window":window,"dates":[first,last],"symbols":SYMBOLS,
        "doc":"docs/f-forensic-preregistered-2026-11-20.md"}),flush=True)
    all_trades=[]
    enriched={}
    errors=[]
    for asset in SYMBOLS:
        sym=asset+"_USDT"
        try:
            h=candles(sym,"Min60",start-100*3600,end)
            m=candles(sym,"Min5",start-52*300,end)
            ts=replay_structural(m,h,"F_sweep_rejection")
            index_by_signal={iso(int(c[0])+FIVE_MS):i for i,c in enumerate(m)}
            for t in ts:
                if not first<=t["signal_at"]<last:
                    continue
                key=(sym,t["signal_at"])
                if key in enriched:
                    raise RuntimeError("Duplicate F entry timestamp per asset")
                enriched[key]={**t,"symbol":sym,"window":window,
                               "features":compute_features(m,h,t,index_by_signal[t["signal_at"]])}
                all_trades.append({**t,"symbol":sym})
            print("F_FORENSIC_ASSET "+json.dumps({
                "window":window,"symbol":sym,"F_candidates":len(ts),
                "M5":len(m),"H1":len(h)},sort_keys=True),flush=True)
        except Exception as exc:
            errors.append({"symbol":sym,"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
            print("F_FORENSIC_SOURCE_ERROR "+json.dumps({"window":window,**errors[-1]}),flush=True)
    if errors:
        raise RuntimeError(f"Refusing partial forensic {window}: {errors}")
    chosen=select_portfolio(all_trades)
    selected=[]
    for t in chosen["chosen"]:
        key=(t["symbol"],t["signal_at"])
        row=enriched[key]
        if row["result"]!=t["result"]:
            raise RuntimeError("Outcome conflict in portfolio selection")
        selected.append(row)
    expected=EXPECTED[window]
    actual=outcome_summary(selected)
    if any(actual[k]!=v for k,v in expected.items()):
        raise RuntimeError(f"Baseline mismatch: {window} got={actual} expected={expected}")
    print("F_FORENSIC_WINDOW "+json.dumps({
        "window":window,"candidates":len(all_trades),
        "selected":actual,"rows":[{
            "symbol":r["symbol"],"signal_at":r["signal_at"],"exit_at":r["exit_at"],
            "result":r["result"],"net_r":r["net_r"],
            "features":{k:round(v,6) if v is not None else None
                        for k,v in r["features"].items()},
        } for r in selected]},sort_keys=True),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--window",choices=tuple(WINDOWS),required=True)
    run(p.parse_args().window)


if __name__=="__main__":
    main()
