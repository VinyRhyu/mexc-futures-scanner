from __future__ import annotations

from decimal import Decimal

from .config import Config
from .market import aggregate_two_hours, atr, latest_breakout, pivots, structure
from .models import Candle, D, Plan, Variant, ceil_step, floor_step, stable_id


def make_variant(plan: Plan, kind: str, c: Candle, hourly: list[Candle], tick: Decimal) -> Variant:
    sign = 1 if plan.side == "LONG" else -1
    e, a, stop = c.close, plan.atr, plan.stop
    assert stop is not None
    if plan.strategy == "CONTINUACAO":
        target = e + sign * D("2.5") * abs(e - stop)
        origin = "PROJECAO_2_5_R"
    else:
        target = plan.level + sign * (plan.upper - plan.lower)
        origin = "PROJECAO_DA_FAIXA"
    known = pivots(hourly, c.end) + pivots(aggregate_two_hours(hourly), c.end)
    obstacles = [p.price for p in known if p.kind == ("HIGH" if sign == 1 else "LOW")
                 and sign * (p.price - e) > 0 and sign * (target - p.price) > 0]
    if obstacles:
        barrier = min(obstacles) if sign == 1 else max(obstacles)
        target = barrier - sign * D("0.10") * a
        origin = "PIVO_CONHECIDO"
    target = floor_step(target, tick) if sign == 1 else ceil_step(target, tick)
    lo, hi = e - D("0.25") * a, e + D("0.25") * a
    threshold = plan.level + sign * a * (D("0.25") if plan.strategy == "CONTINUACAO" else D("0.10"))
    if sign == 1:
        lo = max(lo, threshold + tick)
    else:
        hi = min(hi, threshold - tick)
    lo, hi = ceil_step(lo, tick), floor_step(hi, tick)
    return Variant(kind, c.end, e, lo, hi, stop, target, origin)


def advance_plan(plan: Plan, c: Candle, history: list[Candle], hourly: list[Candle], tick: Decimal) -> None:
    if plan.terminal or c.end <= plan.last_bar:
        return
    if (c.end >= plan.expires_at if plan.entry_started_at else c.end > plan.expires_at):
        plan.status, plan.reason = "EXPIRADO", "PRAZO_ENCERRADO"
        plan.last_bar = c.end
        return
    sign = 1 if plan.side == "LONG" else -1
    had_trigger = bool(plan.variants)
    # Níveis que já existiam são avaliados antes de adicionar um novo gatilho.
    if had_trigger and plan.stop is not None:
        stop_hit = c.low <= plan.stop if sign == 1 else c.high >= plan.stop
        target_hits = [v for v in plan.variants.values() if v.status == "VALIDA" and
                       (c.high >= v.target if sign == 1 else c.low <= v.target)]
        if stop_hit:
            plan.status = "AMBIGUO" if target_hits else "INVALIDADO"
            plan.reason = "STOP_E_ALVO_NO_MESMO_CANDLE" if target_hits else "STOP_ANTES_DA_ENTRADA"
            for v in plan.variants.values():
                v.status = "ENCERRADA"
            plan.last_bar = c.end
            return
        for v in target_hits:
            v.status, v.reason = "EVENTO_PASSADO", "ALVO_JA_ATINGIDO"
    if plan.strategy == "CONTINUACAO":
        invalid_close = c.close < plan.lower if sign == 1 else c.close > plan.upper
        invalid_structure = structure(hourly, c.end) != ("ALTA" if sign == 1 else "BAIXA")
        if invalid_close or invalid_structure:
            plan.status, plan.reason = "INVALIDADO", "PERDA_DA_REGIAO_OU_ESTRUTURA"
        elif not had_trigger:
            touched = c.low <= plan.upper and c.high >= plan.lower
            recovered = c.close > plan.upper if sign == 1 else c.close < plan.lower
            if touched and recovered:
                last = history[-8:]
                plan.stop = (min(x.low for x in last) - D("0.10") * plan.atr if sign == 1 else
                             max(x.high for x in last) + D("0.10") * plan.atr)
                plan.stop = floor_step(plan.stop, tick) if sign == 1 else ceil_step(plan.stop, tick)
                plan.reaction_at = c.end
                plan.entry_started_at = c.end
                plan.expires_at = c.end + 1800
                plan.reaction_extreme = c.high if sign == 1 else c.low
                plan.variants["ANTECIPADA"] = make_variant(plan, "ANTECIPADA", c, hourly, tick)
                plan.revision += 1
                plan.status = "ATIVO"
        elif "CONFIRMADA" not in plan.variants and c.end > plan.reaction_at:
            confirmed = c.close > plan.reaction_extreme if sign == 1 else c.close < plan.reaction_extreme
            if confirmed:
                plan.variants["CONFIRMADA"] = make_variant(plan, "CONFIRMADA", c, hourly, tick)
                plan.revision += 1
                plan.status = "ATIVO"
    else:
        threshold = plan.level + sign * D("0.10") * plan.atr
        outside = c.close > threshold if sign == 1 else c.close < threshold
        back_inside = c.close <= plan.level if sign == 1 else c.close >= plan.level
        if had_trigger and back_inside:
            plan.status, plan.reason = "INVALIDADO", "RETORNO_PARA_CONSOLIDACAO"
        elif not had_trigger and outside:
            # A mínima/máxima deste candle antecede a entrada por fechamento.
            plan.variants["ANTECIPADA"] = make_variant(plan, "ANTECIPADA", c, hourly, tick)
            plan.reaction_at = c.end
            plan.entry_started_at = c.end
            plan.expires_at = c.end + 1800
            plan.status = "ATIVO"
            plan.revision += 1
        elif had_trigger and c.ts == plan.reaction_at and "CONFIRMADA" not in plan.variants:
            if outside:
                plan.variants["CONFIRMADA"] = make_variant(plan, "CONFIRMADA", c, hourly, tick)
                plan.revision += 1
            else:
                plan.observations.append("CONFIRMACAO_SEGUINTE_FALHOU")
    plan.last_bar = c.end


