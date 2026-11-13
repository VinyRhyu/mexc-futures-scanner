"""Fixed 1:1 minimum net RR experiment; preserve technical TP and SL.

Reproduce the earlier 2:1/1.5:1 experiment before considering the user-requested
1:1 threshold. Also reproduce their one-minute execution-delay benchmarks.
Production validation, scanner state and notifications are never changed.
"""
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from mexc_scanner.config import Config
from mexc_scanner.minute_breakout import MAX_SIGNAL_AGE
from mexc_scanner.models import D, jsonable
from scripts.audit_rr_15 import aggregate, key, mark_open, run as run_reference
from scripts.audit_rr_delivery import delayed, stats
from scripts.audit_sustained_trigger import read_dataset, restore_plan, restore_variant, sustained


def entry_map(records, label):
    return {key(r[label]): r for r in records if 'entered_at' in r[label]}


def compare(records, first, second):
    before, after = entry_map(records, first), entry_map(records, second)
    for k in set(before) & set(after):
        a, b = before[k][first], after[k][second]
        if a['outcome'] != b['outcome'] or ('net_r' in a) != ('net_r' in b):
            raise ValueError('Common TP/SL execution changed')
        if 'net_r' in a and abs(D(a['net_r']) - D(b['net_r'])) > D('1e-20'):
            raise ValueError('Common execution normalized return changed')
    return dict(common=len(set(before) & set(after)),
        added=aggregate([r[second] for k, r in after.items() if k not in before]),
        removed=aggregate([r[first] for k, r in before.items() if k not in after]))


