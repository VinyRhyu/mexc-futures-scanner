"""Correct LIMIT cash booking and quantify fees on fixed executions, no new strategy."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from mexc_scanner.config import load_config
from mexc_scanner.models import D, jsonable
from scripts.audit_wallet_entry import build_inputs, fixed_fill_stress, run_wallet, ts


def fee_reprice(wallet, maker, taker, original_fee=D('.0006')):
    cash=D(wallet['initial']);fees=D(0);change=D(0);violations=0
    for trade in wallet['trades']:
        resting=wallet['policy']=='LIMIT' and trade['entry_kind']=='INTRABAR'
        entry_rate=D(maker) if resting else D(taker)
        entry_fee=trade['quantity']*trade['entry']*entry_rate
        original_entry_fee=trade['quantity']*trade['entry']*original_fee
        entry_delta=entry_fee-original_entry_fee
        delta=entry_delta;fees+=entry_fee
        if trade['exit'] is not None:
            exit_fee=trade['quantity']*trade['exit']*D(taker)
            delta+=exit_fee-trade['quantity']*trade['exit']*original_fee;fees+=exit_fee
        # Exit fees are not known cash debits at entry. Check entry feasibility
        # before adding the subsequent round-trip fee change to final cash.
        required=trade['margin']+trade['entry_cost']+entry_delta
        violations+=required>cash
        cash+=trade['net']-delta;change-=delta
    return dict(final=cash,net=cash-D(wallet['initial']),return_pct=(cash/D(wallet['initial'])-1)*100,
        total_trading_fees=fees,pnl_change_from_fees=change,fixed_size_margin_violations=violations,
        interpretation='Same trades, sizes and funding; cash-only fee counterfactual, no new trade selection/resizing.')


def attribute(wallet, fee=D('.0006')):
    gross=D(0);fees=D(0)
    for trade in wallet['trades']:
        assert trade['exit'] is not None,'Liquidation requires separate attribution'
        sign=1 if trade['side']=='LONG' else -1
        gross+=trade['quantity']*sign*(trade['exit']-trade['entry'])
        fees+=trade['quantity']*(trade['entry']+trade['exit'])*fee
    other=wallet['fees_slippage_spread']-fees
    assert abs(gross-fees-other-wallet['funding_paid']-wallet['net'])<D('1E-18')
    turnover=fees/fee
    breakeven=(wallet['net']+fees)/turnover*100 if turnover else None
    return dict(gross_at_assigned_fill_prices=gross,trading_fees=fees,
        explicit_slippage_exit_spread=other,funding_paid=wallet['funding_paid'],net=wallet['net'],
        fixed_execution_uniform_fee_break_even_pct=breakeven,
        note='Gross already includes the modeled MARKET entry quote/spread. Negative break-even means zero fees alone do not cover other costs.')


def decimal_wallet(wallet):
    # Only numeric fields used in cash repricing; preserve labels and timestamps.
    result=dict(wallet)
    for key in ('initial','final','net','fees_slippage_spread','funding_paid'):
        result[key]=D(result[key])
    result['trades']=[dict(t) for t in wallet['trades']]
    fields=('quantity','entry','entry_mid','tick','margin','entry_cost','exit_cost','net','funding_paid')
    for trade in result['trades']:
        for key in fields:trade[key]=D(trade[key])
        if trade['exit'] is not None:trade['exit']=D(trade['exit'])
    return result


def run(sources,valuation,protocol,amendment,correction,parent,reversal):
    p=json.loads(Path(protocol).read_text());a=json.loads(Path(amendment).read_text())
    correction_doc=json.loads(Path(correction).read_text())
    assert hashlib.sha256(Path(parent).read_bytes()).hexdigest()==correction_doc['legacy_entry_result_sha256']
    assert hashlib.sha256(Path(reversal).read_bytes()).hexdigest()==correction_doc['legacy_reversal_result_sha256']
    old=json.loads(Path(parent).read_text());rev=json.loads(Path(reversal).read_text())
    signals,histories,compat,vm=build_inputs(sources,valuation,p)
    cfg=replace(load_config('config/default.toml'),initial_balance=p['capital'],minimum_leverage=10,max_leverage=10,
                risk_fraction=p['risk_fraction'],max_cost_fraction=a['max_cost_fraction']).validate()
    result=dict(correction=correction_doc,protocol=p,compatibility=compat,valuation_manifest=vm,
                continuous={},weekly={},production_changed=False)
    for label,start,end in [('continuous',p['start_brt'],p['end_exclusive_brt'])]+[(str(i+1),w[0],w[1]) for i,w in enumerate(p['weeks'])]:
        control=run_wallet(signals,histories,ts(start),ts(end),'MARKET',p,cfg)
        old_arms=old['continuous'] if label=='continuous' else old['weekly'][label]
        assert jsonable(control)=={k:v for k,v in old_arms['MARKET'].items() if k!='fixed_fill_stress'}
        candidate=run_wallet(signals,histories,ts(start),ts(end),'LIMIT',p,cfg)
        candidate['fixed_fill_stress']=fixed_fill_stress(candidate,p)
        rev_arm=rev['continuous']['REVERSAL'] if label=='continuous' else rev['weekly'][label]['REVERSAL']
        arms=dict(MARKET=control,LIMIT=candidate,REVERSAL=decimal_wallet(rev_arm))
        for key,wallet in arms.items():
            wallet['cost_attribution']=attribute(wallet)
            wallet['fee_scenarios']={s['name']:fee_reprice(wallet,s['maker'],s['taker'])
                                     for s in correction_doc['fee_scenarios']}
            print(json.dumps(jsonable(dict(period=label,model=key,final=wallet['final'],positions=wallet['positions']))),flush=True)
        if label=='continuous':result['continuous']=arms
        else:result['weekly'][label]=arms
    c=result['continuous']['LIMIT'];latest=result['weekly']['3']['LIMIT']
    result.update(exploratory_screen_passed=(c['final']>max(D(100),result['continuous']['MARKET']['final'])
        and c['max_drawdown_pct']<=10 and c['positions']>=30 and latest['positions']>=15 and latest['final']>100
        and all(w['LIMIT']['final']>=100 for w in result['weekly'].values())
        and c['fixed_fill_stress']['final']>100 and c['fixed_fill_stress']['fixed_size_margin_violations']==0),
        approved_for_production=False,independent_validation=False)
    return jsonable(result)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',action='append',required=True)
    for key in ('valuation','protocol','amendment','correction','parent','reversal','output'):ap.add_argument('--'+key,required=True)
    args=ap.parse_args();result=run(args.source,args.valuation,args.protocol,args.amendment,args.correction,args.parent,args.reversal)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
