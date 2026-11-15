"""Diagnose frozen M1 stops and test one causal cost-covering stop move."""
import argparse,gzip,json
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from mexc_scanner.models import D,jsonable,ceil_step,floor_step
from scripts.audit_sustained_trigger import read_dataset


def unit_values(row,tick,cfg):
    sign=1 if row['side']=='LONG' else -1
    entry=D(row['result']['entry_mid'])*(1+sign*D('.0001'))
    stop=D(row['stop']);fee=D(cfg['taker_fee']);slip=D(cfg['slippage_rate'])
    cost=max(2*tick,entry*slip)
    risk=sign*(entry-stop)+cost+max(2*tick,stop*slip)+fee*(entry+stop)
    assert risk>0
    return sign,entry,cost,fee,slip,risk


def net_unit(price,values,tick):
    sign,entry,cost,fee,slip,risk=values
    return sign*(price-entry)-cost-max(2*tick,price*slip)-fee*(entry+price)


def cost_covering_stop(values,tick):
    sign,entry,cost,fee,slip,risk=values
    if sign==1:
        proportional=(entry*(1+fee)+cost)/(1-fee-slip)
        constant=(entry*(1+fee)+cost+2*tick)/(1-fee)
        price=max(proportional,constant)
        result=ceil_step(price,tick)
    else:
        proportional=(entry*(1-fee)-cost)/(1+fee+slip)
        constant=(entry*(1-fee)-cost-2*tick)/(1+fee)
        price=min(proportional,constant)
        result=floor_step(price,tick)
    assert net_unit(result,values,tick)>=0
    return result


def walk(row,bars,tick,cfg,protect=False):
    values=unit_values(row,tick,cfg);sign,*_=values;risk=values[-1]
    original=D(row['stop']);target=D(row['target']);active_stop=original
    be=cost_covering_stop(values,tick);armed_at=None
    for c in bars:
        bad=c.low<=active_stop if sign==1 else c.high>=active_stop
        good=c.high>=target if sign==1 else c.low<=target
        if bad or good:
            if bad:
                price=min(active_stop,c.open) if sign==1 else max(active_stop,c.open)
                reason='PROTEGIDA' if armed_at is not None else 'STOP'
            else:price=target;reason='ALVO'
            net=net_unit(price,values,tick)/risk
            return dict(outcome=reason,net_r=net,marked_r=net,closed_at=c.end,
                        exit_mid=price,armed_at=armed_at,ambiguity=bad and good,
                        gap=bad and sign*(c.open-active_stop)<0)
        if protect and armed_at is None and net_unit(c.close,values,tick)/risk>=D('.5'):
            assert sign*(be-original)>0 and sign*(target-be)>0
            active_stop=be;armed_at=c.end
    return dict(outcome='ABERTO',marked_r=net_unit(bars[-1].close,values,tick)/risk,
                armed_at=armed_at,closed_at=None,ambiguity=False,gap=False)


def walk_failed_break(row,bars,level,tick,cfg):
    values=unit_values(row,tick,cfg);sign=values[0];risk=values[-1]
    stop=D(row['stop']);target=D(row['target']);pending_at=None
    for i,c in enumerate(bars):
        if pending_at is not None:
            assert c.ts==pending_at
            bad=sign*(c.open-stop)<=0;good=sign*(c.open-target)>=0
            reason='STOP' if bad else 'ALVO' if good else 'FALHA_ROMPIMENTO'
            price=c.open if not good else target
            net=net_unit(price,values,tick)/risk
            return dict(outcome=reason,net_r=net,marked_r=net,closed_at=c.ts,
                        exit_mid=price,armed_at=pending_at,ambiguity=False,gap=bad)
        bad=c.low<=stop if sign==1 else c.high>=stop
        good=c.high>=target if sign==1 else c.low<=target
        if bad or good:
            price=(min(stop,c.open) if sign==1 else max(stop,c.open)) if bad else target
            net=net_unit(price,values,tick)/risk
            return dict(outcome='STOP' if bad else 'ALVO',net_r=net,marked_r=net,
                        closed_at=c.end,exit_mid=price,armed_at=None,ambiguity=bad and good,
                        gap=bad and sign*(c.open-stop)<0)
        if i<5 and sign*(c.close-level)<=0:pending_at=c.end
    return dict(outcome='ABERTO',marked_r=net_unit(bars[-1].close,values,tick)/risk,
                armed_at=pending_at,closed_at=None,ambiguity=False,gap=False)


def diagnose(row,bars,level,values,tick,baseline):
    sign=values[0];closed=baseline['closed_at']
    safe=[b for b in bars if closed is None or b.end<closed]
    closes=[net_unit(b.close,values,tick)/values[-1] for b in safe]
    peak=max([D(0)]+closes)
    returned=[b for b in safe[:5] if sign*(b.close-level)<=0]
    later_target=[b for b in bars if closed is not None and b.ts>=closed and
                  (b.high>=D(row['target']) if sign==1 else b.low<=D(row['target']))]
    return dict(peak_completed_m1_net_r=peak,
        early_return_inside=bool(returned),early_return_at=returned[0].end if returned else None,
        minutes_to_exit=D(closed-row['signal'])/60 if closed else None,
        original_target_after_stop=baseline['outcome']=='STOP' and bool(later_target),
        original_target_later_at=later_target[0].end if baseline['outcome']=='STOP' and later_target else None)


