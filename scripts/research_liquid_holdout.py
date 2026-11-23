"""Read-only historical holdout: liquid MEXC assets and frozen M1 volume rule.

This orchestrates the existing validated historical collector, two-close M1
confirmation and chronological wallet. It cannot send orders or Telegram.
It does not choose a strategy or coin based on the observed outcome.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from math import sqrt
import gzip
import json
import os

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from scripts.audit_early_trigger import run as collect, summarize as early_summary, write_gzip
from scripts.audit_historical_trend import midnight
from scripts.audit_portfolio import simulate
from scripts.audit_sustained_trigger import MODE, read_dataset, run as confirm
from scripts.audit_volume_retention import keep_volume


START = "2026-11-08"
END_EXCLUSIVE = "2026-11-22"
WEEKS = ("08–14/11", "15–21/11")
OUT = Path("reports/liquid-holdout")
SOURCE = OUT / "frozen-source"
CONFIRMED = OUT / "confirmed"


def assign_week(formed_at):
    stamp = datetime.fromisoformat(formed_at)
    boundary = midnight("2026-11-15")
    return WEEKS[0] if stamp.timestamp() < boundary else WEEKS[1]


def wilson_95(wins, total):
    """Descriptive interval, not an independence guarantee."""
    if not total:
        return None
    z = 1.959963984540054
    p = wins / total
    d = 1 + z*z/total
    middle = (p + z*z/(2*total))/d
    half = z*sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return [round(max(0, middle-half), 4), round(min(1, middle+half), 4)]


def wallet_brief(result):
    trades = result["trades"]
    closed = [t for t in trades if t["outcome"] in ("STOP", "STOP_AMBIGUO", "ALVO")]
    targets = sum(t["outcome"] == "ALVO" for t in closed)
    wins = sum(D(t["net_usdt"]) > 0 for t in trades)
    gains = D(result["gains_usdt"])
    losses = D(result["losses_usdt"])
    return {
        "initial_usdt": result["initial_balance"],
        "final_usdt": result["final_balance"],
        "net_usdt": result["net_usdt"],
        "return_percent": result["return_percent"],
        "operations": result["entries"],
        "targets": targets,
        "stops": sum(t["outcome"] in ("STOP", "STOP_AMBIGUO") for t in closed),
        "ambiguous_stops": sum(t["outcome"] == "STOP_AMBIGUO" for t in closed),
        "time_exits": sum(t["outcome"] == "ENCERRAMENTO_4H" for t in trades),
        "net_winning_trades": wins,
        "net_losing_trades": sum(D(t["net_usdt"]) < 0 for t in trades),
        "net_win_rate": round(wins / len(trades), 4) if trades else None,
        "target_rate_closed": round(targets / len(closed), 4) if closed else None,
        "target_rate_wilson_95": wilson_95(targets, len(closed)),
        "profit_factor": str(gains / losses) if losses > 0 else None,
        "sum_net_r": str(sum((D(t["net_usdt"]) / D(t["planned_risk"])
                             for t in trades if D(t["planned_risk"]) > 0), D(0))),
        "max_realized_drawdown_percent": result["maximum_realized_drawdown_percent"],
        "skipped": result["skips"],
    }


def retentive_copy(rows, minute_map_by_symbol):
    """Filter AFTER a closed second candle, without inspecting its future result."""
    kept = []
    decisions = Counter()
    for original in rows:
        row = dict(original)
        event = row[MODE]
        if "signal" not in event:
            kept.append(row)
            continue
        signal = int(event["signal"])
        mm = minute_map_by_symbol[row["symbol"]]
        first, second = mm[signal-120], mm[signal-60]
        if first.end != second.ts or second.end != signal:
            raise ValueError("Nonconsecutive M1 confirmation candles")
        accepted = keep_volume(first.volume, second.volume)
        decisions["accepted" if accepted else "volume_rejected"] += 1
        if not accepted:
            # Excluded only by a field known at the time of the second close.
            row[MODE] = {"outcome": "VOLUME_M1_INSUFICIENTE"}
        kept.append(row)
    return kept, dict(decisions)


def relabel_calendar_only(source):
    """Legacy research script hardcodes October week labels; change only labels."""
    prior = json.loads((source / "summary.json").read_text())
    raw = json.loads(gzip.decompress((source / "all-formations.json.gz").read_bytes()))
    for row in raw:
        row["week"] = assign_week(row["formed_at"])
    write_gzip(source / "all-formations.json.gz", raw)
    prior["weekly"] = {
        week: early_summary([r for r in raw if r["week"] == week])
        for week in WEEKS
    }
    # Prior scripts' prose describes earlier October experiments and RR 2:1.
    prior["limitations"] = [
        "Research-only holdout. 2026-11-08 through 2026-11-21 inclusive, BRT.",
        "As-of-collection eligible universe (survivorship bias); not historical top-50 constituents.",
        "No active-plan suppression in formation comparison; historical fills and books are hypothetical.",
        "Current config.default.toml used, including net minimum RR 1:1 and up to 20x.",
        "One-position portfolios and effective filled trades are reported separately.",
        "No order, Telegram notification, or production state mutation."
    ]
    (source / "summary.json").write_text(json.dumps(prior, ensure_ascii=False, indent=2))
    return prior


def markdown(report):
    lines = [
        "# Teste de moedas líquidas — período 08–21/11/2026",
        "",
        f"Universo íntegro: {report['analyzed_symbols']}/{report['selected_symbols']} contratos.",
        f"Formações: {report['formations']}. Confirmações elegíveis para teste: {report['confirmed_signal_rows']}.",
        "",
        "| Carteira cronológica | Saldo inicial | Saldo final | P&L líquido | Operações | TP | Stop | Saída 4h | Acerto líquido | DD realizado |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    ]
    for key, label in (
        ("baseline_50", "Dois fechamentos, USDT 50"),
        ("volume50_50", "Volume sustentado, USDT 50"),
        ("baseline_1", "Dois fechamentos, USDT 1"),
        ("volume50_1", "Volume sustentado, USDT 1")
    ):
        w = report["wallets"][key]
        rate = f"{100*w['net_win_rate']:.1f}%" if w["net_win_rate"] is not None else "n/a"
        lines.append(
            f"| {label} | {w['initial_usdt']} | {w['final_usdt']} | {w['net_usdt']} | "
            f"{w['operations']} | {w['targets']} | {w['stops']} | {w['time_exits']} | "
            f"{rate} | {w['max_realized_drawdown_percent']}% |"
        )
    lines += [
        "", "## Coorte e limites", "",
        f"Selecionadas hoje (não necessariamente as mesmas historicamente): {', '.join(report['symbols'])}.",
        f"Confirmações M1 da coorte: {report['confirmed_signal_rows']}; "
        f"retidas pelo filtro de volume: {report['volume_decisions']['accepted']}; "
        f"rejeitadas: {report['volume_decisions']['volume_rejected']}.",
        "",
        "Acerto líquido inclui lucro/prejuízo de saídas por tempo. Taxa de TP considera somente TP ou stop.",
        "Amostra histórica posterior à janela principal usada para escolher o filtro, mas NÃO é teste prospectivo cego.",
        "Uma posição por vez, desempate cronológico/alfabético, níveis congelados, stop primeiro quando ambíguo.",
        "A liquidez e contratos são selecionados pelo catálogo atual, e não pela elegibilidade histórica.",
        "Custos são estimados: taxa taker 0,06% por lado, spread 0,02%, slippage configurada e funding zero.",
        "Abertura seguinte à confirmação idealizada, sem latência real nem livro histórico; MEXC LAST não prova execução no FAIR.",
        "Falta amostra prospectiva com fills e taxas reais. Nenhum critério de sinal é promovido a produção por este teste.",
        ""
    ]
    return "\n".join(lines)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    initial = collect(midnight(START), midnight(END_EXCLUSIVE), SOURCE, limit=50)
    if initial["errors"] or initial["analyzed_symbols"] != initial["selected_symbols"]:
        result = {
            "status": "INCOMPLETE", "selected": initial["selected_symbols"],
            "analyzed": initial["analyzed_symbols"], "errors": initial["errors"]
        }
        (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        raise ValueError("Historical source missing for at least one current eligible asset")

    relabeled = relabel_calendar_only(SOURCE)
    confirmed = confirm(SOURCE, CONFIRMED)
    if confirmed["analyzed_symbols"] != relabeled["selected_symbols"]:
        raise ValueError("Confirmed cohort coverage differs from original")

    rows = json.loads(gzip.decompress((CONFIRMED / "all-formations.json.gz").read_bytes()))
    if len(rows) != confirmed["formations"]:
        raise ValueError("Reconstructed confirmed cohort incomplete")

    datasets, minute_maps = {}, {}
    for manifest in relabeled["datasets"]:
        data = read_dataset(SOURCE, manifest)
        minute_maps[manifest["symbol"]] = {c.ts: c for c in data.pop("minute")}
        data["minute_map"] = minute_maps[manifest["symbol"]]
        datasets[manifest["symbol"]] = data
    kept, decisions = retentive_copy(rows, minute_maps)
    signal_rows = sum("signal" in r[MODE] for r in rows)
    if signal_rows != sum(decisions.values()):
        raise ValueError("Volume acceptance ledger is incomplete")

    cfg = Config(**relabeled["config"]).validate()
    if cfg.mode != "paper" or D(cfg.minimum_rr) != D(1) or cfg.max_leverage != 20:
        raise ValueError("Unexpected production-financial baseline")

    wallets_full = {
        "baseline_50": simulate(rows, datasets, cfg, initial=D(50)),
        "volume50_50": simulate(kept, datasets, cfg, initial=D(50)),
        "baseline_1": simulate(rows, datasets, cfg, initial=D(1)),
        "volume50_1": simulate(kept, datasets, cfg, initial=D(1))
    }
    by_symbol = []
    for symbol in sorted(datasets):
        subset = [r for r in kept if r["symbol"] == symbol]
        one = simulate(subset, datasets, cfg, initial=D(50))
        by_symbol.append({
            "symbol": symbol,
            "confirmed_candidates": sum("signal" in r[MODE] for r in subset),
            "wallet_50": wallet_brief(one)
        })

    selected_trades = wallets_full["volume50_50"]["trades"]
    by_week = []
    for label, start, end in (
        (WEEKS[0], midnight("2026-11-08"), midnight("2026-11-15")),
        (WEEKS[1], midnight("2026-11-15"), midnight("2026-11-22"))
    ):
        subset = [t for t in selected_trades
                  if start <= datetime.fromisoformat(t["entered_at"]).timestamp() < end]
        by_week.append({
            "week": label,
            "operations": len(subset),
            "targets": sum(t["outcome"] == "ALVO" for t in subset),
            "stops": sum(t["outcome"] in ("STOP", "STOP_AMBIGUO") for t in subset),
            "time_exits": sum(t["outcome"] == "ENCERRAMENTO_4H" for t in subset),
            "net_usdt": str(sum((D(t["net_usdt"]) for t in subset), D(0)))
        })

    report = jsonable({
        "status": "COMPLETE",
        "kind": "LIQUID_M1_FIXED_RULE_HOLDOUT",
        "period_start_brt": START,
        "period_end_exclusive_brt": END_EXCLUSIVE,
        "source_snapshot": "MEXC current selected turnover>=5m, NOT historical constituents",
        "source_code_sha": os.environ.get("GITHUB_SHA", "local"),
        "selected_symbols": initial["selected_symbols"],
        "analyzed_symbols": initial["analyzed_symbols"],
        "symbols": [d["symbol"] for d in relabeled["datasets"]],
        "formations": len(rows),
        "confirmed_signal_rows": signal_rows,
        "volume_decisions": decisions,
        "wallets": {k: wallet_brief(v) for k,v in wallets_full.items()},
        "by_symbol": by_symbol,
        "by_week_volume50_50": by_week,
        "full_wallet_trades": {k: v["trades"] for k,v in wallets_full.items()},
        "source_manifest": relabeled["datasets"],
        "limitations": [
            "Single time period not independent validation of strategy optimization.",
            "Uses selection of liquid contracts from collection date (survivorship bias).",
            "Production suppresses some overlapping active plans, whereas research enumerates all formations.",
            "Single-position wallet and first chronological/lexical admissible trade are simulated.",
            "Prices and fills are hypothetical, including funding=0, no historical depth or latency.",
            "No user real fills or taker fee schedule observed; paper leverage 10x–20x.",
            "No parameter optimized on this outcome and no production modification."
        ]
    })
    (OUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (OUT / "report.md").write_text(markdown(report), encoding="utf-8")
    print("LIQUID_HOLDOUT_SUMMARY_BEGIN", flush=True)
    print(json.dumps({
        "status": report["status"], "symbols": report["symbols"],
        "formations": report["formations"], "confirmed_signal_rows": signal_rows,
        "volume_decisions": decisions, "wallets": report["wallets"],
        "by_week_volume50_50": by_week
    }, ensure_ascii=False, indent=2), flush=True)
    print("LIQUID_HOLDOUT_SUMMARY_END", flush=True)
    if step := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(step).write_text(markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    run()
