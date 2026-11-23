"""Production-eligible snapshot cohort research, not a production-universe replay.

Freezes the current MEXC top-50 USDT contracts before calculating ANY trades.
Requires historical 24h turnover >= production 5M cutoff at signal.
READ ONLY public endpoints. NO orders, Telegram, state or config edits.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.market import select_universe
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Contract, D, jsonable
from scripts.research_entry_context import portfolio_diagnostics, pick_portfolio
from scripts.research_financial_diagnostics import analyze_financial_robustness
from scripts.research_rr15_entry_audit import audit_selection, audit_summary
from scripts.research_liquidity_cohort import analyze_symbol, iso, START, END

MIN_COMPLETE = 20  # preflight observed only 24 currently eligible; require >=20 complete


def freeze_snapshot(contracts, tickers, assets, config, captured_at):
    """Exactly production's CURRENT selection algorithm; never imply past top-50."""
    selection, exclusions = select_universe(
        contracts, tickers, assets, D(config.minimum_turnover), config.universe_size)
    rank = {row["symbol"]: i+1 for i, row in enumerate(selection)}
    quote_by_symbol = {x["symbol"]:x for x in tickers}
    names = [r["symbol"] for r in selection]
    if not names or len(names) != len(set(names)):
        raise ValueError("empty or duplicated live eligible universe")
    if len(names) < MIN_COMPLETE:
        raise ValueError(f"too few eligible symbols for research: {len(names)} (<{MIN_COMPLETE})")
    # Never replace selected symbols after seeing historical outcomes.
    digest = hashlib.sha256(",".join(names).encode("utf-8")).hexdigest()
    return {
        "schema": 1,
        "snapshot_utc": iso(captured_at),
        "selection":"current MEXC selection, not historical top50",
        "minimum_turnover_now": str(config.minimum_turnover),
        "universe_size": config.universe_size,
        "ticker_source": "MEXC contracts/ticker public GET",
        "sha256_ordered_symbols": digest,
        "symbols": [
            {"symbol":r["symbol"],"rank_now":rank[r["symbol"]],
             "turnover24_now":str(D(quote_by_symbol[r["symbol"]]["amount24"]))}
            for r in selection],
        "source_universe_excluded":len(exclusions),
        "critical_bias":"survivorship and future snapshot of eligibility vs past signals",
    }


def validate_frozen(value, min_length=MIN_COMPLETE):
    """Refuse hand edited/unfrozen top-50 sample, omitted or duplicate symbols."""
    if value.get("schema") != 1 or value.get("selection") != "current MEXC selection, not historical top50":
        raise ValueError("invalid frozen universe metadata")
    rows=value.get("symbols")
    if not isinstance(rows,list) or not min_length<=len(rows)<=50:
        raise ValueError("frozen universe size outside expected range")
    names=[x["symbol"] for x in rows]
    if len(set(names))!=len(names):
        raise ValueError("duplicate frozen symbol")
    if any(x.get("rank_now")!=i+1 for i,x in enumerate(rows)):
        raise ValueError("universe ranking changed")
    digest=hashlib.sha256(",".join(names).encode("utf-8")).hexdigest()
    if digest != value.get("sha256_ordered_symbols"):
        raise ValueError("universe fingerprint mismatch")
    return names


def dedupe_viable_by_event(rows, key="cost_base"):
    """Choose a reproducible plan per asset/direction/minute, not a winning one.

    This choice is after financial viability, before outcome inspection, as in
    baseline queue, with smallest stable plan_id as deterministic tie break.
    """
    viable=sorted(
        (r for r in rows if r[key]["status"]=="FILLED_SIMULATED"),
        key=lambda r:(r["signal_at"],r["symbol"],r["side"],r["plan_id"]))
    event_map={}
    for r in viable:
        event_map.setdefault((r["symbol"],r["side"],r["signal_at"]),r)
    return list(event_map.values()), len(viable)-len(event_map)


def paired_cost_stress(selected, key="cost_stress"):
    """Compare SAME baseline selected trades; do not substitute different fills."""
    rows=[]
    for r in selected:
        variant=r[key]
        rows.append({"symbol":r["symbol"],"side":r["side"],"signal_at":r["signal_at"],
                     "status":variant["status"],
                     "net_r":variant.get("net_r"),
                     "baseline_net_r":r["cost_base"]["net_r"]})
    paired=[r for r in rows if r["status"]=="FILLED_SIMULATED"]
    return {
        "baseline_selected":len(rows),"stress_still_filled":len(paired),
        "stress_unfilled":len(rows)-len(paired),
        "paired_baseline_net_r":str(sum((D(r["baseline_net_r"]) for r in paired), D(0))),
        "paired_stress_net_r":str(sum((D(r["net_r"]) for r in paired), D(0))),
        "caution":"conditional on stress still allowing fill; unfilled not equivalent to profitable trade",
        "trades":rows,
    }


