"""Frozen exploratory20x/same-asset historical neighbors; never production execution."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from mexc_scanner.models import D, jsonable
from scripts.audit_multihour import (DAY,HOUR,iso,stamp,events,load_markets,simulate,floor_step,ceil_step,
    risk_budget,market_gate_allows,settlement_amount,find_exit,close)
from scripts.audit_momentum_intrahour import attach_resolution
from scripts.audit_momentum_relative_btc import relative_btc_score, contributions, verify_signal_causality

FROZEN_SHA256='529798e980a11afde7877f2dc68ceda152fc1dac7304838839b25198c223c69c'


def features(markets, signal):
    at=signal['signal_at'];bars=markets[signal['symbol']]['hourly']
    current=bars[at-HOUR].close;previous=bars[at-DAY-HOUR].close
    if min(current,previous,signal['atr'])<=0:raise ValueError('Nonpositive feature input')
    return (signal['sign']*(current/previous-1)/(signal['atr']/current),relative_btc_score(markets,signal))


def isolated_label(markets, signal, protocol, variant, costs, as_of):
    """Same daily24h position mechanics, without competition from other symbols."""
    at=signal['signal_at']+HOUR;deadline=at+24*HOUR;release=deadline+HOUR
    if release>as_of:return None,'IMMATURE'
    m=markets[signal['symbol']]
    if any(t not in m['hourly'] or t not in m['fair'] for t in range(at,release,HOUR)):
        return None,'MISSING_OBSERVATIONS'
    if not market_gate_allows(markets,signal,'BTC7_SIGN'):return None,'BTC_GATE'
    pos,reason=risk_budget(signal,m,at,D(100),dict(protocol,risk_fraction='.01',leverage=20),variant,costs)
    if pos is None:return None,reason
    for t in range(at,deadline,HOUR):
        last,fair=m['hourly'][t],m['fair'][t]
        if t>at:
            for event in m['funding_by_time'].get(t,[]):
                pos['funding_paid']+=settlement_amount(pos,event,last,fair,m['contract'].stop_only_fair)
        result,exit_at,used=find_exit(pos,last,fair,m['contract'].stop_only_fair,m.get('minute_resolution',{}).get(t))
        if result:
            reason,mid,ambiguous=result
            trade,_=close(pos,mid,exit_at,reason,costs,ambiguous)
            break
    else:
        _,updates=events(signal['symbol'],m,variant,deadline,deadline+HOUR,HOUR)
        update=updates.get(deadline);reason='TEMPO'
        if update and update['signal_at']>=at:
            channel=update['exit_long'] if pos['sign']==1 else update['exit_short']
            proposed=update['close']-pos['sign']*D(variant['trail_atr'])*update['atr']
            rounded=floor_step(proposed,pos['tick']) if pos['sign']==1 else ceil_step(proposed,pos['tick'])
            pos['stop']=max(pos['stop'],rounded) if pos['sign']==1 else min(pos['stop'],rounded)
            if channel:reason='CANAL'
        trade,_=close(pos,m['hourly'][deadline].open,deadline,reason,costs)
    label=dict(symbol=signal['symbol'],sign=signal['sign'],signal_at=signal['signal_at'],
        entry_at=at,release_at=release,features=features(markets,signal),
        r=trade['net']/trade['planned_risk'],trade=trade)
    assert trade['exit_at']<=deadline and release<=as_of
    return label,None


def build_labels(markets, protocol, variant, costs, as_of):
    labels=[];skips=Counter();signals={}
    start=min(markets['BTC_USDT']['hourly'])
    for symbol,m in markets.items():
        rows,_=events(symbol,m,variant,start,as_of,HOUR)
        for at,entries in sorted(rows.items()):
            for signal in entries:
                label,reason=isolated_label(markets,signal,protocol,variant,costs,as_of)
                if label is None:skips[reason]+=1
                else:labels.append(label);signals[(symbol,signal['signal_at'])]=signal
    return sorted(labels,key=lambda r:(r['signal_at'],r['symbol'])),dict(skips),signals


def predict(labels, symbol, sign, at, vector):
    mature=[r for r in labels if r['symbol']==symbol and r['sign']==sign and r['release_at']<=at]
    if len(mature)<20:return dict(accepted=False,reason='PADRAO_AMOSTRA_INSUFICIENTE',training_count=len(mature),neighbors=[],mean_r=None)
    def distance(row):return sum((a-b)**2 for a,b in zip(row['features'],vector))
    neighbors=sorted(mature,key=lambda r:(distance(r),r['signal_at']))[:20]
    mean=sum((r['r'] for r in neighbors),D(0))/20
    return dict(accepted=mean>0,reason=None if mean>0 else 'PADRAO_MEDIA_NAO_POSITIVA',
        training_count=len(mature),mean_r=mean,
        neighbors=[dict(signal_at=r['signal_at'],release_at=r['release_at'],distance=distance(r),r=r['r']) for r in neighbors])


class PatternFilter:
    def __init__(self,labels):self.labels=labels;self.rows=[]
    def __call__(self,markets,signal):
        vector=features(markets,signal)
        result=predict(self.labels,signal['symbol'],signal['sign'],signal['signal_at'],vector)
        self.rows.append(dict(symbol=signal['symbol'],sign=signal['sign'],signal_at=signal['signal_at'],features=vector,**result))
        assert all(r['release_at']<=signal['signal_at'] for r in result['neighbors'])
        return result['reason']


def prefix(markets, cutoff):
    output={}
    for s,m in markets.items():
        output[s]=dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=cutoff},
            fair={t:b for t,b in m['fair'].items() if b.end<=cutoff},
            funding=[e for e in m['funding'] if e['ts']<=cutoff],
            funding_by_time={t:e for t,e in m['funding_by_time'].items() if t<=cutoff},
            minute_resolution={t:e for t,e in m.get('minute_resolution',{}).items() if t+HOUR<=cutoff})
    return output


def verify_labels_and_predictions(markets,labels,signals,p,variant,costs):
    checks=0
    # Every eligible reference label must match an independent full account replay.
    for row in labels:
        symbol=row['symbol']
        signal=signals[(symbol,row['signal_at'])];at=row['entry_at']
        def frozen(symbol_arg,*args):
            _,updates=events(symbol_arg,markets[symbol_arg],variant,at,at+25*HOUR,HOUR)
            return ({at:[signal]} if symbol_arg==symbol else {}),updates
        block=dict(start=iso(at),end=iso(at+25*HOUR),validation_start=iso(at+12*HOUR))
        with patch('scripts.audit_multihour.events',side_effect=frozen):
            wallet=simulate(markets,variant,block,dict(p,leverage=20,risk_fraction='.01'),costs)
        assert len(wallet['trades'])==1
        for key in ('entry','stop','original_stop','quantity','planned_risk','net','exit_at','exit','funding_paid','entry_fee','exit_fee','outcome'):
            assert wallet['trades'][0][key]==row['trade'][key],(symbol,key)
        checks+=1
    causal=0
    for cutoff in [stamp('2026-07-01T00:00:00Z'),stamp('2026-09-01T00:00:00Z'),stamp('2026-11-01T00:00:00Z')]:
        past=prefix(markets,cutoff)
        short,_,_=build_labels(past,p,variant,costs,cutoff)
        assert jsonable(short)==jsonable([r for r in labels if r['release_at']<=cutoff])
        for s,m in markets.items():
            entries,_=events(s,m,variant,cutoff,cutoff+DAY,HOUR)
            for signal in entries.get(cutoff+HOUR,[]):
                vector=features(past,signal)
                assert vector==features(markets,signal)
                a=predict(labels,s,signal['sign'],cutoff,vector)
                b=predict(short,s,signal['sign'],cutoff,vector)
                assert a==b;causal+=1
    return dict(independent_label_replays=checks,prefix_predictions=causal,prefix_label_rebuilds=3)


def run(protocol_path,parent_path,intrahour_source,data_root=None):
    raw=Path(protocol_path).read_bytes();assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA256
    spec=json.loads(raw);root=Path(__file__).resolve().parents[1]
    rawbase=(root/spec['base_protocol']).read_bytes();assert hashlib.sha256(rawbase).hexdigest()==spec['base_protocol_sha256']
    p=json.loads(rawbase);rawparent=Path(parent_path).read_bytes()
    assert hashlib.sha256(rawparent).hexdigest()==spec['parent_results_sha256'];parent=json.loads(rawparent)
    markets,hashes=load_markets(p['blocks'][-1],p,data_root);source=attach_resolution(markets,intrahour_source,p)
    original=next(v for v in p['variants'] if v['name']=='MOMENTUM_BTC_RISK1')
    arms=[dict(deepcopy(original),name=name) for name in spec['arms']]
    base_cost=next(c for c in p['costs'] if c['name']=='base')
    labels,skips,signals=build_labels(markets,p,arms[1],base_cost,max(markets['BTC_USDT']['hourly'])+HOUR)
    print(json.dumps(dict(training_labels=len(labels),training_skips=skips)),flush=True)
    verified=verify_labels_and_predictions(markets,labels,signals,p,arms[1],base_cost)
    verified['closed_signal_prefixes']=verify_signal_causality(markets,arms[0],p)
    result=dict(protocol=spec,protocol_sha256=FROZEN_SHA256,source_sha256=hashes,intrahour_source=source,
        verification=verified,baseline_wallets_reproduced=0,labels=labels,label_skips=skips,
        experiments={},predictions={},production_changed=False,prospective_protocol_changed=False,
        independent_validation=False,approved_for_production=False)
    for block in p['blocks']:
        period=block['name'];result['experiments'][period]={};result['predictions'][period]={}
        for i,v in enumerate(arms):
            result['experiments'][period][v['name']]={}
            for costs in p['costs']:
                filt=PatternFilter(labels) if i==2 else None
                wallet=simulate(markets,v,block,dict(p,leverage=10 if i==0 else 20),costs,
                    entry_ranker=relative_btc_score,entry_filter=filt)
                if i==0:
                    assert jsonable(wallet)==parent['experiments'][period][v['name']][costs['name']]
                    result['baseline_wallets_reproduced']+=1
                for t in wallet['trades']:
                    assert t['planned_risk']<=t['equity_before']*D('.01')+D('1E-18')
                    assert t['exit_at']-t['opened_at']<=24*HOUR
                result['experiments'][period][v['name']][costs['name']]=wallet
                if filt:result['predictions'][period][costs['name']]=filt.rows
                print(json.dumps(jsonable(dict(period=period,arm=v['name'],costs=costs['name'],**wallet['summary']))),flush=True)
    continuous=result['experiments']['continuous_all'];a,b,c=[continuous[v['name']] for v in arms]
    candidate_wallets=[r[arms[2]['name']][costs['name']] for r in result['experiments'].values() for costs in p['costs']]
    checks=dict(continuous_roi_beats_both_controls=all(c[k]['summary']['return_pct']>max(a[k]['summary']['return_pct'],b[k]['summary']['return_pct']) for k in ('base','stress')),
        continuous_base_dd_at_most10=c['base']['summary']['max_drawdown_pct']<=10,
        at_least20_closed_per_cost=all(c[k]['summary']['positions']>=20 for k in ('base','stress')),
        all_three_periods_positive=all(result['experiments'][block['name']][arms[2]['name']][k]['summary']['return_pct']>0 for block in p['blocks'][:3] for k in ('base','stress')),
        no_modeled_liquidations=all(w['summary']['outcomes'].get('LIQUIDACAO',0)==0 for w in candidate_wallets))
    result['exploratory_screen']=dict(conditions=checks,passed=all(checks.values()))
    result['unresolved_liquidation_hours']=[dict(period=period,arm=name,costs=cost,
        symbol=t['symbol'],hour=(t['exit_at']-1)//HOUR*HOUR,ambiguous=t['ambiguous'])
        for period,arms in result['experiments'].items() for name,wallets in arms.items()
        for cost,wallet in wallets.items() for t in wallet['trades']
        if t['outcome']=='LIQUIDACAO' and 'price_resolution' not in t]
    result['ambiguous_training_labels']=[dict(symbol=r['symbol'],signal_at=r['signal_at'],
        outcome=r['trade']['outcome']) for r in labels if r['trade']['ambiguous']]
    return jsonable(result)


def outputs(result,directory):
    out=Path(directory);out.mkdir(parents=True,exist_ok=True)
    full=json.dumps(result,indent=2)+'\n';(out/'results.json').write_text(full)
    compact={k:v for k,v in result.items() if k not in ('experiments','predictions','labels')}
    compact['full_results_sha256']=hashlib.sha256(full.encode()).hexdigest()
    compact['labels_count']=len(result['labels']);compact['labels_by_symbol']=dict(Counter(r['symbol'] for r in result['labels']))
    compact['experiments']={}
    for period,arms in result['experiments'].items():
        compact['experiments'][period]={name:{cost:dict(summary=w['summary'],months=w['months'],temporal_blocks=w['temporal_blocks'],per_symbol=contributions(w)) for cost,w in wallets.items()} for name,wallets in arms.items()}
    (out/'summary.json').write_text(json.dumps(jsonable(compact),indent=2)+'\n')
    rows=[]
    for period,costs in result['predictions'].items():
        for cost,predictions in costs.items():
            for r in predictions:
                rows.append(dict(period=period,costs=cost,symbol=r['symbol'],sign=r['sign'],signal_at=r['signal_at'],
                    accepted=r['accepted'],reason=r['reason'],training_count=r['training_count'],mean_r=r['mean_r'],
                    feature_day=r['features'][0],feature_relative=r['features'][1],
                    neighbors=';'.join(str(n['signal_at']) for n in r['neighbors']),
                    latest_release=max((n['release_at'] for n in r['neighbors']),default='')))
    fields=['period','costs','symbol','sign','signal_at','accepted','reason','training_count','mean_r','feature_day','feature_relative','neighbors','latest_release']
    with (out/'predictions.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
    # Complete labels, including negative outcomes, support independent filter replay.
    (out/'labels.json').write_text(json.dumps(result['labels'],indent=2)+'\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ('protocol','parent','intrahour-source','output'):ap.add_argument('--'+name,required=True)
    ap.add_argument('--data-root')
    a=ap.parse_args();r=run(a.protocol,a.parent,a.intrahour_source,a.data_root);outputs(r,a.output)
    print(json.dumps(r['exploratory_screen'],indent=2))
