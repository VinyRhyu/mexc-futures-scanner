"""Exploratory MEXC M1 liquidity cohort; public reads only, no notifications or orders.

Reuses the production M1 consolidation, volume-confirmed signal and financial
evaluator. Historical fills/books/funding are simulated, not observed.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
from statistics import median

from mexc_scanner.config import load_config
from mexc_scanner.market import parse_candles, select_universe
from mexc_scanner.mexc import MexcClient
from mexc_scanner.minute_breakout import MODEL, form_plans, process_minutes
from mexc_scanner.models import Contract, D, jsonable, seconds
from scripts.audit_pullback import close_outcome, paper_quote

END = int(datetime(2026, 11, 21, tzinfo=timezone.utc).timestamp())
START = END - 14 * 86400
LOW_MIN, CORE_MIN = D("200000"), D("5000000")
SAMPLES_PER_COHORT = 6
HORIZON = 4 * 3600


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def fetch_range(client, symbol, tf, begin, end):
    """GET time slices and demand a gap-free, exact-length closed-candle sequence."""
    if begin % tf or end % tf or end <= begin:
        raise ValueError("unaligned historical window")
    interval = {60: "Min1", 900: "Min15", 3600: "Min60"}[tf]
    per_call = 1400 if tf == 60 else 1300
    bars, amount_by_ts = [], {}
    for cursor in range(begin, end, per_call * tf):
        stop = min(end, cursor + per_call * tf)
        raw = client._get("/api/v1/contract/kline/" + symbol, {
            "interval": interval, "start": cursor - tf, "end": stop
        })
        parsed = parse_candles(raw, tf, stop + 10)
        bars.extend(x for x in parsed if cursor <= x.ts < stop)
        if tf == 60:
            stamps = raw.get("time", [])
            amounts = raw.get("amount", [])
            if len(stamps) != len(amounts):
                raise ValueError("M1 amount turnover unavailable")
            for stamp, amount in zip(stamps, amounts):
                t = seconds(stamp)
                if cursor <= t < stop:
                    amount = D(amount)
                    if amount < 0 or (t in amount_by_ts and amount_by_ts[t] != amount):
                        raise ValueError("bad/duplicate M1 amount")
                    amount_by_ts[t] = amount
    by_time = {c.ts: c for c in bars}
    expected = list(range(begin, end, tf))
    if len(by_time) != len(expected) or any(t not in by_time for t in expected):
        raise ValueError(f"incomplete {interval}: {len(by_time)}/{len(expected)}")
    if tf == 60 and (len(amount_by_ts) != len(expected) or
                      any(t not in amount_by_ts for t in expected)):
        raise ValueError("incomplete minute quote turnover")
    ordered = [by_time[t] for t in expected]
    return ordered, ([amount_by_ts[t] for t in expected] if tf == 60 else None)


def select_samples(contracts, tickers, assets):
    """Frozen before results: ORCA + nearest-by-turnover low, and near-threshold core."""
    current = {r["symbol"]: r for r in tickers}
    eligible, _ = select_universe(contracts, tickers, assets | {"ORCA"},
                                  D(0), max(1, len(contracts)))
    allowed = []
    for c in eligible:
        sym = c["symbol"]
        try:
            Contract.from_api(c)
            amount = D(current[sym].get("amount24", 0))
        except (KeyError, ValueError):
            continue
        allowed.append((sym, amount))
    if not any(sym == "ORCA_USDT" for sym, _ in allowed):
        raise ValueError("ORCA unavailable as regular public MEXC contract")
    orca_turnover = next(v for s, v in allowed if s == "ORCA_USDT")
    low = sorted((s, a) for s, a in allowed
                 if LOW_MIN <= a < CORE_MIN and s != "ORCA_USDT")
    low.sort(key=lambda x: (abs(x[1] - orca_turnover), x[0]))
    high = sorted(((s, a) for s, a in allowed if a >= CORE_MIN),
                  key=lambda x: (x[1], x[0]))
    chosen_low = [("ORCA_USDT", orca_turnover)] + low[:SAMPLES_PER_COHORT-1]
    chosen_high = high[:SAMPLES_PER_COHORT]
    if len(chosen_low) < SAMPLES_PER_COHORT or len(chosen_high) < SAMPLES_PER_COHORT:
        raise ValueError("too few eligible candidate symbols")
    return {"lower_liquidity": chosen_low, "core_liquidity": chosen_high}


def candles_consistent(q, m):
    mm = {c.ts: c for c in m}
    checked, mismatches = 0, 0
    for c in q:
        parts = [mm.get(c.ts + i*60) for i in range(15)]
        if any(x is None for x in parts):
            continue
        checked += 1
        if ((parts[0].open, max(x.high for x in parts),
             min(x.low for x in parts), parts[-1].close) !=
                (c.open, c.high, c.low, c.close)):
            mismatches += 1
    return checked, mismatches


def financial_experiment(plan, variant, contract, next_bar, future, cfg):
    """Financial quote at first next-minute opening and 4h pessimistic OHLC exit."""
    if not future or future[0].ts != variant.triggered_at or len(future) != 240:
        return {"status": "UNRESOLVED"}
    f = paper_quote(plan, variant, contract, next_bar.open,
                    variant.triggered_at + 1, cfg)
    if f["status"] != "VIAVEL_SIMULADO":
        return {"status": "FINANCIAL_BLOCK", "reasons": f.get("reasons", [])}
    sign = 1 if plan.side == "LONG" else -1
    entry = next_bar.open * (1 + sign * D(".0001"))
    entry += sign * max(2 * contract.tick, entry * D(cfg.slippage_rate))
    if not D(f["entry_low"]) <= entry <= D(f["entry_high"]):
        return {"status": "NO_FILL_BAND", "net_rr": f.get("net_rr")}
    out = close_outcome(future, plan, variant, contract, f, next_bar.open, cfg, True)
    if "net_r" not in out:
        end = future[-1]
        price = end.close
        slip = max(2*contract.tick, price*D(cfg.slippage_rate))
        fee = D(cfg.taker_fee)
        quantity = D(f["base_quantity"])
        risk = quantity * (sign*(entry-variant.stop) +
                           max(2*contract.tick, entry*D(cfg.slippage_rate)) +
                           max(2*contract.tick, variant.stop*D(cfg.slippage_rate)) +
                           fee*(entry+variant.stop))
        net = quantity*(sign*(price-entry) - slip - fee*(entry+price))
        out.update(outcome="TIME_4H", net_r=net/risk,
                   net_usdt=net, exited_at=iso(end.end))
    return {"status": "FILLED_SIMULATED", "outcome": out["outcome"],
            "net_r": str(out["net_r"]), "net_usdt": str(out["net_usdt"]),
            "exit_at": out["exited_at"],
            "entry_at": iso(variant.triggered_at),
            "net_rr": f.get("net_rr")}



def append_unseen_plans(active, proposed, lifetime_ids):
    """Do not resurrect terminal formations after pruning their live instances."""
    fresh = [p for p in proposed if p.id not in lifetime_ids]
    lifetime_ids.update(p.id for p in fresh)
    active.extend(fresh)
    return len(fresh)


def analyze_symbol(client, contract_row, selected_cohort, cfg, strict=True):
    symbol = contract_row["symbol"]
    contract = Contract.from_api(contract_row)
    # Quarter warmup: 480 M15 bars (5d). Hourly warmup: 240 H1 bars (10d).
    q, _ = fetch_range(client, symbol, 900, START-5*86400, END)
    h, _ = fetch_range(client, symbol, 3600, START-10*86400, END)
    # One day before START is required for causal 24h turnover at first signal.
    m, amounts = fetch_range(client, symbol, 60, START-86400, END+HORIZON)
    checked, mismatches = candles_consistent(q, m)
    if strict and (mismatches or checked < 14*96):
        raise ValueError(f"M1 vs M15 mismatch: {mismatches}/{checked}; expected 1344")
    h_ends, q_ends = [c.end for c in h], [c.end for c in q]
    m_by_ts = {c.ts: i for i, c in enumerate(m)}
    prefix = [D(0)]
    for a in amounts:
        prefix.append(prefix[-1]+a)
    plans, cursor, seen, records = [], 0, set(), []
    lifetime_ids = set()
    formed = 0
    for j, candle in enumerate(m):
        if candle.end < START or candle.end > END:
            continue
        pos_q = bisect_right(q_ends, candle.end)
        if candle.end in q_ends:
            new = form_plans(symbol, q[max(0,pos_q-480):pos_q],
                             contract.tick, START, START)
            formed += append_unseen_plans(plans, new, lifetime_ids)
        if not plans:
            # The M1 source is continuous even when there are no active plans.
            # Moving the clock prevents a future formation looking like a data gap.
            cursor = candle.end
            continue
        pos_h = bisect_right(h_ends, candle.end)
        active_hourly = h[:pos_h]
        plans, cursor, diagnostics = process_minutes(
            symbol, [], active_hourly, m[max(0,j-1):j+1],
            plans, cursor, candle.end + 10, contract.tick, cfg, START
        )
        if diagnostics:
            raise ValueError("Unexpected M1 gap: " + repr(diagnostics))
        for p in plans:
            v = p.variants.get("CONFIRMADA")
            if not v or v.status != "VALIDA" or v.triggered_at != candle.end:
                continue
            key = (p.id, v.triggered_at)
            if key in seen:
                continue
            seen.add(key)
            # Require complete 24-hour turnover strictly known at confirmation.
            left = m_by_ts.get(candle.end - 86400)
            right = m_by_ts.get(candle.end - 60)
            if left is None or right is None or right-left != 1439:
                raise ValueError("historical rolling 24h turnover gap")
            turnover = prefix[right+1]-prefix[left]
            group = ("lower_liquidity" if LOW_MIN <= turnover < CORE_MIN else
                     "core_liquidity" if turnover >= CORE_MIN else "under_minimum")
            later = m[j+1:j+241]
            row = {
                "symbol": symbol, "side": p.side, "plan_id": p.id,
                "signal_at": iso(v.triggered_at), "turnover24": str(turnover),
                "historical_group": group, "sampling_group": selected_cohort,
                "stop": str(v.stop), "target": str(v.target),
                "entry_low": str(v.entry_low), "entry_high": str(v.entry_high),
            }
            for label, trial_cfg in (
                ("cost_base", replace(cfg, initial_balance="50", slippage_rate=".0002")),
                ("cost_stress", replace(cfg, initial_balance="50", slippage_rate=".0010")),
                ("wallet_1usdt", replace(cfg, initial_balance="1", slippage_rate=".0002")),
            ):
                row[label] = financial_experiment(
                    p, v, contract, later[0] if later else None, later,
                    trial_cfg
                ) if len(later) == 240 else {"status": "UNRESOLVED"}
            records.append(row)
        # Remove terminated plans to avoid quadratic scans over old history.
        plans = [p for p in plans if not p.terminal]
    return {
        "symbol": symbol, "selected_cohort": selected_cohort,
        "m1_bars": len(m), "m15_bars": len(q), "h1_bars": len(h),
        "ohlc_checked": checked, "ohlc_mismatches": mismatches,
        "formations_examined": formed, "signals": len(records),
        "records": records,
    }


def wilson(wins, n, z=1.96):
    if not n:
        return None
    p = wins/n
    denominator = 1+z*z/n
    centre = (p+z*z/(2*n))/denominator
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return [round(centre-half, 4),round(centre+half,4)]


def summarize(rows, key):
    vals = [r[key] for r in rows]
    trades = [v for v in vals if v["status"] == "FILLED_SIMULATED"]
    closed = [v for v in trades if v["outcome"] != "UNRESOLVED"]
    wins = [v for v in closed if D(v["net_r"]) > 0]
    return {"confirmed": len(rows),
            "financially_viable_and_filled": len(trades),
            "skips": dict(Counter(v["status"] for v in vals)),
            "outcomes": dict(Counter(v["outcome"] for v in closed)),
            "net_profitable": len(wins),
            "resolved": len(closed),
            "positive_rate": round(len(wins)/len(closed),4) if closed else None,
            "wilson_95pct": wilson(len(wins),len(closed)),
            "mean_net_r": round(sum(float(D(v["net_r"])) for v in closed)/len(closed),4) if closed else None,
            "sum_net_r_independent": round(sum(float(D(v["net_r"])) for v in closed),4)}


def portfolio_one_position(rows, key="cost_base"):
    viable = [r for r in rows if r[key]["status"] == "FILLED_SIMULATED"]
    viable.sort(key=lambda r: (r[key]["entry_at"], r["symbol"], r["plan_id"]))
    picked, blocked, available = [], 0, ""
    capital, peak, drawdown = 0.0, 0.0, 0.0
    for row in viable:
        result = row[key]
        if result["entry_at"] < available:
            blocked += 1
            continue
        val = float(D(result["net_r"]))
        capital += val
        peak = max(peak, capital)
        drawdown = max(drawdown, peak-capital)
        picked.append(row)
        available = result["exit_at"]
    return {"trades": len(picked), "skipped_overlap": blocked,
            "wins": sum(D(r[key]["net_r"]) > 0 for r in picked),
            "sum_net_r": round(capital,4),
            "max_realized_drawdown_r": round(drawdown,4),
            "per_group": {g: summarize([r for r in picked if r["historical_group"] == g], key)
                          for g in ("lower_liquidity", "core_liquidity", "under_minimum")}}


def run():
    cfg = load_config("config/default.toml")
    if cfg.mode != "paper":
        raise ValueError("research requires paper mode")
    client = MexcClient()
    now = client.server_time()
    if now <= END:
        raise ValueError("historical evaluation end must precede now")
    assets = set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
    catalog = {c["symbol"]: c for c in client.contracts()}
    tickers = client.tickers()
    cohorts = select_samples(list(catalog.values()), tickers, assets)
    results, errors = [], {}
    for group in ("lower_liquidity", "core_liquidity"):
        for i, (symbol, volume) in enumerate(cohorts[group],1):
            print(json.dumps({"stage": "fetching", "group": group, "index": i,
                              "symbol": symbol, "turnover_now": str(volume)}), flush=True)
            try:
                obj = analyze_symbol(client, catalog[symbol], group, cfg)
                results.append(obj)
                print(json.dumps({"stage": "analyzed", "symbol": symbol,
                                  "signals": obj["signals"], "ohlc_checked": obj["ohlc_checked"]}),
                      flush=True)
            except (ValueError, ArithmeticError, KeyError, TypeError) as exc:
                errors[symbol] = type(exc).__name__ + ": " + str(exc)[:140]
                print(json.dumps({"stage":"excluded", "symbol":symbol,
                                  "reason":errors[symbol]}),flush=True)
    cases = [r for x in results for r in x["records"]]
    out = {
        "name": "LOW_LIQUIDITY_M1_FIXED_COHORT",
        "created_utc": iso(now),
        "sample_start_utc": iso(START), "sample_end_utc_exclusive": iso(END),
        "sampling_rule": "ORCA + 5 nearest current-turnover low; 6 nearest-above-5M core",
        "sampling_selection_bias": "Current universe and survivor bias; ORCA is a known prior winner",
        "current_turnover_cohorts": {g: [{"symbol":s,"turnover24":str(v)} for s,v in items]
                                      for g,items in cohorts.items()},
        "symbols_complete": len(results), "symbols_excluded": errors,
        "symbols": [{k:v for k,v in r.items() if k!="records"} for r in results],
        "confirmed_signals": len(cases),
        "stats_by_historical_turnover": {
            g: {label: summarize([r for r in cases if r["historical_group"]==g],label)
                for label in ("cost_base","cost_stress","wallet_1usdt")}
            for g in ("lower_liquidity","core_liquidity","under_minimum")
        },
        "sampling_groups": {
            g: summarize([r for r in cases if r["sampling_group"]==g], "cost_base")
            for g in ("lower_liquidity","core_liquidity")
        },
        "portfolio_r": portfolio_one_position(cases),
        "limitations": [
            "Exploratory selected symbols, not representative full futures universe",
            "ORCA known prior winner; these are not independent out-of-sample tests",
            "Historical group uses only rolling M1 turnover known at trigger; current ticker selects symbol sample",
            "MEXC current contract constraints, not archival contract changes",
            "Price OHLC M1, not executable bid/ask or observed depth; assumed spread 0.02pct",
            "Base slip 0.02pct; adverse scenario 0.10pct each fill; taker fee 0.06pct each side",
            "No observed funding, market impact, position margin availability or liquidation",
            "Signals follow production M1 two-close volume>=half rule, frozen levels and causal H1 pivots",
            "Next-minute open is a hypothetical execution inside allowed entry band",
            "Candle touching both exit levels: stop first; 4h time exit valued at last close",
            "Only financial paper sizing 1USDT and 50USDT; dollar PnL independent positions not portfolio",
            "Portfolio sequential uses net R without resizing actual wallet and without exchange fills",
            "Wilson interval applies to potentially dependent, correlated trades and understates uncertainty",
            "Missing candles or M1/M15 disagreement exclude the entire symbol rather than count as no signals",
            "Model parameter choices were previously based on historical data; future prospective validation required",
        ],
        "trades": cases,
    }
    path=Path("reports/liquidity-cohort");path.mkdir(parents=True,exist_ok=True)
    (path/"result.json").write_text(json.dumps(jsonable(out),ensure_ascii=False,indent=2))
    md = [
        "# Coorte exploratória de liquidez (sem ordens)",
        "", "Período de sinais UTC: "+iso(START)+" até "+iso(END)+" (exclusivo).",
        "Modelo M1 de produção, duas confirmações, volume >=50%, níveis congelados.",
        "", "Amostra selecionada por ticker atual, com viés de sobrevivência e ORCA vencedor conhecido.",
        "", "| Giro 24h no gatilho | Sinais | Fills hipotéticos (50 USDT) | Vitórias líquidas | Win rate | Intervalo Wilson* | Média R líquida | Stress R |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |"]
    for group in ("lower_liquidity","core_liquidity","under_minimum"):
        b=out["stats_by_historical_turnover"][group]["cost_base"]
        a=out["stats_by_historical_turnover"][group]["cost_stress"]
        md.append(f"| {group} | {b['confirmed']} | {b['financially_viable_and_filled']} | {b['net_profitable']} | {b['positive_rate']} | {b['wilson_95pct']} | {b['mean_net_r']} | {a['mean_net_r']} |")
    md += ["", "Estresse: slippage 0,10% por execução contra 0,02% base. Taxa taker hipotética 0,06% cada ponta.",
           "Carteira sequencial (sem rebalanceamento): "+str(out["portfolio_r"]), "",
           "*Wilson não corrige dependência entre moedas; interpretar apenas como referência descritiva.",
           "Não extrapolar win rate ou expectativa para execução real.", "",
           "## Cobertura", ""]
    for row in out["symbols"]:
        md.append(f"- {row['symbol']}: {row['signals']} confirmações; OHLC M1/M15 {row['ohlc_checked']} validações")
    for sym, err in errors.items():
        md.append(f"- {sym}: EXCLUÍDO {err}")
    md += ["", "## Limitações", ""] + ["- "+s for s in out["limitations"]]
    (path/"report.md").write_text("\n".join(md)+"\n")
    print("LIQUIDITY_COHORT_SUMMARY="+json.dumps({
        k:out[k] for k in ("symbols_complete","symbols_excluded",
                          "confirmed_signals","stats_by_historical_turnover",
                          "portfolio_r")},ensure_ascii=False),flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a") as f:
            f.write("\n".join(md)+"\n")
    if len(results) < 3 or not cases:
        raise SystemExit("Insufficient complete symbols / confirmed signals; no conclusion")


if __name__=="__main__":
    run()
