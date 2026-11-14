"""Frozen daily 7-day relative momentum portfolio test. No trading or alerts."""
from __future__ import annotations

import argparse
from collections import defaultdict,Counter
from dataclasses import dataclass
import gzip,json
from pathlib import Path

from mexc_scanner.models import Candle,Contract,D,floor_step,jsonable

HOUR=3600
DAY=86400
FEE=D('.0006')
HALF_SPREAD=D('.0001')
SLIP=D('.0002')


def fill(mid,direction,tick):
    return mid*(1+direction*HALF_SPREAD)+direction*max(2*tick,mid*SLIP)


def daily_bars(hourly):
    groups=defaultdict(list)
    for c in hourly.values():groups[c.ts//DAY*DAY].append(c)
    out={}
    for ts,bars in groups.items():
        bars=sorted(bars,key=lambda c:c.ts)
        if len(bars)!=24:continue
        assert [b.ts for b in bars]==list(range(ts,ts+DAY,HOUR))
        out[ts]=Candle(ts,DAY,bars[0].open,max(b.high for b in bars),min(b.low for b in bars),
                       bars[-1].close,sum((b.volume for b in bars),D(0)))
    return out


def context(market,decision):
    """Only completed days/hours before the original daily decision are read."""
    hourly,daily,c=market['hourly'],market['daily'],market['contract']
    needed=[decision-i*DAY for i in range(1,16)]
    if not all(t in daily for t in needed):return None
    close=daily[decision-DAY].close
    old=daily[decision-8*DAY].close  # close at decision minus seven days
    tr=[]
    for i in range(1,15):
        b=daily[decision-i*DAY];prev=daily[decision-(i+1)*DAY].close
        tr.append(max(b.high-b.low,abs(b.high-prev),abs(b.low-prev)))
    volume=sum((hourly[t].volume*c.size*hourly[t].close for t in range(decision-DAY,decision,HOUR)),D(0))
    return dict(return7=close/old-1,atr14=sum(tr,D(0))/14,turnover_proxy=volume)


def select(market,decision):
    eligible={s:ctx for s,m in market.items() if (ctx:=context(m,decision)) is not None
              and ctx['turnover_proxy']>=D(5000000) and ctx['atr14']>0}
    ranked=sorted(eligible,key=lambda s:(eligible[s]['return7'],s))
    k=max(1,len(ranked)//5)
    signals=[]
    for side,names in ((1,ranked[-k:]),(-1,ranked[:k])):
        for s in names:
            if side*eligible[s]['return7']>0:
                signals.append(dict(symbol=s,sign=side,weight=min(D('.20'),D('.5')/k),**eligible[s]))
    return signals,dict(eligible=len(eligible),tail_size=k,ranked=ranked)


def funding_coverage(records,start,end):
    times=sorted(f['ts'] for f in records)
    if not times or times[0]>start or times[-1]<end:return False
    before=max(t for t in times if t<=start);after=min(t for t in times if t>=end)
    relevant=[t for t in times if before<=t<=after]
    return all(0<b-a<=8*HOUR for a,b in zip(relevant,relevant[1:]))


def load_source(directory,p):
    manifest=json.loads((Path(directory)/'manifest.json').read_text())
    market,excluded={},dict(manifest.get('errors',{}))
    for path in sorted(Path(directory).glob('*.json.gz')):
        row=json.load(gzip.open(path,'rt'));symbol=row['symbol']
        bars=[Candle.from_dict(b) for b in row['hourly']]
        assert bars[0].ts==p['warmup_start_utc'] and bars[-1].end==p['evaluation_end_utc']+HOUR
        assert all(a.end==b.ts for a,b in zip(bars,bars[1:]))
        funding=[dict(ts=int(f['ts']),rate=D(f['rate'])) for f in row['funding']]
        if not funding_coverage(funding,p['evaluation_start_utc']+HOUR,p['evaluation_end_utc']+HOUR):
            excluded[symbol]='FUNDING_HISTORY_INCOMPLETE';continue
        hourly={b.ts:b for b in bars};daily=daily_bars(hourly)
        market[symbol]=dict(contract=Contract.from_api(row['contract']),hourly=hourly,daily=daily,
                            funding={f['ts']:f['rate'] for f in funding})
    if len(market)<20:raise ValueError('Fewer than20 complete price/funding histories: '+str(excluded))
    return market,excluded


def prepare(signals,market,at,equity):
    candidates,skipped=[],Counter()
    for s in signals:
        m=market[s['symbol']];c=m['contract'];mid=m['hourly'][at].open;sign=s['sign']
        stop=mid-sign*2*s['atr14']
        if stop<=0:skipped['INVALID_STOP']+=1;continue
        entry=fill(mid,sign,c.tick);stop_fill=fill(stop,-sign,c.tick)
        unit_risk=sign*(entry-stop_fill)+FEE*(entry+stop_fill)
        if unit_risk<=0:skipped['INVALID_RISK']+=1;continue
        notional=equity*s['weight']
        candidates.append(dict(s,entry_mid=mid,entry_fill=entry,stop=stop,unit_risk=unit_risk,
                               intended_notional=notional,contract=c))
    gross=sum((s['intended_notional'] for s in candidates),D(0))
    risk=sum((s['intended_notional']/s['entry_fill']*s['unit_risk'] for s in candidates),D(0))
    scale=min(D(1),equity/(gross*(1+2*FEE)) if gross else D(1),
              equity*D('.02')/risk if risk else D(1))
    positions=[];one_dollar=Counter()
    for s in candidates:
        c=s['contract'];notional=s['intended_notional']*scale
        contracts=floor_step(notional/(s['entry_fill']*c.size),c.volume_step)
        mini=floor_step(notional/equity/(s['entry_fill']*c.size),c.volume_step)
        one_dollar['candidates']+=1
        one_dollar['passes_min_lot' if mini>=c.min_volume else 'below_min_lot']+=1
        if contracts<c.min_volume:skipped['MIN_LOT']+=1;continue
        if contracts>c.max_volume:skipped['MAX_LOT']+=1;continue
        qty=contracts*c.size
        positions.append(dict(symbol=s['symbol'],sign=s['sign'],return7=s['return7'],opened_at=at,
                              entry_mid=s['entry_mid'],entry_fill=s['entry_fill'],stop=s['stop'],
                              quantity=qty,contracts=contracts,entry_fee=qty*s['entry_fill']*FEE,
                              funding_cash=D(0),planned_risk=qty*s['unit_risk'],
                              initial_notional=qty*s['entry_fill']))
    assert sum((t['planned_risk'] for t in positions),D(0))<=equity*D('.02')+D('1E-15')
    assert sum((t['initial_notional']*(1+2*FEE) for t in positions),D(0))<=equity+D('1E-15')
    return positions,dict(skipped),dict(one_dollar),scale


def hour_funding(position,candle,rates,stopped):
    """Use only held settlements; uncertain intrahour credits are not counted."""
    cash=D(0);ignored=0
    for stamp,rate in rates.items():
        if not (position['opened_at']<stamp and candle.ts<stamp<=candle.end):continue
        if stopped and stamp==candle.end:continue
        mark=candle.close if stamp==candle.end else candle.open
        change=-position['sign']*rate*position['quantity']*mark
        if stopped and change>0:ignored+=1;continue
        cash+=change
    return cash,ignored


def close_position(pos,mid,at,reason,contract):
    execution=fill(mid,-pos['sign'],contract.tick)
    gross=pos['sign']*pos['quantity']*(execution-pos['entry_fill'])
    fee=pos['quantity']*execution*FEE
    trade=dict(pos,closed_at=at,exit_mid=mid,exit_fill=execution,exit_fee=fee,
               gross_pnl=gross,net_pnl=gross-pos['entry_fee']-fee+pos['funding_cash'],reason=reason)
    return trade,gross-fee


def metrics(days,trades,marks):
    start,end=days[0]['start_equity'],days[-1]['end_equity']
    peak=start;dd=D(0)
    for m in marks:
        peak=max(peak,m['equity']);dd=max(dd,(peak-m['equity'])/peak)
    gains=sum((t['net_pnl'] for t in trades if t['net_pnl']>0),D(0))
    losses=-sum((t['net_pnl'] for t in trades if t['net_pnl']<0),D(0))
    return jsonable(dict(days=len(days),start_equity=start,end_equity=end,net_return_pct=(end/start-1)*100,
                         hourly_mark_max_drawdown_pct=dd*100,trades=len(trades),
                         winning_trades=sum(t['net_pnl']>0 for t in trades),
                         win_rate_pct=D(sum(t['net_pnl']>0 for t in trades))/len(trades)*100 if trades else None,
                         profit_factor=gains/losses if losses else None,
                         fees=sum((t['entry_fee']+t['exit_fee'] for t in trades),D(0)),
                         modeled_spread_slippage_cost=sum((t['quantity']*t['sign']*
                             (t['entry_fill']-t['entry_mid']+t['exit_mid']-t['exit_fill']) for t in trades),D(0)),
                         signed_funding_cash=sum((t['funding_cash'] for t in trades),D(0)),
                         stops=sum(t['reason'].startswith('STOP') for t in trades),
                         timed_exits=sum(t['reason']=='TIME' for t in trades),
                         profitable_days=sum(d['end_equity']>d['start_equity'] for d in days)))


def simulate(market,p):
    cash=D(p['reference_equity_usdt']);days,trades,marks=[],[],[]
    skipped,mini=Counter(),Counter();ignored_funding_credits=0;causal_checks=0
    for day in range(p['evaluation_start_utc'],p['evaluation_end_utc'],DAY):
        start_cash=cash;at=day+HOUR
        signals,ranking=select(market,day)
        # Poisoning all future hours cannot alter today's ranking or ATR.
        prefix={s:dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=day},
                        daily={t:b for t,b in m['daily'].items() if b.end<=day}) for s,m in market.items()}
        assert jsonable(select(prefix,day))==jsonable((signals,ranking));causal_checks+=1
        active,skip,small,scale=prepare(signals,market,at,cash)
        skipped.update(skip);mini.update(small)
        initial_gross=sum((t['initial_notional'] for t in active),D(0))
        initial_risk=sum((t['planned_risk'] for t in active),D(0))
        cash-=sum((t['entry_fee'] for t in active),D(0))
        marks.append(dict(ts=at,equity=cash+sum((t['sign']*t['quantity']*(t['entry_mid']-t['entry_fill']) for t in active),D(0))))
        day_trades=[]
        for ts in range(at,at+DAY,HOUR):
            keep=[]
            for pos in active:
                m=market[pos['symbol']];b=m['hourly'][ts];sign=pos['sign']
                stopped=b.low<=pos['stop'] if sign==1 else b.high>=pos['stop']
                funding,ignored=hour_funding(pos,b,m['funding'],stopped)
                ignored_funding_credits+=ignored;cash+=funding;pos['funding_cash']+=funding
                if stopped:
                    gap=b.open<=pos['stop'] if sign==1 else b.open>=pos['stop']
                    mid=(min(b.open,pos['stop']) if sign==1 else max(b.open,pos['stop']))
                    trade,change=close_position(pos,mid,b.ts if gap else b.end,'STOP_GAP' if gap else 'STOP',m['contract'])
                    cash+=change;day_trades.append(trade)
                else:keep.append(pos)
            active=keep
            equity=cash+sum((t['sign']*t['quantity']*(market[t['symbol']]['hourly'][ts].close-t['entry_fill']) for t in active),D(0))
            marks.append(dict(ts=ts+HOUR,equity=equity))
        for pos in active:
            m=market[pos['symbol']];last=m['hourly'][at+DAY-HOUR]
            trade,change=close_position(pos,last.close,at+DAY,'TIME',m['contract'])
            cash+=change;day_trades.append(trade)
        marks.append(dict(ts=at+DAY,equity=cash))
        trades.extend(day_trades)
        days.append(dict(decision_at=day,entry_at=at,exit_at=at+DAY,start_equity=start_cash,end_equity=cash,
                         eligible=ranking['eligible'],tail_size=ranking['tail_size'],selected=signals,
                         entries=len(day_trades),gross_fraction=initial_gross/start_cash,
                         planned_risk_fraction=initial_risk/start_cash,scale=scale))
        if cash<=0:raise ValueError('Portfolio depleted')
    summaries={}
    for name,left,right in [('all',p['evaluation_start_utc'],p['evaluation_end_utc']),
                            ('first60',p['evaluation_start_utc'],p['validation_start_utc']),
                            ('validation30',p['validation_start_utc'],p['evaluation_end_utc'])]:
        ds=[d for d in days if left<=d['decision_at']<right]
        ts=[t for t in trades if left+HOUR<=t['opened_at']<right+HOUR]
        ms=[m for m in marks if left+HOUR<=m['ts']<=right+HOUR]
        # Remove next segment's entry fees at the shared boundary from earlier DD.
        ms=[m for m in ms if m['ts']<right+HOUR]+[dict(ts=right+HOUR,equity=ds[-1]['end_equity'])]
        summaries[name]=metrics(ds,ts,ms)
        for side,sign in [('long',1),('short',-1)]:
            st=[t for t in ts if t['sign']==sign]
            summaries[name][side]=jsonable(dict(trades=len(st),wins=sum(t['net_pnl']>0 for t in st),
                                                 net_pnl=sum((t['net_pnl'] for t in st),D(0))))
    assert abs(cash-D(p['reference_equity_usdt'])-sum((t['net_pnl'] for t in trades),D(0)))<D('1E-18')
    return dict(summary=summaries,daily=days,trades=trades,hourly_equity=marks,
                skips=dict(skipped),one_dollar_lot_feasibility=dict(mini),causal_checks=causal_checks,
                uncertain_funding_credits_ignored=ignored_funding_credits)


