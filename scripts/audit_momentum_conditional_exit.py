"""One pre-registered exploratory loss exit; no orders or live state access."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from mexc_scanner.models import D, jsonable
from scripts.audit_multihour import HOUR, close, load_markets, simulate
from scripts.audit_momentum_intrahour import attach_resolution
from scripts.audit_collected_momentum import consistency_checks

FROZEN_SHA256 = '184a4c06b9f8b0ea9c158b2a8a88bb84727328f7604c7791f7df19b30993cf98'


class WeakExit:
    """EMA is recursive on closed bars; a decision cannot use the delay bar."""
    def __init__(self, markets):
        self.features = {}
        for symbol, market in markets.items():
            rows = sorted(market['hourly'].values(), key=lambda b: b.ts)
            trend = None; features = {}; alpha = D(2)/21
            previous = None
            for i, bar in enumerate(rows):
                if previous is not None and previous.end != bar.ts:
                    raise ValueError('Discontinuous EMA input')
                trend = bar.close if trend is None else alpha*bar.close+(1-alpha)*trend
                if i >= 19:
                    features[bar.end] = (bar, trend)
                previous = bar
            self.features[symbol] = features

    def __call__(self, position, market, at, costs):
        signal_at = at-HOUR
        if signal_at-position['opened_at'] < 6*HOUR:
            return None
        features = self.features[position['symbol']]
        pair = [features.get(signal_at-HOUR), features.get(signal_at)]
        if any(row is None for row in pair):
            return None
        if any(bar.ts < position['opened_at'] for bar, _ in pair):
            return None
        if not all(position['sign']*(bar.close-trend) < 0 for bar, trend in pair):
            return None
        mark = pair[-1][0].close
        marked, _ = close(position,mark,signal_at,'SIGNAL_MARK',costs)
        if marked['net'] > 0:
            return None
        return dict(signal_at=signal_at,observed_close=mark,estimated_net=marked['net'],
            bar_ends=[row[0].end for row in pair],ema20=[row[1] for row in pair])


def paired(control, candidate):
    """Pair only identical entries. Per-quantity returns remove sizing feedback."""
    key = lambda t: (t['symbol'],t['opened_at'],t['sign'])
    old = {key(t):t for t in control['trades']}; new = {key(t):t for t in candidate['trades']}
    common = sorted(old.keys() & new.keys()); changed = []
    for k in common:
        a,b = old[k],new[k]
        if a['exit_at'] == b['exit_at'] and a['outcome'] == b['outcome']:
            continue
        old_return = a['net']/(a['quantity']*a['entry'])
        new_return = b['net']/(b['quantity']*b['entry'])
        changed.append(dict(symbol=a['symbol'],opened_at=a['opened_at'],
            baseline_outcome=a['outcome'],candidate_outcome=b['outcome'],
            baseline_net_per_notional=old_return,candidate_net_per_notional=new_return,
            delta_per_notional=new_return-old_return,
            baseline_exit_at=a['exit_at'],candidate_exit_at=b['exit_at']))
    return dict(identical_entry_pairs=len(common),control_only_entries=len(old.keys()-new.keys()),
        candidate_only_entries=len(new.keys()-old.keys()),changed_exit_pairs=len(changed),
        baseline_winners_cut=sum(t['baseline_net_per_notional']>0 and t['candidate_net_per_notional']<=0 for t in changed),
        baseline_losers_improved=sum(t['baseline_net_per_notional']<0 and t['delta_per_notional']>0 for t in changed),
        baseline_losers_worsened=sum(t['baseline_net_per_notional']<0 and t['delta_per_notional']<0 for t in changed),
        changed=changed)


def run(protocol_path, baseline_path, intrahour_source, data_root=None):
    raw=Path(protocol_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA256
    spec=json.loads(raw); root=Path(__file__).resolve().parents[1]
    rawbase=(root/spec['base_protocol']).read_bytes()
    assert hashlib.sha256(rawbase).hexdigest()==spec['base_protocol_sha256']
    p=json.loads(rawbase); rawparent=Path(baseline_path).read_bytes()
    assert hashlib.sha256(rawparent).hexdigest()==spec['baseline_results_sha256']
    parent=json.loads(rawparent)
    markets,hashes=load_markets(p['blocks'][-1],p,data_root)
    source=attach_resolution(markets,intrahour_source,p)
    control=next(v for v in p['variants'] if v['name']==spec['control'])
    candidate=dict(deepcopy(control),name=spec['candidate'])
    p['variants']=[control,candidate]
    result=dict(protocol=spec,protocol_sha256=FROZEN_SHA256,source_sha256=hashes,
        intrahour_source=source,baseline_wallets_reproduced=0,experiments={},paired_diagnostics={},
        production_changed=False,prospective_protocol_changed=False,
        independent_validation=False,approved_for_production=False)
    policy=WeakExit(markets)
    for block in p['blocks']:
        period=block['name']; arms={v['name']:{} for v in p['variants']}
        result['paired_diagnostics'][period]={}
        for costs in p['costs']:
            name=costs['name']
            a=simulate(markets,control,block,p,costs)
            assert jsonable(a)==parent['experiments'][period][control['name']][name]
            result['baseline_wallets_reproduced']+=1
            b=simulate(markets,candidate,block,p,costs,exit_policy=policy)
            arms[control['name']][name]=a; arms[candidate['name']][name]=b
            result['paired_diagnostics'][period][name]=paired(a,b)
            for v,w in [(control,a),(candidate,b)]:
                print(json.dumps(jsonable(dict(period=period,variant=v['name'],costs=name,**w['summary']))),flush=True)
        result['experiments'][period]=arms
    result['original_consistency_screen']=consistency_checks(p,result['experiments'])
    continuous=result['experiments']['continuous_all']; c=continuous[candidate['name']]; a=continuous[control['name']]
    all_candidate=[arms[candidate['name']][costs['name']] for arms in result['experiments'].values() for costs in p['costs']]
    conditions=dict(
        continuous_base_roi_improves=c['base']['summary']['return_pct']>a['base']['summary']['return_pct'],
        continuous_stress_roi_improves=c['stress']['summary']['return_pct']>a['stress']['summary']['return_pct'],
        continuous_base_dd_at_most10=c['base']['summary']['max_drawdown_pct']<=10,
        all_three_periods_positive=all(result['experiments'][b['name']][candidate['name']][costs['name']]['summary']['return_pct']>0 for b in p['blocks'][:3] for costs in p['costs']),
        no_modeled_liquidations=all(w['summary']['outcomes'].get('LIQUIDACAO',0)==0 for w in all_candidate))
    result['exploratory_acceptance']=dict(conditions=conditions,passed=all(conditions.values()))
    return jsonable(result)


def compact_report(result):
    """Keep every wallet/period outcome, excluding reproducible hourly curves."""
    output = {k:v for k,v in result.items() if k not in ('experiments','paired_diagnostics')}
    output['experiments'] = {}
    output['paired_diagnostics'] = {}
    for period, arms in result['experiments'].items():
        output['experiments'][period] = {}
        for variant, wallets in arms.items():
            output['experiments'][period][variant] = {}
            for costs, wallet in wallets.items():
                held = sum(t['exit_at']-t['opened_at'] for t in wallet['trades'])
                output['experiments'][period][variant][costs] = dict(
                    summary=wallet['summary'],months=wallet['months'],
                    temporal_blocks=wallet['temporal_blocks'],
                    mean_hours_held=str(D(held)/HOUR/len(wallet['trades'])),
                    fraction_hours_exposed=str(D(held)/(wallet['equity_curve'][-1]['at']-wallet['equity_curve'][0]['at'])))
        output['paired_diagnostics'][period] = {
            costs:{k:v for k,v in values.items() if k!='changed'}
            for costs,values in result['paired_diagnostics'][period].items()}
    output['full_results_sha256'] = hashlib.sha256((json.dumps(result,indent=2)+'\n').encode()).hexdigest()
    return output


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for arg in ('protocol','baseline','intrahour-source','output'): ap.add_argument('--'+arg,required=True)
    ap.add_argument('--data-root'); ap.add_argument('--summary-output'); args=ap.parse_args()
    result=run(args.protocol,args.baseline,args.intrahour_source,args.data_root)
    out=Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    if args.summary_output:
        summary=Path(args.summary_output); summary.parent.mkdir(parents=True,exist_ok=True)
        summary.write_text(json.dumps(compact_report(result),indent=2)+'\n')
    print(json.dumps(result['exploratory_acceptance'],indent=2))
