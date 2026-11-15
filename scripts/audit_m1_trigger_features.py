"""Causal trigger diagnostics and one predeclared second-close progression gate."""
import argparse,gzip,json
from collections import defaultdict,Counter
from datetime import datetime
from pathlib import Path
from statistics import median

from mexc_scanner.models import D,jsonable
from scripts.audit_sustained_trigger import read_dataset
from scripts.audit_m1_profit_protection import walk

FEATURES=('progress_atr','signed_second_body_atr','close_location','confirmation_distance_atr',
          'volume_pair_relative20','volume_retention')


def trigger_features(signal,side,minutes,atr,level):
    first=minutes[signal-120];second=minutes[signal-60]
    assert first.end==second.ts and second.end==signal
    sign=1 if side=='LONG' else -1
    prior=[minutes[t] for t in range(first.ts-1200,first.ts,60)]
    assert len(prior)==20 and all(c.end<=first.ts for c in prior)
    mean=sum((c.volume for c in prior),D(0))/20;width=second.high-second.low
    assert atr>0 and first.volume>0
    return dict(first_close=first.close,second_close=second.close,known_at=second.end,
        progress_atr=sign*(second.close-first.close)/atr,
        signed_second_body_atr=sign*(second.close-second.open)/atr,
        close_location=((second.close-second.low if sign==1 else second.high-second.close)/width) if width else None,
        confirmation_distance_atr=sign*(second.close-level)/atr,
        volume_pair_relative20=(first.volume+second.volume)/(2*mean) if mean else None,
        volume_retention=second.volume/first.volume,
        accepted=sign*(second.close-first.close)>=0)


def distribution(values):
    values=sorted(x for x in values if x is not None);n=len(values)
    return dict(n=n,median=median(values) if n else None,
                q1=median(values[:n//2]) if n>1 else values[0] if n else None,
                q3=median(values[(n+1)//2:]) if n>1 else values[0] if n else None)


def metrics(rows):
    vals=[r['baseline'] for r in rows];closed=[v for v in vals if 'net_r' in v]
    gains=sum((v['net_r'] for v in closed if v['net_r']>0),D(0))
    losses=-sum((v['net_r'] for v in closed if v['net_r']<0),D(0))
    tp=sum(v['outcome']=='ALVO' for v in vals);sl=sum(v['outcome']=='STOP' for v in vals)
    return dict(entries=len(rows),distinct_symbol_side_minutes=len({(r['symbol'],r['side'],r['signal']) for r in rows}),
        targets=tp,stops=sl,open=sum(v['outcome']=='ABERTO' for v in vals),
        tp_rate_closed=D(tp)/(tp+sl)*100 if tp+sl else None,
        closed_r=sum((v['net_r'] for v in closed),D(0)),marked_r=sum((v['marked_r'] for v in vals),D(0)),
        profit_factor=gains/losses if losses else None)


def compare(rows):
    return dict(baseline=metrics(rows),kept=metrics([r for r in rows if r['features']['accepted']]),
                rejected=metrics([r for r in rows if not r['features']['accepted']]))


def run(source,baseline,protocol):
    source=Path(source);p=json.loads(Path(protocol).read_text());old=json.loads(Path(baseline).read_text())
    cfg=old['config_active'];manifest=json.loads((source/'summary.json').read_text())
    forms=json.load(gzip.open(source/'all-formations.json.gz','rt'))
    original={(r['symbol'],r['side'],int(datetime.fromisoformat(r['formed_at']).timestamp())):r for r in forms}
    groups=defaultdict(list)
    for r in old['records']:
        if 'entered_at' in r['result']:groups[r['symbol']].append(r)
    split=int(datetime.fromisoformat('2026-11-01T00:00:00-03:00').timestamp());rows=[];checks=0
    for spec in manifest['datasets']:
        if spec['symbol'] not in groups:continue
        data=read_dataset(source,spec);minutes={b.ts:b for b in data['minute']}
        for row in groups.pop(spec['symbol']):
            form=original[row['symbol'],row['side'],row['formed_at']];atr=D(form['atr']);level=D(form['level'])
            f=trigger_features(row['signal'],row['side'],minutes,atr,level)
            prefix={t:b for t,b in minutes.items() if b.end<=row['signal']}
            assert f==trigger_features(row['signal'],row['side'],prefix,atr,level);checks+=1
            bars=[minutes[t] for t in range(row['signal'],row['signal']+14400,60)]
            outcome=walk(row,bars,data['contract'].tick,cfg)
            assert outcome['outcome']==row['result']['outcome']
            if 'net_r' in row['result']:assert abs(outcome['net_r']-D(row['result']['net_r']))<D('1E-22')
            rows.append(dict(id=row['id'],symbol=row['symbol'],side=row['side'],signal=row['signal'],
                period='training' if row['signal']<split else 'verification',baseline=outcome,features=f))
    assert not groups and len(rows)==123
    periods={name:compare([r for r in rows if r['period']==name]) for name in ('training','verification')}
    training=[r for r in rows if r['period']=='training']
    diagnostics={outcome:{feature:distribution([r['features'][feature] for r in training if r['baseline']['outcome']==outcome])
                          for feature in FEATURES} for outcome in ('ALVO','STOP','ABERTO')}
    all_stats=compare(rows)
    promising=all_stats['kept']['marked_r']>all_stats['baseline']['marked_r']
    promising=promising and all_stats['kept']['profit_factor'] is not None and all_stats['kept']['profit_factor']>all_stats['baseline']['profit_factor']
    promising=promising and all(x['kept']['marked_r']>=x['baseline']['marked_r'] for x in periods.values())
    promising=promising and periods['verification']['kept']['entries']>=20
    return jsonable(dict(protocol=p,training_diagnostics=diagnostics,comparison=all_stats,periods=periods,
        by_side={side:compare([r for r in rows if r['side']==side]) for side in ('LONG','SHORT')},
        causal_prefix_checks=checks,baseline_entries_replayed=123,promising_same_history=promising,
        records=rows,production_changed=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','baseline','protocol','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.baseline,a.protocol)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('records','protocol')},indent=2))
