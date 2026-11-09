from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from .models import D, Plan, Variant


def brt(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M:%S BRT")


def number(value) -> str:
    if value is None:
        return "indisponível"
    return format(D(value).normalize(), "f")


REASONS = {
    "PLANO_NAO_ATUAL": "O plano não está mais válido para uma nova entrada.",
    "SALDO_NAO_POSITIVO": "Não há saldo disponível.",
    "DADOS_NAO_VERIFICADOS": "A cotação não está atualizada ou validada.",
    "LIVRO_NAO_ATUAL": "O livro de ofertas está desatualizado.",
    "PRECO_FORA_DO_PLANO": "O preço está fora da faixa permitida.",
    "GEOMETRIA_DE_PRECOS_INVALIDA": "Entrada, stop ou alvo estão inconsistentes.",
    "RETORNO_RISCO_INSUFICIENTE": "A relação entre ganho e perda ficou abaixo do mínimo.",
    "LOTE_MINIMO_OU_META_EXCEDE_RISCO": "A quantidade necessária ultrapassa o risco permitido para a banca.",
    "CUSTO_RELATIVO_ELEVADO": "Os custos estão altos demais em relação ao risco.",
    "QUANTIDADE_ACIMA_DO_CONTRATO": "A quantidade excede o limite do contrato.",
    "PROFUNDIDADE_INSUFICIENTE": "Não há ofertas suficientes no livro para essa quantidade.",
    "EXECUCAO_FORA_DA_FAIXA": "O preço médio estimado de execução sai da faixa permitida.",
    "CUSTOS_CONSOMEM_SALDO": "Os custos consomem o saldo disponível.",
    "NIVEL_DE_RISCO_INDISPONIVEL": "Os limites de margem do contrato não foram validados.",
    "MARGEM_OU_TETO_DE_ALAVANCAGEM": "A margem disponível ou o limite de alavancagem não comporta a operação.",
    "PARAMETROS_DE_LIQUIDACAO_INVALIDOS": "Os parâmetros de liquidação não foram validados.",
    "STOP_PROXIMO_DA_LIQUIDACAO": "O stop está próximo demais da liquidação estimada.",
    "VERIFICACOES_PARA_REAL_PENDENTES": "Faltam verificações da conta para liberar uso real.",
    "COTACAO_LIVRO_OU_CUSTOS_INDISPONIVEIS": "Cotação, livro ou custos estão indisponíveis.",
    "COLETA_NAO_VALIDADA_NESTA_RODADA": "Os dados deste ativo não foram validados nesta rodada.",
    "FALHA_DA_FONTE_NESTA_RODADA": "A coleta falhou nesta rodada.",
    "PRAZO_ENCERRADO": "A janela para uma nova entrada terminou.",
    "STOP_E_ALVO_NO_MESMO_CANDLE": "O mesmo candle tocou stop e alvo; a ordem dos eventos é desconhecida.",
    "STOP_ANTES_DA_ENTRADA": "O preço tocou o stop do plano antes de uma nova entrada.",
    "ALVO_JA_ATINGIDO": "O movimento já alcançou o alvo do plano.",
    "PERDA_DA_REGIAO_OU_ESTRUTURA": "O preço perdeu a região ou a estrutura necessária.",
    "RETORNO_PARA_CONSOLIDACAO": "O preço voltou para dentro da consolidação.",
    "TAXA_PESSOAL_NAO_VERIFICADA": "taxa pessoal da conta",
    "REGRAS_DA_CONTA_NAO_VERIFICADAS": "regras de margem da conta",
    "GATILHO_FAIR_NAO_VERIFICADO": "disparo do stop pelo preço justo",
    "FUNDING_NAO_VERIFICADO": "funding",
}


def friendly(code: str) -> str:
    return REASONS.get(code, code.replace("_", " ").lower().capitalize())


def fixed(value, places: int = 2) -> str:
    if value is None:
        return "indisponível"
    return format(D(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP), "f")


def money(value) -> str:
    if value is None:
        return "indisponível"
    return fixed(value, 4 if abs(D(value)) < 1 else 2) + " USDT"


def approximate(value) -> str:
    """Somente regiões de atenção: seis algarismos significativos, nunca preços de ordem."""
    d = D(value)
    return number(d.quantize(Decimal(1).scaleb(d.adjusted() - 5), rounding=ROUND_HALF_UP)) if d else "0"


def clock(ts: int, now: int) -> str:
    def local(t):
        return datetime.fromtimestamp(t, timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo"))
    stamp = local(ts)
    return stamp.strftime("%H:%M:%S" if stamp.date() == local(now).date() else "%d/%m %H:%M:%S") + " BRT"


def _mode(mode: str) -> str:
    return "🧪 SIMULAÇÃO" if mode == "paper" else "REAL • EXECUÇÃO MANUAL"


def _identity(plan: Plan) -> str:
    return f"{plan.symbol.replace('_', '/')} • {plan.side}"


def _remaining(expires: int, now: int) -> str:
    seconds = max(0, expires - now)
    return f"{seconds // 60}min {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def plan_message(plan: Plan, mode: str, now: int, variant: Variant | None = None,
                 *, restriction: str = "") -> str:
    terminal = plan.status if plan.terminal else ("EXPIRADO" if now >= plan.expires_at else "")
    footer = f"Plano: {plan.id} • revisão {plan.revision}"
    if terminal:
        title = {"EXPIRADO": "⚪ PLANO EXPIRADO", "INVALIDADO": "🔴 PLANO INVALIDADO",
                 "AMBIGUO": "⚠️ CANDLE AMBÍGUO", "EVENTO_PASSADO": "⚪ MOVIMENTO ENCERRADO"}[terminal]
        reason = "PRAZO_ENCERRADO" if terminal == "EXPIRADO" else plan.reason
        return "\n".join([title, _identity(plan), _mode(mode), "", friendly(reason or terminal),
            "Sem nova entrada por este plano.", f"Validade encerrada: {clock(plan.expires_at, now)}" if terminal == "EXPIRADO" else
            f"Análise: {brt(now)}", "A expiração não encerra uma posição já aberta.", "", footer])

    strategy = "Continuação após correção" if plan.strategy == "CONTINUACAO" else "Rompimento de consolidação"
    if variant is None:
        above = plan.side == "LONG"
        direction = "acima" if above else "abaixo"
        if plan.strategy == "CONTINUACAO":
            early = f"Tocar a região e fechar o candle de 15m {direction} dela."
            confirmed = f"Outro candle de 15m fecha além da {'máxima' if above else 'mínima'} da reação."
        else:
            early = f"Primeiro fechamento de 15m {direction} da faixa, com a tolerância do plano."
            confirmed = "O candle de 15m imediatamente seguinte mantém o rompimento."
        return "\n".join(["👀 POSSÍVEL ENTRADA • AGUARDAR GATILHO", _identity(plan), _mode(mode),
            strategy, "", f"Região de atenção ≈ {approximate(plan.lower)} a {approximate(plan.upper)}",
            "", "Antecipada: " + early, "Confirmada: " + confirmed,
            "Cada modalidade é avaliada de forma independente.", "",
            f"Preparação válida até {clock(plan.expires_at, now)} ({_remaining(plan.expires_at, now)}).",
            f"Análise: {brt(now)}", footer])

    f = variant.financial
    viable = f.get("status") == ("VIAVEL_SIMULADO" if mode == "paper" else "VIAVEL_REAL") and variant.status == "VALIDA"
    title = ("🟢 GATILHO VÁLIDO PARA SIMULAR" if mode == "paper" else "🟢 ENTRADA VALIDADA") if viable else "🟠 ENTRADA BLOQUEADA"
    if restriction:
        title = "👀 APENAS ACOMPANHAMENTO"
    modality = "Antecipada" if variant.kind == "ANTECIPADA" else "Confirmada"
    lines = [title, _identity(plan), f"{_mode(mode)} • {modality}", strategy, ""]
    if restriction:
        lines += [restriction, "Nenhuma nova entrada indicada.", ""]
    elif not viable:
        reasons = f.get("reasons") or [variant.reason or "AVALIACAO_FINANCEIRA_PENDENTE"]
        lines += ["Motivo: " + " ".join(friendly(r) for r in reasons), "Sem entrada liberada nesta análise.", ""]
    lines += [f"📍 {'Entrada' if viable and not restriction else 'Faixa do plano'}: {number(f.get('entry_low', variant.entry_low))} a {number(f.get('entry_high', variant.entry_high))}",
              f"🛑 Stop: {number(variant.stop)}", f"🎯 Alvo: {number(variant.target)}"]
    if viable and not restriction:
        lines += ["", f"Margem isolada estimada: {money(f.get('margin_usdt'))} • {f.get('leverage', 'indisponível')}x",
                  f"Quantidade: {number(f.get('contracts'))} contratos"]
        loss_pct = f" (-{fixed(D(f['loss_fraction']) * 100)}% da banca)" if f.get("loss_fraction") is not None else ""
        gain_pct = f" (+{fixed(D(f['gain_fraction']) * 100)}% da banca)" if f.get("gain_fraction") is not None else ""
        lines += [f"Perda planejada: -{money(f.get('loss_usdt'))}{loss_pct}",
                  f"Ganho projetado: +{money(f.get('gain_usdt'))}{gain_pct}",
                  f"Retorno/risco líquido: {fixed(f.get('net_rr'))}:1 (pior entrada)",
                  f"Custos estimados: {money(f.get('costs_usdt'))}"]
        if f.get("fee_rate") is not None:
            lines.append(f"Taxa por execução: {fixed(D(f['fee_rate']) * 100)}%")
        if f.get("stop_trigger"):
            lines.append("Disparo do stop: " + ("preço justo (Fair)" if f["stop_trigger"] == "FAIR" else "último preço (Last)"))
    if f.get("assumptions"):
        lines += ["", "Estimativas de taxas, deslizamento e funding; ganho não garantido."]
    if f.get("real_gates"):
        lines.append("Falta validar para uso real: " + "; ".join(friendly(r).rstrip(".") for r in f["real_gates"]) + ".")
    lines += ["", f"⏱ Nova entrada até {clock(plan.expires_at, now)} ({_remaining(plan.expires_at, now)}).",
              f"Gatilho 15m: {clock(variant.triggered_at, now)}"]
    if f.get("quote_at"):
        lines.append("Cotação: " + clock(int(f["quote_at"]), now))
    lines += [f"Análise: {brt(now)}", "A validade se aplica a novas entradas.", footer]
    return "\n".join(lines)


def closed_plans_message(plans: list[Plan], mode: str, now: int) -> str:
    labels = {"EXPIRADO": "janela expirou", "INVALIDADO": "plano invalidado",
              "AMBIGUO": "candle ambíguo", "EVENTO_PASSADO": "movimento encerrado"}
    lines = ["⚪ ATUALIZAÇÃO DOS PLANOS ACOMPANHADOS", _mode(mode), ""]
    for p in plans:
        lines.append(f"• {_identity(p)}: {labels[p.status]}\n  Plano: {p.id}")
    lines += ["", "Sem novas entradas por esses planos.",
              "A expiração não encerra posições já abertas.", f"Análise: {brt(now)}"]
    return "\n".join(lines)


def daily_message(state: dict, report: dict, mode: str) -> str:
    closed = sum(e["action"] == "close" for e in state["journal"])
    current = [p for p in state["plans"].values() if p["status"] not in {"EXPIRADO", "INVALIDADO", "AMBIGUO", "EVENTO_PASSADO"}]
    source = {"OK": "Coleta validada", "PARCIAL": "Coleta parcial", "FALHA": "Falha na coleta"}.get(report["source_status"], "Fonte não validada")
    return "\n".join(["📊 RESUMO DO SCANNER", _mode(mode), f"Análise: {brt(report['analyzed_at'])}", "",
        f"{source} • {report['analyzed_symbols']}/{report['selected_symbols']} ativos",
        f"Planos ainda em acompanhamento: {len(current)}", f"Operações encerradas no diário: {closed}",
        f"Saldo registrado: {money(state['wallet']['balance'])}", "",
        "Sem resultados de operação registrados." if not closed else "O diário contém somente operações informadas.",
        "Sem meta obrigatória de entradas."])


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
