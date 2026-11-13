from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, ROUND_CEILING

from .config import Config
from .mexc import quote_is_fresh
from .models import Contract, D, DataError, Plan, Variant, ceil_step, floor_step, seconds


def _depth_price(depth: dict, side: str, contracts: Decimal) -> Decimal | None:
    rows = depth.get("asks" if side == "LONG" else "bids", [])
    rows = sorted(rows, key=lambda r: D(r[0]), reverse=side == "SHORT")
    left, total = contracts, Decimal(0)
    for row in rows:
        if len(row) < 2:
            raise DataError("Linha de livro inválida")
        price, available = D(row[0]), D(row[1])
        if price <= 0 or available < 0:
            raise DataError("Preço/quantidade do livro inválidos")
        take = min(left, available)
        total += take * price
        left -= take
        if left <= 0:
            return total / contracts
    return None


def _funding_cost_rate(side: str, funding: dict, now: int, config: Config) -> tuple[Decimal, list[str]]:
    notes = []
    cycle = int(funding.get("collectCycle", config.assumed_funding_cycle))
    if cycle <= 0:
        raise DataError("Ciclo de funding inválido")
    if "collectCycle" not in funding:
        notes.append("CICLO_FUNDING_ASSUMIDO")
    rate = D(funding.get("fundingRate", 0))
    if "fundingRate" not in funding:
        notes.append("FUNDING_NAO_VERIFICADO")
    sign = 1 if side == "LONG" else -1
    pay_rate = max(rate * sign, Decimal(0))
    end = now + config.funding_hours * 3600
    if funding.get("nextSettleTime"):
        next_time = seconds(funding["nextSettleTime"])
        if next_time < now:
            notes.append("CALENDARIO_FUNDING_DESATUALIZADO")
            count = int((D(config.funding_hours) / cycle).to_integral_value(rounding=ROUND_CEILING))
        else:
            count = 0 if next_time > end else 1 + (end - next_time) // (cycle * 3600)
    else:
        count = int((D(config.funding_hours) / cycle).to_integral_value(rounding=ROUND_CEILING))
        notes.append("CALENDARIO_FUNDING_ASSUMIDO")
    return pay_rate * count, notes


def evaluate(plan: Plan, variant: Variant, contract: Contract, balance: Decimal,
             ticker: dict, depth: dict, funding: dict, now: int, config: Config) -> dict:
    result = _evaluate_band(plan, variant, contract, balance, ticker, depth, funding, now, config)
    # O melhor preço pode exigir mais contratos para usar o orçamento de risco.
    # Seu custo/lote inviável não prova que a cotação atual também é inviável.
    if result.get('reasons') not in (["CUSTO_RELATIVO_ELEVADO"], ["QUANTIDADE_ACIMA_DO_CONTRATO"]):
        return result
    sign = 1 if plan.side == 'LONG' else -1
    current = D(ticker['ask1'] if sign == 1 else ticker['bid1'])
    low, high = floor_step(current, contract.tick), ceil_step(current, contract.tick)
    if not variant.entry_low <= low <= high <= variant.entry_high:
        return result
    if (low, high) == (variant.entry_low, variant.entry_high):
        return result
    narrowed = replace(variant, entry_low=low, entry_high=high)
    # Uma única tentativa, com todos os controles e o livro novamente avaliados.
    retry = _evaluate_band(plan, narrowed, contract, balance, ticker, depth, funding, now, config)
    if retry.get('status') in {'VIAVEL_SIMULADO', 'VIAVEL_REAL'}:
        retry['range_adjustment'] = 'FAIXA_RESTRITA_A_COTACAO_ATUAL'
        retry['original_entry_low'], retry['original_entry_high'] = variant.entry_low, variant.entry_high
        return retry
    return result


