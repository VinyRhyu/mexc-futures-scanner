from copy import deepcopy
import unittest

from mexc_scanner.demo import DemoClient
from mexc_scanner.models import Candle, Contract, D, jsonable
from scripts.audit_multihour import (HOUR, aggregate, close, events, execution,
    exit_event, liquidation, risk_budget, simulate, market_gate_allows,settlement_amount)

T = 1790812800  # Whole UTC day.
COSTS = dict(fee='.0006', spread='.0002', slippage='.0002')
VARIANT = dict(name='TEST',tf_hours=1,channel=24,exit_channel=12,ema=200,
    stop_atr=2,trail_atr=2,max_hold_hours=72,kind='CHANNEL')
PROTOCOL = dict(initial_equity='100',leverage=10,risk_fraction='.02',
    minimum_turnover='0',min_liquidation_buffer='1.5',signal_delay_seconds=HOUR)


def bar(at, op='100', hi='101', lo='99', cl='100'):
    return Candle(at,HOUR,D(op),D(hi),D(lo),D(cl),D(1000000))


def market():
    bars = {t:bar(t) for t in range(T-300*HOUR,T+100*HOUR,HOUR)}
    contract = Contract.from_api(DemoClient(T).contracts()[0])
    return dict(contract=contract,hourly=bars,fair=deepcopy(bars),
        funding=[dict(ts=T-8*HOUR,rate=D(0),cycle=8)],funding_by_time={})


