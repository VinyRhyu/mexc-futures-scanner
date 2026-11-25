"""Triagem e acompanhamento paper de sinais públicos de quatro alvos."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from statistics import median

from .market import parse_candles
from .mexc import MexcClient, SourceError
from .models import D, DataError, jsonable


COST = D("0.002")
RISK = D("0.35")
MINIMUM_RR = D("1.6")
TARGET_STEP = D("0.02")
TARGET_TOLERANCE = D("0.0005")
MINUTE = 60
WINDOW = 24 * 60 * MINUTE


def evaluate(side: str, leverage: int, entry: Decimal, targets: tuple[Decimal, ...]) -> dict:
    if (side not in {"LONG", "SHORT"} or leverage <= 0 or entry <= 0
            or len(targets) != 4 or any(target <= 0 for target in targets)):
        raise DataError("Informe direção, alavancagem positiva, entrada e quatro alvos positivos")
    if COST >= RISK / leverage:
        raise DataError("O custo estimado consome o risco permitido")

    direction = 1 if side == "LONG" else -1
    factors = [1 + direction * TARGET_STEP * step for step in range(1, 5)]
    base = median(target / factor for target, factor in zip(targets, factors))
    deviation = max(abs(target / base - factor) for target, factor in zip(targets, factors))
    tp1 = targets[0]
    net_reward = leverage * (direction * (tp1 / entry - 1) - COST)
    stop = entry * (1 - direction * (RISK / leverage - COST))
    limit = tp1 / (1 + direction * (COST + RISK * MINIMUM_RR / leverage))
    reasons = []
    if deviation > TARGET_TOLERANCE:
        reasons.append("ESPACAMENTO_DOS_ALVOS_FORA_DA_REGRA")
    if direction * (tp1 - entry) <= 0:
        reasons.append("TP1_ALCANCADO_OU_ULTRAPASSADO")
    elif net_reward < RISK * MINIMUM_RR:
        reasons.append("RETORNO_RISCO_INSUFICIENTE")

    return {
        "entrada_simulada": entry, "stop": stop, "tp1": tp1,
        "risco_estimado_na_margem_pct": RISK * 100,
        "custo_estimado_sobre_posicao_pct": COST * 100,
        "roi_liquido_estimado_no_tp1_pct": net_reward * 100,
        "retorno_sobre_risco": net_reward / RISK,
        "entrada_maxima" if direction == 1 else "entrada_minima": limit,
        "motivos": reasons,
    }


def _outcome(candles, direction, stop, tp1, window_complete):
    for candle in candles:
        if direction * (candle.open - stop) <= 0:
            return "STOP_GAP", candle, candle.open
        if direction * (candle.open - tp1) >= 0:
            return "TP1", candle, tp1
        adverse, favorable = ((candle.low, candle.high) if direction == 1
                              else (candle.high, candle.low))
        if direction * (adverse - stop) <= 0:
            return "STOP", candle, stop
        if direction * (favorable - tp1) >= 0:
            return "TP1", candle, tp1
    return ("PRAZO", candles[-1], candles[-1].close) if window_complete else (
        "ABERTO_EM_SIMULACAO", None, None
    )


def assess(client: MexcClient, symbol: str, published_at: datetime, side: str,
           leverage: int, targets: tuple[Decimal, ...]) -> dict:
    if published_at.utcoffset() is None:
        raise DataError("O horário de publicação deve incluir o fuso, como -03:00")
    if (not symbol.endswith("_USDT") or len(targets) != 4 or leverage <= 0
            or side not in {"LONG", "SHORT"} or any(target <= 0 for target in targets)):
        raise DataError("Informe contrato USDT, direção, alavancagem positiva e quatro alvos positivos")

    now = client.server_time()
    published_seconds = int(published_at.timestamp())
    if published_seconds > now:
        raise DataError("O horário de publicação está no futuro segundo a MEXC")
    first = (published_seconds // MINUTE + 1) * MINUTE
    deadline = first + WINDOW
    end = min((now - 10) // MINUTE * MINUTE, deadline)
    report = {
        "modo": "SIMULACAO", "contrato": symbol, "direcao": side,
        "alavancagem": leverage, "alvos_publicados": targets,
        "publicado_em": published_at.isoformat(),
        "abertura_de_referencia_utc": datetime.fromtimestamp(first, timezone.utc).isoformat(),
        "fim_da_janela_utc": datetime.fromtimestamp(deadline, timezone.utc).isoformat(),
    }
    if end <= first:
        return {**report, "status": "AGUARDANDO_FECHAMENTO_DO_CANDLE_DE_ENTRADA"}

    count = (end - first) // MINUTE
    payload = client.candles(symbol, "Min1", count, end)
    candles = parse_candles(payload, MINUTE, end + 10, count=count)
    if candles[0].ts != first or candles[-1].end != end:
        raise DataError("A série não cobre a abertura de referência e o período solicitado")
    entry = candles[0].open
    values = evaluate(side, leverage, entry, targets)
    if values["motivos"]:
        return {**report, **values, "status": "DESCARTADO"}

    direction = 1 if side == "LONG" else -1
    status, candle, price = _outcome(candles, direction, values["stop"], values["tp1"],
                                     window_complete=end == deadline)
    result = {**report, **values, "status": status}
    if candle is not None:
        result.update(
            candle_da_saida_utc=datetime.fromtimestamp(candle.ts, timezone.utc).isoformat(),
            saida_simulada=price,
            roi_liquido_na_margem_pct=100 * leverage * (direction * (price / entry - 1) - COST),
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol", type=str.upper)
    parser.add_argument("published_at", type=datetime.fromisoformat)
    parser.add_argument("side", choices=("LONG", "SHORT"))
    parser.add_argument("leverage", type=int)
    parser.add_argument("targets", nargs=4)
    args = parser.parse_args()
    try:
        report = assess(MexcClient(), args.symbol, args.published_at, args.side, args.leverage,
                        tuple(D(value.replace(",", ".")) for value in args.targets))
    except (DataError, SourceError) as exc:
        parser.exit(1, f"Avaliação indisponível: {exc}\n")
    print(json.dumps(jsonable(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
