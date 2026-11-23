"""Causal paper-portfolio diagnostics: wallet feasibility, cost stress and RR gates.

All entry decisions derive solely from a simulated quote at next M1 open
(before outcomes); no future result may affect dedupe or filter eligibility.
Prices and fills are hypothetical. This is NOT profit optimization/validation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from mexc_scanner.models import D
from scripts.research_entry_context import pick_portfolio

# Scenario labels and slip assumptions are frozen before reading research outcomes.
SCENARIOS = {
    "50usd_base": ("cost_base", "50", "0.0002"),
    "50usd_mid": ("cost_mid", "50", "0.0005"),
    "50usd_stress": ("cost_stress", "50", "0.0010"),
    "1usd_base": ("wallet_1usdt", "1", "0.0002"),
    "1usd_mid": ("wallet_1usdt_mid", "1", "0.0005"),
    "1usd_stress": ("wallet_1usdt_stress", "1", "0.0010"),
}
EXPLORATORY_RR = (D("1.5"), D("2.0"))


def event_id(row):
    return (row["symbol"], row["side"], row["signal_at"])


def dedupe_scenario(rows, key):
    """Deterministic minimum plan_id among feasible plans; no outcome involved."""
    viable = (r for r in rows if r[key]["status"] == "FILLED_SIMULATED")
    ordered = sorted(viable, key=lambda r:(r["signal_at"],r["symbol"],r["side"],r["plan_id"]))
    events = {}
    for row in ordered:
        events.setdefault(event_id(row),row)
    return list(events.values()), len(ordered)-len(events)


def select_at_quote(rows, key, min_net_rr=None, variant="BASE"):
    """Filter using projected quote net_rr known at hypothetical entry time."""
    eligible=[]
    for row in rows:
        quote=row[key]
        if quote["status"]!="FILLED_SIMULATED":
            continue
        if min_net_rr is not None:
            if quote.get("net_rr") is None:
                raise ValueError("filled research plan missing pre-entry projected net_rr")
            if D(quote["net_rr"])<D(min_net_rr):
                continue
        eligible.append(row)
    return pick_portfolio(eligible,variant,key=key)


def summarize_selected(rows, key):
    vals=[D(x[key]["net_r"]) for x in rows]
    total=sum(vals,D(0))
    best=worst=D(0)
    running=D(0)
    max_dd=D(0)
    for v in vals:
        running+=v
        best=max(best,running)
        max_dd=max(max_dd,best-running)
    return {
        "trades":len(rows),"wins":sum(v>0 for v in vals),
        "win_rate":str(D(sum(v>0 for v in vals))/len(rows)) if rows else None,
        "net_r_sum":str(total),"net_r_avg":str(total/len(rows)) if rows else None,
        "max_realized_dd_r":str(max_dd),
        "net_usdt_sum_independent_fixed_balance":str(sum((D(x[key]["net_usdt"]) for x in rows),D(0))),
        "symbols":dict(Counter(x["symbol"] for x in rows)),
        "outcomes":dict(Counter(x[key]["outcome"] for x in rows)),
    }


def paired_repricing(base_selected, compare_key, base_key="cost_base"):
    """Reprice exact identical trades; compare only actual fills in both cases."""
    comparable=[]
    skipped=Counter()
    for row in base_selected:
        case=row[compare_key]
        if case["status"]=="FILLED_SIMULATED":
            comparable.append((D(row[base_key]["net_r"]),D(case["net_r"])))
        else:
            skipped[case["status"]]+=1
            for reason in case.get("reasons",[]):
                skipped[str(reason)]+=1
    return {
        "base_selected":len(base_selected),
        "still_simulated_filled":len(comparable),
        "not_filled_under_compare":len(base_selected)-len(comparable),
        "block_reasons":dict(skipped),
        "on_shared_fills_base_net_r":str(sum((v[0] for v in comparable),D(0))),
        "on_shared_fills_repriced_net_r":str(sum((v[1] for v in comparable),D(0))),
        "important":"Only equal trade IDs on both scenarios; eliminated trades are NOT assigned zero trading PnL",
    }


def analyze_financial_robustness(rows):
    if any(k not in r for k in ("cost_base","cost_mid","cost_stress",
                                "wallet_1usdt","wallet_1usdt_mid","wallet_1usdt_stress")
           for r in rows):
        raise ValueError("all six scenarios are mandatory on every technical signal")
    out={"scenario_definitions":{label:{"field":key,"balance_usdt":balance,
                                      "slippage_each_side":slip}
                                  for label,(key,balance,slip) in SCENARIOS.items()},
         "historical_5m_confirmations":len(rows),
         "scenarios":{},"exploratory_minimum_projected_RR":{},
         "paired_fixed_baseline_trades":{}}
    for label,(key,balance,slip) in SCENARIOS.items():
        statuses=Counter(r[key]["status"] for r in rows)
        reasons=Counter(str(reason) for r in rows
                        for reason in r[key].get("reasons",[]))
        unique,dupes=dedupe_scenario(rows,key)
        p=select_at_quote(unique,key)
        p_a=select_at_quote(unique,key,variant="A")
        out["scenarios"][label]={
            "status_by_plan":dict(statuses),
            "blocking_reasons_by_plan":dict(reasons),
            "unique_viable_market_events":len(unique),
            "duplicate_viable_plan_records":dupes,
            "portfolio_BASE":summarize_selected(p,key),
            "portfolio_A":summarize_selected(p_a,key),
        }
        # Pre-registered exploratory RR: only as-of-entry net RR, no re-optimization.
        if label in ("50usd_base","1usd_base"):
            trials={}
            for floor in EXPLORATORY_RR:
                for variant in ("BASE","A"):
                    chosen=select_at_quote(unique,key,floor,variant)
                    trials[f"{variant}_netRR_at_least_{floor}"]=summarize_selected(chosen,key)
            out["exploratory_minimum_projected_RR"][label]=trials
    base_unique,_=dedupe_scenario(rows,"cost_base")
    base_selected=select_at_quote(base_unique,"cost_base")
    for label,(key,_,_) in SCENARIOS.items():
        if key=="cost_base":
            continue
        out["paired_fixed_baseline_trades"][label]=paired_repricing(base_selected,key)
    out["limitations"]=[
        "Historical order book, personal fills, contract changes and funding are NOT observed",
        "Synthetic spread 0.02pct, taker fee 0.06pct each side, slippage as above",
        "A scenario marked FINANCIAL_BLOCK/NO_FILL_BAND is not a losing executed trade",
        "Net USDT totals use a FIXED paper balance per independent position, not live wallet evolution",
        "Projected net RR thresholds 1.5 and 2.0 are exploratory, not validated or optimized",
        "Each portfolio is reselected independently with one open position at a time",
        "Snapshot of currently eligible coins introduces time-selection survivorship bias",
        "No observed historical top50 ranking; rolling historical 5M turnover only",
    ]
    return out
