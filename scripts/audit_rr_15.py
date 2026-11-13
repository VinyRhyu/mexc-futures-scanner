"""Read-only comparison of net RR 2 vs 1.5 on the frozen M1 volume cohort.

The Config validation floor stays unchanged in production. The lower value is
an explicit experiment-only dataclass override passed to the same evaluator.
"""
from collections import Counter, defaultdict
from dataclasses import replace
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from scripts.audit_early_trigger import check_ohlc
from scripts.audit_sustained_trigger import read_dataset, restore_plan, sustained, metrics


def key(row):
    return row['symbol'], row['side'], row['signal'], row['stop'], row['target']


def mark_open(row, bars, contract, cfg):
    sign = 1 if row['side'] == 'LONG' else -1
    entry = D(row['entry_mid']) * (1 + sign * D('.0001'))
    stop, exit_price = D(row['stop']), bars[-1].close
    fee, slip, tick = D(cfg.taker_fee), D(cfg.slippage_rate), contract.tick
    entry_cost = max(2 * tick, entry * slip)
    risk = sign * (entry - stop) + entry_cost + max(2 * tick, stop * slip) + fee * (entry + stop)
    net = sign * (exit_price - entry) - entry_cost - max(2 * tick, exit_price * slip) - fee * (entry + exit_price)
    return net / risk


def aggregate(rows):
    entered = [r for r in rows if 'entered_at' in r]
    unique = list({key(r): r for r in entered}.values())
    return dict(metrics(unique),
        all_entry_records=len(entered),
        distinct_symbol_side_minutes=len({(r['symbol'], r['side'], r['signal']) for r in unique}),
        four_hour_marked_r=sum((D(r.get('net_r', r.get('open_mark_r', 0))) for r in unique), D(0)),
        blocked_reasons=dict(Counter(x for r in rows for x in r.get('reasons', []))),
        outcomes=dict(Counter(r['outcome'] for r in rows)))


def run(source, output):
    original_bytes = (source / 'all-formations.json.gz').read_bytes()
    cohort = json.loads(gzip.decompress(original_bytes))
    prior = json.loads((source / 'summary.json').read_text())
    if prior['errors'] or prior['analyzed_symbols'] != prior['selected_symbols']:
        raise ValueError('Incomplete original source')
    cfg = Config(**prior['config']).validate()
    if cfg.fingerprint != prior['config_fingerprint'] or D(cfg.minimum_rr) != 2:
        raise ValueError('Original config mismatch')
    configs = {'RR_2': cfg, 'RR_1_5': replace(cfg, minimum_rr='1.5')}
    grouped = defaultdict(list)
    for r in cohort:
        grouped[r['symbol']].append(r)
    records, technical = [], Counter()
    for manifest in prior['datasets']:
        d = read_dataset(source, manifest)
        mm = {c.ts: c for c in d['minute']}
        check_ohlc(d['quarter'], mm, d['minute'][0].ts, d['minute'][-1].end)
        for old in grouped.pop(manifest['symbol']):
            first = old['M1']
            if 'signal' not in first:
                continue
            t = int(first['signal'])
            a, b = mm[t - 60], mm.get(t)
            if b is None or a.volume <= 0 or 2 * b.volume < a.volume:
                continue
            p = restore_plan(old)
            record = {k: old[k] for k in ('id', 'symbol', 'side', 'week')}
            for label, config in configs.items():
                row = sustained(p, first, mm, d['contract'], config)
                if label == 'RR_2':
                    technical[row['outcome']] += 1
                row.update({k: record[k] for k in ('id', 'symbol', 'side', 'week')})
                if row['outcome'] == 'ABERTO':
                    bars = [mm[t] for t in range(row['signal'], row['signal'] + 14400, 60)]
                    row['open_mark_r'] = mark_open(row, bars, d['contract'], config)
                record[label] = row
            records.append(record)
        print(json.dumps({'symbol': manifest['symbol'], 'records': len(records)}), flush=True)
    if grouped:
        raise ValueError('Missing source instruments')
    summary = {label: aggregate([r[label] for r in records]) for label in configs}
    base = summary['RR_2']
    if (base['entries'], base['targets'], base['stops'], base['open']) != (28, 14, 11, 3):
        raise ValueError('Frozen 28-entry baseline did not reproduce')
    if abs(D(base['net_r']) - D('25.41759581675119873281914694')) > D('.000001'):
        raise ValueError('Frozen baseline R did not reproduce: ' + base['net_r'])
    entries = {label: {key(r[label]): r[label] for r in records if 'entered_at' in r[label]} for label in configs}
    common = set(entries['RR_2']) & set(entries['RR_1_5'])
    for k in common:
        a, b = entries['RR_2'][k], entries['RR_1_5'][k]
        changed_r = ('net_r' in a) != ('net_r' in b)
        if 'net_r' in a and 'net_r' in b:
            changed_r = abs(D(a['net_r']) - D(b['net_r'])) > D('1e-20')
        if a['outcome'] != b['outcome'] or changed_r:
            raise ValueError('Common execution outcome changed')
    added = [v for k, v in entries['RR_1_5'].items() if k not in entries['RR_2']]
    removed = [v for k, v in entries['RR_2'].items() if k not in entries['RR_1_5']]
    result = dict(kind='FIXED_NET_RR_2_VS_1_5',
        source_artifact_id=13792493410, source_code=prior['code_sha'],
        source_formations_sha256=hashlib.sha256(original_bytes).hexdigest(),
        start_brt=prior['start_brt'], end_exclusive_brt=prior['end_exclusive_brt'],
        source_config=prior['config'], instruments=len(prior['datasets']), formations=len(cohort),
        baseline_reproduced=True, summary=summary,
        incremental=aggregate(added), removed=aggregate(removed), common_entries=len(common),
        weekly={w: {label: aggregate([r[label] for r in records if r['week'] == w]) for label in configs}
                for w in prior['weekly']},
        by_side={side: {label: aggregate([r[label] for r in records if r['side'] == side]) for label in configs}
                 for side in ('LONG', 'SHORT')},
        limitations=[
            'Single change: minimum net RR 2 -> 1.5. No target/stop/confirmation/volume changes; no ROI minimum added.',
            'Experiment-only override; production Config validation, strategy and Telegram were not modified.',
            'Same already explored Oct25-Nov7 2026 history; exploratory, not out-of-sample validation.',
            'Frozen 31-instrument universe/contract rules reflect original collection, not historical membership.',
            'All frozen formations considered, including previously blocked triggers; only identical executions deduplicated.',
            'Immediate next-minute fills, synthetic spread .02%, fee .06% per side, configured slippage or 2 ticks; zero funding and infinite depth.',
            'Four-hour horizon and stop-first ambiguous candles. Open marks are hypothetical four-hour exits, separate from actual TP/SL.',
            'Independent overlapping trials; sum R is not dollars or portfolio ROI. More entries do not establish better performance.',
            'No threshold sweep; 1.5 was fixed before running the comparison.'
        ], records=records)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').write_text(json.dumps(jsonable(result), ensure_ascii=False, indent=2))
    print(json.dumps(jsonable({k: v for k, v in result.items() if k != 'records'}), ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.output)
