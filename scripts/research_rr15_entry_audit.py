"""Pre-entry features and exact selected trades for RR>=1.5 research.

Research only; uses frozen trading rules and causal closed candles. Outcomes
are read exclusively AFTER selecting the hypothetical one-position portfolio.
No thresholds are optimized here and this module does not place orders.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from statistics import median
from zoneinfo import ZoneInfo

from mexc_scanner.models import D, DataError
from scripts.research_financial_diagnostics import dedupe_scenario, select_at_quote

BRT=ZoneInfo("America/Sao_Paulo")
RR=Decimal("1.5")


def as_brt(iso_utc):
    return datetime.fromisoformat(iso_utc).astimezone(BRT).isoformat(timespec="minutes")


def pre_entry_features(minute, index, completed_quarter, ctx, side):
    """All reads <= index / last M15 closed at confirmation; no hindsight."""
    if side not in ("LONG","SHORT") or index<240 or len(completed_quarter)<9:
        raise DataError("invalid causal entry context")
    signal=minute[index]
    if not completed_quarter or completed_quarter[-1].end>signal.end:
        raise DataError("future M15 candle in pre_entry_features")
    for p,c in enumerate(minute[index-240:index+1]):
        if c.ts != minute[index-240].ts+p*60:
            raise DataError("gap in pre-entry M1")
    atr=D(ctx["m15_atr"])
    if atr<=0:
        raise DataError("invalid ATR")
    sign=D(1 if side=="LONG" else -1)
    prior20=minute[index-20:index]
    avg_volume=sum((x.volume for x in prior20),D(0))/D(20)
    candle_range=signal.high-signal.low
    lastq=completed_quarter[-1]
    return {
        "asof_utc":datetime.fromtimestamp(signal.end, __import__("datetime").timezone.utc).isoformat(),
        "M1_volume_vs_prev20":str(signal.volume/avg_volume) if avg_volume>0 else None,
        "M1_body_fraction_of_range":str(abs(signal.close-signal.open)/candle_range) if candle_range>0 else None,
        "M1_close_near_side_fraction":str(
            ((signal.close-signal.low) if sign>0 else (signal.high-signal.close))/candle_range
        ) if candle_range>0 else None,
        "M1_range_over_M15_ATR":str(candle_range/atr),
        "signed_1h_M1_extension_ATR":str(sign*(signal.close-minute[index-60].close)/atr),
        "signed_4h_M1_extension_ATR":ctx["m1_signed_4h_extension_atr"],
        "signed_2h_M15_extension_ATR":str(sign*(lastq.close-completed_quarter[-9].close)/atr),
        "H1_structure":ctx["h1_structure"],
        "A_late":ctx["A_late"],
        "B_against_H1":ctx["B_against_h1"],
    }


def audit_selection(rows, period):
    """Choose before inspecting outcomes, then return full forensic 1-USDT ledger."""
    eligible=[r for r in rows if r["historical_group"]=="core_liquidity"]
    unique,dupes=dedupe_scenario(eligible,"wallet_1usdt")
    selected=select_at_quote(unique,"wallet_1usdt",RR,variant="BASE")
    output=[]
    for r in selected:
        v=r["wallet_1usdt"]
        f=r["exante_features"]
        if v.get("net_rr") is None or D(v["net_rr"])<RR:
            raise ValueError("RR floor violated in audited selection")
        if datetime.fromisoformat(f["asof_utc"]) != datetime.fromisoformat(r["signal_at"]):
            raise ValueError("pre-entry feature stamp differs from signal time")
        entry=D(v["entry_fill_estimate"])
        stop=D(r["stop"]);target=D(r["target"])
        sign=D(1 if r["side"]=="LONG" else -1)
        if sign*(entry-stop)<=0 or sign*(target-entry)<=0:
            raise ValueError("invalid side-adjusted stop/target at modeled entry")
        entry_dt=datetime.fromisoformat(v["entry_at"])
        exit_dt=datetime.fromisoformat(v["exit_at"])
        if exit_dt<=entry_dt:
            raise ValueError("exit cannot precede entry")
        output.append({
            "period":period,
            "plan_id":r["plan_id"],
            "symbol":r["symbol"],
            "side":r["side"],
            "signal_utc":r["signal_at"],
            "signal_BRT":as_brt(r["signal_at"]),
            "entry_utc":v["entry_at"],
            "entry_BRT":as_brt(v["entry_at"]),
            "entry_price_estimated":v["entry_fill_estimate"],
            "stop":r["stop"],
            "target":r["target"],
            "exit_utc":v["exit_at"],
            "exit_BRT":as_brt(v["exit_at"]),
            "minutes_to_exit":int((exit_dt-entry_dt).total_seconds()/60),
            "exit_type":v["outcome"],
            "net_R":v["net_r"],
            "net_USDT_independent_paper":v["net_usdt"],
            "pretrade_projected_net_RR":v["net_rr"],
            "historical_24h_turnover_USDT":r["turnover24"],
            "risk_distance_entry_to_SL_percent":str(abs(entry-stop)/entry*100),
            "reward_distance_entry_to_TP_percent":str(abs(target-entry)/entry*100),
            **f,
        })
    if len({(r["symbol"],r["side"],r["signal_utc"]) for r in output})!=len(output):
        raise ValueError("duplicate selected market events")
    return output, len(unique), dupes


def describe_group(rows):
    fields=("pretrade_projected_net_RR",
            "M1_volume_vs_prev20","M1_body_fraction_of_range",
            "M1_close_near_side_fraction","M1_range_over_M15_ATR",
            "signed_1h_M1_extension_ATR","signed_4h_M1_extension_ATR",
            "signed_2h_M15_extension_ATR","minutes_to_exit",
            "risk_distance_entry_to_SL_percent")
    def median_or_none(field):
        found=[D(r[field]) for r in rows if r.get(field) is not None]
        return str(median(found)) if found else None
    return {
        "trades":len(rows),
        "wins":sum(D(r["net_R"])>0 for r in rows),
        "total_net_R":str(sum((D(r["net_R"]) for r in rows),D(0))),
        "mean_net_R":str(sum((D(r["net_R"]) for r in rows),D(0))/len(rows)) if rows else None,
        "outcomes":dict(Counter(r["exit_type"] for r in rows)),
        "H1_states":dict(Counter(r["H1_structure"] for r in rows)),
        "A_late":sum(bool(r["A_late"]) for r in rows),
        "medians_preentry_and_exit":{field:median_or_none(field) for field in fields},
    }


def audit_summary(all_selected):
    by_period={}
    for period in sorted({r["period"] for r in all_selected}):
        subset=[r for r in all_selected if r["period"]==period]
        by_period[period]=describe_group(subset)
    return {
        "note":"exploratory descriptive comparisons, 12 selected trades, not statistical validation",
        "total":describe_group(all_selected),
        "by_period":by_period,
        "winners":describe_group([r for r in all_selected if D(r["net_R"])>0]),
        "nonwinners":describe_group([r for r in all_selected if D(r["net_R"])<=0]),
        "do_not_infer":"Features measured before trades; outcome groups are post-hoc for diagnosis, do not use their medians as optimized filters",
    }
