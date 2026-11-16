"""Causal, single-wallet comparison of one frozen entry-policy hypothesis.

No live scanner state, orders, Telegram, network or parameter search.
"""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.finance import evaluate
from mexc_scanner.minute_breakout import process_minutes
from mexc_scanner.models import Candle, D, jsonable, floor_step, ceil_step
from scripts.audit_m1_trend_context import evaluate as legacy_evaluate
from scripts.audit_sustained_trigger import read_dataset


def ts(text):
    return int(datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp())


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()


def levels_touched(bar, side, stop, target):
    return ((bar.low <= stop, bar.high >= target) if side == 'LONG'
            else (bar.high >= stop, bar.low <= target))


def known_funding(events, at):
    prior = [e for e in events if e['at'] < at]
    if not prior:
        raise ValueError('No known prior funding event at decision')
    row = prior[-1]
    cycle = row['cycle_hours']*3600
    next_at = row['at'] + ((at-row['at'])//cycle+1)*cycle
    return {'fundingRate': row['rate'], 'collectCycle': row['cycle_hours'],
            'nextSettleTime': next_at*1000}


def price_financial(signal, history, price, at, equity, config, spread):
    """Budget/rank at a known actual or contingent price, never future fill price."""
    plan, variant = deepcopy(signal['plan']), deepcopy(signal['variant'])
    if not variant.entry_low <= price <= variant.entry_high:
        return {'status': 'BLOQUEADA', 'reasons': ['PRECO_FORA_DA_FAIXA_ORIGINAL']}
    plan.status = 'ATIVO'
    plan.expires_at = signal['signal']+120
    variant.status = 'VALIDA'
    variant.entry_low = variant.entry_high = price
    # The contingent LIMIT quote is an order-budget assumption, not an observed book.
    bid, ask = (price-price*spread, price) if plan.side == 'LONG' else (price, price+price*spread)
    ticker = {'bid1': bid, 'ask1': ask, 'timestamp': at*1000}
    book = {'bids': [[bid, D('1E15')]], 'asks': [[ask, D('1E15')]], 'timestamp': at*1000}
    funding = known_funding(history['funding'], at-1)
    return evaluate(plan, variant, signal['contract'], equity, ticker, book, funding, at, config)


def preentry_valid(signal, history, decision):
    for at in range(signal['signal'], decision, 60):
        bar = history['minute'][at]
        if any(levels_touched(bar, signal['side'], signal['stop'], signal['target'])):
            return False
    return True


def entry_quote(mid, side, spread, tick):
    return (ceil_step(mid*(1+spread/2),tick) if side=='LONG'
            else floor_step(mid*(1-spread/2),tick))


def limit_fill(bar, side, price, spread, tick):
    sign = 1 if side == 'LONG' else -1
    opening_quote = entry_quote(bar.open,side,spread,tick)
    if opening_quote == price:
        return 'OPEN'
    if sign*(opening_quote-price) < 0:
        return None  # Already through the original band before order placement.
    penetration = price*spread/2 + 2*tick
    crossed = bar.low <= price-penetration if sign == 1 else bar.high >= price+penetration
    return 'INTRABAR' if crossed else None


def entry_cost(quantity, price, tick, fee, slip):
    return quantity*(fee*price+max(2*tick, price*slip))


def exit_cost(quantity, price, tick, fee, slip, spread):
    return quantity*(fee*price+max(2*tick, price*slip)+price*spread/2)


def budget_position(signal, price, financial, equity, config, spread):
    contract=signal['contract'];fee=D(config.taker_fee);slip=D(config.slippage_rate)
    funding=price*D(financial['funding_cost_rate']);tick=contract.tick
    entry_unit=entry_cost(D(1),price,tick,fee,slip)
    stop_unit=exit_cost(D(1),signal['stop'],tick,fee,slip,spread)
    target_unit=exit_cost(D(1),signal['target'],tick,fee,slip,spread)
    sign=1 if signal['side']=='LONG' else -1
    loss_unit=sign*(price-signal['stop'])+entry_unit+stop_unit+funding
    gain_unit=sign*(signal['target']-price)-entry_unit-target_unit-funding
    if loss_unit<=0 or gain_unit/loss_unit<D(config.minimum_rr):
        return None,'RETORNO_RISCO_COM_SPREAD_INSUFICIENTE'
    reserve_unit=entry_unit+max(stop_unit,target_unit)+funding
    max_quantity=min(equity*D(config.risk_fraction)/loss_unit,
                     equity/(price/config.max_leverage+reserve_unit),
                     D(financial['contracts'])*contract.size)
    volume=floor_step(max_quantity/contract.size,contract.volume_step)
    if volume<contract.min_volume:return None,'LOTE_MINIMO_EXCEDE_RISCO_COM_SPREAD'
    quantity=volume*contract.size;margin=quantity*price/config.max_leverage
    mmr,tier=contract.margin_tier(volume)
    assert tier>=config.max_leverage
    assert margin+quantity*reserve_unit<=equity+D('1E-18')
    assert quantity*loss_unit<=equity*D(config.risk_fraction)+D('1E-18')
    return dict(quantity=quantity,margin=margin,mmr=mmr,entry_cost=quantity*entry_unit,
                planned_loss=quantity*loss_unit,net_rr=gain_unit/loss_unit,
                costs=quantity*reserve_unit),None


def liquidation_price(position):
    quantity, entry = position['quantity'], position['entry']
    remaining = position['margin']-position['funding_paid']
    rate = position['mmr']+position['liquidation_fee']
    if position['side'] == 'LONG':
        return (quantity*entry-remaining)/(quantity*(1-rate))
    return (quantity*entry+remaining)/(quantity*(1+rate))


def choose_exit(position, last, fair, *, intrabar_entry=False, deadline=False):
    side, sign = position['side'], 1 if position['side'] == 'LONG' else -1
    liq = liquidation_price(position)
    liquidated = fair.low <= liq if sign == 1 else fair.high >= liq
    if liquidated:
        return 'LIQUIDACAO', None, False
    stop_bar = fair if position['stop_only_fair'] else last
    bad, _ = levels_touched(stop_bar, side, position['stop'], position['target'])
    _, good = levels_touched(last, side, position['stop'], position['target'])
    if bad:
        if not position['stop_only_fair']:
            price = min(position['stop'], last.open) if sign == 1 else max(position['stop'], last.open)
        elif sign*(fair.open-position['stop']) <= 0:
            price = last.open
        else:
            # Last at the instant of an intrabar Fair trigger is unobserved.
            price = last.low if sign == 1 else last.high
        return 'STOP', price, good
    if good and (not intrabar_entry or sign*(last.close-position['target']) >= 0):
        return 'ALVO', position['target'], False
    if deadline:
        return 'TEMPO', last.close, False
    return None


def run_wallet(signals, histories, start, end, policy, protocol, config, *, legacy_limit_entry_slippage=False):
    spread = D(protocol['costs'][0]['spread'])
    fee, slip = D(config.taker_fee), D(config.slippage_rate)
    equity = D(protocol['capital']); initial = equity; position = None
    decisions = defaultdict(list)
    eligible = [s for s in signals if start <= s['signal'] < end]
    boundaries = [ts(w[1]) for w in protocol['weeks'] if start < ts(w[1]) <= end]
    skipped = Counter(); trades=[]; curve=[]; cashflows=[]; peak=equity; max_dd=D(0)
    for signal in eligible:
        cutoff = next(b for b in boundaries if b > signal['signal'])
        if signal['signal']+protocol['horizon_seconds'] >= cutoff:
            skipped['PURGA_ULTIMAS_4H'] += 1
            continue
        decisions[signal['signal']+protocol['entry_delay_seconds']].append(signal)
    for at in range(start, end, 60):
        entry_kind = None
        candidates = decisions.get(at, [])
        if position is not None:
            skipped['CARTEIRA_OCUPADA'] += len(candidates)
        elif candidates:
            ranked=[]
            for signal in candidates:
                history=histories[signal['symbol']];bar=history['minute'][at]
                if not preentry_valid(signal,history,at):
                    skipped['SL_OU_TP_DURANTE_ESPERA'] += 1;continue
                sign=1 if signal['side']=='LONG' else -1
                if policy=='MARKET':
                    price=entry_quote(bar.open,signal['side'],spread,signal['contract'].tick)
                else:
                    price=signal['variant'].entry_low if sign==1 else signal['variant'].entry_high
                    if sign*(entry_quote(bar.open,signal['side'],spread,signal['contract'].tick)-price)<0:
                        skipped['PRECO_JA_ATRAVESSOU_LIMITE'] += 1;continue
                financial=price_financial(signal,history,price,at+1,equity,config,spread)
                if financial['status']!='VIAVEL_SIMULADO':
                    for reason in financial['reasons']:skipped[reason]+=1
                    continue
                budget,reason=budget_position(signal,price,financial,equity,config,spread)
                if budget is None:
                    skipped[reason]+=1;continue
                financial['budget']=budget
                rank=(-budget['net_rr'],budget['costs']/budget['planned_loss'],
                      signal['symbol'],signal['id'])
                ranked.append((rank,signal,financial,price))
            if ranked:
                ranked.sort(key=lambda item:item[0])
                _,signal,financial,price=ranked[0]
                skipped['OUTRO_PLANO_PRIORIZADO'] += len(ranked)-1
                history=histories[signal['symbol']];contract=signal['contract'];bar=history['minute'][at]
                entry_kind='OPEN' if policy=='MARKET' else limit_fill(bar,signal['side'],price,spread,contract.tick)
                if entry_kind is None:
                    # The chosen order reserves the wallet through this last valid minute.
                    skipped['LIMITE_NAO_PREENCHIDO'] += 1
                else:
                    budget=financial['budget'];quantity=budget['quantity']
                    cost,margin,mmr,planned_loss=(budget[k] for k in ('entry_cost','margin','mmr','planned_loss'))
                    if policy=='LIMIT' and not legacy_limit_entry_slippage:
                        # Reserve remains conservative, but an executed LIMIT
                        # cannot incur an adverse fill price beyond its limit.
                        cost=quantity*fee*price
                    position=dict(id=signal['id'],symbol=signal['symbol'],side=signal['side'],signal=signal['signal'],
                        decision_at=at,entry_bar=at,entry_interval=[at,at+60] if entry_kind=='INTRABAR' else [at,at],
                        entry_kind=entry_kind,entry=price,entry_mid=bar.open,quantity=quantity,tick=contract.tick,
                        stop=signal['stop'],target=signal['target'],margin=margin,mmr=mmr,
                        liquidation_fee=contract.liquidation_fee if contract.liquidation_fee is not None else fee,stop_only_fair=contract.stop_only_fair,
                        funding_paid=D(0),equity_before=equity,entry_cost=cost,planned_loss=planned_loss,
                        deadline=signal['signal']+protocol['horizon_seconds'],projected_net_rr=budget['net_rr'])
                    if policy=='LIMIT' and not legacy_limit_entry_slippage:
                        position.update(limit_entry_no_slippage=True,reserved_entry_cost=budget['entry_cost'])
                    equity-=cost;cashflows.append(dict(at=at,kind='ENTRY_COST',amount=-cost,plan_id=position['id']))
        if position is not None:
            history=histories[position['symbol']];last=history['minute'][at];fair=history['fair'][at]
            for funding in history['funding_by_time'].get(at,[]):
                sign=1 if position['side']=='LONG' else -1
                amount=position['quantity']*fair.open*D(funding['rate'])*sign
                if entry_kind=='INTRABAR' and amount<0:
                    continue # No unproved credit before the unknown intraminute fill.
                position['funding_paid']+=amount;equity-=amount
                cashflows.append(dict(at=at,kind='FUNDING',amount=-amount,plan_id=position['id']))
            result=choose_exit(position,last,fair,intrabar_entry=entry_kind=='INTRABAR',deadline=last.end>=position['deadline'])
            if result:
                label,price,ambiguous=result
                if label=='LIQUIDACAO':
                    change=-(position['margin']-position['funding_paid']);cost=D(0)
                else:
                    sign=1 if position['side']=='LONG' else -1
                    cost=exit_cost(position['quantity'],price,position['tick'],fee,slip,spread)
                    change=position['quantity']*sign*(price-position['entry'])-cost
                equity+=change;cashflows.append(dict(at=last.end,kind='EXIT_PNL_COST',amount=change,plan_id=position['id']))
                assert equity>=0, 'Equity negative despite isolated margin constraints'
                trades.append(dict(position,outcome=label,exit=price,exit_at=last.end,exit_cost=cost,
                    ambiguous=ambiguous,net=equity-position['equity_before'],equity_after=equity))
                position=None
        marked=equity
        if position is not None:
            bar=histories[position['symbol']]['minute'][at]
            sign=1 if position['side']=='LONG' else -1
            marked+=position['quantity']*sign*(bar.close-position['entry'])-exit_cost(
                position['quantity'],bar.close,position['tick'],fee,slip,spread)
        peak=max(peak,marked)
        max_dd=max(max_dd,(peak-marked)/peak)
        if (at+60-start)%86400==0:curve.append(dict(at=at+60,equity=marked))
    assert position is None, 'Weekly purge failed to close all positions'
    assert abs(initial+sum((e['amount'] for e in cashflows),D(0))-equity)<D('1E-18')
    assert all(a['exit_at']<=b['decision_at'] for a,b in zip(trades,trades[1:]))
    gains=sum((t['net'] for t in trades if t['net']>0),D(0));losses=-sum((t['net'] for t in trades if t['net']<0),D(0))
    return dict(policy=policy,start=start,end=end,initial=initial,final=equity,net=equity-initial,
        return_pct=(equity/initial-1)*100,max_drawdown_pct=max_dd*100,positions=len(trades),
        outcomes=dict(Counter(t['outcome'] for t in trades)),positive=sum(t['net']>0 for t in trades),
        negative=sum(t['net']<0 for t in trades),win_rate_pct=D(sum(t['net']>0 for t in trades))/len(trades)*100 if trades else None,
        profit_factor=gains/losses if losses else None,fees_slippage_spread=sum((t['entry_cost']+t['exit_cost'] for t in trades),D(0)),
        funding_paid=sum((t['funding_paid'] for t in trades),D(0)),skipped=dict(skipped),trades=trades,daily_curve=curve,cashflows=cashflows)


def fixed_fill_stress(result, protocol):
    base,stress=protocol['costs'];cash=D(protocol['capital']);violations=0;extra=D(0)
    for t in result['trades']:
        q,entry,tick=t['quantity'],t['entry'],t['tick']
        stressed_entry=(q*entry*D(stress['taker_fee']) if t.get('limit_entry_no_slippage') else
                        entry_cost(q,entry,tick,D(stress['taker_fee']),D(stress['slippage_rate'])))
        delta=stressed_entry-t['entry_cost']
        if t['entry_kind']=='OPEN' and result['policy']=='MARKET':
            delta+=q*t['entry_mid']*(D(stress['spread'])-D(base['spread']))/2
        entry_delta=delta
        if t['exit'] is not None:
            delta+=exit_cost(q,t['exit'],tick,D(stress['taker_fee']),D(stress['slippage_rate']),D(stress['spread']))-t['exit_cost']
        if t['margin']+t['entry_cost']+entry_delta>cash:violations+=1
        cash+=t['net']-delta;extra+=delta
    return dict(final=cash,net=cash-D(protocol['capital']),return_pct=(cash/D(protocol['capital'])-1)*100,
                extra_cost=extra,fixed_size_margin_violations=violations,
                interpretation='Same base executions and quantities repriced; not a reselected higher-fee strategy.')


def build_inputs(sources, valuation, protocol):
    config=load_config('config/default.toml');histories={};signals=[];compat=[]
    val=Path(valuation);vm=json.loads((val/'summary.json').read_text())
    assert vm['complete']==vm['selected']==len(protocol['symbols']) and not vm['errors']
    for directory in map(Path,sources):
        manifest=json.loads((directory/'summary.json').read_text());start=ts(manifest['start_brt']);end=ts(manifest['end_exclusive_brt'])
        old=[];formed=0
        for spec in manifest['datasets']:
            assert spec['ohlc_matches']
            data=read_dataset(directory,spec);symbol=spec['symbol']
            plans,_,_=process_minutes(symbol,data['quarter'],data['hourly'],data['minute'],[],0,
                data['minute'][-1].end+10,data['contract'].tick,config,start)
            for plan in plans:
                if not start<=plan.formed_at<end or 'CONFIRMADA' not in plan.variants:continue
                variant=plan.variants['CONFIRMADA'];formed+=1
                old.append(dict(symbol=symbol,side=plan.side,signal=variant.triggered_at,
                    stop=variant.stop,target=variant.target,result=legacy_evaluate(plan,variant,data,config)))
                if symbol not in protocol['symbols']:continue
                signals.append(dict(id=plan.id,symbol=symbol,side=plan.side,signal=variant.triggered_at,
                    stop=variant.stop,target=variant.target,plan=plan,variant=variant,contract=data['contract']))
            if symbol in protocol['symbols']:
                existing=histories.setdefault(symbol,dict(contract=data['contract'],minute={}))
                for bar in data['minute']:
                    if bar.ts in existing['minute']:assert existing['minute'][bar.ts]==bar
                    existing['minute'][bar.ts]=bar
            print(json.dumps(dict(stage='compatibility',source=directory.name,symbol=symbol,confirmations=formed)),flush=True)
        unique={(r['symbol'],r['side'],r['signal'],r['stop'],r['target']):r for r in old}
        entered=[r for r in unique.values() if 'entered_at' in r['result']]
        counts=Counter('STOP' if r['result']['outcome'].startswith('STOP') else r['result']['outcome'] for r in entered)
        expected={'ALVO':49,'STOP':71,'ABERTO':3} if manifest['analyzed_symbols']==31 else {'ALVO':25,'STOP':65,'ABERTO':17}
        assert dict(counts)==expected,(directory,counts,expected)
        compat.append(dict(source=str(directory),confirmations=formed,entries=len(entered),outcomes=dict(counts),reproduced=True))
    for spec in vm['datasets']:
        raw=gzip.decompress((val/(spec['symbol']+'.json.gz')).read_bytes())
        assert hashlib.sha256(raw).hexdigest()==spec['sha256_uncompressed']
        data=json.loads(raw);history=histories[spec['symbol']]
        history['fair']={b['ts']:Candle.from_dict(b) for b in data['fair']}
        history['funding']=sorted(data['funding'],key=lambda r:r['at']);history['funding_by_time']=defaultdict(list)
        assert all(e['at']%60==0 for e in data['funding'])
        for event in data['funding']:history['funding_by_time'][event['at']].append(event)
    unique={(r['symbol'],r['side'],r['signal'],r['stop'],r['target']):r for r in signals}
    return list(unique.values()),histories,compat,vm


def run(sources, valuation, protocol, amendment, *, legacy_limit_entry_slippage=False):
    p=json.loads(Path(protocol).read_text());a=json.loads(Path(amendment).read_text())
    signals,histories,compat,vm=build_inputs(sources,valuation,p)
    cfg=replace(load_config('config/default.toml'),initial_balance=p['capital'],minimum_leverage=10,max_leverage=10,
        risk_fraction=p['risk_fraction'],max_cost_fraction=a['max_cost_fraction']).validate()
    result=dict(protocol=p,amendment=a,protocol_sha256=hashlib.sha256(Path(protocol).read_bytes()).hexdigest(),
        compatibility=compat,valuation_manifest=vm,unique_confirmations=len(signals),weekly={},continuous={},production_changed=False)
    for label,start,end in [('continuous',p['start_brt'],p['end_exclusive_brt'])]+[(str(i+1),w[0],w[1]) for i,w in enumerate(p['weeks'])]:
        arms={}
        for policy in ('MARKET','LIMIT'):
            wallet=run_wallet(signals,histories,ts(start),ts(end),policy,p,cfg,
                              legacy_limit_entry_slippage=legacy_limit_entry_slippage)
            wallet['fixed_fill_stress']=fixed_fill_stress(wallet,p);arms[policy]=wallet
            print(json.dumps(jsonable(dict(stage='wallet',period=label,policy=policy,final=wallet['final'],
                positions=wallet['positions'],return_pct=wallet['return_pct'],outcomes=wallet['outcomes']))),flush=True)
        if label=='continuous':result['continuous']=arms
        else:result['weekly'][label]=arms
    control,candidate=result['continuous']['MARKET'],result['continuous']['LIMIT'];latest=result['weekly']['3']['LIMIT']
    screen=(candidate['final']>max(D(p['capital']),control['final']) and candidate['max_drawdown_pct']<=10
        and candidate['positions']>=30 and latest['positions']>=15 and latest['final']>D(p['capital'])
        and all(w['LIMIT']['final']>=D(p['capital']) for w in result['weekly'].values())
        and candidate['fixed_fill_stress']['final']>D(p['capital']) and candidate['fixed_fill_stress']['fixed_size_margin_violations']==0)
    result.update(exploratory_screen_passed=screen,independent_validation=False,approved_for_production=False)
    return jsonable(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',action='append',required=True);parser.add_argument('--valuation',required=True)
    parser.add_argument('--protocol',required=True);parser.add_argument('--amendment',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--legacy-limit-entry-slippage',action='store_true',help='Reproduce the superseded cash-booking approximation')
    args=parser.parse_args();result=run(args.source,args.valuation,args.protocol,args.amendment,
        legacy_limit_entry_slippage=args.legacy_limit_entry_slippage)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('unique_confirmations','compatibility','exploratory_screen_passed','approved_for_production')},indent=2))
