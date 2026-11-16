"""Re-simulate all fixed models with OHLC-verified intrahour exit resolution."""
import argparse,gzip,hashlib,json
from pathlib import Path

from mexc_scanner.models import Candle,D,jsonable
from scripts.audit_multihour import load_markets,simulate,HOUR
from scripts.audit_collected_momentum import consistency_checks
from scripts.collect_momentum_minutes import verify_hour


def attach_resolution(markets,directory,protocol):
    root=Path(directory);raw=(root/'summary.json').read_bytes();summary=json.loads(raw)
    assert hashlib.sha256(raw).hexdigest()==protocol['intrahour_summary_sha256']
    assert summary['protocol_sha256']==protocol['intrahour_protocol_sha256']
    assert not summary['errors'] and summary['selected']==summary['complete']==len(summary['datasets'])
    for spec in summary['datasets']:
        raw=gzip.decompress((root/(spec['key']+'.json.gz')).read_bytes())
        assert hashlib.sha256(raw).hexdigest()==spec['sha256_uncompressed']
        row=json.loads(raw);market=markets[row['symbol']];tf=row['timeframe_seconds'];at=row['start']
        assert tf in (60,300,900) and row['end']==at+HOUR
        values={}
        for key,source in [('last','hourly'),('fair','fair')]:
            bars=[Candle.from_dict(b) for b in row[key]]
            for bar in bars:bar.validate();assert bar.tf==tf
            assert [b.ts for b in bars]==list(range(at,at+HOUR,tf))
            verify_hour(bars,jsonable(market[source][at]))
            values[key]=bars
        values['timeframe_seconds']=tf
        market.setdefault('minute_resolution',{})[at]=values
    return summary


def run(protocol_path,intrahour_source,parent_path,allocation_parent_path,data_root=None):
    p=json.loads(Path(protocol_path).read_text())
    parent=json.loads(Path(parent_path).read_text());allocation=json.loads(Path(allocation_parent_path).read_text())
    markets,hashes=load_markets(p['blocks'][-1],p,data_root)
    # A new data resolution cannot silently alter the unrefined controls.
    compared=0
    for block in p['blocks']:
        for variant in p['variants']:
            name=variant['name'];old=parent if name=='MOMENTUM_24H' else allocation
            for costs in p['costs']:
                coarse=simulate(markets,variant,block,p,costs)
                assert jsonable(coarse)==old['experiments'][block['name']][name][costs['name']]
                compared+=1
    source=attach_resolution(markets,intrahour_source,p)
    result=dict(protocol=p,source_sha256=hashes,intrahour_source=source,
        coarse_wallets_reproduced=compared,experiments={},production_changed=False,
        independent_validation=False,approved_for_production=False,unresolved_liquidation_hours=[])
    unresolved=set()
    for block in p['blocks']:
        arms={}
        for variant in p['variants']:
            name=variant['name'];arms[name]={}
            for costs in p['costs']:
                wallet=simulate(markets,variant,block,p,costs)
                arms[name][costs['name']]=wallet
                for t in wallet['trades']:
                    if t['outcome']=='LIQUIDACAO' and 'price_resolution' not in t:
                        unresolved.add((t['symbol'],(t['exit_at']-1)//HOUR*HOUR))
                print(json.dumps(jsonable(dict(period=block['name'],variant=name,costs=costs['name'],
                    **wallet['summary']))),flush=True)
        result['experiments'][block['name']]=arms
    result['unresolved_liquidation_hours']=[dict(symbol=s,start=t) for s,t in sorted(unresolved)]
    result['original_consistency_screen']=consistency_checks(p,result['experiments'])
    result['risk_screen']={}
    for variant in p['variants']:
        name=variant['name'];w=result['experiments']['continuous_all'][name];recent=result['experiments']['recent_extended'][name]
        result['risk_screen'][name]=dict(
            continuous_base_positive=D(w['base']['summary']['final'])>100,
            continuous_stress_positive=D(w['stress']['summary']['final'])>100,
            base_dd_at_most10=D(w['base']['summary']['max_drawdown_pct'])<=10,
            stress_dd_at_most10=D(w['stress']['summary']['max_drawdown_pct'])<=10,
            recent_base_and_stress_positive=all(D(recent[c]['summary']['final'])>100 for c in ('base','stress')),
            no_modeled_liquidation=all(w[c]['summary']['outcomes'].get('LIQUIDACAO',0)==0 for c in ('base','stress')))
    return jsonable(result)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('protocol','intrahour-source','parent','allocation-parent','output'):ap.add_argument('--'+key,required=True)
    ap.add_argument('--data-root');a=ap.parse_args()
    r=run(a.protocol,a.intrahour_source,a.parent,a.allocation_parent,a.data_root)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r['risk_screen'],indent=2))
