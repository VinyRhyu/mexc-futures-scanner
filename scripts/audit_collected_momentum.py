"""Evaluate the pre-collection candidate unchanged on the complete public source."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from mexc_scanner.models import D,jsonable
from scripts.audit_multihour import load_markets,simulate,events,HOUR,DAY,stamp


def data_comparison(archived,fresh):
    output={}
    for symbol,old in archived.items():
        new=fresh[symbol]
        diffs={}
        for field in ('open','high','low','close','volume'):
            diffs[field]=sum(getattr(b,field)!=getattr(new['hourly'][t],field) for t,b in old['hourly'].items())
        old_contract=jsonable(old['contract']);new_contract=jsonable(new['contract'])
        contract_changes={k:dict(old=v,new=new_contract.get(k)) for k,v in old_contract.items() if v!=new_contract.get(k)}
        common={e['ts']:e for e in new['funding']}
        rate_changes=sum(e['rate']!=common[e['ts']]['rate'] for e in old['funding'] if e['ts'] in common)
        output[symbol]=dict(hourly_changes=diffs,contract_changes=contract_changes,funding_rate_changes_on_common_events=rate_changes)
    return output


def consistency_checks(protocol,experiments):
    screen={}
    for variant in protocol['variants']:
        name=variant['name'];conditions={}
        for block in protocol['blocks'][:3]:
            period=block['name'];w=experiments[period][name]
            conditions[period]=dict(base_positive=D(w['base']['summary']['final'])>D(protocol['initial_equity']),
                stress_positive=D(w['stress']['summary']['final'])>D(protocol['initial_equity']),
                base_dd_at_most10=D(w['base']['summary']['max_drawdown_pct'])<=10,
                base_subblocks_positive=all(D(v)>0 for v in w['base']['temporal_blocks'].values()),
                stress_subblocks_positive=all(D(v)>0 for v in w['stress']['temporal_blocks'].values()))
        continuous=experiments['continuous_all'][name]
        conditions['continuous_all']=dict(
            base_positive=D(continuous['base']['summary']['final'])>D(protocol['initial_equity']),
            stress_positive=D(continuous['stress']['summary']['final'])>D(protocol['initial_equity']))
        screen[name]=dict(conditions=conditions,passed=all(all(c.values()) for c in conditions.values()))
    return screen


def run(protocol_path,old_protocol_path,old_results_path=None,data_root=None):
    protocol=json.loads(Path(protocol_path).read_text())
    assert hashlib.sha256(Path(old_protocol_path).read_bytes()).hexdigest()==protocol['strategy_protocol_sha256']
    old_protocol=json.loads(Path(old_protocol_path).read_text())
    assert protocol['variants']==old_protocol['variants']
    for key in ('costs','risk_fraction','leverage','initial_equity','signal_delay_seconds','symbols'):
        assert protocol[key]==old_protocol[key]
    fresh,hashes=load_markets(protocol['blocks'][-1],protocol,data_root)
    result=dict(protocol=protocol,protocol_sha256=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        source_sha256=hashes,experiments={},production_changed=False,approved_for_production=False,
        independent_validation=False)
    for block in protocol['blocks']:
        arms={}
        for variant in protocol['variants']:
            arms[variant['name']]={}
            for costs in protocol['costs']:
                wallet=simulate(fresh,variant,block,protocol,costs)
                arms[variant['name']][costs['name']]=wallet
                print(json.dumps(jsonable(dict(period=block['name'],variant=variant['name'],costs=costs['name'],
                    **wallet['summary'],temporal_blocks=wallet['temporal_blocks']))),flush=True)
        result['experiments'][block['name']]=arms
    # Isolate Fair from changes in metadata, candles, or funding snapshots.
    block=old_protocol['blocks'][0]
    archived,_=load_markets(block,old_protocol,data_root)
    result['source_comparison']=data_comparison(archived,fresh)
    fair_only={s:dict(m,fair={t:fresh[s]['fair'][t] for t in m['hourly']}) for s,m in archived.items()}
    baseline={};corrected={}
    old_results=json.loads(Path(old_results_path).read_text()) if old_results_path else None
    for variant in protocol['variants']:
        name=variant['name'];baseline[name]={};corrected[name]={}
        for costs in protocol['costs']:
            a=simulate(archived,variant,block,old_protocol,costs)
            if old_results:
                assert jsonable(a)==old_results['experiments']['historical_last_proxy'][name][costs['name']]
            b=simulate(fair_only,variant,block,old_protocol,costs)
            baseline[name][costs['name']]=a['summary']
            corrected[name][costs['name']]=b['summary']
    result['fair_isolation']=dict(archived_last_proxy=baseline,only_fair_replaced=corrected,
        original_full_wallet_reproduced=bool(old_results))
    causal=0;nonempty=0
    for block in protocol['blocks'][:3]:
        start,end=stamp(block['start']),stamp(block['end'])
        for variant in protocol['variants']:
            for symbol,market in fresh.items():
                full,updates=events(symbol,market,variant,start,end,HOUR)
                for fraction in (1,2,3):
                    known=(start+(end-start)*fraction//4)//DAY*DAY
                    prefix=dict(market,hourly={t:b for t,b in market['hourly'].items() if b.end<=known})
                    short,supdates=events(symbol,prefix,variant,start,end,HOUR)
                    at=known+HOUR
                    assert jsonable(full.get(at,[]))==jsonable(short.get(at,[]))
                    assert jsonable(updates.get(at))==jsonable(supdates.get(at))
                    causal+=1;nonempty+=len(short.get(at,[]))
    result['causal_checks']=dict(snapshots=causal,nonempty_signal_candidates=nonempty)
    screen=consistency_checks(protocol,result['experiments'])
    result['consistency_screen']=screen
    return jsonable(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True)
    parser.add_argument('--archived-protocol',required=True);parser.add_argument('--archived-results')
    parser.add_argument('--output',required=True);parser.add_argument('--data-root');args=parser.parse_args()
    result=run(args.protocol,args.archived_protocol,args.archived_results,args.data_root)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['consistency_screen'],indent=2))
