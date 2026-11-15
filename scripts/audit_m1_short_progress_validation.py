"""Apply one frozen SHORT-only gate to a new historical period."""
import argparse,json
from pathlib import Path
from datetime import datetime
from mexc_scanner.config import Config
from mexc_scanner.models import D,jsonable
from mexc_scanner.minute_breakout import process_minutes
from scripts.audit_sustained_trigger import read_dataset
from scripts.audit_m1_trend_context import evaluate,key
from scripts.audit_m1_trigger_features import trigger_features,compare
from scripts.audit_m1_profit_protection import walk


def run(source,protocol):
    source=Path(source);p=json.loads(Path(protocol).read_text())
    manifest=json.loads((source/'summary.json').read_text())
    assert manifest['selected_symbols']==manifest['analyzed_symbols']==31 and not manifest['errors']
    assert set(p['symbols'])=={d['symbol'] for d in manifest['datasets']}
    cfg=Config(**manifest['config']).validate()
    start=int(datetime.fromisoformat(p['start_brt']).timestamp());end=int(datetime.fromisoformat(p['end_exclusive_brt']).timestamp())
    records=[];confirmations=0;checks=0
    for spec in manifest['datasets']:
        assert spec['ohlc_matches']
        data=read_dataset(source,spec);minutes={b.ts:b for b in data['minute']}
        plans,_,_=process_minutes(spec['symbol'],data['quarter'],data['hourly'],data['minute'],[],0,
             data['minute'][-1].end+10,data['contract'].tick,cfg,start)
        for plan in plans:
            if not start<=plan.formed_at<end or 'CONFIRMADA' not in plan.variants:continue
            confirmations+=1;v=plan.variants['CONFIRMADA'];old=evaluate(plan,v,data,cfg)
            if 'entered_at' not in old:continue
            row=dict(id=plan.id,symbol=plan.symbol,side=plan.side,signal=v.triggered_at,
                     stop=v.stop,target=v.target,result=old)
            f=trigger_features(v.triggered_at,plan.side,minutes,plan.atr,plan.level)
            before={t:b for t,b in minutes.items() if b.end<=v.triggered_at}
            assert f==trigger_features(v.triggered_at,plan.side,before,plan.atr,plan.level);checks+=1
            f['global_progress_ok']=f['accepted'];f['accepted']=plan.side=='LONG' or f['accepted']
            bars=[minutes[t] for t in range(v.triggered_at,v.triggered_at+14400,60)]
            outcome=walk(row,bars,data['contract'].tick,manifest['config'])
            assert outcome['outcome']==old['outcome']
            if 'net_r' in old:assert abs(outcome['net_r']-D(old['net_r']))<D('1E-22')
            records.append(dict(row,baseline=outcome,features=f))
        print(json.dumps(dict(symbol=spec['symbol'],confirmations=confirmations,entered_formations=len(records))),flush=True)
    rows=list({key(r):r for r in records}.values());stats=compare(rows)
    sides={s:compare([r for r in rows if r['side']==s]) for s in ('LONG','SHORT')}
    promising=stats['kept']['marked_r']>0 and stats['kept']['marked_r']>stats['baseline']['marked_r']
    promising=promising and stats['kept']['profit_factor'] is not None and stats['baseline']['profit_factor'] is not None
    promising=promising and stats['kept']['profit_factor']>stats['baseline']['profit_factor']
    promising=promising and stats['kept']['entries']>=20 and sides['SHORT']['kept']['entries']>=10
    return jsonable(dict(protocol=p,source_manifest=manifest,confirmations=confirmations,
        comparison=stats,by_side=sides,causal_checks=checks,promising_new_period=promising,
        records=rows,production_changed=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','protocol','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.protocol)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('records','source_manifest','protocol')},indent=2))
