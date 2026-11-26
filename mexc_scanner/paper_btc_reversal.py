"""Prospective, observation-only replay of the frozen BTC-relative rule."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .market import parse_candles
from .mexc import MexcClient, SourceError
from .models import DataError, seconds


HOUR = 3600
DAY = 24 * HOUR
CADENCE = 2 * HOUR
REENTRY_WAIT = HOUR
HISTORY = 15 * 24 + 1
HOLD = 48
LEVERAGE = 2
RISK = .008
CAP = .75
REWARD = 1.8
COST = .003
STARTING_BALANCE = 1000.
DURATION = 45 * DAY
COMMIT_BUFFER = 120
SYMBOLS = ("AAVE", "ADA", "ARB", "AVAX", "BNB", "BTC", "DOGE", "DOT", "ENA",
           "ETH", "FET", "HYPE", "ICP", "INJ", "LINK", "ONDO", "PEPE", "QNT",
           "SOL", "SUI", "TAO", "TIA", "UNI", "WLD", "XLM", "XRP")


class PaperMarket(MexcClient):
    def spot_turnover(self, asset, decision):
        query = urlencode({"symbol": asset + "USDT", "interval": "60m", "limit": 24,
                           "startTime": (decision - DAY) * 1000, "endTime": decision * 1000 - 1})
        url = "https://api.mexc.com/api/v3/klines?" + query
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=self.timeout) as response:
                    rows = json.load(response)
                amounts = {int(row[0]) // 1000: float(row[7]) for row in rows
                           if (decision - DAY) * 1000 <= int(row[0]) < decision * 1000}
                if (sorted(amounts) != list(range(decision - DAY, decision, HOUR))
                        or any(not math.isfinite(v) or v < 0 for v in amounts.values())):
                    raise SourceError(f"{asset}: volume spot H1 incompleto")
                return sum(amounts.values())
            except (URLError, TimeoutError, ValueError, TypeError, IndexError, KeyError) as exc:
                if attempt == 2:
                    raise SourceError(f"{asset}: falha na fonte spot") from exc
                time.sleep(attempt + 1)

    def closed_hours(self, symbol, count, end, fair=False):
        if fair:
            raw = self._get("/api/v1/contract/kline/fair_price/" + self._symbol(symbol), {
                "interval": "Min60", "start": end - count * HOUR - 1, "end": end - 1})
            if "vol" not in raw:
                raw = {**raw, "vol": [0] * len(raw["time"])}
        else:
            raw = self.candles(symbol, "Min60", count, end)
        return parse_candles(raw, HOUR, end + 10, count)

    def funding_rates(self, symbol, start, end):
        raw = self._get("/api/v1/contract/funding_rate/history", {
            "symbol": symbol, "page_num": 1, "page_size": 100})
        history = sorted((seconds(row["settleTime"]), float(row["fundingRate"]),
                          int(row["collectCycle"])) for row in raw["resultList"] if row["symbol"] == symbol)
        if not history or history[0][0] > start:
            raise SourceError(f"{symbol}: funding sem cobertura na entrada")
        relevant = [(ts, rate, cycle) for ts, rate, cycle in history if start - DAY <= ts < end]
        if (not relevant or any(ts % HOUR or not math.isfinite(rate) or not 1 <= cycle <= 8
                                for ts, rate, cycle in relevant)
                or any(b[0] - a[0] != b[2] * HOUR for a, b in zip(relevant, relevant[1:]))):
            raise SourceError(f"{symbol}: funding incompleto no período")
        last = relevant[-1][0]
        later = next((row[0] for row in history if row[0] > last), None)
        next_at = later if later is not None else seconds(self.funding(symbol)["nextSettleTime"])
        if next_at < end:
            raise SourceError(f"{symbol}: funding recente pendente")
        return {ts: rate for ts, rate, _ in relevant if start < ts < end}


def choose_candidate(series, turnovers):
    """Same ranking, filters and range as the frozen historical detector."""
    btc = series["BTC"]
    btc_day = float(btc[-1].close) / float(btc[-25].close) - 1
    btc_four = float(btc[-1].close) / float(btc[-5].close) - 1
    ranked = []
    for asset, bars in series.items():
        if turnovers[asset] < 4_000_000:
            continue
        close = float(bars[-1].close)
        amplitude = (sum(math.log(float(b.high) / float(b.low)) for b in bars[-337:]) / 337
                     * math.sqrt(24))
        relative = (close / float(bars[-25].close) - 1 - btc_day) / max(.016, amplitude)
        side = 1 if relative < 0 else -1
        recovery = side * (close / float(bars[-5].close) - 1)
        if abs(relative) >= 1 and recovery >= .003 and side * btc_four >= 0:
            ranked.append((abs(relative), asset, side, max(.017, min(.055, amplitude * 1.5))))
    if not ranked:
        return None
    score, asset, side, distance = max(ranked)
    return {"symbol": asset + "_USDT", "side": side, "stop_distance": distance, "score": score}


def discover(market, decision):
    def collect(asset):
        return (asset, market.closed_hours(asset + "_USDT", HISTORY, decision),
                market.spot_turnover(asset, decision))
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(collect, SYMBOLS))
    return choose_candidate({a: b for a, b, _ in rows}, {a: v for a, _, v in rows})


def round_price(value, tick, up):
    units = value / tick
    return (math.ceil(units - 1e-10) if up else math.floor(units + 1e-10)) * tick


def setup(signal, opening, contract, balance):
    tick = float(contract["priceUnit"])
    direction, distance = signal["side"], signal["stop_distance"]
    unit, step, minimum = map(lambda key: float(contract[key]), ("contractSize", "volUnit", "minVol"))
    mmr = float(contract["maintenanceMarginRate"]) + float(contract["liquidationFeeRate"])
    if not (0 <= mmr < 1 / LEVERAGE and min(tick, unit, step, minimum) > 0):
        raise DataError("Metadados do contrato inválidos")
    entry = round_price(float(opening), tick, direction > 0)
    stop = round_price(entry * (1 - direction * distance), tick, direction < 0)
    target = round_price(entry * (1 + direction * distance * REWARD), tick, direction > 0)
    risk = abs(stop / entry - 1) + COST
    budget = min(CAP * balance, RISK * balance / risk)
    quantity = round_price(budget / (unit * entry), step, False)
    if quantity < minimum:
        return None
    return {"entry": entry, "stop": stop, "target": target, "contracts": quantity, "tick": tick,
            "notional": quantity * unit * entry, "maintenance_and_liquidation_fee": mmr}


def outcome(pos, bars, fair, rates):
    entry, side = pos["entry"], pos["side"]
    stop, target = pos["stop"], pos["target"]
    marked, funding = [], 0.
    for b, f in zip(bars, fair, strict=True):
        if b.ts != f.ts or b.ts < pos["entry_at"]:
            raise DataError("Séries H1 Last e Fair desalinhadas")
        if b.ts > pos["entry_at"]:
            funding += side * rates.get(b.ts, 0.) * float(f.open) / entry
        stressed = float(f.low if side > 0 else f.high)
        if 1 / LEVERAGE + side * (stressed / entry - 1) - funding <= pos["maintenance_and_liquidation_fee"] * stressed / entry:
            return (b.end, -1 / LEVERAGE - COST, "LIQ_EST", funding), marked
        o, h, l, c = map(float, (b.open, b.high, b.low, b.close))
        if side * (o - stop) <= 0:
            px, at, why = o, b.ts, "GAP"
        elif side * (o - target) >= 0:
            px, at, why = target, b.ts, "ALVO"
        elif side * ((l if side > 0 else h) - stop) <= 0:
            px, at, why = stop, b.end, "STOP"
        elif side * ((h if side > 0 else l) - target) >= 0:
            px, at, why = target, b.end, "ALVO"
        elif b.end >= pos["entry_at"] + HOLD * HOUR:
            px, at, why = c, b.end, "TEMPO"
        else:
            mark = float(f.close)
            marked.append(side * (mark / entry - 1) - funding - COST / 2 * (1 + mark / entry))
            continue
        px = round_price(px, pos["tick"], side < 0)
        net = side * (px / entry - 1) - funding - COST / 2 * (1 + px / entry)
        return (at, net, why, funding), marked
    return None, marked


def brt_day(ts):
    return (ts - 3 * HOUR) // DAY


def snapshot_contract(market, symbol):
    keys = ("priceUnit", "contractSize", "volUnit", "minVol", "maintenanceMarginRate", "liquidationFeeRate")
    row = next((r for r in market.contracts() if r["symbol"] == symbol), None)
    if row is None:
        raise SourceError(f"{symbol}: contrato ausente no catálogo")
    return {key: str(row[key]) for key in keys}


def new_state(now):
    window = now // CADENCE * CADENCE
    first = window if now < window + HOUR - COMMIT_BUFFER else window + CADENCE
    return {"version": 1, "first_decision": first, "end": first + DURATION, "decisions": [],
            "trades": [], "position": None, "balance": STARTING_BALANCE, "peak": STARTING_BALANCE,
            "max_drawdown": 0.}


def reconcile(state, market, now):
    while _reconcile_next(state, market, now):
        pass


def _reconcile_next(state, market, now):
    pending = [d for d in state["decisions"] if d["status"] == "REGISTRADO"]
    current = pending[0] if pending else None
    position = state["position"]
    signal = position if position is not None else current
    if not signal:
        return False
    start = signal["entry_at"]
    end = min((now - 10) // HOUR * HOUR, start + HOLD * HOUR)
    if end <= start:
        return False
    count = (end - start) // HOUR
    last = market.closed_hours(signal["symbol"], count, end)
    if last[0].ts != start:
        raise SourceError("Candle de entrada ausente")
    if position is None:
        prior = state["trades"][-1] if state["trades"] else None
        if prior and (prior["exit_at"] + REENTRY_WAIT > start
                      or brt_day(prior["entry_at"]) == brt_day(start)):
            current["status"] = "IGNORADO_LIMITE_DA_CARTEIRA"
            return True
        values = setup(current, last[0].open, current["contract"], state["balance"])
        if values is None:
            current["status"] = "IGNORADO_LOTE_MINIMO"
            return True
        position = {**current, **values}
    fair = market.closed_hours(signal["symbol"], count, end, fair=True)
    result, marks = outcome(position, last, fair, market.funding_rates(signal["symbol"], start, end))
    for gain in [*marks, *([result[1]] if result is not None else [])][position.get("marked_hours", 0):]:
        equity = state["balance"] + position["notional"] * gain
        state["peak"] = max(state["peak"], equity)
        state["max_drawdown"] = max(state["max_drawdown"], 1 - equity / state["peak"])
    position["marked_hours"] = len(marks)
    if result is None:
        state["position"] = position
        if current and current["entry_at"] == start:
            current["status"] = "ENTRADA_SIMULADA"
        for scheduled in pending:
            if scheduled["status"] == "REGISTRADO" and scheduled["entry_at"] < end:
                scheduled["status"] = "IGNORADO_LIMITE_DA_CARTEIRA"
        return False
    at, roi, why, funding = result
    pnl = position["notional"] * roi
    state["balance"] += pnl
    state["trades"].append({k: position[k] for k in ("symbol", "side", "entry_at", "entry", "stop", "target", "notional")}
                           | {"exit_at": at, "reason": why, "pnl": pnl, "funding_position": funding})
    state["position"] = None
    if current and current["entry_at"] == start:
        current["status"] = "ENTRADA_SIMULADA"
    return True


def advance(state, market, now):
    reconcile(state, market, now)
    # At most one current decision can still be registered. Late windows count as missed.
    decision = state["decisions"][-1]["decision"] + CADENCE if state["decisions"] else state["first_decision"]
    while decision < state["end"] and decision + 10 <= now:
        entry_at = decision + HOUR
        row = {"decision": decision, "entry_at": entry_at, "status": "PERDIDO_POR_ATRASO"}
        if now < entry_at - COMMIT_BUFFER:
            candidate = discover(market, decision)
            contract = snapshot_contract(market, candidate["symbol"]) if candidate else None
            observed_at = market.server_time()
            if observed_at < entry_at - COMMIT_BUFFER:
                row.update(status="REGISTRADO" if candidate else "SEM_SINAL", observed_at=observed_at)
                if candidate:
                    row.update(candidate, contract=contract)
        state["decisions"].append(row)
        decision += CADENCE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    market = PaperMarket(timeout=12)
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {}
    if state and state["version"] != 1:
        raise DataError("Versão do diário incompatível")
    if args.smoke or not state or time.time() < state["end"] + HOLD * HOUR + HOUR:
        now = market.server_time()
        if abs(now - time.time()) > COMMIT_BUFFER:
            raise SourceError("Relógio da MEXC diverge do executor")
        if args.smoke:
            decision = ((now - 10) // CADENCE) * CADENCE
            discover(market, decision)
            market.closed_hours("BTC_USDT", 24, decision, fair=True)
            market.funding_rates("BTC_USDT", decision - DAY, decision)
            snapshot_contract(market, "BTC_USDT")
            print("Coleta pública H1, spot, Fair, funding e catálogo verificados na MEXC")
            return
        state = state or new_state(now)
        advance(state, market, now)
    trades = state["trades"]
    counts = {status: sum(d["status"] == status for d in state["decisions"])
              for status in sorted({d["status"] for d in state["decisions"]})}
    iso = lambda ts: datetime.fromtimestamp(ts, timezone.utc).isoformat()
    report = (
        "# Reversão relativa ao BTC a 2× em paper, decisões a cada 2h\n\n"
        f"- Universo avaliado: {len(SYMBOLS)} contratos\n"
        f"- Primeira decisão programada em {iso(state['first_decision'])}\n"
        f"- Fim da janela de sinais em {iso(state['end'])}\n"
        f"- Decisões registradas por estado: `{json.dumps(counts)}`\n"
        f"- Posição em simulação: {'aberta' if state['position'] else 'nenhuma'}\n"
        f"- Operações encerradas: {len(trades)}\n"
        f"- Operações com lucro: {sum(t['pnl'] > 0 for t in trades)}\n"
        f"- ROI realizado da banca: {100 * (state['balance'] / STARTING_BALANCE - 1):+.2f}%\n"
        f"- Queda máxima marcada: {100 * state['max_drawdown']:.2f}%\n"
    )
    args.report.write_text(report, encoding="utf-8")
    args.state.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
