"""Last seven completed daily momentum cycles, $100, isolated10x. Research only."""
from __future__ import annotations

import argparse,gzip,json
from collections import Counter
from pathlib import Path

from mexc_scanner.models import Candle,D,floor_step,jsonable
from scripts.audit_relative_momentum_daily import (DAY,HOUR,FEE,fill,select,load_source,
                                                   hour_funding,close_position)


def liquidation_level(entry,sign,leverage,mmr,liq_fee):
    return entry*(1-D(sign)/leverage+sign*(mmr+liq_fee))


def prepare_week(signals,market,at,equity,leverage,risk_fraction,stop_buffer=None):
    candidates=[];skips=Counter()
    for s in signals:
        c=market[s['symbol']]['contract'];mid=market[s['symbol']]['hourly'][at].open;sign=s['sign']
        if leverage>c.max_leverage:skips['LEVERAGE_CAP']+=1;continue
        stop=mid-sign*2*s['atr14']
        if stop<=0:skips['INVALID_STOP']+=1;continue
        entry=fill(mid,sign,c.tick)
        original_stop=stop
        if stop_buffer is not None:
            if stop_buffer <= 1:raise ValueError('Liquidation buffer must exceed one')
            initial_mmr,_=c.margin_tier(c.min_volume)
            liq_fee=c.liquidation_fee if c.liquidation_fee is not None else FEE
            initial_liq=liquidation_level(entry,sign,leverage,initial_mmr,liq_fee)
            safe_distance=sign*(entry-initial_liq)/stop_buffer
            if safe_distance<=0:raise ValueError('No safe liquidation distance')
            stop=entry-sign*min(sign*(entry-original_stop),safe_distance)
        stop_fill=fill(stop,-sign,c.tick)
        unit_risk=sign*(entry-stop_fill)+FEE*(entry+stop_fill)
        if unit_risk<=0:skips['INVALID_RISK']+=1;continue
        candidates.append(dict(s,contract=c,entry_mid=mid,entry_fill=entry,stop=stop,
                               original_stop=original_stop,unit_risk=unit_risk,
                               intended_notional=equity*s['weight']*leverage))
    gross=sum((s['intended_notional'] for s in candidates),D(0))
    risk=sum((s['intended_notional']/s['entry_fill']*s['unit_risk'] for s in candidates),D(0))
    scale=min(D(1),equity/(gross/leverage+2*FEE*gross) if gross else D(1),
              equity*risk_fraction/risk if risk else D(1))
    positions=[]
    for s in candidates:
        c=s['contract'];n=floor_step(s['intended_notional']*scale/(s['entry_fill']*c.size),c.volume_step)
        if n<c.min_volume:skips['MIN_LOT']+=1;continue
        if n>c.max_volume:skips['MAX_LOT']+=1;continue
        mmr,tier=c.margin_tier(n)
        if stop_buffer is not None and mmr!=c.margin_tier(c.min_volume)[0]:
            raise ValueError('Sizing changed margin tier; recalculate capped stop before proceeding')
        if leverage>tier:skips['TIER_LEVERAGE']+=1;continue
        qty=n*c.size;notional=qty*s['entry_fill'];margin=notional/leverage
        liq_fee=c.liquidation_fee if c.liquidation_fee is not None else FEE
        liq=liquidation_level(s['entry_fill'],s['sign'],leverage,mmr,liq_fee)
        stop_distance=s['sign']*(s['entry_fill']-s['stop'])
        liq_distance=s['sign']*(s['entry_fill']-liq)
        positions.append(dict(symbol=s['symbol'],sign=s['sign'],opened_at=at,return7=s['return7'],
            entry_mid=s['entry_mid'],entry_fill=s['entry_fill'],quantity=qty,contracts=n,
            entry_fee=qty*s['entry_fill']*FEE,funding_cash=D(0),stop=s['stop'],
            planned_risk=qty*s['unit_risk'],initial_notional=notional,isolated_margin=margin,
            leverage=leverage,liquidation_price=liq,maintenance_rate=mmr,liquidation_fee_rate=liq_fee,
            stop_before_liquidation=s['sign']*(s['stop']-liq)>0,
            has_1_5_liquidation_buffer=liq_distance>=D('1.5')*stop_distance))
        if stop_buffer is not None:
            positions[-1].update(original_stop=s['original_stop'],stop_buffer=stop_buffer,
                                stop_adjusted=s['stop']!=s['original_stop'])
            assert positions[-1]['has_1_5_liquidation_buffer']
    assert sum((t['planned_risk'] for t in positions),D(0))<=equity*risk_fraction+D('1E-18')
    assert sum((t['isolated_margin']+2*t['entry_fee'] for t in positions),D(0))<=equity+D('1E-18')
    return positions,dict(skips)