def summary(rows,arm):
    values=[r[arm] for r in rows];closed=[v for v in values if 'net_r' in v]
    gains=sum((v['net_r'] for v in closed if v['net_r']>0),D(0))
    losses=-sum((v['net_r'] for v in closed if v['net_r']<0),D(0))
    return dict(entries=len(rows),outcomes=dict(Counter(v['outcome'] for v in values)),
        positive_net=sum(v['net_r']>0 for v in closed),negative_net=sum(v['net_r']<0 for v in closed),
        realized_r=sum((v['net_r'] for v in closed),D(0)),
        total_with_open_marks_r=sum((v['marked_r'] for v in values),D(0)),
        open_mark_r=sum((v['marked_r'] for v in values if v['outcome']=='ABERTO'),D(0)),
        profit_factor=gains/losses if losses else None,ambiguities=sum(v['ambiguity'] for v in values),
        protected_negative=sum(v['outcome']=='PROTEGIDA' and v['net_r']<0 for v in values))


def run(source,baseline,protocol,failed_protocol=None):
    p=json.loads(Path(protocol).read_text());prior=json.loads(Path(baseline).read_text())
    cfg=prior['config_active'];source=Path(source)
    manifest=json.loads((source/'summary.json').read_text())
    formations=json.load(gzip.open(source/'all-formations.json.gz','rt'))
    levels={(r['symbol'],r['side'],int(datetime.fromisoformat(r['formed_at']).timestamp())):D(r['level'])
            for r in formations}
    by_symbol=defaultdict(list)
    for r in prior['records']:
        if 'entered_at' in r['result']:by_symbol[r['symbol']].append(r)
    cases=[]
    for spec in manifest['datasets']:
        if spec['symbol'] not in by_symbol:continue
        data=read_dataset(source,spec);mm={b.ts:b for b in data['minute']};tick=data['contract'].tick
        for row in by_symbol.pop(spec['symbol']):
            bars=[mm[ts] for ts in range(row['signal'],row['signal']+14400,60)]
            a=walk(row,bars,tick,cfg);b=walk(row,bars,tick,cfg,True)
            old=row['result'];assert a['outcome']==old['outcome']
            if 'net_r' in old:assert abs(a['net_r']-D(old['net_r']))<D('1E-22')
            level=levels[row['symbol'],row['side'],row['formed_at']]
            diag=diagnose(row,bars,level,unit_values(row,tick,cfg),tick,a)
            failed=walk_failed_break(row,bars,level,tick,cfg) if failed_protocol else None
            cases.append(dict(id=row['id'],symbol=row['symbol'],side=row['side'],signal=row['signal'],
                              week=row['week'],baseline=a,protected=b,diagnostic=diag,failed_break=failed))
    assert not by_symbol and len(cases)==123
    losses=[r for r in cases if r['baseline']['outcome']=='STOP']
    assert len(losses)==71
    diag=dict(stops=len(losses),early_return_inside=sum(r['diagnostic']['early_return_inside'] for r in losses),
        had_positive_completed_m1=sum(r['diagnostic']['peak_completed_m1_net_r']>0 for r in losses),
        reached_thresholds={str(t):sum(r['diagnostic']['peak_completed_m1_net_r']>=D(t) for r in losses) for t in ('.25','.5','1')},
        original_target_later=sum(r['diagnostic']['original_target_after_stop'] for r in losses),
        median_minutes_to_stop=median(r['diagnostic']['minutes_to_exit'] for r in losses),
        stops_within_minutes={str(t):sum(r['diagnostic']['minutes_to_exit']<=t for r in losses) for t in (5,15,30)})
    weekly={w:{arm:summary([r for r in cases if r['week']==w],arm) for arm in ('baseline','protected')}
            for w in ('25–31/10','01–07/11')}
    overall={arm:summary(cases,arm) for arm in ('baseline','protected')}
    promising=all(v['protected']['total_with_open_marks_r']>=v['baseline']['total_with_open_marks_r'] for v in weekly.values())
    promising=promising and overall['protected']['total_with_open_marks_r']>overall['baseline']['total_with_open_marks_r']
    promising=promising and overall['protected']['profit_factor']>overall['baseline']['profit_factor']
    extra={}
    if failed_protocol:
        fs=summary(cases,'failed_break')
        fw={w:summary([r for r in cases if r['week']==w],'failed_break') for w in weekly}
        good=fs['total_with_open_marks_r']>overall['baseline']['total_with_open_marks_r'] and fs['profit_factor']>overall['baseline']['profit_factor']
        good=good and all(fw[w]['total_with_open_marks_r']>=weekly[w]['baseline']['total_with_open_marks_r'] for w in weekly)
        extra=dict(failed_break_test=dict(protocol=json.loads(Path(failed_protocol).read_text()),summary=fs,
            weekly=fw,promising_same_history=good,transitions=dict(Counter(r['baseline']['outcome']+'->'+r['failed_break']['outcome'] for r in cases))))
    return jsonable(dict(protocol=p,diagnostic=diag,summary=overall,weekly=weekly,promising_same_history=promising,
        baseline_replayed_entries=123,transitions=dict(Counter(r['baseline']['outcome']+'->'+r['protected']['outcome'] for r in cases)),
        cases=cases,production_changed=False,**extra))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','baseline','protocol','output'):ap.add_argument('--'+k,required=True)
    ap.add_argument('--failed-protocol')
    a=ap.parse_args();r=run(a.source,a.baseline,a.protocol,a.failed_protocol)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('cases','protocol')},indent=2))
