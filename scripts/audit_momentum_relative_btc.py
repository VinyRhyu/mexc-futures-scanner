"""One frozen BTC-relative ordering hypothesis; paper research only."""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from mexc_scanner.models import D, jsonable
from scripts.audit_multihour import DAY, HOUR, load_markets, simulate, events, stamp
from scripts.audit_momentum_intrahour import attach_resolution
from scripts.audit_collected_momentum import consistency_checks

FROZEN_SHA256='69dfcbaa793337bf5a018687bb21f7a75aae4f0baf264bd228b6f2a368c6d115'


def relative_btc_score(markets, signal):
    """All prices end at/before the frozen daily signal boundary, never fill time."""
    at=signal['signal_at']; symbol=signal['symbol']
    def prices(name):
        bars=markets[name]['hourly']
        return bars[at-HOUR].close, bars[at-7*DAY-HOUR].close
    current,previous=prices(symbol); btc,old_btc=prices('BTC_USDT')
    if min(current,previous,btc,old_btc,signal['atr'])<=0:
        raise ValueError('Nonpositive price or ATR in frozen ranking')
    asset_return=current/previous-1;btc_return=btc/old_btc-1
    return signal['sign']*(asset_return-btc_return)/(signal['atr']/current)


def selection_diagnostics(control,candidate):
    """Compare entries, without pretending paired winners were knowable ex ante."""
    by_day=lambda w:{t['opened_at']:t for t in w['trades']}
    a=by_day(control);b=by_day(candidate); rows=[]
    assert len(a)==len(control['trades']) and len(b)==len(candidate['trades'])
    same=0;changed=0;only_control=0;only_candidate=0
    for at in sorted(a.keys()|b.keys()):
        old=a.get(at);new=b.get(at)
        identical=bool(old and new and old['symbol']==new['symbol'] and old['sign']==new['sign'])
        if identical:same+=1
        elif old and new:changed+=1
        elif old:only_control+=1
        else:only_candidate+=1
        rows.append(dict(at=at,same_entry=identical,
            control_symbol=old['symbol'] if old else None,candidate_symbol=new['symbol'] if new else None,
            control_sign=old['sign'] if old else None,candidate_sign=new['sign'] if new else None,
            control_net=old['net'] if old else None,candidate_net=new['net'] if new else None,
            control_outcome=old['outcome'] if old else None,candidate_outcome=new['outcome'] if new else None,
            control_exit_at=old['exit_at'] if old else None,candidate_exit_at=new['exit_at'] if new else None,
            control_score=old['score'] if old else None,candidate_score=new['score'] if new else None,
            candidate_original_score=new.get('original_score') if new else None))
    return dict(same_entries=same,changed_symbols_or_sides=changed,control_only_entries=only_control,
        candidate_only_entries=only_candidate,rows=rows)


def contributions(wallet):
    rows=defaultdict(lambda:dict(positions=0,net=D(0),positive=0,fees=D(0),funding_paid=D(0)))
    for t in wallet['trades']:
        r=rows[t['symbol']];r['positions']+=1;r['net']+=D(t['net'])
        r['positive']+=D(t['net'])>0;r['fees']+=D(t['entry_fee'])+D(t['exit_fee'])
        r['funding_paid']+=D(t['funding_paid'])
    assert sum((r['net'] for r in rows.values()),D(0))==D(wallet['summary']['final'])-D(wallet['summary']['initial'])
    return dict(sorted(rows.items()))


def verify_signal_causality(markets,variant,protocol):
    checked=0
    for block in protocol['blocks'][:3]:
        start,end=stamp(block['start']),stamp(block['end'])
        for fraction in (1,2,3):
            boundary=(start+(end-start)*fraction//4)//DAY*DAY
            prefix={s:dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=boundary}) for s,m in markets.items()}
            for symbol,market in markets.items():
                full,_=events(symbol,market,variant,boundary,boundary+DAY,HOUR)
                short,_=events(symbol,prefix[symbol],variant,boundary,boundary+DAY,HOUR)
                at=boundary+HOUR
                assert full.get(at,[])==short.get(at,[])
                for signal in full.get(at,[]):
                    assert relative_btc_score(markets,signal)==relative_btc_score(prefix,signal)
                    checked+=1
    assert checked>0
    return checked