def run_study(frozen_path, output_path, fail_on_partial=False):
    config=load_config("config/default.toml")
    if config.mode!="paper" or config.universe_size!=50 or D(config.minimum_turnover)!=D("5000000"):
        raise ValueError("production liquidity assumptions changed; do not silently adapt research")
    frozen=json.loads(frozen_path.read_text())
    names=validate_frozen(frozen)
    client=MexcClient()
    now=client.server_time()
    if now <= END+4*3600+10:
        raise ValueError("four-hour exit horizon not yet closed")
    catalog={r["symbol"]:r for r in client.contracts()}
    results, errors={}, {}
    for i,sym in enumerate(names,1):
        print(json.dumps({"stage":"fetching","index":i,"total":len(names),"symbol":sym}),flush=True)
        try:
            row=catalog[sym]
            Contract.from_api(row)
            obj=analyze_symbol(client,row,"production_snapshot",config)
            results[sym]=obj
            print(json.dumps({"stage":"analyzed","symbol":sym,"signals":obj["signals"],
                              "ohlc_checked":obj["ohlc_checked"]}),flush=True)
        except (ValueError,ArithmeticError,KeyError,TypeError) as exc:
            errors[sym]=type(exc).__name__+": "+str(exc)[:200]
            print(json.dumps({"stage":"excluded","symbol":sym,"reason":errors[sym]}),flush=True)
    if len(results)<MIN_COMPLETE or (fail_on_partial and errors):
        raise ValueError("UNIVERSE_INCOMPLETE: "+json.dumps(errors,ensure_ascii=False))
    cases=[r for sym in names if sym in results for r in results[sym]["records"]]
    production_gate=[r for r in cases if r["historical_group"]=="core_liquidity"]
    viable_raw=sum(r["cost_base"]["status"]=="FILLED_SIMULATED" for r in production_gate)
    unique,duplicate_count=dedupe_viable_by_event(production_gate)
    comp=portfolio_diagnostics(unique)
    base=comp["BASE"]
    a=comp["A"]
    base_picked=pick_portfolio(unique,"BASE")
    a_picked=pick_portfolio(unique,"A")
    base_ids={(r["symbol"],r["side"],r["signal_at"]) for r in base_picked}
    a_ids={(r["symbol"],r["side"],r["signal_at"]) for r in a_picked}
    skipped=[r for r in base_picked if (r["symbol"],r["side"],r["signal_at"]) not in a_ids]
    replacements=[r for r in a_picked if (r["symbol"],r["side"],r["signal_at"]) not in base_ids]
    side_stats=lambda rows: {
        side: {"trades":sum(r["side"]==side for r in rows),
               "net_r":str(sum((D(r["cost_base"]["net_r"]) for r in rows if r["side"]==side),D(0)))}
        for side in ("LONG","SHORT")}
    out={
        "name":"PRODUCTION_LIQUIDITY_SNAPSHOT_TOP50_HISTORICAL_A",
        "window_start_utc":iso(START),"window_end_utc_exclusive":iso(END),
        "frozen_universe":frozen,
        "actual_eligible_selected_now":len(names),
        "completed_symbols":len(results),"incomplete_symbols":errors,
        "minimum_complete":MIN_COMPLETE,
        "sample_bias":frozen["critical_bias"],
        "production_gate_reconstructed":"historical trailing 24h USDT turnover >=5M at signal; past top50, market depth and quotes unavailable",
        "all_confirmed_signals":len(cases),
        "historical_5m_signals":len(production_gate),
        "filled_simulated_raw_plans":viable_raw,
        "viable_distinct_market_events":len(unique),
        "duplicate_financial_plan_records":duplicate_count,
        "comparison_sequential":comp,
        "baseline_side_stats":side_stats(base_picked),
        "A_side_stats":side_stats(a_picked),
        "baseline_trade_ids_eliminated_by_A":[
            {"symbol":r["symbol"],"side":r["side"],"at":r["signal_at"],
             "outcome":r["cost_base"]["outcome"],"net_r":r["cost_base"]["net_r"],
             "extension_atr":r["causal_context"]["m1_signed_4h_extension_atr"],
             "stop":r["stop"],"target":r["target"]}
            for r in skipped],
        "newly_selected_after_A":[
            {"symbol":r["symbol"],"side":r["side"],"at":r["signal_at"],
             "outcome":r["cost_base"]["outcome"],"net_r":r["cost_base"]["net_r"]}
            for r in replacements],
        "cost_sensitivity":{
            "BASE":paired_cost_stress(base_picked),
            "A":paired_cost_stress(a_picked),
        },
        "financial_viability_and_profit_exploratory":analyze_financial_robustness(production_gate),
        "model_limitations":[
            "selected universe is from one CURRENT snapshot and has survivorship bias",
            "Historical top50 membership cannot be recovered from these 50 ticker histories",
            "Historical 5M turnover known causally at signal, not rank or order book",
            "price entries and fills, depth, costs and funding are simulated, not observed",
            "R sums separate windows, not a live USDT equity balance",
            "frozen A rule is 2 ATR(14) M15 directional 4h; do not optimize thresholds here",
        ],
        "symbol_coverage":[{"symbol":s,"signals":results[s]["signals"],
                             "ohlc_checked":results[s]["ohlc_checked"]}
                            for s in names if s in results],
    }
    output_path.mkdir(parents=True,exist_ok=True)
    (output_path/"result.json").write_text(json.dumps(jsonable(out),ensure_ascii=False,indent=2)+"\n")
    (output_path/"frozen-universe.json").write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+"\n")
    def export_csv(rows,path):
        import csv
        with (output_path/path).open("w",newline="",encoding="utf-8-sig") as h:
            cols=["symbol","side","signal_at","entry_at","entry_estimated",
                  "stop","target","exit_at","outcome","net_r",
                  "extension_atr","historical_turnover24","slippage_case"]
            writer=csv.DictWriter(h,fieldnames=cols)
            writer.writeheader()
            for r in rows:
                v=r["cost_base"]
                writer.writerow({
                    "symbol":r["symbol"],"side":r["side"],"signal_at":r["signal_at"],
                    "entry_at":v["entry_at"],"entry_estimated":v.get("entry_fill_estimate"),
                    "stop":r["stop"],"target":r["target"],"exit_at":v["exit_at"],
                    "outcome":v["outcome"],"net_r":v["net_r"],
                    "extension_atr":r["causal_context"]["m1_signed_4h_extension_atr"],
                    "historical_turnover24":r["turnover24"],"slippage_case":"base_0.02pct"})
    export_csv(base_picked,"portfolio_BASE.csv")
    export_csv(a_picked,"portfolio_A.csv")
    export_csv(unique,"viable_unique.csv")
    # Separate forensic ledger for RR>=1.5 / 1USDT, NOT a new trading rule.
    # Selection is performed by frozen quote-level RR before grouping by outcome.
    import csv
    audit_rows,eligible_count,audit_dupes=audit_selection(
        production_gate,out["window_start_utc"])
    if len(audit_rows)!=out["financial_viability_and_profit_exploratory"][
            "exploratory_minimum_projected_RR"]["1usd_base"][
                "BASE_netRR_at_least_1.5"]["trades"]:
        raise ValueError("audited RR15 ledger disagrees with scenario replay")
    columns=[
        "period","signal_BRT","symbol","side","entry_price_estimated",
        "target","stop","exit_BRT","exit_type","minutes_to_exit",
        "net_R","net_USDT_independent_paper","pretrade_projected_net_RR",
        "M1_volume_vs_prev20","M1_body_fraction_of_range",
        "M1_close_near_side_fraction","M1_range_over_M15_ATR",
        "signed_1h_M1_extension_ATR","signed_4h_M1_extension_ATR",
        "signed_2h_M15_extension_ATR","H1_structure","A_late","B_against_H1",
        "risk_distance_entry_to_SL_percent",
        "reward_distance_entry_to_TP_percent","historical_24h_turnover_USDT",
        "signal_utc","entry_utc","exit_utc","plan_id",
    ]
    with (output_path/"rr15_1usdt_selected_ledger.csv").open(
        "w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit_rows)
    audit=audit_summary(audit_rows)
    audit["unique_1usdt_base_viable_events"]=eligible_count
    audit["duplicate_1usdt_base_viable_plan_records"]=audit_dupes
    (output_path/"rr15_1usdt_summary.json").write_text(
        json.dumps(audit,ensure_ascii=False,indent=2)+"\n")
    print("RR15_TRADE_AUDIT="+json.dumps({
        "start":out["window_start_utc"],
        "number_of_selections":audit["total"]["trades"],
        "wins":audit["total"]["wins"],
        "sum_R":audit["total"]["total_net_R"],
        "median_winner_features":audit["winners"]["medians_preentry_and_exit"],
        "median_loser_features":audit["nonwinners"]["medians_preentry_and_exit"],
    },ensure_ascii=False),flush=True)
    # Export the actual pre-entry wallet/cost decisions for each confirmed signal;
    # these are not executed positions or realized account outcomes.
    import csv
    fields=["symbol","side","signal_at","plan_id","turnover24","A_late",
            "wallet_50_base","wallet_50_mid","wallet_50_stress",
            "wallet_1_base","wallet_1_mid","wallet_1_stress",
            "wallet_1_reason","wallet_50_rr_entry","wallet_1_rr_entry"]
    with (output_path/"financial_status_all_signals.csv").open("w",newline="",
                    encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for row in production_gate:
            writer.writerow({
                "symbol":row["symbol"],"side":row["side"],
                "signal_at":row["signal_at"],"plan_id":row["plan_id"],
                "turnover24":row["turnover24"],
                "A_late":row["causal_context"]["A_late"],
                "wallet_50_base":row["cost_base"]["status"],
                "wallet_50_mid":row["cost_mid"]["status"],
                "wallet_50_stress":row["cost_stress"]["status"],
                "wallet_1_base":row["wallet_1usdt"]["status"],
                "wallet_1_mid":row["wallet_1usdt_mid"]["status"],
                "wallet_1_stress":row["wallet_1usdt_stress"]["status"],
                "wallet_1_reason":";".join(map(str,row["wallet_1usdt"].get("reasons",[]))),
                "wallet_50_rr_entry":row["cost_base"].get("net_rr"),
                "wallet_1_rr_entry":row["wallet_1usdt"].get("net_rr"),
            })
    money=out["financial_viability_and_profit_exploratory"]
    wallet_summaries={
        label:{
            "base_fills":value["portfolio_BASE"]["trades"],
            "base_net_r":value["portfolio_BASE"]["net_r_sum"],
            "A_fills":value["portfolio_A"]["trades"],
            "A_net_r":value["portfolio_A"]["net_r_sum"],
            "plan_status":value["status_by_plan"],
        }
        for label,value in money["scenarios"].items()
    }
    print("RESEARCH_FINANCIAL_DIAGNOSTICS="+json.dumps({
        "start":out["window_start_utc"],"end":out["window_end_utc_exclusive"],
        "technical_confirmations_5m":len(production_gate),
        "wallet_cost_scenarios":wallet_summaries,
        "pretrade_RR_trials":{
            label:{
                floor_key:{"trades":stats["trades"],"wins":stats["wins"],
                           "net_r":stats["net_r_sum"]}
                for floor_key,stats in trials.items()
            }
            for label,trials in money["exploratory_minimum_projected_RR"].items()
        }
    },ensure_ascii=False),flush=True)
    summary={
        "start":out["window_start_utc"],"end":out["window_end_utc_exclusive"],
        "frozen_sha256":frozen["sha256_ordered_symbols"],
        "selected":len(names),"completed":len(results),"errors":len(errors),
        "signals":len(cases),"gate_5m":len(production_gate),
        "raw_filled":viable_raw,"unique_filled":len(unique),
        "BASE":{"trades":base["trades"],"wins":base["wins"],"net_r":base["sum_net_r"]},
        "A":{"trades":a["trades"],"wins":a["wins"],"net_r":a["sum_net_r"]},
        "eliminated":len(skipped),"replacements":len(replacements),
    }
    print("PRODUCTION_EXPANDED_AB="+json.dumps(summary,ensure_ascii=False),flush=True)
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--freeze-only",action="store_true")
    parser.add_argument("--universe",type=Path,default=Path("frozen/universe.json"))
    parser.add_argument("--output",type=Path,default=Path("reports/expanded-production"))
    parser.add_argument("--fail-on-partial",action="store_true")
    args=parser.parse_args()
    if args.freeze_only:
        config=load_config("config/default.toml")
        if config.mode!="paper":
            raise ValueError("research requires paper mode")
        assets=set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
        client=MexcClient()
        now=client.server_time()
        frozen=freeze_snapshot(client.contracts(),client.tickers(),assets,config,now)
        args.universe.parent.mkdir(parents=True,exist_ok=True)
        args.universe.write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+"\n")
        print("FROZEN_PRODUCTION_UNIVERSE="+json.dumps({
            "count":len(frozen["symbols"]),
            "sha256":frozen["sha256_ordered_symbols"],
            "selected":[r["symbol"] for r in frozen["symbols"]],
            "snapshot":frozen["snapshot_utc"]
        },ensure_ascii=False),flush=True)
    else:
        run_study(args.universe,args.output,args.fail_on_partial)

if __name__=="__main__":
    main()