class MultihourTests(unittest.TestCase):
    def signal(self):
        return dict(symbol='A',sign=1,signal_at=T-HOUR,stop=D(96),turnover=D(10000000),score=D(1))

    def position(self):
        return dict(sign=1,quantity=D(1),entry=D(100),margin=D(10),mmr=D('.005'),
            liquidation_fee=D('.0006'),funding_paid=D(0),stop=D(96),entry_fee=D('.06'))

    def test_timeframe_aggregation_keeps_only_complete_groups(self):
        bars = [bar(T+i*HOUR) for i in range(7)]
        result = aggregate(bars,4)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].tf,4*HOUR)
        self.assertEqual(result[0].volume,D(4000000))

    def test_signal_and_rank_do_not_change_with_future_bars(self):
        m=market();m['hourly'][T-HOUR]=bar(T-HOUR,hi='104',cl='103')
        full=events('A',m,VARIANT,T,T+10*HOUR)
        short=deepcopy(m)
        short['hourly']={t:b for t,b in m['hourly'].items() if b.end<=T}
        truncated=events('A',short,VARIANT,T,T+10*HOUR)
        at=T+HOUR
        self.assertEqual(jsonable(full[0][at]),jsonable(truncated[0][at]))
        self.assertEqual(jsonable(full[1][at]),jsonable(truncated[1][at]))
        self.assertEqual(full[0][at][0]['signal_at'],T)

    def test_costs_are_adverse_and_rounded_for_both_sides(self):
        self.assertEqual(execution(D(100),1,D('.01'),COSTS),D('100.03'))
        self.assertEqual(execution(D(100),-1,D('.01'),COSTS),D('99.97'))

    def test_stop_during_delay_cancels_the_signal(self):
        m=market();m['hourly'][T-HOUR]=bar(T-HOUR,lo='95')
        p,reason=risk_budget(self.signal(),m,T,D(100),PROTOCOL,VARIANT,COSTS)
        self.assertIsNone(p);self.assertEqual(reason,'STOP_DURANTE_LATENCIA')

    def test_future_funding_cannot_change_size(self):
        m=market();a,_=risk_budget(self.signal(),m,T,D(100),PROTOCOL,VARIANT,COSTS)
        m['funding'].append(dict(ts=T+HOUR,rate=D('.5'),cycle=1))
        b,_=risk_budget(self.signal(),m,T,D(100),PROTOCOL,VARIANT,COSTS)
        self.assertEqual(a,b)
        self.assertLessEqual(a['planned_risk'],D(2))
        self.assertLessEqual(a['margin']+a['entry_fee'],D(100))

    def test_stop_beyond_liquidation_is_rejected(self):
        s=self.signal();s['stop']=D(80)
        p,reason=risk_budget(s,market(),T,D(100),PROTOCOL,VARIANT,COSTS)
        self.assertIsNone(p);self.assertEqual(reason,'STOP_PROXIMO_DA_LIQUIDACAO')

    def test_gap_stop_uses_actual_open(self):
        b=bar(T,op='94',hi='95',lo='93',cl='94')
        self.assertEqual(exit_event(self.position(),b,b,False),('STOP',D(94),False))

    def test_fair_liquidation_overrides_last_stop_with_ambiguity(self):
        last=bar(T,lo='95');fair=bar(T,lo='80')
        self.assertEqual(exit_event(self.position(),last,fair,False),('LIQUIDACAO',None,True))

    def test_fair_stop_uses_conservative_last_bound(self):
        last=bar(T,lo='97');fair=bar(T,lo='95')
        self.assertEqual(exit_event(self.position(),last,fair,True),('STOP',D(97),False))

    def test_liquidation_does_not_double_charge_funding(self):
        p=self.position();p['funding_paid']=D(1)
        trade,delta=close(p,None,T,'LIQUIDACAO',COSTS)
        self.assertEqual(delta,D(-9))
        self.assertEqual(trade['net'],D('-10.06'))

    def test_mirrored_short_exit(self):
        p=self.position();p.update(sign=-1,stop=D(104))
        b=bar(T,op='106',hi='107',lo='105',cl='106')
        self.assertEqual(exit_event(p,b,b,False),('STOP',D(106),False))

    def test_single_wallet_reconciles_trades_and_funding(self):
        m=market();m['hourly'][T-HOUR]=bar(T-HOUR,hi='104',cl='103')
        m['fair'][T-HOUR]=m['hourly'][T-HOUR]
        block=dict(start='2026-10-01T00:00:00+00:00',end='2026-10-02T00:00:00+00:00',
            validation_start='2026-10-01T12:00:00+00:00')
        # A flat future path keeps stop before liquidation; boundary closes it.
        for t in range(T,T+24*HOUR,HOUR):
            m['hourly'][t]=bar(t,op='103',hi='104',lo='102',cl='103')
            m['fair'][t]=m['hourly'][t]
        r=simulate({'A':m},VARIANT,block,PROTOCOL,COSTS)
        self.assertGreater(r['summary']['positions'],0)
        self.assertEqual(D(100)+sum((t['net'] for t in r['trades']),D(0)),r['summary']['final'])
        self.assertTrue(all(a['exit_at']<=b['opened_at'] for a,b in zip(r['trades'],r['trades'][1:])))

    def test_momentum_uses_only_closed_days_and_known_volatility(self):
        m=market()
        m['hourly']={}
        for i in range(40*24):
            at=T-30*24*HOUR+i*HOUR
            price=D(100)+D(i)/1000
            m['hourly'][at]=Candle(at,HOUR,price,price+1,price-1,price,D(1000000))
        v=dict(kind='MOMENTUM',lookback_days=7,stop_atr=2,stop_cap='.05',
            trail_atr=2,max_hold_hours=168)
        all_events=events('A',m,v,T,T+24*HOUR)
        prefix=deepcopy(m)
        prefix['hourly']={t:b for t,b in m['hourly'].items() if b.end<=T}
        causal=events('A',prefix,v,T,T+24*HOUR)
        self.assertEqual(jsonable(all_events[0][T+HOUR]),jsonable(causal[0][T+HOUR]))
        event=all_events[0][T+HOUR][0]
        self.assertEqual(event['sign'],1)
        self.assertGreater(event['stop'],0)
        self.assertEqual(event['signal_at'],T)

    def test_momentum_stop_cap_is_applied_before_actual_entry_gate(self):
        m=market()
        m['hourly']={}
        for i in range(40*24):
            at=T-30*24*HOUR+i*HOUR;price=D(100)+D(i)/1000
            m['hourly'][at]=Candle(at,HOUR,price,price+10,price-10,price,D(1000000))
        v=dict(kind='MOMENTUM',lookback_days=7,stop_atr=2,stop_cap='.05',
            trail_atr=2,max_hold_hours=168)
        e,u=events('A',m,v,T,T+24*HOUR)
        event=e[T+HOUR][0];reference=u[T+HOUR]['close']
        self.assertLessEqual(reference-event['stop'],reference*D('.05')+m['contract'].tick)

    def test_market_gate_uses_known_week_and_day_without_future_prices(self):
        m=market();s=self.signal();at=s['signal_at']
        m['hourly'][at-HOUR]=bar(at-HOUR,op='110',hi='111',lo='109',cl='110')
        m['hourly'][at-7*24*HOUR-HOUR]=bar(at-7*24*HOUR-HOUR,cl='99')
        m['hourly'][at-24*HOUR-HOUR]=bar(at-24*HOUR-HOUR,op='111',hi='113',cl='112')
        markets={'BTC_USDT':m}
        self.assertTrue(market_gate_allows(markets,s,'BTC7_SIGN'))
        self.assertFalse(market_gate_allows(markets,s,'BTC7_AND_1_SIGN'))
        prefix=deepcopy(markets)
        prefix['BTC_USDT']['hourly']={t:b for t,b in m['hourly'].items() if b.end<=at}
        self.assertEqual(market_gate_allows(markets,s,'BTC7_SIGN'),market_gate_allows(prefix,s,'BTC7_SIGN'))
        self.assertEqual(market_gate_allows(markets,s,'BTC7_AND_1_SIGN'),market_gate_allows(prefix,s,'BTC7_AND_1_SIGN'))

    def test_flat_market_gates_both_directions(self):
        for side in (1,-1):
            s=self.signal();s['sign']=side
            self.assertFalse(market_gate_allows({'BTC_USDT':market()},s,'BTC7_SIGN'))

    def test_funding_credit_at_gap_exit_is_not_assumed(self):
        p=self.position();b=bar(T,op='95',hi='96',lo='94',cl='95')
        credit=dict(rate='-.001');debit=dict(rate='.001')
        self.assertEqual(settlement_amount(p,credit,b,b,False),D(0))
        self.assertEqual(settlement_amount(p,debit,b,b,False),D('.095'))
        normal=bar(T)
        self.assertEqual(settlement_amount(p,credit,normal,normal,False),D('-.1'))
