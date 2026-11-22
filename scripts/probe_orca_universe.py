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

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if not contract or not ticker:
        print("ORCA symbol missing from current MEXC market catalog or tickers.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
