"""Reproduce the complete, bounded research batch without external services."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import math

from mexc_scanner.models import D, jsonable
from scripts.audit_multihour import DAY, HOUR, events, load_markets, run, stamp

PROTOCOLS = [
    'multihour-v1-2026-11-16.json',
    'momentum-persistence-v1-2026-11-16.json',
    'momentum-market-gate-v1-2026-11-16.json',
    'momentum-market-confirm-v1-2026-11-16.json',
]


def causal_audit(results, data_root):
    snapshots = 0; signals_checked = 0
    unique = {}
    for r in results:
        for variant in r['protocol']['variants']:
            unique[variant['name']] = (variant, r['protocol'])
    for variant, p in unique.values():
        for block in p['blocks']:
            market, _ = load_markets(block, p, data_root)
            start, end = stamp(block['start']), stamp(block['end'])
            step = variant['tf_hours']*HOUR
            times = sorted({(start+(end-start)*n//4)//step*step for n in (1,2,3)})
            for symbol, m in market.items():
                full_entries, full_updates = events(symbol, m, variant, start, end, HOUR)
                for known_at in times:
                    prefix = dict(m, hourly={t:b for t,b in m['hourly'].items() if b.end <= known_at})
                    before, updates = events(symbol, prefix, variant, start, end, HOUR)
                    decision = known_at+HOUR
                    assert jsonable(full_entries.get(decision, [])) == jsonable(before.get(decision, []))
                    assert jsonable(full_updates.get(decision)) == jsonable(updates.get(decision))
                    snapshots += 1; signals_checked += len(before.get(decision, []))
    return dict(actual_dataset_prefix_snapshots=snapshots,
        nonempty_signal_candidates_checked=signals_checked,
        scope='Signals/ATR/rank scores and stop updates compared with every future H1 bar removed; synthetic tests cover funding and BTC gate.')


def robustness(wallet):
    eq = {r['at']:D(r['equity']) for r in wallet['equity_curve']}
    stamps = sorted(eq); days = list(range(stamps[0], stamps[-1]+1, DAY))
    returns = [math.log(float(eq[b]/eq[a])) for a,b in zip(days, days[1:])]
    intervals = {}
    for length in (3,7):
        rng = random.Random(20261116+length)
        blocks = [returns[i:i+length] for i in range(len(returns)-length+1)]
        values = []
        for _ in range(10000):
            sample = []
            while len(sample) < len(returns):
                sample.extend(rng.choice(blocks))
            values.append((math.exp(sum(sample[:len(returns)]))-1)*100)
        values.sort()
        intervals[str(length)] = dict(low_percentile2_5=values[249],high_percentile97_5=values[9749])
    best = max(D(t['net']) for t in wallet['trades'])
    return dict(observed_days=len(returns), exploratory_block_bootstrap=intervals,
        fixed_quantity_balance_without_best_trade=D(wallet['summary']['final'])-best,
        largest_profit=best, largest_profit_fraction_of_net=best/(D(wallet['summary']['final'])-100),
        note='Post-selection sensitivity, not a formal confidence interval or forecast. Removing a trade keeps original quantities; it is not a re-simulated wallet.')


def batch(output, data_root=None):
    destination = Path(output); destination.mkdir(parents=True, exist_ok=True)
    results = []
    for i, name in enumerate(PROTOCOLS, 1):
        result = run(Path('config')/name, data_root)
        (destination/f'round-{i}.json').write_text(json.dumps(result,indent=2)+'\n')
        results.append(result)
    for block in results[1]['experiments']:
        assert results[1]['experiments'][block]['MOMENTUM_24H'] == results[2]['experiments'][block]['MOMENTUM_24H']
        assert results[2]['experiments'][block]['MOMENTUM_BTC_GATE'] == results[3]['experiments'][block]['MOMENTUM_BTC_GATE']
    audit = causal_audit(results, data_root)
    ledger = {}; executions = 0
    for round_number, r in enumerate(results, 1):
        for block, variants in r['experiments'].items():
            for name, arms in variants.items():
                for costs, wallet in arms.items():
                    executions += 1
                    key = (name,block,costs)
                    row = dict(variant=name,block=block,costs=costs,
                        first_round=round_number,summary=wallet['summary'],
                        temporal_blocks=wallet['temporal_blocks'],months=wallet['months'])
                    if key in ledger:
                        assert ledger[key]['summary'] == row['summary']
                    else:
                        ledger[key] = row
    candidate = results[2]['experiments']['recent_fair']['MOMENTUM_BTC_GATE']
    summary = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        variants=7,distinct_scenarios=len(ledger),executions_including_control_repeats=executions,
        exact_control_comparisons=8,causal_audit=audit,
        ledger=list(ledger.values()),candidate='MOMENTUM_BTC_GATE',
        candidate_robustness={c:robustness(candidate[c]) for c in ('base','stress')},
        screens={k:v for r in results for k,v in r['research_screen'].items()},
        production_changed=False,approved_for_production=False,independent_validation=False,
        caveats=['All historical sources were previously available in the project; no untouched holdout.',
            'July-September use Last as a proxy for Fair; recent21days have actual archived Fair.',
            'Current survivor universe and contract rules, not historical eligibility.',
            'Fees and fills are modeled; no personal fee schedule or historical order book.',
            'Protocols were sequentially frozen before each trial, after reviewing earlier trials; this is adaptive research.',
            'Conservative simultaneous opening gap/funding handling is included in the final rerun.'])
    (destination/'summary.json').write_text(json.dumps(jsonable(summary),indent=2)+'\n')
    print('BATCH_SUMMARY '+json.dumps(jsonable({k:v for k,v in summary.items() if k not in ('ledger','candidate_robustness')})),flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-root'); parser.add_argument('--output',required=True)
    args = parser.parse_args(); batch(args.output,args.data_root)