def run(source, output):
    reference = run_reference(source, output / 'reference')
    prior = json.loads((source / 'summary.json').read_text())
    raw = (source / 'all-formations.json.gz').read_bytes()
    original = {r['id']: r for r in json.loads(gzip.decompress(raw))}
    base = Config(**prior['config']).validate()
    configs = {'RR_2': base, 'RR_1_5': replace(base, minimum_rr='1.5'), 'RR_1': replace(base, minimum_rr='1')}
    groups = defaultdict(list)
    for row in reference['records']:
        groups[row['symbol']].append(row)
    records, delivery_records = [], []
    for manifest in prior['datasets']:
        data = read_dataset(source, manifest)
        mm = {c.ts: c for c in data['minute']}
        local_rows = groups.pop(manifest['symbol'], [])
        for row in local_rows:
            old = original[row['id']]
            value = sustained(restore_plan(old), old['M1'], mm, data['contract'], configs['RR_1'])
            value.update({k: row[k] for k in ('id', 'symbol', 'side', 'week')})
            if value['outcome'] == 'ABERTO':
                bars = [mm[t] for t in range(value['signal'], value['signal'] + 14400, 60)]
                value['open_mark_r'] = mark_open(value, bars, data['contract'], configs['RR_1'])
            row['RR_1'] = value
            records.append(row)
        for label, cfg in configs.items():
            for row in entry_map(local_rows, label).values():
                old, v0 = original[row['id']], row[label]
                p = restore_plan(old); v = restore_variant(old['M1'])
                v.kind, v.status, v.triggered_at = 'CONFIRMADA', 'VALIDA', v0['signal']
                p.status, p.variants = 'ATIVO', {'CONFIRMADA': v}
                p.expires_at = min(int(old['M1']['signal']) + 1800, v.triggered_at + MAX_SIGNAL_AGE)
                tests = {str(lag): delayed(jsonable(p), data['minute'], data['contract'], cfg, lag) for lag in (0, 60)}
                if tests['0']['outcome'] != v0['outcome'] or 'entered_at' not in tests['0']:
                    raise ValueError('Immediate entry does not reproduce')
                if 'net_r' in v0 and abs(D(tests['0']['net_r']) - D(v0['net_r'])) > D('1e-20'):
                    raise ValueError('Immediate return does not reproduce')
                delivery_records.append(dict(id=row['id'], symbol=row['symbol'], side=row['side'],
                    week=row['week'], signal=v.triggered_at, scenario=label, delays=tests))
        print(json.dumps({'symbol': manifest['symbol'], 'formations_processed': len(records)}), flush=True)
    if groups:
        raise ValueError('Missing source instruments')
    summary = {label: aggregate([r[label] for r in records]) for label in configs}
    # Reproducing the 1.5 benchmark is separate from validating the new 1.0 rule.
    b = summary['RR_1_5']
    if (b['entries'], b['targets'], b['stops'], b['open']) != (57, 28, 26, 3):
        raise ValueError('The 1.5 reference was not reproduced')
    if abs(D(b['net_r']) - D('34.79506167724948573727125662')) > D('1e-20'):
        raise ValueError('The 1.5 reference return was not reproduced')
    delivery = {}
    for label in configs:
        rows = [r for r in delivery_records if r['scenario'] == label]
        delivery[label] = {}
        for lag in ('0', '60'):
            accepted = [r for r in rows if 'entered_at' in r['delays'][lag]]
            delivery[label][lag] = dict(stats([r['delays'][lag] for r in rows]),
                distinct_symbol_side_minutes=len({(r['symbol'], r['side'], r['signal']) for r in accepted}),
                confirmation_dates_brt=sorted({datetime.fromtimestamp(r['signal'], ZoneInfo('America/Sao_Paulo')).strftime('%Y-%m-%d') for r in accepted}))
    for label, expected in [('RR_2', (17, 12, 3, 2)), ('RR_1_5', (34, 21, 11, 2))]:
        x = delivery[label]['60']
        if tuple(x[k] for k in ('entries', 'targets', 'stops', 'open')) != expected:
            raise ValueError('One-minute baseline differs')
    result = dict(kind='USER_REQUESTED_MINIMUM_NET_RR_ONE', source_artifact_id=13792493410,
        prior_code_commit='46670ddbd12d73cebb22d6cefbd273925ab64fe2',
        source_formations_sha256=hashlib.sha256(raw).hexdigest(), source_config=prior['config'],
        start_brt=prior['start_brt'], end_exclusive_brt=prior['end_exclusive_brt'],
        instruments=len(prior['datasets']), formations=reference['formations'],
        baseline_reproduced=True, errors=[], summary=summary, delivery=delivery,
        comparison_to_1_5=compare(records, 'RR_1_5', 'RR_1'), comparison_to_2=compare(records, 'RR_2', 'RR_1'),
        weekly={w: {label: aggregate([r[label] for r in records if r['week'] == w]) for label in configs} for w in prior['weekly']},
        by_side={side: {label: aggregate([r[label] for r in records if r['side'] == side]) for label in configs} for side in ('LONG', 'SHORT')},
        limitations=[
            'Only change is minimum net RR=1. Target remains the frozen technical target; it is not moved to exactly 1R.',
            '1.0 threshold explicitly requested before the test; no additional threshold sweep or direction filter applied.',
            'Isolated configuration override, production Config.validate floor and scanner/Telegram remain unchanged.',
            'Both earlier immediate-entry and one-minute-delay benchmarks reproduced; checksums/OHLC of all31 source instruments validated.',
            'Same Oct25-Nov7 2026 history already explored repeatedly; not out-of-sample validation.',
            'All technically eligible frozen formations considered, not just the earlier57 accepted entries.',
            'Assumed fee .06% per side, spread .02%, configured slippage or two ticks, funding zero, infinite book depth.',
            'Execution immediately or60s after confirmation; historical minute opens cannot establish manual second-level fills.',
            'Wait touching SL/TP cancels delayed entry; at120s the production entry window expires.',
            'Four-hour horizon from original confirmation, stop-first ambiguity, open marks separate from TP/SL counts.',
            'Only identical execution keys deduplicated; correlated overlapping plans remain. R is not dollars or portfolio ROI.',
            'Historical universe and contract metadata come from original collection; no new-period data collected.'
        ], records=[r for r in records if any('entered_at' in r[label] for label in configs)], delivery_cases=delivery_records)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').write_text(json.dumps(jsonable(result), ensure_ascii=False, indent=2))
    print(json.dumps(jsonable({k: v for k, v in result.items() if k not in {'records', 'delivery_cases'}}), ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    run(args.source, args.output)