def exit_flags(pos,last,fair,stop_only_fair=False):
    source=fair if stop_only_fair else last
    stopped=source.low<=pos['stop'] if pos['sign']==1 else source.high>=pos['stop']
    liquidated=fair.low<=pos['liquidation_price'] if pos['sign']==1 else fair.high>=pos['liquidation_price']
    return stopped,liquidated


def liquidate(pos,at,ambiguous):
    loss=pos['isolated_margin']
    return dict(pos,closed_at=at,exit_mid=None,exit_fill=None,exit_fee=D(0),gross_pnl=-loss,
                net_pnl=-loss-pos['entry_fee']+pos['funding_cash'],
                reason='LIQUIDATION_AMBIGUOUS' if ambiguous else 'LIQUIDATION',
                forfeited_margin=loss),-loss


def summarize_week(days,trades,marks):
    start,end=days[0]['start_equity'],days[-1]['end_equity'];peak=start;dd=D(0)
    for row in marks:
        peak=max(peak,row['equity']);dd=max(dd,(peak-row['equity'])/peak)
    gains=sum((t['net_pnl'] for t in trades if t['net_pnl']>0),D(0))
    losses=-sum((t['net_pnl'] for t in trades if t['net_pnl']<0),D(0))
    impact=D(0)
    for t in trades:
        impact+=t['quantity']*t['sign']*(t['entry_fill']-t['entry_mid'])
        if t['exit_fill'] is not None:impact+=t['quantity']*t['sign']*(t['exit_mid']-t['exit_fill'])
    return jsonable(dict(start_balance=start,end_balance=end,net_pnl=end-start,return_pct=(end/start-1)*100,
        days=len(days),trades=len(trades),winning_trades=sum(t['net_pnl']>0 for t in trades),
        losing_trades=sum(t['net_pnl']<0 for t in trades),
        win_rate_pct=D(sum(t['net_pnl']>0 for t in trades))/len(trades)*100 if trades else None,
        profit_factor=gains/losses if losses else None,h1_fair_mark_max_drawdown_pct=dd*100,
        trading_fees=sum((t['entry_fee']+t['exit_fee'] for t in trades),D(0)),
        modeled_execution_impact=impact,signed_funding_cash=sum((t['funding_cash'] for t in trades),D(0)),
        liquidations=sum(t['reason'].startswith('LIQUIDATION') for t in trades),
        liquidation_stop_order_ambiguous=sum(t['reason']=='LIQUIDATION_AMBIGUOUS' for t in trades),
        stops=sum(t['reason'].startswith('STOP') for t in trades),timed_exits=sum(t['reason']=='TIME' for t in trades),
        positions_with_stop_beyond_liquidation=sum(not t['stop_before_liquidation'] for t in trades),
        positions_without_1_5_liquidation_buffer=sum(not t['has_1_5_liquidation_buffer'] for t in trades),
        mean_initial_notional=sum((d['initial_notional'] for d in days),D(0))/len(days),
        mean_initial_margin=sum((d['initial_margin'] for d in days),D(0))/len(days)))


