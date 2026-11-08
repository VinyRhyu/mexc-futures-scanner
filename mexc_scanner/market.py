from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .models import Candle, D, DataError, Pivot, seconds


def parse_candles(data: dict, tf: int, server_time: int, count: int | None = None) -> list[Candle]:
    keys = ("time", "open", "high", "low", "close", "vol")
    if any(k not in data for k in keys):
        raise DataError("Resposta de candles incompleta")
    if len({len(data[k]) for k in keys}) != 1:
        raise DataError("Arrays de candles têm tamanhos diferentes")
    unique = {}
    for values in zip(*(data[k] for k in keys)):
        ts, op, hi, lo, cl, vol = values
        c = Candle(seconds(ts), tf, D(op), D(hi), D(lo), D(cl), D(vol))
        c.validate()
        if c.end + 10 > server_time:
            continue
        if c.ts in unique and unique[c.ts] != c:
            raise DataError("Candles duplicados conflitantes")
        unique[c.ts] = c
    result = sorted(unique.values(), key=lambda c: c.ts)
    if count is not None:
        result = result[-count:]
    if count is not None and len(result) < count:
        raise DataError(f"Histórico insuficiente: {len(result)}/{count}")
    for a, b in zip(result, result[1:]):
        if a.end != b.ts:
            raise DataError("Lacuna temporal nos candles")
    expected_end = ((server_time - 10) // tf) * tf
    if result and result[-1].end < expected_end:
        raise DataError("Último candle fechado indisponível")
    return result


def aggregate_two_hours(hourly: list[Candle]) -> list[Candle]:
    groups = defaultdict(list)
    for c in hourly:
        if c.tf != 3600:
            raise DataError("Agregação de 2h exige candles de 1h")
        groups[(c.ts // 7200) * 7200].append(c)
    result = []
    for start, items in sorted(groups.items()):
        items = sorted(items, key=lambda x: x.ts)
        if len(items) == 2 and [x.ts for x in items] == [start, start + 3600]:
            result.append(Candle(start, 7200, items[0].open, max(x.high for x in items),
                                 min(x.low for x in items), items[-1].close,
                                 sum((x.volume for x in items), Decimal(0))))
    return result


def atr(candles: list[Candle], period: int = 14) -> list[Decimal | None]:
    result = []
    trs = []
    current = None
    for i, c in enumerate(candles):
        tr = c.high - c.low
        if i:
            tr = max(tr, abs(c.high - candles[i - 1].close), abs(c.low - candles[i - 1].close))
        trs.append(tr)
        if i == period - 1:
            current = sum(trs, Decimal(0)) / period
        elif i >= period:
            current = (current * (period - 1) + tr) / period
        result.append(current)
    return result


def pivots(candles: list[Candle], known_at: int) -> list[Pivot]:
    result = []
    for i in range(2, len(candles) - 2):
        c = candles[i]
        learned = candles[i + 2].end
        if learned > known_at:
            continue
        neighbors = candles[i - 2:i] + candles[i + 1:i + 3]
        if all(c.high > n.high for n in neighbors):
            result.append(Pivot("HIGH", c.high, c.ts, learned))
        if all(c.low < n.low for n in neighbors):
            result.append(Pivot("LOW", c.low, c.ts, learned))
    return result


def structure(candles: list[Candle], at: int) -> str:
    known = pivots(candles, at)
    highs = [p.price for p in known if p.kind == "HIGH"][-2:]
    lows = [p.price for p in known if p.kind == "LOW"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "DESCONHECIDA"
    if highs[1] > highs[0] and lows[1] > lows[0]:
        return "ALTA"
    if highs[1] < highs[0] and lows[1] < lows[0]:
        return "BAIXA"
    return "INDEFINIDA"


def latest_breakout(hourly: list[Candle], at: int, side: str) -> Decimal | None:
    bars = [c for c in hourly if c.end <= at]
    kind = "HIGH" if side == "LONG" else "LOW"
    for i in range(len(bars) - 1, max(0, len(bars) - 13), -1):
        prior, c = bars[i - 1], bars[i]
        candidates = [p for p in pivots(bars[:i], c.ts) if p.kind == kind]
        if not candidates:
            continue
        level = candidates[-1].price
        if side == "LONG" and prior.close <= level < c.close:
            return level
        if side == "SHORT" and prior.close >= level > c.close:
            return level
    return None


def select_universe(contracts: list[dict], tickers: list[dict], crypto_assets: set[str],
                    minimum_turnover: Decimal, limit: int) -> tuple[list[dict], list[dict]]:
    quotes = {str(q["symbol"]): q for q in tickers}
    eligible, excluded = [], []
    for c in contracts:
        symbol = str(c.get("symbol", ""))
        reason = ""
        asset = str(c.get("baseCoin", ""))
        if int(c.get("state", -1)) != 0:
            reason = "CONTRATO_INATIVO"
        elif c.get("settleCoin") != "USDT" or c.get("quoteCoin") != "USDT":
            reason = "FORA_USDT"
        elif int(c.get("futureType", 1)) != 1 or c.get("preMarket", False):
            reason = "FORA_PERPETUO_REGULAR"
        elif int(c.get("typeLabel", 0) or 0) in {1, 2}:
            reason = "NAO_CRIPTO"
        elif asset not in crypto_assets:
            reason = "CLASSIFICACAO_PENDENTE"
        elif symbol not in quotes:
            reason = "TICKER_AUSENTE"
        elif D(quotes[symbol].get("amount24", 0)) < minimum_turnover:
            reason = "VOLUME_FINANCEIRO_INSUFICIENTE"
        if reason:
            excluded.append({"symbol": symbol, "reason": reason})
        else:
            eligible.append(c)
    eligible.sort(key=lambda c: (-D(quotes[c["symbol"]]["amount24"]), c["symbol"]))
    excluded.extend({"symbol": c["symbol"], "reason": "FORA_DOS_MAIORES_ELEGIVEIS"}
                    for c in eligible[limit:])
    return eligible[:limit], excluded
