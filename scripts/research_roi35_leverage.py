"""Read-only sensitivity: 35% NET take-profit ROI on initial MEXC margin.

Predeclared 10/15/20x leverage with unchanged fixed 1-USDT paper wallet,
existing 10% risk budget, technical TP/SL, RR>=1.5 and scenario costs.
This is NOT blind out-of-sample validation and never orders trades.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from statistics import median
import csv
import json

from mexc_scanner.models import D
from scripts.research_equity_curve import combine_replay_inputs, run_wallet

REF_BASE="0.9408652174548"   # invariant from PR16, replays 27 trades


def summary(replay):
    detail=replay["trades_detail"]
    positive=[D(x["net_realized_roi_pct_of_margin"]) for x in detail
              if D(x["net_usdt"])>0]
    negative=[D(x["net_realized_roi_pct_of_margin"]) for x in detail
              if D(x["net_usdt"])<=0]
    pct_at_least_35=sum(v>=D("35") for v in positive)
    peak=D("1")
    max_dd_pct=D("0")
    for t in detail:
        p=D(t["balance_after"])
        peak=max(peak,p)
        max_dd_pct=max(max_dd_pct,((peak-p)/peak)*D("100"))
    return {
        "fixed_leverage":replay["leverage_fixed"],
        "pretrade_net_roi35_gate":replay["projected_tp_roi_gate_pct"] is not None,
        "initial_balance_usdt":replay["initial_usdt"],
        "ending_balance_usdt":replay["ending_usdt"],
        "net_usdt":replay["net_usdt"],
        "net_equity_pct":replay["net_pct_of_initial"],
        "trades":replay["trades"],
        "wins":replay["wins"],
        "wins_realized_roi_at_least_35pct":pct_at_least_35,
        "median_positive_realized_roi_pct":str(median(positive)) if positive else None,
        "median_nonpositive_realized_roi_pct":str(median(negative)) if negative else None,
        "max_realized_drawdown_usdt":replay["max_realized_drawdown_usdt"],
        "max_realized_drawdown_pct_peak":str(max_dd_pct),
        "max_losing_streak":replay["max_losing_streak"],
        "selected_symbols":sorted({x["symbol"] for x in detail}),
        "blocked_counts":replay["skipped_or_blocked_counts"],
        "trades_detail":detail,
    }


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--inputs",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    sources=sorted(args.inputs.glob("**/equity_candidates_*.json"))
    if len(sources)!=5:
        raise ValueError("need exactly five frozen source artifacts")
    records,windows=combine_replay_inputs(sources)

    # Baseline invariants are checked before exploring changed leverage.
    reference=run_wallet(records,rule="RR15",slip="0.0002")
    if reference["ending_usdt"]!=REF_BASE or reference["trades"]!=27:
        raise ValueError("original paper result changed; do not compare against drifting baseline")
    scenarios=[]
    for leverage in (10,15,20):
        for gate in (None,"35"):
            x=run_wallet(records,rule="RR15",slip="0.0002",
                         fixed_leverage=leverage,min_projected_tp_roi_pct=gate)
            scenarios.append(summary(x))

    args.output.mkdir(parents=True,exist_ok=True)
    report={
        "purpose":"MEXC-like net realized PNL / initial margin; 35% is PROJECTED TP acceptance, not a realized guarantee",
        "historical_data_origin":"5 approved read-only research artifacts from PR16",
        "reference_paper_balance":REF_BASE,
        "fixed_initial_usdt":"1",
        "baseline_rr15_trades":reference["trades"],
        "periods":windows,
        "warnings":[
            "These exact 5 periods have already been used to study RR1.5 and volume/extension, not blind validation",
            "ROI on initial margin is not return on total account equity",
            "Changing leverage alone does not multiply USDT PNL for a fixed quantity; it changes posted margin, liquidation risk, eligibility",
            "The reported 'net realized ROI' includes modeled fee/slippage but not actual historical funding",
            "Pretrade 35% projected TP ROI does not guarantee a 35% realized win; other exits or intrabar slippage can differ",
            "MEXC displayed unrealized ROI uses fair price; this research compares net realized PNL divided by initial modeled margin",
            "Contract tiers and market depth are current or synthetic, not historical",
            "Current frozen 24 symbols are selected as of 2026-11-23, historical top50 ranking unavailable",
            "No simulated result authorizes leverage changes or production merge",
        ],
        "scenarios":[{k:v for k,v in x.items() if k!="trades_detail"} for x in scenarios],
    }
    (args.output/"roi35_leverage_results.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    columns=("fixed_leverage","pretrade_net_roi35_gate","signal_at","exit_at",
             "symbol","side","outcome","balance_before","net_usdt",
             "balance_after","leverage","margin_usdt","notional_usdt","net_rr_projected",
             "net_tp_projected_roi_pct_of_margin","net_realized_roi_pct_of_margin",
             "risk_usdt","plan_id")
    with (args.output/"roi35_margin_ledger.csv").open(
            "w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        for sc in scenarios:
            for t in sc["trades_detail"]:
                writer.writerow({
                    "fixed_leverage":sc["fixed_leverage"],
                    "pretrade_net_roi35_gate":sc["pretrade_net_roi35_gate"],**t})
    for sc in scenarios:
        print("ROI35_MARGIN_LEVERAGE="+json.dumps({
            k:sc[k] for k in ("fixed_leverage","pretrade_net_roi35_gate",
                "trades","wins","wins_realized_roi_at_least_35pct",
                "ending_balance_usdt","net_equity_pct",
                "max_realized_drawdown_pct_peak","median_positive_realized_roi_pct")
        },ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
