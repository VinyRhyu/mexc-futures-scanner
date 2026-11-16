from copy import deepcopy
from dataclasses import replace
import unittest

from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient
from mexc_scanner.models import Candle, Contract, D, Plan, Variant
from scripts.audit_wallet_entry import (budget_position, choose_exit, iso, known_funding, entry_quote,
    limit_fill, price_financial, run_wallet)
from tests.test_minute_breakout import T


def bar(at, op='101', hi='101.2', lo='100.8', close='101'):
    return Candle(at, 60, D(op), D(hi), D(lo), D(close), D(100))


def signal(symbol='A_USDT', *, low='99', stop='98', target='106'):
    contract = Contract.from_api({**DemoClient(T).contracts()[0], 'symbol': symbol})
    plan = Plan(symbol, symbol, 'ROMPIMENTO_M1_VOLUME', 'LONG', T-900, T-900, T+120,
                D(1), D(100), D(98), D(100), D(stop), symbol)
    variant = Variant('CONFIRMADA', T, D(101), D(low), D(103), D(stop), D(target), 'TEST')
    return dict(id=symbol, symbol=symbol, side='LONG', signal=T, stop=D(stop), target=D(target),
                plan=plan, variant=variant, contract=contract)


def history(sig):
    bars = {t: bar(t) for t in range(T, T+600, 60)}
    rates = [dict(at=T-3600, rate='0', cycle_hours=8)]
    return dict(contract=sig['contract'], minute=bars, fair=deepcopy(bars), funding=rates,
                funding_by_time={})


CFG = replace(Config(), initial_balance='100', risk_fraction='0.02', max_cost_fraction='0.30',
              minimum_leverage=10, max_leverage=10, minimum_rr='1')
PROTOCOL = dict(capital='100', leverage=10, risk_fraction='0.02', entry_delay_seconds=60,
                horizon_seconds=240, weeks=[[iso(T),iso(T+600)]],
                costs=[dict(spread='0.0002',taker_fee='0.0006',slippage_rate='0.0002')])


