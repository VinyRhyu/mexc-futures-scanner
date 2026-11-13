"""Execution-lag sensitivity of the frozen 28/57-entry confirmation cohorts.

Production's 120-second entry expiry is enforced. A separately labelled
counterfactual estimates market eligibility if that expiry were longer.
No scanner state, notifications, prices or production configuration are changed.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from mexc_scanner.minute_breakout import MAX_SIGNAL_AGE
from scripts.audit_early_trigger import check_ohlc
from scripts.audit_minute_execution import audit_delay
from scripts.audit_rr_15 import key, mark_open
from scripts.audit_sustained_trigger import metrics, read_dataset, restore_plan, restore_variant

DELAYS = (0, 60, 120, 180)


def delayed(row, minute, contract, cfg, seconds, *, enforce_expiry=True):
    if seconds not in DELAYS:
        raise ValueError('Undefined experiment delay')
    p = deepcopy(row)
    signal = p['variants']['CONFIRMADA']['triggered_at']
    if enforce_expiry and signal + seconds + 1 >= p['expires_at']:
        return {'outcome': 'EXPIRADO_PRAZO_M1'}
    if not enforce_expiry:
        p['expires_at'] = signal + 14400
    result = audit_delay(p, minute, contract, cfg, seconds)
    if result['outcome'] == 'ABERTO':
        v = p['variants']['CONFIRMADA']
        mark_row = dict(result, side=p['side'], stop=v['stop'])
        bars = [c for c in minute if signal + seconds <= c.ts < signal + 14400]
        result['open_mark_r'] = str(mark_open(mark_row, bars, contract, cfg))
    return result


def stats(rows):
    entries = [r for r in rows if 'entered_at' in r]
    return dict(metrics(entries), total_cases=len(rows),
        outcomes=dict(Counter(r['outcome'] for r in rows)),
        blocked_reasons=dict(Counter(x for r in rows for x in r.get('reasons', []))),
        four_hour_marked_r=str(sum((D(r.get('net_r', r.get('open_mark_r', 0))) for r in entries), D(0))))


def run(source, cohort_file, output):
    frozen_bytes = cohort_file.read_bytes()
    cohort = json.loads(frozen_bytes)
    original = json.loads(gzip.decompress((source / 'all-formations.json.gz').read_bytes()))
    by_id = {r['id']: r for r in original}
    prior = json.loads((source / 'summary.json').read_text())
    cfg = Config(**prior['config']).validate()
    if cfg.fingerprint != prior['config_fingerprint'] or prior['errors']:
        raise ValueError('Source config or integrity mismatch')
    scenarios = {'RR_2': cfg, 'RR_1_5': replace(cfg, minimum_rr='1.5')}
    selected = {}
    for label in scenarios:
        selected[label] = {key(r[label]): r for r in cohort['records'] if 'entered_at' in r[label]}
    groups = defaultdict(list)
    for label, items in selected.items():
        for row in items.values():
            groups[row['symbol']].append((label, row))
    records = []
    for manifest in prior['datasets']:
        symbol = manifest['symbol']
        # Validate every source instrument, not just those with selected entries.
        d = read_dataset(source, manifest)
        minute = d['minute']; mm = {c.ts: c for c in minute}
        check_ohlc(d['quarter'], mm, minute[0].ts, minute[-1].end)
        for label, row in groups.pop(symbol, []):
            old = by_id[row['id']]
            reference = row[label]
            p = restore_plan(old); v = restore_variant(old['M1'])
            v.kind, v.status, v.triggered_at = 'CONFIRMADA', 'VALIDA', reference['signal']
            p.status = 'ATIVO'; p.variants = {'CONFIRMADA': v}
            p.expires_at = min(int(old['M1']['signal']) + 1800, v.triggered_at + MAX_SIGNAL_AGE)
            for field in ('reference', 'entry_low', 'entry_high', 'stop', 'target'):
                if getattr(v, field) != D(reference[field]):
                    raise ValueError('Frozen level mismatch')
            serialized = jsonable(p)
            result = {k: row[k] for k in ('id', 'symbol', 'side', 'week')}
            result.update(scenario=label, signal=v.triggered_at,
                delays={str(delay): delayed(serialized, minute, d['contract'], scenarios[label], delay)
                        for delay in DELAYS},
                extended_expiry_counterfactual={str(delay): delayed(serialized, minute, d['contract'], scenarios[label], delay, enforce_expiry=False)
                        for delay in DELAYS})
            zero = result['delays']['0']
            if zero['outcome'] != reference['outcome'] or 'entered_at' not in zero:
                raise ValueError('Immediate baseline outcome mismatch')
            if 'net_r' in reference and abs(D(reference['net_r']) - D(zero['net_r'])) > D('1e-20'):
                raise ValueError('Immediate baseline net R mismatch')
            records.append(result)
        print(json.dumps({'symbol': symbol, 'records': len(records)}), flush=True)
    if groups:
        raise ValueError('Some source contracts were not validated')
    summary = {}
    for label in scenarios:
        rows = [r for r in records if r['scenario'] == label]
        summary[label] = {mode: {str(delay): stats([r[mode][str(delay)] for r in rows]) for delay in DELAYS}
                          for mode in ('delays', 'extended_expiry_counterfactual')}
        for mode in ('delays', 'extended_expiry_counterfactual'):
            for delay in DELAYS:
                entries = [r for r in rows if 'entered_at' in r[mode][str(delay)]]
                summary[label][mode][str(delay)]['distinct_symbol_side_minutes'] = len({
                    (r['symbol'], r['side'], r['signal']) for r in entries})
                summary[label][mode][str(delay)]['plans_by_confirmation_date_brt'] = dict(sorted(Counter(
                    datetime.fromtimestamp(r['signal'], ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d')
                    for r in entries).items()))
        zero = summary[label]['delays']['0']
        prior_stats = cohort['summary'][label]
        for k in ('entries', 'targets', 'stops', 'open'):
            if zero[k] != prior_stats[k]:
                raise ValueError('Prior cohort summary mismatch')
    result = dict(kind='FROZEN_COHORT_DELIVERY_DELAY', source_artifact_id=13792493410,
        prior_experiment_commit='6e31014742be5df8e0c69d14077b07916d850910',
        prior_result_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
        start_brt=prior['start_brt'], end_exclusive_brt=prior['end_exclusive_brt'],
        expiry_seconds=MAX_SIGNAL_AGE, baseline_reproduced=True, errors=[], summary=summary,
        limitations=[
            'Same frozen 28 and 57 immediate-entry cohorts. All their cases included, with no selection by result.',
            'Fixed delays 0/60/120/180 seconds from the confirmation close; historical minute-open prices, not actual alert latency.',
            'At 120 seconds and beyond the production expiry blocks entries. Market-only counts explicitly waive this expiry and are counterfactual.',
            'No orders/alerts/production edits. No stop/target/band changes; delayed quotes rerun all financial gates.',
            'SL or TP touched during the wait cancels the attempt. Stop takes precedence in ambiguous candles.',
            'Common horizon ends 4h after original confirmation; delayed entries have less time. Open marks are hypothetical exits, separate from TP/SL.',
            'Same assumed costs, zero funding, infinite depth. Minute OHLC cannot establish second-level executable quotes or manual fills.',
            'Only survival of the immediate-entry cohorts is measured. No search for newly eligible previously blocked setups after a delay.',
            'Overlapping correlated trades; R is not portfolio ROI. Same previously explored history, not out-of-sample validation.',
            'At zero delay the fill is an idealized benchmark: the live feed requires closed-candle availability and collection time.'
        ], cases=records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(jsonable(result), ensure_ascii=False, indent=2))
    print(json.dumps(jsonable({k: v for k, v in result.items() if k != 'cases'}), ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    run(args.source, args.cohort, args.output)
