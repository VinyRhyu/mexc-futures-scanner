"""Causal diagnostic filters for M1 signal timing and H1 structure.

Research only. Inputs MUST end no later than the completed confirmation M1.
No lookahead, no execution/alerts, no dynamic threshold selection.
"""
from __future__ import annotations

from bisect import bisect_right
from decimal import Decimal

from mexc_scanner.market import atr, structure
from mexc_scanner.models import D, DataError

EXTENSION_ATR = D("2")
LOOKBACK_MINUTES = 240


def entry_context(quarter, hourly, minute, signal_index, side):
    """Features known at confirmation close. Unknown structure never means opposite."""
    if side not in ("LONG", "SHORT"):
        raise DataError("invalid direction")
    if signal_index < LOOKBACK_MINUTES:
        raise DataError("insufficient M1 warmup for causal 4h extension")
    signal = minute[signal_index]
    if signal.tf != 60:
        raise DataError("M1 required")
    anchor = minute[signal_index - LOOKBACK_MINUTES]
    if anchor.ts != signal.ts - LOOKBACK_MINUTES * 60:
        raise DataError("gap in M1 4h lookback")
    if not quarter or quarter[-1].end > signal.end or not hourly or hourly[-1].end > signal.end:
        raise DataError("future bars passed into entry_context")
    if any(a.end != b.ts for a,b in zip(minute[signal_index-LOOKBACK_MINUTES:signal_index+1],
                                          minute[signal_index-LOOKBACK_MINUTES+1:signal_index+1])):
        raise DataError("missing M1 in lookback")
    a = atr(quarter, 14)[-1]
    if a is None or a <= 0:
        raise DataError("nonpositive closed M15 ATR")
    sign = 1 if side == "LONG" else -1
    signed_4h = sign * (signal.close - anchor.close) / a
    h1_state = structure(hourly, signal.end)
    opp = "BAIXA" if side == "LONG" else "ALTA"
    late = signed_4h >= EXTENSION_ATR
    against = h1_state == opp
    return {
        "asof": signal.end,
        "m15_atr": str(a),
        "m1_closed_4h_anchor": anchor.end,
        "m1_signed_4h_extension_atr": str(signed_4h),
        "h1_structure": h1_state,
        "h1_known_opposite": against,
        "A_late": late,
        "B_against_h1": against,
        "A_or_B": late or against,
        "A_threshold_atr": str(EXTENSION_ATR),
    }


def passes_filter(row, experiment):
    x = row["causal_context"]
    if experiment == "BASE":
        return True
    if experiment == "A":
        return not x["A_late"]
    if experiment == "B":
        return not x["B_against_h1"]
    if experiment == "A+B":
        return not x["A_or_B"]
    raise ValueError("unknown experiment")


def pick_portfolio(rows, experiment, key="cost_base"):
    """Reallocate freed slots, not merely delete losers from an old portfolio."""
    eligible = [r for r in rows
                if r[key]["status"] == "FILLED_SIMULATED"
                and passes_filter(r, experiment)]
    eligible.sort(key=lambda r:(r[key]["entry_at"],r["symbol"],r["plan_id"]))
    chosen = []
    next_available = ""
    for row in eligible:
        v = row[key]
        if v["entry_at"] < next_available:
            continue
        chosen.append(row)
        next_available = v["exit_at"]
    return chosen


def portfolio_diagnostics(rows, key="cost_base"):
    result = {}
    baseline = pick_portfolio(rows, "BASE", key)
    base_ids = {(r["symbol"], r["plan_id"]) for r in baseline}
    for experiment in ("BASE", "A", "B", "A+B"):
        chosen = pick_portfolio(rows, experiment, key)
        ids = {(r["symbol"], r["plan_id"]) for r in chosen}
        returns = [D(r[key]["net_r"]) for r in chosen]
        wins = sum(v > 0 for v in returns)
        total = sum(returns, D(0))
        running = peak = D(0)
        max_dd = D(0)
        for v in returns:
            running += v
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)
        result[experiment] = {
            "trades": len(chosen), "wins": wins,
            "win_rate": (str(D(wins)/len(chosen)) if chosen else None),
            "sum_net_r": str(total), "mean_net_r": (str(total/len(chosen)) if chosen else None),
            "max_realized_drawdown_r": str(max_dd),
            "lost_baseline_ids": len(base_ids - ids),
            "newly_available_ids": len(ids - base_ids),
            "symbols": sorted({r["symbol"] for r in chosen}),
            "selected": [
                {"symbol":r["symbol"],"side":r["side"],"signal_at":r["signal_at"],
                 "outcome":r[key]["outcome"],"net_r":r[key]["net_r"],
                 "entry_fill_estimate":r[key].get("entry_fill_estimate"),
                 "stop":r.get("stop"),"target":r.get("target"),
                 "A_late":r["causal_context"]["A_late"],
                 "B_against_h1":r["causal_context"]["B_against_h1"]}
                for r in chosen
            ],
        }
    return result
