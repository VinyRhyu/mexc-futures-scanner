"""Summarize sanitized own-clock measurements; no market/network/Telegram calls."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from statistics import median


def summarize(samples):
    phases = {}
    coverage, deliveries, start_delays = [], [], []
    for sample in samples:
        rows = sample['rows']
        ends = [r for r in rows if r.get('telemetry') == 'phase_v1' and r.get('event') == 'end']
        assert all(r['status'] == 'OK' and r['duration_s'] >= 0 for r in ends)
        for phase in ('round', 'restore', 'scan', 'persist_before_notify', 'notify',
                      'persist_after_notify', 'telegram_commands', 'persist_after_commands'):
            found = [r for r in ends if r['phase'] == phase]
            assert len(found) == 1, (sample['run_id'], phase)
            phases.setdefault(phase, []).append(found[0]['duration_s'])
        scan = next(r for r in rows if 'source_status' in r)
        coverage.append(scan['coverage'])
        assert scan['source_status'] == 'OK'
        delivery = next(r for r in rows if 'sent' in r and 'configuration' in r)
        deliveries.append(delivery)
        round_row = next(r for r in ends if r['phase'] == 'round')
        created = datetime.fromisoformat(sample['created_at'].replace('Z', '+00:00'))
        started = datetime.fromisoformat(round_row['started_at_utc'])
        start_delays.append((started-created).total_seconds())
    def stats(values):
        return {'n': len(values), 'min_s': min(values), 'median_s': median(values), 'max_s': max(values)}
    return {'runs': len(samples), 'phase_seconds': {p: stats(v) for p, v in phases.items()},
        'dispatch_to_round_start': stats(start_delays), 'coverage': dict(Counter(coverage)),
        'messages_sent': sum(d['sent'] for d in deliveries),
        'messages_expired': sum(d['expired'] for d in deliveries),
        'delivery_failures': sum(d['failed'] for d in deliveries),
        'all_rounds_under_60s': all(s < 60 for s in phases['round'])}


def run(source):
    source = json.loads(Path(source).read_text())
    before, after = source['before'], source['after']
    assert len(before) == 3 and len(after) == source['protocol']['minimum_after_runs'] == 10
    assert len({r['run_id'] for r in before+after}) == 13
    assert all(r['commit'] == source['protocol']['instrumentation_commit'] for r in before)
    assert all(r['commit'] == source['protocol']['optimization_commit'] for r in after)
    assert [r['created_at'] for r in after] == sorted(r['created_at'] for r in after)
    a, b = summarize(before), summarize(after)
    improvement = {phase: 100*(1-b['phase_seconds'][phase]['median_s']/a['phase_seconds'][phase]['median_s'])
                   for phase in ('round', 'restore')}
    workflow_outcomes = dict(Counter(r['conclusion'] for r in source['post_workflow_runs']))
    return {'protocol': source['protocol'], 'before': a, 'after': b,
        'median_reduction_pct': improvement, 'post_workflow_outcomes': workflow_outcomes,
        'operational_target_met_in_sample': b['all_rounds_under_60s'] and b['delivery_failures'] == 0,
        'strategy_profitability_validated': False, 'strategy_changed': False,
        'limitations': ['Three before and ten after observations; not a long-run P95 or failure-rate estimate.',
            'Quote/market conditions and message counts vary; runtime overhead and dispatcher delays remain distinct.',
            'Telegram counts include INFO; not a count of executed or profitable trades.',
            'No outcome, account-fee or realized-PnL validation is inferred from speed.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.source)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