def process_symbol(symbol: str, quarter: list[Candle], hourly: list[Candle],
                   plans: list[Plan], cursor: int, now: int, tick: Decimal,
                   config: Config) -> tuple[list[Plan], int]:
    values = atr(quarter, config.atr_period)
    if not cursor:
        start = max(14, len(quarter) - config.replay_bars)
    else:
        start = next((i for i, c in enumerate(quarter) if c.end > cursor), len(quarter))
        if start == 0 and quarter and cursor < quarter[0].ts:
            raise ValueError("Reconciliação sem histórico suficiente; não ignorar lacuna")
    known_ids = {p.id for p in plans}
    for i in range(start, len(quarter)):
        c = quarter[i]
        a = values[i - 1]
        if a is None or a <= 0:
            continue
        active = [p for p in plans if not p.terminal]
        for p in active:
            advance_plan(p, c, quarter[:i + 1], hourly, tick)
        for side in ("LONG", "SHORT"):
            sign = 1 if side == "LONG" else -1
            if not any(not p.terminal and p.strategy == "CONTINUACAO" and p.side == side for p in plans):
                direction = structure(hourly, c.ts)
                level = latest_breakout(hourly, c.ts, side) if direction == ("ALTA" if sign == 1 else "BAIXA") else None
                if level is not None:
                    lower, upper = level - D("0.25") * a, level + D("0.25") * a
                    previous = quarter[i - 1]
                    approach = (previous.close > level + D("0.75") * a and c.low <= level + D("0.75") * a
                                if sign == 1 else previous.close < level - D("0.75") * a and c.high >= level - D("0.75") * a)
                    fresh_reaction = (c.low <= upper and c.high >= lower and c.close > upper and previous.low > upper
                                      if sign == 1 else c.high >= lower and c.low <= upper and c.close < lower and previous.high < lower)
                    if approach or fresh_reaction:
                        pid = stable_id(symbol, "CONTINUACAO", side, level, c.end)
                        if pid not in known_ids:
                            p = Plan(pid, symbol, "CONTINUACAO", side, c.end, now,
                                     c.end + config.ttl_seconds, a, level, lower, upper, None,
                                     stable_id(symbol, "CONTINUACAO", side, level))
                            plans.append(p)
                            known_ids.add(pid)
                            advance_plan(p, c, quarter[:i + 1], hourly, tick)
            if not any(not p.terminal and p.strategy == "ROMPIMENTO" and p.side == side for p in plans):
                box = quarter[i - 8:i]
                if len(box) != 8:
                    continue
                upper, lower = max(x.high for x in box), min(x.low for x in box)
                width = upper - lower
                high_touches = sum(x.high >= upper - D("0.25") * a for x in box)
                low_touches = sum(x.low <= lower + D("0.25") * a for x in box)
                if a <= width <= 4 * a and high_touches >= 2 and low_touches >= 2:
                    # A janela é formada somente por barras anteriores; o gatilho
                    # atual precisa ser novo, nunca um evento antigo recarimbado.
                    formed_at = box[-1].end
                    pid = stable_id(symbol, "ROMPIMENTO", side, lower, upper, formed_at)
                    if pid not in known_ids:
                        level = upper if sign == 1 else lower
                        stop = level - sign * D("0.50") * a
                        stop = floor_step(stop, tick) if sign == 1 else ceil_step(stop, tick)
                        p = Plan(pid, symbol, "ROMPIMENTO", side, formed_at, now,
                                 formed_at + config.ttl_seconds, a, level, lower, upper, stop,
                                 stable_id(symbol, "ROMPIMENTO", lower, upper))
                        plans.append(p)
                        known_ids.add(pid)
                        advance_plan(p, c, quarter[:i + 1], hourly, tick)
        cursor = c.end
    for p in plans:
        if not p.terminal and now >= p.expires_at:
            p.status, p.reason = "EXPIRADO", "PRAZO_ENCERRADO"
    return plans, cursor
