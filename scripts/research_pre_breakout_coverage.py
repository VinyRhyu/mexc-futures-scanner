"""PREDICT V2 E1: read-only MEXC M1 coverage pilot, not a backtest."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import Candle, D, DataError, jsonable, seconds

DAY = 86400
SYMBOLS = ("BTC_USDT", "ETH_USDT", "SOL_USDT", "LINK_USDT", "HYPE_USDT", "ORCA_USDT")
KEYS = ("time", "open", "high", "low", "close", "vol")


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def utc_date(value):
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def parse_window(payload, left, right):
    """Retain valid closed candles only in [left,right); never manufacture gaps."""
    if not isinstance(payload, dict) or any(k not in payload for k in KEYS):
        raise DataError("missing kline arrays")
    if len({len(payload[k]) for k in KEYS}) != 1:
        raise DataError("inconsistent array lengths")
    bars = {}
    duplicate = 0
    for values in zip(*(payload[k] for k in KEYS)):
        ts = seconds(values[0])
        if not left <= ts < right:
            continue
        c = Candle(ts, 60, *(D(v) for v in values[1:]))
        c.validate()
        if ts in bars:
            if bars[ts] != c:
                raise DataError("conflicting duplicate timestamp")
            duplicate += 1
        bars[ts] = c
    return bars, duplicate


def coverage(bars, start, end, btc_times=None):
    expected = (end - start) // 60
    timestamps = {t for t in bars if start <= t < end}
    daily = Counter(day(t) for t in timestamps)
    missing_runs = []
    missing_start = None
    for t in range(start, end, 60):
        if t not in timestamps:
            if missing_start is None:
                missing_start = t
        elif missing_start is not None:
            missing_runs.append((missing_start, t))
            missing_start = None
    if missing_start is not None:
        missing_runs.append((missing_start, end))
    return {
        "expected": expected, "observed": len(timestamps),
        "missing": expected - len(timestamps),
        "coverage_pct": round(100 * len(timestamps) / expected, 5),
        "daily": [{"utc_date": day(t), "observed": daily[day(t)],
                   "missing": 1440 - daily[day(t)]}
                  for t in range(start, end, DAY)],
        "first_ts": min(timestamps, default=None),
        "last_ts": max(timestamps, default=None),
        "gap_count": len(missing_runs),
        "longest_gap_minutes": max(((b-a)//60 for a,b in missing_runs), default=0),
        "gap_intervals_utc_epoch": missing_runs,
        "btc_synchronized": len(timestamps & btc_times) if btc_times is not None else None,
    }


def collect(client, symbol, start, end, chunk_minutes=1800):
    if not 1 <= chunk_minutes <= 1800 or start % 60 or end % 60 or start >= end:
        raise ValueError("invalid collection range")
    bars, failures, duplicates = {}, [], 0
    for left in range(start, end, chunk_minutes * 60):
        right = min(end, left + chunk_minutes * 60)
        count = (right-left)//60
        try:
            data = client.candles(symbol, "Min1", count, right + 10)
            parsed, repeated = parse_window(data, left, right)
            bars.update(parsed)
            duplicates += repeated
        except Exception as exc:
            failures.append({"start": left, "end": right, "type": type(exc).__name__,
                             "reason": str(exc)[:200]})
    return bars, failures, duplicates


def save_raw(path, bars):
    digest = hashlib.sha256()
    with path.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as out:
        for t in sorted(bars):
            line = (json.dumps(jsonable(bars[t]), sort_keys=True, separators=(",", ":"))+"\n").encode()
            digest.update(line)
            out.write(line)
    return digest.hexdigest()


def run(client, start, end, directory, symbols=SYMBOLS):
    if start % DAY or end % DAY or end <= start or symbols[0] != "BTC_USDT":
        raise ValueError("UTC days and BTC-first universe required")
    directory.mkdir(parents=True, exist_ok=True)
    warmup = start - 2 * DAY
    now = client.server_time()
    if end + 10 > now:
        raise ValueError("end not closed at MEXC")
    metadata_errors = []
    try:
        catalog = {c.get("symbol"): c for c in client.contracts()}
    except Exception as exc:
        catalog = {}
        metadata_errors.append({"catalog": str(exc)[:200]})
    try:
        tickers = {c.get("symbol"): c for c in client.tickers()}
    except Exception as exc:
        tickers = {}
        metadata_errors.append({"tickers": str(exc)[:200]})
    report = {"kind": "PRE_BREAKOUT_V2_E1_COVERAGE", "start": start, "end_exclusive": end,
              "warmup_start": warmup, "collected_at": now, "metadata_errors": metadata_errors,
              "universe": "fixed diagnostic pilot; not historical eligibility or representative sample",
              "limitations": ["No point-in-time historical listing, turnover, tick-size or delisting archive verified.",
                              "Missing intervals are not proof of no trading; no imputation.",
                              "No historical OI, funding, trade aggressor or order book validated.",
                              "Only candle integrity and BTC synchronization, not predictions or PNL."],
              "symbols": {}}
    btc_times = None
    for symbol in symbols:
        bars, failures, duplicates = collect(client, symbol, warmup, end)
        if symbol == "BTC_USDT":
            btc_times = set(bars)
        result = coverage(bars, start, end, btc_times)
        result.update({"warmup": coverage(bars, warmup, start, btc_times),
                       "failed_chunks": failures, "identical_duplicates": duplicates,
                       "current_catalog_present": symbol in catalog,
                       "current_contract": catalog.get(symbol),
                       "current_turnover_24h": tickers.get(symbol, {}).get("amount24"),
                       "raw_file": symbol + ".jsonl.gz",
                       "sha256_uncompressed": save_raw(directory/(symbol+".jsonl.gz"), bars)})
        report["symbols"][symbol] = result
        print(json.dumps({"symbol": symbol, "observed": result["observed"],
                          "expected": result["expected"], "coverage_pct": result["coverage_pct"],
                          "failed_chunks": len(failures), "btc_synchronized": result["btc_synchronized"]}),
              flush=True)
    report["total_expected"] = sum(x["expected"] for x in report["symbols"].values())
    report["total_observed"] = sum(x["observed"] for x in report["symbols"].values())
    report["fully_covered_symbols"] = sum(x["missing"] == 0 and x["warmup"]["missing"] == 0
                                          and x["btc_synchronized"] == x["expected"]
                                          for x in report["symbols"].values())
    (directory/"coverage.json").write_text(json.dumps(jsonable(report), indent=2), encoding="utf-8")
    lines = ["# PREDICT V2 E1 — coverage", "", "| Symbol | M1 received | Expected | Coverage % | BTC aligned | Failed chunks |", "|---|---:|---:|---:|---:|---:|"]
    for s, r in report["symbols"].items():
        lines.append(f"| {s} | {r['observed']} | {r['expected']} | {r['coverage_pct']} | {r['btc_synchronized']} | {len(r['failed_chunks'])} |")
    lines += ["", "Pilot only; current universe metadata is not point-in-time eligibility."]
    (directory/"report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-09-25")
    parser.add_argument("--end", default="2026-11-24")
    parser.add_argument("--output", default="reports/predict-v2-coverage")
    args = parser.parse_args()
    result = run(MexcClient(), utc_date(args.start), utc_date(args.end), Path(args.output))
    if not result["total_observed"]:
        raise SystemExit("No historical observations collected")