def run(protocol_path,baseline_path,intrahour_source,data_root=None):
    raw=Path(protocol_path).read_bytes();assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA256
    spec=json.loads(raw);root=Path(__file__).resolve().parents[1]
    rawbase=(root/spec['base_protocol']).read_bytes();assert hashlib.sha256(rawbase).hexdigest()==spec['base_protocol_sha256']
    p=json.loads(rawbase);rawparent=Path(baseline_path).read_bytes()
    assert hashlib.sha256(rawparent).hexdigest()==spec['baseline_results_sha256'];parent=json.loads(rawparent)
    markets,hashes=load_markets(p['blocks'][-1],p,data_root)
    source=attach_resolution(markets,intrahour_source,p)
    control=next(v for v in p['variants'] if v['name']==spec['control'])
    candidate=dict(deepcopy(control),name=spec['candidate']);p['variants']=[control,candidate]
    result=dict(protocol=spec,protocol_sha256=FROZEN_SHA256,source_sha256=hashes,intrahour_source=source,
        baseline_wallets_reproduced=0,closed_signal_causality_checks=verify_signal_causality(markets,control,p),
        experiments={},selection_diagnostics={},production_changed=False,prospective_protocol_changed=False,
        independent_validation=False,approved_for_production=False)
    for block in p['blocks']:
        period=block['name'];arms={v['name']:{} for v in p['variants']};result['selection_diagnostics'][period]={}
        for costs in p['costs']:
            name=costs['name'];a=simulate(markets,control,block,p,costs)
            assert jsonable(a)==parent['experiments'][period][control['name']][name]
            result['baseline_wallets_reproduced']+=1
            b=simulate(markets,candidate,block,p,costs,entry_ranker=relative_btc_score)
            for t in b['trades']:
                assert t['planned_risk']<=t['equity_before']*D('.01')+D('1E-18')
                assert t['effective_risk_fraction']==D('.01')
                assert t['exit_at']-t['opened_at']<=24*HOUR
            arms[control['name']][name]=a;arms[candidate['name']][name]=b
            result['selection_diagnostics'][period][name]=selection_diagnostics(a,b)
            for v,w in [(control,a),(candidate,b)]:
                print(json.dumps(jsonable(dict(period=period,variant=v['name'],costs=name,**w['summary']))),flush=True)
        result['experiments'][period]=arms
    result['original_consistency_screen']=consistency_checks(p,result['experiments'])
    continuous=result['experiments']['continuous_all'];a=continuous[control['name']];b=continuous[candidate['name']]
    wallets=[arms[candidate['name']][costs['name']] for arms in result['experiments'].values() for costs in p['costs']]
    conditions=dict(
        continuous_base_roi_improves=b['base']['summary']['return_pct']>a['base']['summary']['return_pct'],
        continuous_stress_roi_improves=b['stress']['summary']['return_pct']>a['stress']['summary']['return_pct'],
        continuous_base_dd_at_most10=b['base']['summary']['max_drawdown_pct']<=10,
        all_three_periods_positive=all(result['experiments'][block['name']][candidate['name']][costs['name']]['summary']['return_pct']>0 for block in p['blocks'][:3] for costs in p['costs']),
        no_modeled_liquidations=all(w['summary']['outcomes'].get('LIQUIDACAO',0)==0 for w in wallets))
    result['exploratory_acceptance']=dict(conditions=conditions,passed=all(conditions.values()))
    return jsonable(result)


def compact_report(result):
    output={k:v for k,v in result.items() if k not in ('experiments','selection_diagnostics')}
    output['experiments']={};output['selection_diagnostics']={}
    for period,arms in result['experiments'].items():
        output['experiments'][period]={}
        for variant,wallets in arms.items():
            output['experiments'][period][variant]={}
            for costs,wallet in wallets.items():
                held=sum(t['exit_at']-t['opened_at'] for t in wallet['trades'])
                output['experiments'][period][variant][costs]=dict(summary=wallet['summary'],
                    months=wallet['months'],temporal_blocks=wallet['temporal_blocks'],
                    per_symbol=contributions(wallet),mean_hours_held=str(D(held)/HOUR/len(wallet['trades'])))
        output['selection_diagnostics'][period]={costs:{k:v for k,v in values.items() if k!='rows'}
            for costs,values in result['selection_diagnostics'][period].items()}
    output['full_results_sha256']=hashlib.sha256((json.dumps(result,indent=2)+'\n').encode()).hexdigest()
    return jsonable(output)


def write_outputs(result,output,summary_output=None,ledger_output=None):
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    if summary_output:
        path=Path(summary_output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(compact_report(result),indent=2)+'\n')
    if ledger_output:
        import csv
        path=Path(ledger_output);path.parent.mkdir(parents=True,exist_ok=True)
        rows=[dict(period=period,costs=costs,**row) for period,arms in result['selection_diagnostics'].items()
            for costs,values in arms.items() for row in values['rows']]
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(rows)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for arg in ('protocol','baseline','intrahour-source','output'):ap.add_argument('--'+arg,required=True)
    for arg in ('data-root','summary-output','ledger-output'):ap.add_argument('--'+arg)
    a=ap.parse_args();r=run(a.protocol,a.baseline,a.intrahour_source,a.data_root)
    write_outputs(r,a.output,a.summary_output,a.ledger_output)
    print(json.dumps(r['exploratory_acceptance'],indent=2))
