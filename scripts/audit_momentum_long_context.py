"""One fixed LONG context filter evaluated on prior14 days, with known-week diagnostic."""
import argparse,gzip,json
from pathlib import Path

from mexc_scanner.models import Candle,D,jsonable
from scripts.audit_relative_momentum_daily import HOUR,load_source,funding_coverage
from scripts.audit_momentum_week10x import simulate_week


def ema_context(market,decision,period=20):
    bars=sorted((b for b in market['hourly'].values() if b.end<=decision),key=lambda b:b.ts)
    if len(bars)<period:raise ValueError('Insufficient completed H1 bars for EMA')
    ema=sum((b.close for b in bars[:period]),D(0))/period
    alpha=D(2)/(period+1)
    for b in bars[period:]:ema=alpha*b.close+(1-alpha)*ema
    return dict(close=bars[-1].close,ema20=ema,last_bar_end=bars[-1].end,
                long_allowed=bars[-1].close>ema)


def allow_long(position,market,decision):
    if position['sign']<0:return True
    return ema_context(market[position['symbol']],decision)['long_allowed']


def split_outcomes(trades):
    gains=sum((D(t['net_pnl']) for t in trades if D(t['net_pnl'])>0),D(0))
    losses=sum((D(t['net_pnl']) for t in trades if D(t['net_pnl'])<0),D(0))
    return jsonable(dict(trades=len(trades),wins=sum(D(t['net_pnl'])>0 for t in trades),
        losses=sum(D(t['net_pnl'])<0 for t in trades),net_pnl=gains+losses,
        positive_pnl=gains,negative_pnl=losses,
        stops=sum(t['reason'].startswith('STOP') for t in trades),
        liquidations=sum(t['reason'].startswith('LIQUIDATION') for t in trades)))


def run(source,protocol,baseline):
    p=json.loads(Path(protocol).read_text());market,excluded=load_source(source,p)
    for symbol,m in market.items():
        raw=json.load(gzip.open(Path(source)/(symbol+'.json.gz'),'rt'))
        m['fair']={b['ts']:Candle.from_dict(b) for b in raw['fair']}
        assert set(m['fair'])==set(m['hourly'])
        records=[dict(ts=ts,rate=rate) for ts,rate in m['funding'].items()]
        for window in p['evaluation_windows']:
            assert funding_coverage(records,window['start_utc']+HOUR,window['end_utc']+HOUR),symbol
    results={}
    for window in p['evaluation_windows']:
        config=dict(p,evaluation_start_utc=window['start_utc'],evaluation_end_utc=window['end_utc'])
        control=jsonable(simulate_week(market,config,10))
        gate_log=[]
        def gate(t,data,day):
            allowed=allow_long(t,data,day)
            context=ema_context(data[t['symbol']],day) if t['sign']>0 else None
            gate_log.append(dict(symbol=t['symbol'],sign=t['sign'],decision_at=day,
                                 opened_at=t['opened_at'],allowed=allowed,context=context))
            return allowed
        filtered=jsonable(simulate_week(market,config,10,gate))
        rejected=[];kept=[];contexts=[];causal=0
        for t in control['trades']:
            day=t['opened_at']-HOUR;m=market[t['symbol']]
            context=ema_context(m,day)
            prefix=dict(m,hourly={ts:b for ts,b in m['hourly'].items() if b.end<=day})
            assert context==ema_context(prefix,day);causal+=1
            allowed=t['sign']<0 or context['long_allowed']
            (kept if allowed else rejected).append(t)
            contexts.append(dict(symbol=t['symbol'],opened_at=t['opened_at'],sign=t['sign'],
                                 allowed=allowed,context=context,baseline_net_pnl=t['net_pnl'],
                                 baseline_reason=t['reason']))
        if window['name']=='known7_diagnostic':
            old=json.loads(Path(baseline).read_text())['scenarios']['capped_risk2']
            for key in ('summary','days','trades','hourly_equity','skips','causal_checks'):
                assert control[key]==old[key],f'Known-week baseline changed: {key}'
        a={(t['opened_at'],t['symbol']):t for t in control['trades']}
        for t in filtered['trades']:
            key=t['opened_at'],t['symbol']
            assert key in a,'Filter introduced a new unranked entry'
            assert t['sign']==a[key]['sign']
        results[window['name']]=dict(window=window,control=control,filtered=filtered,
            control_sides={side:split_outcomes([t for t in control['trades'] if t['sign']==sign])
                           for side,sign in [('long',1),('short',-1)]},
            filtered_sides={side:split_outcomes([t for t in filtered['trades'] if t['sign']==sign])
                           for side,sign in [('long',1),('short',-1)]},
            fixed_baseline_positions=dict(rejected=split_outcomes(rejected),kept=split_outcomes(kept),
                note='Removal attribution at baseline quantities, not full filtered-equity simulation.'),
            gate_log=gate_log,baseline_contexts=contexts,ema_causal_prefix_checks=causal)
    return jsonable(dict(protocol=p,complete_symbols=sorted(market),excluded=excluded,
        windows=results,known7_control_replay_identical=True,production_changed=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for k in ('source','protocol','baseline','output'):ap.add_argument('--'+k,required=True)
    a=ap.parse_args();r=run(a.source,a.protocol,a.baseline)
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({name:dict(control=x['control']['summary'],filtered=x['filtered']['summary'],
        rejected_baseline=x['fixed_baseline_positions']['rejected'],
        control_sides=x['control_sides'],filtered_sides=x['filtered_sides'])
        for name,x in r['windows'].items()},indent=2))
