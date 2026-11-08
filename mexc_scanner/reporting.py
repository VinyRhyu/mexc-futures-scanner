from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .models import D, Plan, Variant, jsonable


def brt(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S BRT")


def number(value) -> str:
    if value is None:
        return "indisponível"
    return format(D(value).normalize(), "f")


def plan_message(plan: Plan, mode: str, now: int, variant: Variant | None = None) -> str:
    label = "SIMULAÇÃO" if mode == "paper" else "REAL — EXECUÇÃO MANUAL"
    lines = [f"{label} | " + ("GATILHO CUMPRIDO" if variant else plan.status),
             f"ID {plan.id}/r{plan.revision} | {plan.symbol} | {plan.side} | {plan.strategy}",
             f"Formação: {brt(plan.formed_at)} | Análise: {brt(now)}"]
    if variant:
        f = variant.financial
        lines += [f"Modalidade: {variant.kind} | Gatilho: {brt(variant.triggered_at)}",
                  f"Faixa: {number(f.get('entry_low', variant.entry_low))} a {number(f.get('entry_high', variant.entry_high))}",
                  f"SL: {number(variant.stop)} | Alvo: {number(variant.target)} ({variant.target_origin})",
                  "Situação financeira: " + f.get("status", "NAO_AVALIADA")]
        if f.get("contracts") is not None:
            lines += [f"Contratos: {number(f['contracts'])} | Margem: {number(f.get('margin_usdt'))} USDT | Alavancagem: {f.get('leverage', 'indisponível')}x",
                      f"Perda planejada: {number(f.get('loss_usdt'))} USDT | Ganho projetado: {number(f.get('gain_usdt'))} USDT",
                      f"RR líquido no pior preço: {number(f.get('net_rr'))}",
                      f"Taxa por execução: {number(f.get('fee_rate'))} (fração) | Custos estimados: {number(f.get('costs_usdt'))} USDT",
                      f"Disparo do TP/SL: {f.get('stop_trigger', 'indisponível')}"]
        if f.get("reasons"):
            lines.append("Bloqueios: " + ", ".join(f["reasons"]))
        if f.get("assumptions"):
            lines.append("Hipóteses: " + ", ".join(f["assumptions"]))
        if f.get("quote_at"):
            lines.append("Cotação usada: " + brt(f["quote_at"]))
        if f.get("real_gates"):
            lines.append("Pendências para uso real: " + ", ".join(f["real_gates"]))
    else:
        lines += [f"Região: {number(plan.lower)} a {number(plan.upper)}",
                  "Antecipada: " + ("reação fechada de 15m recuperando a região" if plan.strategy == "CONTINUACAO" else "primeiro fechamento de 15m além da faixa + tolerância"),
                  "Confirmada: " + ("fechamento posterior além do extremo da reação" if plan.strategy == "CONTINUACAO" else "fechamento imediatamente seguinte permanece além da faixa"),
                  f"Estado: {plan.status} | Motivo: {plan.reason or 'aguardando gatilho'}"]
    lines += [f"Plano expira: {brt(plan.expires_at)}.",
              "A validade de entrada não encerra uma posição já aberta."]
    return "\n".join(lines)


def markdown_report(report: dict) -> str:
    lines = ["# MEXC Futures Scanner — rodada", "", f"Modo: **{report['mode']}**. Análise: {brt(report['analyzed_at'])}.",
             "", f"Fonte: {report.get('source_status', 'DESCONHECIDA')}",
             f"Cobertura: {report.get('analyzed_symbols', 0)}/{report.get('selected_symbols', 0)} contratos selecionados.", ""]
    if report.get("error"):
        lines += ["**Falha de coleta:** " + report["error"], "", "Nenhuma entrada nova foi liberada com essa falha.", ""]
    lines += ["## Sinais e observações", "", "| Ativo | Padrão | Lado | Estado | Modalidade | Financeiro / motivo |", "| --- | --- | --- | --- | --- | --- |"]
    for p in report.get("plans", []):
        variants = p.get("variants", {}) or {"—": {}}
        for kind, v in variants.items():
            f = v.get("financial", {})
            reason = ", ".join(f.get("reasons", [])) or f.get("status", p.get("reason") or "aguardando gatilho")
            lines.append(f"| {p['symbol']} | {p['strategy']} | {p['side']} | {p['status']} | {kind} | {reason} |")
    if not report.get("plans"):
        lines += ["", "Nenhum plano identificado nesta rodada."]
    lines += ["", "## Diagnósticos", ""]
    for item in report.get("diagnostics", []):
        lines.append(f"- {item.get('symbol', 'GERAL')}: {item['reason']}")
    lines += ["", "Os parâmetros e os custos simulados não demonstram rentabilidade. Sinal técnico e viabilidade para o saldo são avaliações separadas.", ""]
    return "\n".join(lines)