class WalletEntryResearchTests(unittest.TestCase):
    def test_limit_cash_booking_has_no_adverse_entry_slippage(self):
        a=signal();h=history(a)
        h['minute'][T+60]=bar(T+60,lo='98.8',close='99.1')
        h['fair'][T+60]=h['minute'][T+60]
        x=run_wallet([a],{'A_USDT':h},T,T+600,'LIMIT',PROTOCOL,CFG)
        self.assertEqual(x['positions'],1)
        trade=x['trades'][0]
        self.assertEqual(trade['entry_cost'],trade['quantity']*trade['entry']*D(CFG.taker_fee))
        self.assertGreater(trade['reserved_entry_cost'],trade['entry_cost'])
        legacy=run_wallet([a],{'A_USDT':h},T,T+600,'LIMIT',PROTOCOL,CFG,legacy_limit_entry_slippage=True)
        self.assertGreater(x['final'],legacy['final'])

    def test_fee_scenario_assigns_maker_only_to_resting_limit(self):
        from scripts.audit_cost_correction import fee_reprice
        a=signal();h=history(a)
        h['minute'][T+60]=bar(T+60,lo='98.8',close='99.1')
        h['fair'][T+60]=h['minute'][T+60]
        x=run_wallet([a],{'A_USDT':h},T,T+600,'LIMIT',PROTOCOL,CFG)
        t=x['trades'][0]
        scenario=fee_reprice(x,'0','0.0002')
        self.assertEqual(t['entry_kind'],'INTRABAR')
        self.assertEqual(scenario['total_trading_fees'],t['quantity']*t['exit']*D('.0002'))

    def test_modeled_bid_ask_respect_tick_instead_of_creating_empty_singleton_band(self):
        ask=entry_quote(D(101),'LONG',D('.0002'),D('.001'))
        bid=entry_quote(D(101),'SHORT',D('.0002'),D('.001'))
        self.assertEqual(ask,D('101.011'));self.assertEqual(bid,D('100.989'))
        self.assertEqual(ask % D('.001'),0);self.assertEqual(bid % D('.001'),0)

    def position(self):
        return dict(side='LONG', quantity=D(1), entry=D(100), margin=D(10), funding_paid=D(0),
                    mmr=D('.005'), liquidation_fee=D('.0004'), stop_only_fair=False,
                    stop=D(98), target=D(105))

    def test_future_funding_is_not_used_for_entry_decision(self):
        past = dict(at=T-3600,rate='0.0001',cycle_hours=8)
        future = dict(at=T+60,rate='0.5',cycle_hours=1)
        self.assertEqual(known_funding([past],T),known_funding([past,future],T))
        with self.assertRaises(ValueError):known_funding([future],T)

    def test_touch_without_penetration_does_not_fill_limit(self):
        self.assertIsNone(limit_fill(bar(T,lo='100'), 'LONG',D(100),D('.0002'),D('.001')))
        self.assertEqual(limit_fill(bar(T,lo='99.9'), 'LONG',D(100),D('.0002'),D('.001')), 'INTRABAR')

    def test_tp_touch_in_intrabar_entry_minute_does_not_prove_post_fill_tp(self):
        candle=bar(T,op='104',hi='106',lo='100',close='101')
        self.assertIsNone(choose_exit(self.position(),candle,candle,intrabar_entry=True))
        candle=bar(T,op='104',hi='106',lo='100',close='105.5')
        self.assertEqual(choose_exit(self.position(),candle,candle,intrabar_entry=True)[0],'ALVO')

    def test_stop_has_priority_in_ambiguous_bar(self):
        candle=bar(T,hi='106',lo='97')
        self.assertEqual(choose_exit(self.position(),candle,candle),('STOP',D(98),True))

    def test_adverse_gap_fills_beyond_stop(self):
        candle=bar(T,op='96',hi='97',lo='95',close='96')
        self.assertEqual(choose_exit(self.position(),candle,candle),('STOP',D(96),False))

    def test_liquidation_uses_fair_even_if_last_did_not_hit_stop(self):
        last=bar(T);fair=bar(T,lo='85')
        self.assertEqual(choose_exit(self.position(),last,fair)[0],'LIQUIDACAO')

    def test_fair_trigger_execution_uses_conservative_last_bound(self):
        position=self.position();position['stop_only_fair']=True
        last=bar(T,lo='99');fair=bar(T,lo='97')
        self.assertEqual(choose_exit(position,last,fair),('STOP',D(99),False))

    def test_single_price_budget_keeps_original_frozen_band(self):
        sig=signal();before=deepcopy(sig['variant'])
        financial=price_financial(sig,history(sig),D(101),T+61,D(100),CFG,D('.0002'))
        self.assertEqual(financial['status'],'VIAVEL_SIMULADO')
        self.assertEqual(sig['variant'],before)
        budget,reason=budget_position(sig,D(101),financial,D(100),CFG,D('.0002'))
        self.assertIsNone(reason)
        self.assertLessEqual(budget['planned_loss'],D(2))
        self.assertLessEqual(budget['margin']+budget['costs'],D(100))

    def test_limit_is_selected_before_future_fill_is_observed(self):
        a,b=signal(),signal('B_USDT',low='100',stop='99',target='104')
        ha,hb=history(a),history(b)
        hb['minute'][T+60]=bar(T+60,lo='99.8') # B fills, but lower-ranked at decision.
        result=run_wallet([a,b],{'A_USDT':ha,'B_USDT':hb},T,T+600,'LIMIT',PROTOCOL,CFG)
        self.assertEqual(result['positions'],0)
        self.assertEqual(result['skipped']['LIMITE_NAO_PREENCHIDO'],1)
        self.assertEqual(result['skipped']['OUTRO_PLANO_PRIORIZADO'],1)

    def test_future_realized_funding_changes_pnl_not_initial_size(self):
        a=signal();base=history(a);costly=deepcopy(base)
        event=dict(at=T+120,rate='0.01',cycle_hours=8)
        costly['funding'].append(event);costly['funding_by_time']={T+120:[event]}
        for h in (base,costly):
            h['minute'][T+180]=bar(T+180,hi='107',close='106')
            h['fair'][T+180]=h['minute'][T+180]
        x=run_wallet([a],{'A_USDT':base},T,T+600,'MARKET',PROTOCOL,CFG)
        y=run_wallet([a],{'A_USDT':costly},T,T+600,'MARKET',PROTOCOL,CFG)
        self.assertEqual(x['positions'],1);self.assertEqual(y['positions'],1)
        self.assertEqual(x['trades'][0]['quantity'],y['trades'][0]['quantity'])
        self.assertEqual(x['trades'][0]['entry'],y['trades'][0]['entry'])
        self.assertEqual(x['final']-y['final'],y['funding_paid'])

    def test_one_position_blocks_same_bar_reentry_before_exit_is_known(self):
        a,b=signal(),signal('B_USDT',stop='99',target='104')
        b['signal']=T+60;b['variant'].triggered_at=T+60
        ha,hb=history(a),history(b)
        ha['minute'][T+120]=bar(T+120,hi='107',close='106')
        ha['fair'][T+120]=ha['minute'][T+120]
        result=run_wallet([a,b],{'A_USDT':ha,'B_USDT':hb},T,T+600,'MARKET',PROTOCOL,CFG)
        self.assertEqual(result['positions'],1)
        self.assertEqual(result['skipped']['CARTEIRA_OCUPADA'],1)

    def test_prior_sl_or_tp_during_latency_cancels_instead_of_backdating_fill(self):
        a=signal();h=history(a);h['minute'][T]=bar(T,hi='107',close='106')
        result=run_wallet([a],{'A_USDT':h},T,T+600,'MARKET',PROTOCOL,CFG)
        self.assertEqual(result['positions'],0)
        self.assertEqual(result['skipped']['SL_OU_TP_DURANTE_ESPERA'],1)

    def test_short_cashflow_and_target_follow_mirrored_price_path(self):
        a=signal();h=history(a)
        h['minute'][T+180]=bar(T+180,hi='107',close='106')
        h['fair'][T+180]=h['minute'][T+180]
        a['side']='SHORT';a['plan'].side='SHORT';a['plan'].stop=D(102)
        a['stop']=D(102);a['target']=D(94)
        a['variant'].stop=D(102);a['variant'].target=D(94)
        a['variant'].entry_low=D(97);a['variant'].entry_high=D(101)
        for key in ('minute','fair'):
            h[key]={t:Candle(c.ts,c.tf,200-c.open,200-c.low,200-c.high,200-c.close,c.volume)
                    for t,c in h[key].items()}
        result=run_wallet([a],{'A_USDT':h},T,T+600,'MARKET',PROTOCOL,CFG)
        self.assertEqual(result['outcomes'],{'ALVO':1})
        self.assertGreater(result['final'],D(100))
        self.assertEqual(result['trades'][0]['side'],'SHORT')

    def test_round_trip_cost_stress_reprices_same_fill_without_selecting_again(self):
        from scripts.audit_wallet_entry import fixed_fill_stress
        a=signal();h=history(a)
        h['minute'][T+180]=bar(T+180,hi='107',close='106')
        h['fair'][T+180]=h['minute'][T+180]
        p=deepcopy(PROTOCOL)
        p['costs'].append(dict(spread='0.0004',taker_fee='0.0010',slippage_rate='0.0004'))
        result=run_wallet([a],{'A_USDT':h},T,T+600,'MARKET',p,CFG)
        stressed=fixed_fill_stress(result,p)
        self.assertGreater(stressed['extra_cost'],0)
        self.assertEqual(stressed['final'],result['final']-stressed['extra_cost'])