def benchmark(market,p):
    m=market['BTC_USDT'];c=m['contract'];at=p['evaluation_start_utc']+HOUR;end=p['evaluation_end_utc']+HOUR
    mid=m['hourly'][at].open;entry=fill(mid,1,c.tick);equity=D(p['reference_equity_usdt'])
    n=floor_step(equity/((1+2*FEE)*entry*c.size),c.volume_step);q=n*c.size
    pos=dict(symbol='BTC_USDT',sign=1,opened_at=at,entry_mid=mid,entry_fill=entry,quantity=q,
             contracts=n,entry_fee=q*entry*FEE,funding_cash=D(0))
    cash=equity-pos['entry_fee'];marks=[];split_equity=None
    for ts in range(at,end,HOUR):
        b=m['hourly'][ts];funding,_=hour_funding(pos,b,m['funding'],False)
        cash+=funding;pos['funding_cash']+=funding
        value=cash+q*(b.close-entry);marks.append(dict(ts=b.end,equity=value))
        if b.end==p['validation_start_utc']+HOUR:split_equity=value
    trade,change=close_position(pos,m['hourly'][end-HOUR].close,end,'TIME',c);cash+=change
    peak=equity;dd=D(0)
    for mark in marks+[dict(ts=end,equity=cash)]:peak=max(peak,mark['equity']);dd=max(dd,(peak-mark['equity'])/peak)
    return jsonable(dict(start_equity=equity,end_equity=cash,return_pct=(cash/equity-1)*100,
                          hourly_mark_max_drawdown_pct=dd*100,validation30_marked_return_pct=(cash/split_equity-1)*100,
                          fees=trade['entry_fee']+trade['exit_fee'],signed_funding_cash=pos['funding_cash'],
                          caveat='Context only: BTC buy-and-hold has different exposure and no2% portfolio stop-risk cap.'))