def simulate_week(market,p,leverage,position_gate=None):
    cash=D(p['reference_equity_usdt']);trades,days,marks=[],[],[];skips=Counter();checks=0
    holding=int(p.get('holding_hours',24))*HOUR
    if not 0<holding<=DAY:raise ValueError('Holding hours must be between1 and24')
    for day in range(p['evaluation_start_utc'],p['evaluation_end_utc'],DAY):
        before=cash;at=day+HOUR;signals,ranking=select(market,day)
        prefix={s:dict(m,hourly={t:b for t,b in m['hourly'].items() if b.end<=day},
                        daily={t:b for t,b in m['daily'].items() if b.end<=day}) for s,m in market.items()}
        assert jsonable(select(prefix,day))==jsonable((signals,ranking));checks+=1
        buffer=D(p['liquidation_stop_buffer']) if p.get('liquidation_stop_buffer') else None
        active,skip=prepare_week(signals,market,at,cash,D(leverage),D(p['portfolio_risk_fraction']),buffer)
        if position_gate is not None:
            kept=[t for t in active if position_gate(t,market,day)]
            skip['LONG_CONTEXT']=len(active)-len(kept)
            active=kept
        skips.update(skip);notional=sum((t['initial_notional'] for t in active),D(0))
        margin=sum((t['isolated_margin'] for t in active),D(0));risk=sum((t['planned_risk'] for t in active),D(0))
        cash-=sum((t['entry_fee'] for t in active),D(0));day_trades=[]
        marks.append(dict(ts=at,equity=cash+sum((t['sign']*t['quantity']*
            (market[t['symbol']]['fair'][at].open-t['entry_fill']) for t in active),D(0))))
        for ts in range(at,at+holding,HOUR):
            keep=[]
            locked=sum((t['isolated_margin'] for t in active),D(0))
            for pos in active:
                m=market[pos['symbol']];last=m['hourly'][ts];fair=m['fair'][ts]
                stopped,liq=exit_flags(pos,last,fair,m['contract'].stop_only_fair)
                funding,_=hour_funding(pos,fair,m['funding'],stopped or liq)
                # Funding is paid from free collateral; no automatic position topup.
                if cash+funding < locked:
                    raise ValueError('Available collateral insufficient for funding; dynamic margin not modeled')
                cash+=funding;pos['funding_cash']+=funding
                if liq:
                    trade,change=liquidate(pos,last.end,stopped);cash+=change;day_trades.append(trade)
                    locked-=pos['isolated_margin']
                elif stopped:
                    sign=pos['sign'];gap=last.open<=pos['stop'] if sign==1 else last.open>=pos['stop']
                    mid=min(last.open,pos['stop']) if sign==1 else max(last.open,pos['stop'])
                    trade,change=close_position(pos,mid,last.ts if gap else last.end,
                                               'STOP_GAP' if gap else 'STOP',m['contract'])
                    cash+=change;day_trades.append(trade)
                    locked-=pos['isolated_margin']
                else:keep.append(pos)
            active=keep
            value=cash+sum((t['sign']*t['quantity']*(market[t['symbol']]['fair'][ts].close-t['entry_fill']) for t in active),D(0))
            marks.append(dict(ts=ts+HOUR,equity=value))
        for pos in active:
            m=market[pos['symbol']];last=m['hourly'][at+holding-HOUR]
            trade,change=close_position(pos,last.close,at+holding,'TIME',m['contract'])
            cash+=change;day_trades.append(trade)
        marks.append(dict(ts=at+holding,equity=cash));trades.extend(day_trades)
        days.append(dict(decision_at=day,entry_at=at,exit_at=at+holding,start_equity=before,end_equity=cash,
                         eligible=ranking['eligible'],selected=signals,entries=len(day_trades),
                         initial_notional=notional,initial_margin=margin,planned_stop_risk=risk,
                         net_pnl=cash-before))
    assert abs(cash-D(p['reference_equity_usdt'])-sum((t['net_pnl'] for t in trades),D(0)))<D('1E-18')
    return dict(leverage=leverage,summary=summarize_week(days,trades,marks),days=days,trades=trades,
                hourly_equity=marks,skips=dict(skips),causal_checks=checks)


def run(source_path,protocol_path):
    p=json.loads(Path(protocol_path).read_text());market,excluded=load_source(source_path,p)
    for symbol,m in market.items():
        raw=json.load(gzip.open(Path(source_path)/(symbol+'.json.gz'),'rt'))
        m['fair']={c['ts']:Candle.from_dict(c) for c in raw['fair']}
        assert set(m['fair'])==set(m['hourly'])
    actual=simulate_week(market,p,10);control=simulate_week(market,p,1)
    return jsonable(dict(experiment=p['name'],protocol=p,complete_symbols=sorted(market),excluded=excluded,
        primary10x=actual,control1x=control,production_changed=False,
        limitations=['Same fixed26 current survivors; retrospective contract, MMR and lot rules.',
                     'Keep2% joint planned stop risk, not invest100%margin times10.',
                     'Fixed isolated margin; liquidation trigger is an approximation using current risk tier.',
                     'H1 Fair versus Last cannot order SL and liquidation within an hour: liquidation wins conservatively.',
                     'Full isolated-margin loss assumed for liquidation; no extra exit fee double-counted.',
                     'Actual funding events and Fair H1 valuation; historical fills and order book not observed.',
                     'Seven completed daily cycles, current incomplete cycle excluded; no live orders or Telegram changes.']))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('source','protocol','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();r=run(args.source,args.protocol)
    Path(args.output).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('primary10x','control1x','protocol')},ensure_ascii=False,indent=2))
    print(json.dumps({k:r[k]['summary'] for k in ('primary10x','control1x')},ensure_ascii=False,indent=2))
