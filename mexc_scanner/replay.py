"""Replay exploratório de OHLC; explicita custos e fills hipotéticos."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from .config import Config
from .finance import evaluate
from .models import Candle, Contract, D, DataError, jsonable
from .strategies import process_symbol


def replay_snapshot(snapshot: dict, config: Config) -> dict:
    if not snapshot.get("market"):
        raise DataError("Captura sem dados: não executar replay de coleta falha")
    # Replay não herda habilitação de uso real nem taxas 'verificadas' atuais.
    config = replace(config, mode="paper", fees_verified=False, account_rules_verified=False)
    contracts = {r["symbol"]: Contract.from_api(r) for r in snapshot.get("contracts", [])}
    portfolios = {}
    for strategy in ("CONTINUACAO", "ROMPIMENTO"):
        for kind in ("ANTECIPADA", "CONFIRMADA"):
            portfolios[strategy + ":" + kind] = {"balance": D(config.initial_balance), "initial": D(config.initial_balance),
                "position": None, "pending": [], "pause_until": 0, "review_required": False,
                "trades": [], "peak_realized": D(config.initial_balance), "max_realized_drawdown": D(0),
                "skips": {}, "ambiguous_trades": 0}
    datasets = {}
    clock = set()
    for symbol, market in snapshot["market"].items():
        if symbol not in contracts:
            continue
        q = [Candle.from_dict(r) for r in market["quarter"]]
        h = [Candle.from_dict(r) for r in market["hourly"]]
        for c in q + h:
            c.validate()
        q.sort(key=lambda c: c.ts)
        h.sort(key=lambda c: c.ts)
        if len(q) < 30 or any(a.end != b.ts for a, b in zip(q, q[1:])):
            raise DataError("Replay exige candles contínuos e histórico suficiente")
        datasets[symbol] = {"q": q, "h": h, "plans": [], "cursor": 0, "bars": {c.ts: (i, c) for i, c in enumerate(q)}}
        clock.update(c.ts for c in q[14:])
    if not datasets:
        raise DataError("Nenhum contrato com dados utilizáveis no replay")
    seen_signals = {key: set() for key in portfolios}
    for ts in sorted(clock):
        for key, portfolio in portfolios.items():
            # Uma posição por carteira; alternativas são carteiras separadas.
            if not portfolio["position"] and not portfolio["review_required"] and ts >= portfolio["pause_until"]:
                candidates = []
                for pid, symbol, plan, variant in portfolio["pending"]:
                    data = datasets[symbol]
                    item = data["bars"].get(ts)
                    if not item or ts + 10 >= plan.expires_at:
                        continue
                    _, c = item
                    # Bid/ask e livro são hipóteses de fill na abertura seguinte.
                    spread = c.open * D("0.0002")
                    ticker = {"bid1": c.open - spread / 2, "ask1": c.open + spread / 2,
                              "timestamp": (ts + 10) * 1000}
                    book = {"asks": [[ticker["ask1"], "1E15", 1]],
                            "bids": [[ticker["bid1"], "1E15", 1]], "timestamp": (ts + 10) * 1000}
                    # Cenário: funding zero. Não é série histórica observada.
                    funding = {"fundingRate": "0", "collectCycle": config.assumed_funding_cycle,
                               "nextSettleTime": (ts + 8 * 3600) * 1000}
                    f = evaluate(plan, variant, contracts[symbol], portfolio["balance"], ticker, book, funding, ts + 10, config)
                    if f["status"] == "VIAVEL_SIMULADO":
                        candidates.append((plan, variant, f, c))
                    else:
                        reason = ",".join(f["reasons"])
                        portfolio["skips"][reason] = portfolio["skips"].get(reason, 0) + 1
                candidates.sort(key=lambda r: (-D(r[2]["net_rr"]), r[0].symbol))
                if candidates:
                    plan, variant, f, c = candidates[0]
                    sign = 1 if plan.side == "LONG" else -1
                    entry = c.open * (1 + sign * D("0.0001"))
                    entry += sign * max(contracts[plan.symbol].tick * 2, entry * D(config.slippage_rate))
                    if D(f["entry_low"]) <= entry <= D(f["entry_high"]):
                        entry_fee = D(f["base_quantity"]) * entry * D(config.taker_fee)
                        portfolio["position"] = {"symbol": plan.symbol, "side": plan.side, "plan_id": plan.id,
                            "entry": entry, "entered_at": ts + 10, "quantity": D(f["base_quantity"]),
                            "stop": variant.stop, "target": variant.target, "balance_before": portfolio["balance"],
                            "planned_risk": D(f["loss_usdt"]), "entry_fee": entry_fee}
                        portfolio["balance"] -= entry_fee
                    else:
                        portfolio["skips"]["FILL_FORA_DA_FAIXA"] = portfolio["skips"].get("FILL_FORA_DA_FAIXA", 0) + 1
            portfolio["pending"] = []
            pos = portfolio["position"]
            if pos and ts in datasets[pos["symbol"]]["bars"]:
                _, c = datasets[pos["symbol"]]["bars"][ts]
                sign = 1 if pos["side"] == "LONG" else -1
                stop_hit = c.low <= pos["stop"] if sign == 1 else c.high >= pos["stop"]
                target_hit = c.high >= pos["target"] if sign == 1 else c.low <= pos["target"]
                if stop_hit or target_hit:
                    ambiguous = stop_hit and target_hit
                    if ambiguous:
                        portfolio["ambiguous_trades"] += 1
                    level = pos["stop"] if stop_hit else pos["target"]
                    # Gap adverso na abertura do candle passa pelo stop.
                    if stop_hit:
                        level = min(level, c.open) if sign == 1 else max(level, c.open)
                    slip = max(contracts[pos["symbol"]].tick * 2, level * D(config.slippage_rate))
                    exit_price = level - sign * slip
                    net = sign * pos["quantity"] * (exit_price - pos["entry"]) - pos["entry_fee"] - pos["quantity"] * exit_price * D(config.taker_fee)
                    portfolio["balance"] = max(D(0), portfolio["balance"] + net + pos["entry_fee"])
                    full = pos["planned_risk"] >= D("0.95") * D(config.risk_fraction) * pos["balance_before"]
                    if (stop_hit and full) or net <= -D(config.risk_fraction) * pos["balance_before"]:
                        portfolio["pause_until"] = c.end + 86400
                    trade = dict(pos, exit=exit_price, exited_at=c.end, net_usdt=net,
                                 balance_after=portfolio["balance"], ambiguous=ambiguous,
                                 exit_reason="STOP_PESSIMISTA_AMBIGUO" if ambiguous else "STOP" if stop_hit else "TARGET")
                    portfolio["trades"].append(trade)
                    portfolio["position"] = None
                    portfolio["peak_realized"] = max(portfolio["peak_realized"], portfolio["balance"])
                    drawdown = 1 - portfolio["balance"] / portfolio["peak_realized"]
                    portfolio["max_realized_drawdown"] = max(portfolio["max_realized_drawdown"], drawdown)
                    portfolio["review_required"] = portfolio["balance"] >= D(config.phase_target)
        for symbol, data in datasets.items():
            if ts not in data["bars"]:
                continue
            index, c = data["bars"][ts]
            data["plans"], data["cursor"] = process_symbol(symbol, data["q"][:index + 1], data["h"],
                data["plans"], data["cursor"], c.end + 10, contracts[symbol].tick, config)
            for p in data["plans"]:
                if p.terminal:
                    continue
                for kind, v in p.variants.items():
                    key = p.strategy + ":" + kind
                    signature = (p.id, kind)
                    if v.status == "VALIDA" and signature not in seen_signals[key]:
                        portfolios[key]["pending"].append((p.id, symbol, p, v))
                        seen_signals[key].add(signature)
    lines = ["# Replay exploratório", "", "**Simulação com hipóteses; não demonstra rentabilidade.**", "",
             "| Estratégia/modalidade | Operações encerradas | Saldo realizado (USDT) | Queda máxima realizada | Ambíguas |",
             "| --- | --- | --- | --- | --- |"]
    for key, p in portfolios.items():
        lines.append(f"| {key} | {len(p['trades'])} | {p['balance']:.6f} | {p['max_realized_drawdown']:.2%} | {p['ambiguous_trades']} |")
        p["pending"] = []
    limitations = ["Universo e regras do contrato da captura atual; possível viés de sobrevivência.",
        "Entradas na abertura seguinte com spread assumido de 0,02%, deslizamento e taxa configurados.",
        "Livro histórico sem observações: profundidade infinita é uma hipótese, não verificação de liquidez.",
        "Funding zero neste cenário; custos históricos de funding não foram recuperados.",
        "Stop e alvo no mesmo candle usam o stop primeiro; a sequência real permanece desconhecida.",
        "Queda máxima calculada sobre saldo realizado; não inclui todo o caminho intraposição.",
        "Carteiras de estratégias/modalidades são independentes; seus lucros não devem ser somados.",
        "Sem ajuste fora da amostra e acompanhamento prospectivo, não há taxa de acerto validada nem prazo para atingir a meta."]
    lines += ["", "## Hipóteses e limites", ""] + ["- " + x for x in limitations]
    return jsonable({"data_origin": snapshot.get("source", "DESCONHECIDA"), "kind": "EXPLORATORY_SIMULATION",
                     "portfolios": portfolios, "limitations": limitations, "markdown": "\n".join(lines) + "\n"})