def run(source_path,protocol_path):
    p=json.loads(Path(protocol_path).read_text());market,excluded=load_source(source_path,p)
    result=simulate(market,p)
    # A separate chronological replay must reproduce every first-segment trade.
    prefix_protocol=dict(p,evaluation_end_utc=p['validation_start_utc'],
                         validation_start_utc=p['evaluation_start_utc']+30*DAY)
    prefix={s:dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=p['validation_start_utc']+HOUR},
                   daily={t:b for t,b in m['daily'].items() if b.end<=p['validation_start_utc']},
                   funding={t:v for t,v in m['funding'].items() if t<=p['validation_start_utc']+HOUR})
            for s,m in market.items()}
    first=simulate(prefix,prefix_protocol)
    expected=[t for t in result['trades'] if t['opened_at']<p['validation_start_utc']+HOUR]
    assert jsonable(first['trades'])==jsonable(expected)
    assert first['summary']['all']['end_equity']==result['summary']['first60']['end_equity']
    result['extra_validation']=dict(prefix_60day_replay_identical=True,matched_prefix_trades=len(expected),
        mean_initial_gross_exposure_fraction=sum((d['gross_fraction'] for d in result['daily']),D(0))/90,
        max_planned_portfolio_stop_risk_fraction=max(d['planned_risk_fraction'] for d in result['daily']),
        historical_eligible_symbol_range=[min(d['eligible'] for d in result['daily']),max(d['eligible'] for d in result['daily'])])
    return jsonable(dict(experiment=p['name'],protocol=p,complete_symbols=sorted(market),excluded=excluded,
                         **result,btc_benchmark=benchmark(market,p),
                         limitations=['Universe fixed from currently listed/liquid assets: survivorship and selection bias.',
                                      'Current lot/tick/contract-size rules are applied retrospectively.',
                                      'Costs modeled; no historical order-book/depth or Fair-price series.',
                                      'Funding events observed but valuation approximated with hourly trade-price marks.',
                                      'Stops and drawdown use H1 data; intrahour exact execution is unknown.',
                                      'Dates precede prior Oct/Nov intraday tests; a single reserved30-day block is limited evidence.',
                                      'This is an adaptation, not a replication of a cited academic portfolio.',
                                      'No leverage amplification, no fixedTP or TP-basedRR gate; not a1USD or10x viability claim.',
                                      'Production scanner and Telegram unchanged.']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--protocol',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();r=run(args.source,args.protocol)
    Path(args.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ['daily','trades','hourly_equity','protocol']},ensure_ascii=False,indent=2))
