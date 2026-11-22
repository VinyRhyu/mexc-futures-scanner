"""Read-only MEXC futures ORCA universe probe. No accounts, orders or Telegram."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys

from mexc_scanner.market import parse_candles, select_universe
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D


SYMBOL = "ORCA_USDT"
MIN_TURNOVER = D("5000000")
RANK_LIMIT = 50


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def minute_window(client, *, start, end):
    """Validate a historical M1 interval and sum exchange-provided quote turnover.

    Both endpoints are UTC epoch seconds. A complete 24h interval is 1440
    closed one-minute candles: [start, end). No missing bars are fabricated.
    """
    from mexc_scanner.models import seconds

    raw = client._get("/api/v1/contract/kline/" + SYMBOL, {
        "interval": "Min1", "start": start - 60, "end": end,
    })
    timestamps = raw.get("time", []) if isinstance(raw, dict) else []
    amounts = raw.get("amount", []) if isinstance(raw, dict) else []
    result = {"first_requested_utc": iso(start), "end_exclusive_utc": iso(end),
              "expected_candles": (end - start) // 60,
              "returned_candles": len(timestamps)}
    if not isinstance(amounts, list) or len(timestamps) != len(amounts):
        result.update({"status": "NO_USDT_TURNOVER_FIELD",
                       "reason": "MEXC M1 amount field unavailable or arrays misaligned"})
        return result
    by_time = {}
    for ts, amount in zip(timestamps, amounts):
        t = seconds(ts)
        value = D(amount)
        if value < 0:
            raise ValueError("Negative candle transaction amount")
        if start <= t < end:
            if t in by_time and by_time[t] != value:
                raise ValueError("Conflicting duplicate historical M1 candle")
            by_time[t] = value
    expected = list(range(start, end, 60))
    missing = [t for t in expected if t not in by_time]
    result.update({"status": "OK" if not missing else "INCOMPLETE",
                   "covered": len(expected) - len(missing),
                   "missing": len(missing)})
    if not missing:
        result["sum_amount_raw"] = str(sum((by_time[t] for t in expected), Decimal(0)))
        result["turnover_assumption"] = "MEXC kline amount interpreted as USDT turnover; corroborate against recent ticker"
    return result


def main():
    assets = set(json.loads(Path("config/crypto-assets.json").read_text())["assets"])
    if "ORCA" not in assets:
        raise AssertionError("ORCA missing from experimental crypto-asset list")

    client = MexcClient()
    now = client.server_time()
    contracts, tickers = client.contracts(), client.tickers()
    contract = next((row for row in contracts if row.get("symbol") == SYMBOL), None)
    ticker = next((row for row in tickers if row.get("symbol") == SYMBOL), None)

    # Use the same selection function as the scanner. 'before' differs only in
    # whether ORCA is recognized as a cryptoasset.
    before, before_excluded = select_universe(
        contracts, tickers, assets - {"ORCA"}, MIN_TURNOVER, RANK_LIMIT
    )
    after, after_excluded = select_universe(
        contracts, tickers, assets, MIN_TURNOVER, RANK_LIMIT
    )
    full, _ = select_universe(
        contracts, tickers, assets, MIN_TURNOVER, max(1, len(contracts))
    )
    before_reason = next((x["reason"] for x in before_excluded if x["symbol"] == SYMBOL), None)
    after_reason = next((x["reason"] for x in after_excluded if x["symbol"] == SYMBOL), None)
    rank = next((i + 1 for i, x in enumerate(full) if x["symbol"] == SYMBOL), None)

    result = {
        "probe": "orca_universe_v1",
        "server_time_utc": iso(now),
        "symbol": SYMBOL,
        "source": "MEXC_PUBLIC_GET",
        "contracts_seen": len(contracts),
        "tickers_seen": len(tickers),
        "contract_found": bool(contract),
        "ticker_found": bool(ticker),
        "contract": (
            {k: contract.get(k) for k in (
                "state", "baseCoin", "quoteCoin", "settleCoin", "futureType", "preMarket", "typeLabel"
            )} if contract else None
        ),
        "turnover_24h_usdt": str(D(ticker.get("amount24", 0))) if ticker else None,
        "minimum_turnover_usdt": str(MIN_TURNOVER),
        "rank_among_eligible": rank,
        "rank_limit": RANK_LIMIT,
        "selected_before": any(x["symbol"] == SYMBOL for x in before),
        "selected_after": any(x["symbol"] == SYMBOL for x in after),
        "reason_before": before_reason,
        "reason_after": after_reason,
        "candles": {},
    }
    # Historical availability, not a backtest. Check recent candles only.
    if contract and ticker:
        for interval, tf, count in (("Min1", 60, 120), ("Min15", 900, 480), ("Min60", 3600, 240)):
            try:
                rows = client.candles(SYMBOL, interval, count, now)
                parsed = parse_candles(rows, tf, now, count)
                result["candles"][interval] = {
                    "status": "OK",
                    "count": len(parsed),
                    "first_utc": iso(parsed[0].ts),
                    "last_closed_utc": iso(parsed[-1].end),
                }
            except Exception as exc:
                # This is an observation about data coverage, never a signal.
                result["candles"][interval] = {
                    "status": "UNAVAILABLE",
                    "error_type": type(exc).__name__,
                    "reason": str(exc)[:180],
                }

    # The user reported a LONG around 10:45 BRT on 2026-11-21.
    # Check the preceding 24h (no access to the actual fill or fees).
    event_end = int(datetime(2026, 11, 21, 13, 45, tzinfo=timezone.utc).timestamp())
    event_start = event_end - 24 * 3600
    try:
        result["historical_24h_before_example"] = minute_window(
            client, start=event_start, end=event_end
        )
    except Exception as exc:
        result["historical_24h_before_example"] = {
            "status": "UNAVAILABLE", "error_type": type(exc).__name__,
            "reason": str(exc)[:180],
        }

    # Compare M1 `amount` against the live 24h ticker to check units.
    current_end = (now // 60) * 60
    try:
        current = minute_window(
            client, start=current_end - 24 * 3600, end=current_end
        )
        if current.get("status") == "OK" and ticker:
            live_amount = D(ticker.get("amount24", 0))
            if live_amount > 0:
                current["ratio_to_live_ticker_amount24"] = str(
                    D(current["sum_amount_raw"]) / live_amount
                )
        result["current_24h_crosscheck"] = current
    except Exception as exc:
        result["current_24h_crosscheck"] = {
            "status": "UNAVAILABLE", "error_type": type(exc).__name__,
            "reason": str(exc)[:180],
        }

    # Probe shorter historical horizons to characterize API availability.
    for days in (14, 30):
        sample_start = (now // 60) * 60 - days * 24 * 3600
        try:
            result[f"historical_{days}d_sample"] = minute_window(
                client, start=sample_start, end=sample_start + 60 * 60
            )
        except Exception as exc:
            result[f"historical_{days}d_sample"] = {
                "status": "UNAVAILABLE", "error_type": type(exc).__name__,
                "reason": str(exc)[:180],
            }

    # A single distant M1 sample is not evidence of 60 days of complete data.
    old_start = (now // 60) * 60 - 60 * 24 * 3600
    try:
        result["historical_60d_sample"] = minute_window(
            client, start=old_start, end=old_start + 60 * 60
        )
    except Exception as exc:
        result["historical_60d_sample"] = {
            "status": "UNAVAILABLE", "error_type": type(exc).__name__,
            "reason": str(exc)[:180],
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not contract or not ticker:
        print("ORCA symbol missing from current MEXC market catalog or tickers.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
