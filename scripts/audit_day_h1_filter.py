"""One frozen-cohort H1 EMA20 filter experiment; never sends or trades."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json

from mexc_scanner.models import Candle, D, jsonable


def hourly_context(bars, signal):
    # Match the collector's closed-candle availability buffer. Delivery delay
    # never grants this filter access to another H1 candle.
    known = [b for b in bars if b.end + 10 <= signal]
    if len(known) < 240:
        raise ValueError('Require 240 known H1 bars before each signal')
    if any(a.end != b.ts for a, b in zip(known, known[1:])):
        raise ValueError('H1 gap before signal')
    ema = sum((b.close for b in known[:20]), D(0)) / 20
    alpha = D(2) / 21
    previous = None
    for b in known[20:]:
        previous, ema = ema, alpha * b.close + (1-alpha) * ema
    close = known[-1].close
    direction = ('LONG' if close > ema and ema > previous else
                 'SHORT' if close < ema and ema < previous else 'NEUTRAL')
    return dict(known_bars=len(known), known_end=known[-1].end,
                last_close=close, ema20=ema, previous_ema20=previous,
                direction=direction)


def validate_aggregation(hourly, minute):
    groups = defaultdict(list)
    for b in minute:
        groups[(b.ts // 3600) * 3600].append(b)
    checked = 0
    for h in hourly:
        group = sorted(groups[h.ts], key=lambda b: b.ts)
        if len(group) != 60:
            continue
        if group[0].ts != h.ts or group[-1].end != h.end:
            raise ValueError('Incomplete M1 hour')
        observed = (group[0].open, max(b.high for b in group),
                    min(b.low for b in group), group[-1].close)
        if observed != (h.open, h.high, h.low, h.close):
            raise ValueError('H1 and M1 OHLC differ')
        checked += 1
    return checked


def summarize(rows):
    entries = [r for r in rows if r['status'] == 'VIAVEL_SIMULADO']
    resolved = [r for r in entries if 'net_r' in r]
    return dict(events=len(rows), entries=len(entries),
                targets=sum(r['outcome'] == 'ALVO' for r in entries),
                stops=sum(r['outcome'] in ('STOP', 'STOP_AMBIGUO') for r in entries),
                open=sum(r['outcome'] == 'ABERTO' for r in entries),
                net_r_sum=str(sum((D(r['net_r']) for r in resolved), D(0))))


def run(baseline_path, hourly_path, minute_path):
    baseline = json.loads(Path(baseline_path).read_text())
    rows = baseline['records']
    assert baseline['unique_events'] == 61
    assert len(rows) == 122
    symbols = sorted({r['symbol'] for r in rows})
    contexts, checked = {}, 0
    for symbol in symbols:
        h = json.loads((Path(hourly_path) / (symbol+'.json')).read_text())
        m = json.loads((Path(minute_path) / (symbol+'.json')).read_text())
        assert h['historical_cutoff'] == baseline['price_cutoff']
        hourly = [Candle.from_dict(b) for b in h['candles']]
        minute = [Candle.from_dict(b) for b in m['candles']]
        checked += validate_aggregation(hourly, minute)
        for signal in {r['confirmed_at'] for r in rows if r['symbol'] == symbol}:
            contexts[symbol, signal] = hourly_context(hourly, signal)
    result_rows = []
    for row in rows:
        ctx = contexts[row['symbol'], row['confirmed_at']]
        result_rows.append(dict(row, h1=jsonable(ctx),
                                h1_pass=ctx['direction'] == row['side']))
    summaries = {}
    for delay in (0, 60):
        source = [r for r in result_rows if r['delay'] == delay]
        kept = [r for r in source if r['h1_pass']]
        removed_entries = [r for r in source if not r['h1_pass']
                           and r['status'] == 'VIAVEL_SIMULADO']
        before = summarize(source)
        assert before['entries'] == baseline['summary'][str(delay)]['entries']
        assert before['net_r_sum'] == baseline['summary'][str(delay)]['net_r_sum']
        summaries[str(delay)] = dict(baseline=before, filtered=summarize(kept),
                                     removed_eligible=summarize(removed_entries),
                                     direction_counts=dict(Counter(r['h1']['direction'] for r in source)))
    return dict(experiment='H1_EMA20_CLOSE_AND_SLOPE',
                rule='LONG: last known H1 close > EMA20 and EMA20 rising; SHORT: inverse',
                availability='H1 end + 10s <= original confirmation; fixed across delays',
                ema_seed='SMA of first 20 collected H1 closes; alpha=2/21; >=240 known bars',
                production_changed=False, state_sha=baseline['state_sha'],
                state_cutoff=baseline['state_cutoff'], price_cutoff=baseline['price_cutoff'],
                unique_events=61, symbols=len(symbols), validated_h1_m1_hours=checked,
                summaries=summaries, records=result_rows,
                limitations=['Single previously inspected day; exploratory, not out-of-sample.',
                             'Same frozen TP/SL, finance and M1 fills; only H1 eligibility changes.',
                             'Synthetic spread/depth and funding zero; historical fills unproven.',
                             'Current public contract parameters; independent overlapping signals, not a wallet.',
                             'Zero-delay entries are an idealized upper-bound timing scenario.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--hourly', required=True)
    parser.add_argument('--minute', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.baseline, args.hourly, args.minute)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False, indent=2))
