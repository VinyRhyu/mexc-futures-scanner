"""Read-only production M1 replay stratified by known H1/H2 pivot structure."""
import argparse,json
from collections import Counter,defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from mexc_scanner.config import Config,load_config
from mexc_scanner.market import structure,aggregate_two_hours
from mexc_scanner.minute_breakout import process_minutes
from mexc_scanner.models import D,jsonable
from scripts.audit_pullback import paper_quote,close_outcome
from scripts.audit_sustained_trigger import read_dataset,metrics

GROUPS=('A_FAVOR','CONTRA','MISTO','SEM_DIRECAO')


def classify(side,h1,h2):
    aligned='ALTA' if side=='LONG' else 'BAIXA'
    opposite='BAIXA' if side=='LONG' else 'ALTA'
    def one(x):return 'A_FAVOR' if x==aligned else 'CONTRA' if x==opposite else 'SEM_DIRECAO'
    a,b=one(h1),one(h2)
    joint='SEM_DIRECAO' if 'SEM_DIRECAO' in (a,b) else a if a==b else 'MISTO'
    return dict(h1=a,h2=b,joint=joint,structure1h=h1,structure2h=h2)


def known_context(hourly,signal,side):
    h=[c for c in hourly if c.end<=signal][-240:]
    if len(h)<240:raise ValueError('Less than240 known H1 candles')
    return classify(side,structure(h,signal),structure(aggregate_two_hours(h),signal))


def key(row):
    v=row['result']
    return row['symbol'],row['side'],row['signal'],D(row['stop']),D(row['target'])


def entered_metrics(rows):
    return metrics([r['result'] for r in rows if 'entered_at' in r['result']])


def grouped(rows,axis='joint'):
    groups=GROUPS if axis=='joint' else ('A_FAVOR','CONTRA','SEM_DIRECAO')
    return {g:entered_metrics([r for r in rows if r['context'][axis]==g]) for g in groups}


def evaluate(p,variant,data,cfg):
    signal=variant.triggered_at;mm={c.ts:c for c in data['minute']}
    bars=[mm[ts] for ts in range(signal,signal+14400,60) if ts in mm]
    if len(bars)!=240:raise ValueError('Incomplete4h M1 outcome path')
    p=deepcopy(p);v=deepcopy(variant)
    p.status='ATIVO';p.expires_at=max(p.expires_at,signal+120);v.status='VALIDA'
    f=paper_quote(p,v,data['contract'],bars[0].open,signal+1,cfg)
    if f['status']!='VIAVEL_SIMULADO':return dict(outcome='BLOQUEADA',reasons=f['reasons'])
    result=close_outcome(bars,p,v,data['contract'],f,bars[0].open,cfg,True)
    result.update(entered_at=signal,entry_mid=bars[0].open,net_rr=f['net_rr'],planned_loss=f['loss_usdt'],
                  leverage=f['leverage'])
    return result


def run(source,protocol,reference):
    source=Path(source);p=json.loads(Path(protocol).read_text())
    manifest=json.loads((source/'summary.json').read_text())
    assert not manifest['errors'] and manifest['analyzed_symbols']==manifest['selected_symbols']==31
    archived=Config(**manifest['config']).validate();cfg=load_config('config/default.toml')
    start=int(datetime.fromisoformat(manifest['start_brt']).timestamp())
    end=int(datetime.fromisoformat(manifest['end_exclusive_brt']).timestamp())
    records=[];legacy=[];counts=Counter();causal=0
    for spec in manifest['datasets']:
        assert spec['ohlc_matches'] is True,'Source M1/M15 OHLC mismatch'
        data=read_dataset(source,spec);symbol=spec['symbol']
        plans,_,_=process_minutes(symbol,data['quarter'],data['hourly'],data['minute'],[],0,
            data['minute'][-1].end+10,data['contract'].tick,cfg,start)
        for plan in plans:
            if not start<=plan.formed_at<end or 'CONFIRMADA' not in plan.variants:continue
            v=plan.variants['CONFIRMADA'];counts['confirmations']+=1
            context=known_context(data['hourly'],v.triggered_at,plan.side)
            assert context==known_context([c for c in data['hourly'] if c.end<=v.triggered_at],v.triggered_at,plan.side)
            causal+=1
            base=dict(id=plan.id,symbol=symbol,side=plan.side,formed_at=plan.formed_at,
                signal=v.triggered_at,stop=v.stop,target=v.target,entry_low=v.entry_low,
                entry_high=v.entry_high,context=context,
                week='25–31/10' if plan.formed_at<int(datetime.fromisoformat('2026-11-01T00:00:00-03:00').timestamp()) else '01–07/11')
            records.append(dict(base,result=evaluate(plan,v,data,cfg)))
            legacy.append(dict(base,result=evaluate(plan,v,data,archived)))
        print(json.dumps(dict(symbol=symbol,confirmations=counts['confirmations'])),flush=True)
    unique=list({key(r):r for r in records}.values())
    legacy_unique=[r for r in {key(r):r for r in legacy}.values() if 'entered_at' in r['result']]
    old=json.loads(Path(reference).read_text());expected=[r for r in old['cases'] if r['accepted']]
    old_map={(r['symbol'],r['side'],r['signal'],D(r['baseline']['stop']),D(r['baseline']['target'])):r for r in expected}
    actual_map={key(r):r for r in legacy_unique}
    assert set(actual_map)==set(old_map),f'Archived cohort mismatch: got{len(actual_map)} expected{len(old_map)}'
    for k,r in actual_map.items():
        expected_result=old_map[k]['baseline']
        assert r['result']['outcome']==expected_result['outcome'],k
        if 'net_r' in expected_result:assert r['result']['net_r']==D(expected_result['net_r']),k
    primary=[r for r in unique if 'entered_at' in r['result']]
    return jsonable(dict(protocol=p,config_active=asdict(cfg),config_archived=asdict(archived),
        period=dict(start_brt=manifest['start_brt'],end_exclusive_brt=manifest['end_exclusive_brt']),
        source_checksums={x['symbol']:x['sha256_uncompressed'] for x in manifest['datasets']},
        confirmations_full=len(records),confirmations_unique=len(unique),
        all_confirmation_outcomes=dict(Counter(r['result']['outcome'] for r in unique)),
        blocked_reasons=dict(Counter(reason for r in unique for reason in r['result'].get('reasons',[]))),
        summary=entered_metrics(unique),groups=grouped(unique),individual={axis:grouped(unique,axis) for axis in ('h1','h2')},
        full_formation_summary=entered_metrics(records),full_formation_groups=grouped(records),
        weekly={week:dict(summary=entered_metrics([r for r in unique if r['week']==week]),
                     groups=grouped([r for r in unique if r['week']==week])) for week in ('25–31/10','01–07/11')},
        archived_compatibility=dict(entries=len(legacy_unique),matches_original28=True,
            summary=entered_metrics(legacy_unique),groups=grouped(legacy_unique)),
        context_causal_checks=causal,primary_entries_distinct_symbol_side_minutes=len({(r['symbol'],r['side'],r['signal']) for r in primary}),
        distinct_minutes_by_group={g:len({(r['symbol'],r['side'],r['signal']) for r in primary
                                         if r['context']['joint']==g}) for g in GROUPS},
        records=unique,production_changed=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','protocol','reference','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.protocol,a.reference)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:r[k] for k in ('summary','groups','individual','archived_compatibility','all_confirmation_outcomes','blocked_reasons')},indent=2))