def _evaluate_band(plan: Plan, variant: Variant, contract: Contract, balance: Decimal,
                   ticker: dict, depth: dict, funding: dict, now: int, config: Config) -> dict:
    result = {"status": "BLOQUEADA", "reasons": [], "assumptions": [], "mode": config.mode}

    def blocked(reason: str) -> dict:
        result["reasons"].append(reason)
        return result

    if variant.status != "VALIDA" or plan.terminal or now >= plan.expires_at:
        return blocked("PLANO_NAO_ATUAL")
    if balance <= 0:
        return blocked("SALDO_NAO_POSITIVO")
    if not quote_is_fresh(ticker, now, config.quote_max_age):
        return blocked("DADOS_NAO_VERIFICADOS")
    if not depth.get("timestamp") or not -10 <= now - seconds(depth["timestamp"]) <= config.quote_max_age:
        return blocked("LIVRO_NAO_ATUAL")
    if variant.entry_low > variant.entry_high:
        return blocked("PRECO_FORA_DO_PLANO")
    if min(variant.entry_low, variant.entry_high, variant.stop, variant.target) <= 0:
        return blocked("GEOMETRIA_DE_PRECOS_INVALIDA")
    sign = 1 if plan.side == "LONG" else -1
    fee, slip = D(config.taker_fee), D(config.slippage_rate)
    fund_rate, assumptions = _funding_cost_rate(plan.side, funding, now, config)
    result["assumptions"] = assumptions + ["FUNDING_FUTURO_MANTIDO_POR_6H", "DESLIZAMENTO_ESTIMADO"]
    if not config.fees_verified:
        result["assumptions"].append("TAXA_SIMULADA_NAO_PESSOAL")
    stop, target, tick = variant.stop, variant.target, contract.tick

    def units(entry: Decimal) -> tuple[Decimal, Decimal, Decimal]:
        entry_slip = max(2 * tick, slip * entry)
        stop_slip = max(2 * tick, slip * stop)
        target_slip = max(2 * tick, slip * target)
        cost_stop = fee * (entry + stop) + entry_slip + stop_slip + entry * fund_rate
        cost_target = fee * (entry + target) + entry_slip + target_slip + entry * fund_rate
        loss = sign * (entry - stop) + cost_stop
        gain = sign * (target - entry) - cost_target
        return loss, gain, max(cost_stop, cost_target)

    # 10% por entrada é a exposição planejada; 30% permanece o limite absoluto
    # e o gatilho de pausa do diário. 60% é meta de acompanhamento, não filtro.
    budget = balance * min(D(config.risk_fraction), D("0.10"))
    cost_budget = balance * D(config.risk_fraction) * D(config.max_cost_fraction)

    def ratio_ok(entry: Decimal) -> bool:
        loss, gain, _ = units(entry)
        return sign * (entry - stop) > 0 and sign * (target - entry) > 0 and loss > 0 and gain / loss >= D(config.minimum_rr)

    def quantity_at(entry: Decimal) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        loss, gain, costs = units(entry)
        volume = max(floor_step(budget / (loss * contract.size), contract.volume_step),
                     ceil_step(contract.min_volume, contract.volume_step))
        q = volume * contract.size
        return volume, q * loss, q * gain, q * costs

    def admissible(entry: Decimal) -> bool:
        if not ratio_ok(entry):
            return False
        volume, loss, _, costs = quantity_at(entry)
        return loss <= budget and costs <= cost_budget and volume <= contract.max_volume

    # Reduzir a faixa para preservar RR no pior preço; não mover SL/TP.
    low_i = int((variant.entry_low / tick).to_integral_value(rounding=ROUND_CEILING))
    high_i = int(variant.entry_high // tick)
    best = D(low_i if sign == 1 else high_i) * tick
    if low_i > high_i or not ratio_ok(best):
        return blocked("RETORNO_RISCO_INSUFICIENTE")
    best_volume, best_loss, _, best_costs = quantity_at(best)
    if best_loss > budget:
        return blocked("LOTE_MINIMO_OU_META_EXCEDE_RISCO")
    if best_costs > cost_budget:
        return blocked("CUSTO_RELATIVO_ELEVADO")
    if best_volume > contract.max_volume:
        return blocked("QUANTIDADE_ACIMA_DO_CONTRATO")
    left, right = low_i, high_i
    if sign == 1:
        while left < right:
            mid = (left + right + 1) // 2
            if admissible(D(mid) * tick):
                left = mid
            else:
                right = mid - 1
        high_i = left
    else:
        while left < right:
            mid = (left + right) // 2
            if admissible(D(mid) * tick):
                right = mid
            else:
                left = mid + 1
        low_i = left
    low, high = D(low_i) * tick, D(high_i) * tick
    entry = high if sign == 1 else low
    loss_unit, gain_unit, costs_unit = units(entry)
    volume = max(floor_step(budget / (loss_unit * contract.size), contract.volume_step),
                 ceil_step(contract.min_volume, contract.volume_step))
    quantity = volume * contract.size
    loss, gain, costs = quantity * loss_unit, quantity * gain_unit, quantity * costs_unit
    result.update({"entry_low": low, "entry_high": high, "worst_entry": entry, "contract_size": contract.size,
                   "contracts": volume, "base_quantity": quantity, "stop": stop, "target": target,
                   "loss_usdt": loss, "gain_usdt": gain, "loss_fraction": loss / balance,
                   "gain_fraction": gain / balance, "daily_goal_fraction": D(config.gain_fraction),
                   "daily_goal_reachable_in_one_trade": gain / balance >= D(config.gain_fraction),
                   "net_rr": gain / loss,
                   "costs_usdt": costs, "fee_rate": fee, "funding_cost_rate": fund_rate,
                   "quote_at": seconds(ticker["timestamp"]), "evaluated_at": now,
                   "stop_trigger": "FAIR" if contract.stop_only_fair else "LAST"})
    if volume > contract.max_volume:
        return blocked("QUANTIDADE_ACIMA_DO_CONTRATO")
    if loss > budget:
        return blocked("LOTE_MINIMO_OU_META_EXCEDE_RISCO")
    if costs > cost_budget:
        return blocked("CUSTO_RELATIVO_ELEVADO")
    current = D(ticker["ask1"] if sign == 1 else ticker["bid1"])
    if not low <= current <= high:
        return blocked("PRECO_FORA_DO_PLANO")
    vwap = _depth_price(depth, plan.side, volume)
    if vwap is None:
        return blocked("PROFUNDIDADE_INSUFICIENTE")
    if not low <= vwap <= high:
        return blocked("EXECUCAO_FORA_DA_FAIXA")
    notional = quantity * entry
    available_margin = balance - costs
    if available_margin <= 0:
        return blocked("CUSTOS_CONSOMEM_SALDO")
    leverage = max(1, int((notional / available_margin).to_integral_value(rounding=ROUND_CEILING)))
    try:
        mmr, tier_leverage = contract.margin_tier(volume)
    except DataError:
        return blocked("NIVEL_DE_RISCO_INDISPONIVEL")
    if leverage > min(config.max_leverage, tier_leverage):
        return blocked("MARGEM_OU_TETO_DE_ALAVANCAGEM")
    margin = notional / leverage
    liq_fee = contract.liquidation_fee
    if liq_fee is None:
        result["assumptions"].append("TAXA_LIQUIDACAO_ASSUMIDA")
        liq_fee = fee
    if mmr + liq_fee >= 1:
        return blocked("PARAMETROS_DE_LIQUIDACAO_INVALIDOS")
    # Contratos lineares USDT, margem isolada, taxas reservadas fora da margem.
    liquidation = ((notional - margin) / (quantity * (1 - mmr - liq_fee)) if sign == 1 else
                   (notional + margin) / (quantity * (1 + mmr + liq_fee)))
    distance = sign * (entry - liquidation)
    result.update({"leverage": leverage, "margin_usdt": margin,
                   "liquidation_estimate": liquidation, "entry_vwap": vwap})
    if distance <= 0 or distance < D(config.liquidation_buffer) * abs(entry - stop):
        return blocked("STOP_PROXIMO_DA_LIQUIDACAO")
    gates = []
    if not config.fees_verified:
        gates.append("TAXA_PESSOAL_NAO_VERIFICADA")
    if not config.account_rules_verified or contract.liquidation_fee is None:
        gates.append("REGRAS_DA_CONTA_NAO_VERIFICADAS")
    if contract.stop_only_fair and not config.fair_trigger_verified:
        gates.append("GATILHO_FAIR_NAO_VERIFICADO")
    if assumptions:
        gates.append("FUNDING_NAO_VERIFICADO")
    result["real_gates"] = gates
    if config.mode == "real" and gates:
        return blocked("VERIFICACOES_PARA_REAL_PENDENTES")
    result["status"] = "VIAVEL_SIMULADO" if config.mode == "paper" else "VIAVEL_REAL"
    return result
