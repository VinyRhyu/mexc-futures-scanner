from copy import deepcopy
import unittest
from unittest.mock import patch

from mexc_scanner.demo import DemoClient
from mexc_scanner.models import Candle, Contract, D
from scripts.audit_multihour import HOUR, iso, simulate
from scripts.audit_momentum_conditional_exit import WeakExit

T=1790812800
COSTS=dict(fee='.0006',spread='.0002',slippage='.0002')


def bar(t,price):
    p=D(price)
    return Candle(t,HOUR,p,p,p,p,D(1000000))


def market(sign=1):
    bars={t:bar(t,'100') for t in range(T-40*HOUR,T+30*HOUR,HOUR)}
    for t in range(T+4*HOUR,T+30*HOUR,HOUR):
        bars[t]=bar(t,'99' if sign==1 else '101')
    return dict(hourly=bars,fair=deepcopy(bars),
        contract=Contract.from_api(DemoClient(T).contracts()[0]),
        funding=[dict(ts=T-HOUR,rate=D(0),cycle=8)],funding_by_time={})


def position(sign=1):
    return dict(symbol='A',sign=sign,quantity=D(1),entry=D(100),margin=D(10),
        mmr=D('.005'),liquidation_fee=D('.0006'),funding_paid=D(0),
        stop=D(96 if sign==1 else 104),entry_fee=D('.06'),tick=D('.01'),opened_at=T)


class ConditionalExitTests(unittest.TestCase):
    def test_six_hours_at_signal_means_seven_at_execution(self):
        m=market(); policy=WeakExit({'A':m})
        self.assertIsNone(policy(position(),m,T+6*HOUR,COSTS))
        s=policy(position(),m,T+7*HOUR,COSTS)
        self.assertEqual(s['signal_at'],T+6*HOUR)
        self.assertEqual(s['bar_ends'],[T+5*HOUR,T+6*HOUR])

    def test_full_and_prefix_inputs_produce_identical_signal(self):
        m=market(); at=T+7*HOUR
        prefix=deepcopy(m);prefix['hourly']={t:b for t,b in m['hourly'].items() if b.end<=at-HOUR}
        self.assertEqual(WeakExit({'A':m})(position(),m,at,COSTS),
            WeakExit({'A':prefix})(position(),prefix,at,COSTS))
        # Both the delay hour and execution hour are unknown to the trigger.
        m['hourly'][at-HOUR]=bar(at-HOUR,'1000000')
        m['hourly'][at]=bar(at,'0.001')
        self.assertEqual(WeakExit({'A':m})(position(),m,at,COSTS),
            WeakExit({'A':prefix})(position(),prefix,at,COSTS))

    def test_one_against_ema_close_does_not_trigger(self):
        m=market();m['hourly'][T+4*HOUR]=bar(T+4*HOUR,'101')
        self.assertIsNone(WeakExit({'A':m})(position(),m,T+7*HOUR,COSTS))

    def test_equality_to_ema_does_not_trigger(self):
        m=market()
        m['hourly']={t:bar(t,'100') for t in m['hourly']}
        self.assertIsNone(WeakExit({'A':m})(position(),m,T+7*HOUR,COSTS))

    def test_short_is_mirrored(self):
        m=market(-1)
        self.assertIsNotNone(WeakExit({'A':m})(position(-1),m,T+7*HOUR,COSTS))

    def test_positive_net_does_not_exit_even_with_weakness(self):
        m=market();p=position();p['entry']=D(98)
        self.assertIsNone(WeakExit({'A':m})(p,m,T+7*HOUR,COSTS))

    def test_costs_and_settled_funding_are_included(self):
        m=market();p=position();p['entry']=D('98.99')
        self.assertIsNotNone(WeakExit({'A':m})(p,m,T+7*HOUR,COSTS))
        p['entry']=D(98);p['funding_paid']=D(2)
        self.assertIsNotNone(WeakExit({'A':m})(p,m,T+7*HOUR,COSTS))

    def test_missing_bar_is_not_silently_bridged(self):
        m=market();del m['hourly'][T]
        with self.assertRaises(ValueError):WeakExit({'A':m})

    def simulate(self,gap=None,stop_during_delay=False):
        m=market();at=T+7*HOUR
        if gap:
            m['hourly'][at]=bar(at,gap);m['fair'][at]=m['hourly'][at]
        if stop_during_delay:
            m['hourly'][at-HOUR]=bar(at-HOUR,'95');m['fair'][at-HOUR]=m['hourly'][at-HOUR]
        p=dict(initial_equity='100',leverage=10,risk_fraction='.01',
            minimum_turnover='0',min_liquidation_buffer='1.5',signal_delay_seconds=HOUR)
        v=dict(kind='MOMENTUM',name='T',max_hold_hours=24,trail_atr=2)
        b=dict(start=iso(T),end=iso(T+12*HOUR),validation_start=iso(T+6*HOUR))
        signal=dict(symbol='A',sign=1,signal_at=T-HOUR,stop=D(96),turnover=D(10000000),score=D(1))
        with patch('scripts.audit_multihour.events',return_value=({T:[signal]},{})):
            return simulate({'A':m},v,b,p,COSTS,exit_policy=WeakExit({'A':m}))

    def test_exit_executes_at_delayed_open_and_reconciles(self):
        r=self.simulate();t=r['trades'][0]
        self.assertEqual(t['outcome'],'FRAQUEZA_H1')
        self.assertEqual(t['exit_at'],T+7*HOUR)
        self.assertLess(t['exit'],D(99))
        self.assertEqual(D(100)+t['net'],r['summary']['final'])

    def test_stop_remains_active_during_delay(self):
        t=self.simulate(stop_during_delay=True)['trades'][0]
        self.assertEqual(t['outcome'],'STOP')
        self.assertNotIn('conditional_exit_signal',t)

    def test_opening_gap_stop_precedes_conditional_exit(self):
        t=self.simulate(gap='95')['trades'][0]
        self.assertEqual(t['outcome'],'STOP');self.assertLess(t['exit'],D(95))
        self.assertEqual(t['exit_at'],T+7*HOUR)

    def test_opening_gap_liquidation_cannot_be_escaped(self):
        t=self.simulate(gap='80')['trades'][0]
        self.assertEqual(t['outcome'],'LIQUIDACAO')

    def test_favorable_execution_gap_does_not_cancel_known_signal(self):
        t=self.simulate(gap='105')['trades'][0]
        self.assertEqual(t['outcome'],'FRAQUEZA_H1')
        self.assertGreater(t['net'],0)
