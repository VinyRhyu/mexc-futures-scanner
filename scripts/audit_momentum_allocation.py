"""Two frozen risk policies; same technical candidate, delay, costs and exits."""
import argparse
import hashlib
import json
from pathlib import Path

from mexc_scanner.models import D,jsonable
from scripts.audit_collected_momentum import consistency_checks
from scripts.audit_multihour import load_markets,simulate


def run(protocol_path,parent_path,data_root=None):
    p=json.loads(Path(protocol_path).read_text());parent=json.loads(Path(parent_path).read_text())
    markets,hashes=load_markets(p['blocks'][-1],p,data_root)
    result=dict(protocol=p,protocol_sha256=hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        parent_sha256=hashlib.sha256(Path(parent_path).read_bytes()).hexdigest(),source_sha256=hashes,
        experiments={},production_changed=False,approved_for_production=False,independent_validation=False)
    for block in p['blocks']:
        arms={}
        for variant in p['variants']:
            arms[variant['name']]={}
            for costs in p['costs']:
                wallet=simulate(markets,variant,block,p,costs)
                if variant['name']=='MOMENTUM_BTC_GATE':
                    assert jsonable(wallet)==parent['experiments'][block['name']][variant['name']][costs['name']]
                arms[variant['name']][costs['name']]=wallet
                print(json.dumps(jsonable(dict(period=block['name'],variant=variant['name'],costs=costs['name'],
                    **wallet['summary']))),flush=True)
        result['experiments'][block['name']]=arms
    result['original_consistency_screen']=consistency_checks(p,result['experiments'])
    result['risk_screen']={}
    for v in p['variants']:
        name=v['name'];continuous=result['experiments']['continuous_all'][name]
        recent=result['experiments']['recent_extended'][name]
        result['risk_screen'][name]=bool(continuous['base']['summary']['final']>D(p['initial_equity'])
            and continuous['stress']['summary']['final']>D(p['initial_equity'])
            and continuous['base']['summary']['max_drawdown_pct']<=10
            and recent['base']['summary']['final']>D(p['initial_equity'])
            and recent['stress']['summary']['final']>D(p['initial_equity']))
    return jsonable(result)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--protocol',required=True)
    ap.add_argument('--parent',required=True);ap.add_argument('--output',required=True);ap.add_argument('--data-root');a=ap.parse_args()
    result=run(a.protocol,a.parent,a.data_root)
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['risk_screen'],indent=2))
