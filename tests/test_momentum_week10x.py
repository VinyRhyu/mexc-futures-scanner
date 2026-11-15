import unittest

from mexc_scanner.models import Candle,D
from scripts.audit_momentum_week10x import liquidation_level,prepare_week,exit_flags,liquidate
from tests.test_relative_momentum_daily import market


class LeveragedMomentumTests(unittest.TestCase):
    def test_isolated_liquidation_thresholds_follow_initial_margin(self):
        self.assertEqual(liquidation_level(D(100),1,D(10),D('.005'),D('.0004')),D('90.54'))
        self.assertEqual(liquidation_level(D(100),-1,D(10),D('.005'),D('.0004')),D('109.46'))

    def test_liquidation_uses_fair_price_and_does_not_assume_stop_wins(self):
        p=dict(sign=1,stop=D(95),liquidation_price=D('90.54'))
        last=Candle(0,3600,D(100),D(101),D(94),D(98))
        fair=Candle(0,3600,D(100),D(101),D(90),D(98))
        self.assertEqual(exit_flags(p,last,fair),(True,True))
        self.assertEqual(exit_flags(p,last,Candle(0,3600,D(100),D(101),D(96),D(98))),(True,False))

    def test_same_risk_does_not_multiply_notional_by_ten(self):
        data={'TEST_USDT':market()};at=20*86400+3600
        signals=[dict(symbol='TEST_USDT',sign=1,weight=D('.1'),return7=D('.1'),atr14=D(10))]
        a,_=prepare_week(signals,data,at,D(100),D(1),D('.02'))
        b,_=prepare_week(signals,data,at,D(100),D(10),D('.02'))
        self.assertTrue(a and b)
        self.assertEqual(a[0]['quantity'],b[0]['quantity'])
        self.assertEqual(a[0]['isolated_margin']/10,b[0]['isolated_margin'])
        self.assertLessEqual(b[0]['planned_risk'],D(2))
        self.assertFalse(b[0]['stop_before_liquidation'])

    def test_liquidation_charge_does_not_double_charge_exit_fees(self):
        p=dict(isolated_margin=D(10),entry_fee=D('.06'),funding_cash=-D('.01'))
        trade,change=liquidate(p,3600,True)
        self.assertEqual(change,-D(10));self.assertEqual(trade['exit_fee'],D(0))
        self.assertEqual(trade['net_pnl'],-D('10.07'))
        self.assertEqual(trade['reason'],'LIQUIDATION_AMBIGUOUS')


if __name__=='__main__':unittest.main()
