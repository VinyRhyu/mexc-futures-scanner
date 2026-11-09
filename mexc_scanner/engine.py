from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import time
from zoneinfo import ZoneInfo

from .config import Config
from .finance import evaluate
from .market import parse_candles, select_universe, structure, aggregate_two_hours
from .mexc import MexcClient, SourceError
from .models import Contract, D, DataError, Plan, jsonable, stable_id
from .reporting import brt, closed_plans_message, daily_message, plan_message
from .state import queue_message
from .strategies import process_symbol


def run_scan(client: MexcClient, config: Config, state: dict, assets: set[str],
             now: int | None = None, symbol_limit: int | None = None) -> tuple[dict, dict]:
    started = int(time.time()) if now is None else now
    wall_start = time.monotonic()
    report = {"mode": config.mode, "analyzed_at": started, "source_status": "FALHA",
              "selected_symbols": 0, "analyzed_symbols": 0, "plans": [], "diagnostics": [],
              "execution": "MANUAL_SEM_ENVIO_DE_ORDENS", "config_fingerprint": config.fingerprint}
    snapshot = {"schema_version": 1, "source": "MEXC_LIVE", "captured_at": started, "market": {}, "contracts": []}
    previous_plans = state["plans"]
    try:
        server = client.server_time()
        if abs(server - started) > 300:
            raise SourceError("Horários local e da fonte divergem mais de cinco minutos")
        catalog, tickers = client.contracts(), client.tickers()
        selected, excluded = select_universe(catalog, tickers, assets, D(config.minimum_turnover),
                                             min(config.universe_size, symbol_limit or config.universe_size))
        report["selected_symbols"], report["excluded"] = len(selected), excluded
        # Planos ativos continuam sendo reconciliados mesmo fora do universo principal.
        active_symbols = {p["symbol"] for p in previous_plans.values()
                          if p["status"] not in {"INVALIDADO", "EXPIRADO", "AMBIGUO", "EVENTO_PASSADO"}}
        selected_symbols = {c["symbol"] for c in selected}
        selected += [c for c in catalog if c.get("symbol") in active_symbols - selected_symbols]
        for symbol in active_symbols - {c["symbol"] for c in selected}:
            report["diagnostics"].append({"symbol": symbol, "reason": "CONTRATO_ATIVO_NAO_ENCONTRADO_NO_CATALOGO"})
        snapshot["contracts"], snapshot["tickers"] = selected, tickers
        def collect(row):
            symbol = row["symbol"]
            h = client.candles(symbol, "Min60", config.hourly_bars, server)
            q = client.candles(symbol, "Min15", config.quarter_bars, server)
            return (row, parse_candles(h, 3600, server, config.hourly_bars),
                    parse_candles(q, 900, server, config.quarter_bars))
        results = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(collect, row): row["symbol"] for row in selected}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    results.append(future.result())
                except (DataError, SourceError, ValueError, KeyError, TypeError) as exc:
                    report["diagnostics"].append({"symbol": symbol, "reason": str(exc)})
        new_plans = dict(previous_plans)
        good_symbols = set()
        for row, hourly, quarter in sorted(results, key=lambda r: r[0]["symbol"]):
            symbol = row["symbol"]
            analysis_time = server + int(time.monotonic() - wall_start)
            try:
                contract = Contract.from_api(row)
                plans = [Plan.from_dict(p) for p in previous_plans.values() if p["symbol"] == symbol]
                plans, cursor = process_symbol(symbol, quarter, hourly, plans,
                    int(state["cursors"].get(symbol, 0)), analysis_time, contract.tick, config)
                active = [p for p in plans if not p.terminal and any(v.status == "VALIDA" for v in p.variants.values())]
                market = {"hourly": hourly, "quarter": quarter,
                          "context_1h": structure(hourly, server),
                          "context_2h": structure(aggregate_two_hours(hourly), server)}
                if active:
                    try:
                        ticker = client.ticker(symbol)
                        book = client.depth(symbol)
                        funding = client.funding(symbol)
                        analysis_time = server + int(time.monotonic() - wall_start)
                        market.update({"ticker": ticker, "depth": book, "funding": funding})
                        for p in active:
                            for v in p.variants.values():
                                v.financial = evaluate(p, v, contract, D(state["wallet"]["balance"]),
                                                       ticker, book, funding, analysis_time, config)
                    except (SourceError, DataError, KeyError, ValueError, TypeError) as exc:
                        for p in active:
                            for v in p.variants.values():
                                v.financial = {"status": "BLOQUEADA", "reasons": ["COTACAO_LIVRO_OU_CUSTOS_INDISPONIVEIS"]}
                        report["diagnostics"].append({"symbol": symbol, "reason": str(exc)})
                for p in plans:
                    new_plans[p.id] = jsonable(p)
                state["cursors"][symbol] = cursor
                snapshot["market"][symbol] = jsonable(market)
                good_symbols.add(symbol)
            except (DataError, KeyError, ValueError, TypeError) as exc:
                report["diagnostics"].append({"symbol": symbol, "reason": str(exc)})
        for pid, row in new_plans.items():
            if row["symbol"] not in good_symbols:
                for v in row.get("variants", {}).values():
                    v["financial"] = {"status": "BLOQUEADA", "reasons": ["COLETA_NAO_VALIDADA_NESTA_RODADA"]}
        state["plans"] = new_plans
        report["analyzed_symbols"] = len(good_symbols & selected_symbols)
        report["source_status"] = "OK" if report["analyzed_symbols"] == report["selected_symbols"] and good_symbols else "PARCIAL"
        if not selected_symbols:
            report["diagnostics"].append({"symbol": "GERAL", "reason": "NENHUM_CONTRATO_ELEGIVEL"})
        state["source_status"] = report["source_status"]
        state["last_success"] = server + int(time.monotonic() - wall_start)
        report["analyzed_at"] = state["last_success"]
        _queue_transitions(state, previous_plans, config, report["analyzed_at"])
    except (SourceError, DataError, KeyError, ValueError, TypeError) as exc:
        report["error"] = str(exc)
        state["source_status"] = "FALHA"
        for p in state["plans"].values():
            for v in p.get("variants", {}).values():
                v["financial"] = {"status": "BLOQUEADA", "reasons": ["FALHA_DA_FONTE_NESTA_RODADA"]}
        for message in state["outbox"].values():
            if message["status"] == "PENDING" and message["category"] == "ENTRY":
                message["status"] = "EXPIRED"
        error_key = stable_id("SOURCE_ERROR", str(exc), started // 86400)
        queue_message(state, error_key, "⚠️ FALHA NA COLETA\n" +
                      ("🧪 SIMULAÇÃO" if config.mode == "paper" else "REAL • EXECUÇÃO MANUAL") +
                      "\n\n" + str(exc) + "\nNenhuma nova entrada liberada.\nÚltima coleta válida: " +
                      (brt(state["last_success"]) if state["last_success"] else "nenhum"), started, started + 3600)
    report["plans"] = [p for p in state["plans"].values() if not p.get("hidden", False)
                        and p["formed_at"] >= report["analyzed_at"] - 86400]
    _daily_summary(state, report, config)
    snapshot["source_status"] = report["source_status"]
    return jsonable(report), jsonable(snapshot)


def _queue_transitions(state: dict, previous: dict, config: Config, now: int) -> None:
    viable = []
    closed = []
    observations_queued = 0

    def was_notified(p: Plan) -> bool:
        ids = [stable_id(p.id, "POSSIVEL")]
        for kind in p.variants:
            ids += [stable_id(p.id, kind, "OBSERVACAO"), stable_id(p.id, kind, "GATILHO", config.mode)]
        return any((m := state["outbox"].get(event)) and
                   (m["status"] == "SENT" or m.get("attempts", 0) > 0) for event in ids)

    for row in state["plans"].values():
        p = Plan.from_dict(row)
        old = previous.get(p.id)
        if old is None and p.status == "POSSIVEL" and observations_queued < config.max_alerts:
            queue_message(state, stable_id(p.id, "POSSIVEL"), plan_message(p, config.mode, now), now, p.expires_at)
            observations_queued += 1
        if p.terminal:
            if old and old["status"] != p.status and was_notified(p) and len(closed) < config.max_alerts:
                closed.append(p)
            continue
        for v in p.variants.values():
            if v.status != "VALIDA":
                continue
            f = v.financial
            if f.get("status") in {"VIAVEL_SIMULADO", "VIAVEL_REAL"}:
                viable.append((p, v))
            elif (old is None or not old.get("variants", {}).get(v.kind)) and observations_queued < config.max_alerts:
                # Não esconder sinal técnico apenas porque a banca não comporta.
                queue_message(state, stable_id(p.id, v.kind, "OBSERVACAO"),
                              plan_message(p, config.mode, now, v), now, p.expires_at, "INFO")
                observations_queued += 1
    viable.sort(key=lambda pair: (-D(pair[1].financial["net_rr"]),
                                 D(pair[1].financial["costs_usdt"]) / D(pair[1].financial["loss_usdt"]),
                                 abs(D(pair[1].financial["entry_vwap"]) - pair[1].reference), pair[0].symbol, pair[1].kind))
    wallet = state["wallet"]
    available = not wallet.get("position") and not wallet.get("pending") and now >= wallet["pause_until"] and not wallet["review_required"]
    for index, (p, v) in enumerate(viable[:config.max_alerts]):
        suffix, restriction = "", ""
        event_id = stable_id(p.id, v.kind, "GATILHO", config.mode)
        if config.mode == "real":
            if index == 0 and available:
                wallet["pending"] = {"plan_id": p.id, "variant": v.kind, "indicated_at": now,
                                     "delivery_event_id": event_id}
                suffix = "\nIndicação selecionada. Registrar entrada ou não execução antes de outra indicação."
            else:
                if wallet.get("position"):
                    restriction = "Já existe uma posição registrada para esta banca."
                elif wallet.get("pending"):
                    restriction = "Outra indicação aguarda registro de entrada ou não execução."
                elif now < wallet["pause_until"]:
                    restriction = "A banca está em pausa até " + brt(wallet["pause_until"]) + "."
                else:
                    restriction = "A banca atingiu uma fase que exige revisão dos parâmetros."
        quote_at = int(v.financial.get("quote_at", 0))
        queue_message(state, event_id, plan_message(p, config.mode, now, v, restriction=restriction) + suffix,
                      now, p.expires_at, "ENTRY", quote_at)
    if closed:
        event_id = stable_id("CLOSED_PLANS", [(p.id, p.status) for p in closed], config.mode)
        queue_message(state, event_id, closed_plans_message(closed, config.mode, now), now, now + 3600)


def _daily_summary(state: dict, report: dict, config: Config) -> None:
    now = report["analyzed_at"]
    local = datetime.fromtimestamp(now, timezone.utc).astimezone(ZoneInfo("America/Sao_Paulo"))
    date = local.date().isoformat()
    if local.hour < 21 or state["last_summary_date"] == date:
        return
    text = daily_message(state, report, config.mode)
    queue_message(state, stable_id("SUMMARY", date, config.mode), text, now, now + 86400)
    state["last_summary_date"] = date
