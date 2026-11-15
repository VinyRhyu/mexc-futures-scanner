import unittest

from mexc_scanner.models import D
from scripts.audit_momentum_week10x import prepare_week
from tests.test_relative_momentum_daily import market,DAY,HOUR


class RiskLadderTests(unittest.TestCase):
    def test_stop_capping_protects_long_and_short_and_keeps_portfolio_risk(self):
        data={s:market(s) for s in ('LONG_USDT','SHORT_USDT')}
        signals=[dict(symbol=s,sign=sign,weight=D('.2'),return7=D('.1')*sign,atr14=D(20))
                 for s,sign in [('LONG_USDT',1),('SHORT_USDT',-1)]]
        for risk in (D('.02'),D('.05'),D('.10')):
            positions,_=prepare_week(signals,data,20*DAY+HOUR,D(100),D(10),risk,D('1.6'))
            self.assertEqual(len(positions),2)
            self.assertLessEqual(sum(p['planned_risk'] for p in positions),D(100)*risk)
            for p in positions:
                self.assertTrue(p['stop_adjusted'])
                self.assertTrue(p['has_1_5_liquidation_buffer'])
                self.assertTrue(p['stop_before_liquidation'])

    def test_already_close_stop_is_not_widened(self):
        data={'TEST_USDT':market()}
        signals=[dict(symbol='TEST_USDT',sign=1,weight=D('.1'),return7=D('.1'),atr14=D(1))]
        positions,_=prepare_week(signals,data,20*DAY+HOUR,D(100),D(10),D('.02'),D('1.6'))
        self.assertTrue(positions)
        self.assertEqual(positions[0]['stop'],positions[0]['original_stop'])
        self.assertFalse(positions[0]['stop_adjusted'])

    def test_increasing_risk_changes_quantity_not_signal_or_stop(self):
        data={'TEST_USDT':market()}
        signals=[dict(symbol='TEST_USDT',sign=1,weight=D('.2'),return7=D('.1'),atr14=D(20))]
        a,_=prepare_week(signals,data,20*DAY+HOUR,D(100),D(10),D('.02'),D('1.6'))
        b,_=prepare_week(signals,data,20*DAY+HOUR,D(100),D(10),D('.10'),D('1.6'))
        self.assertEqual(a[0]['stop'],b[0]['stop'])
        self.assertEqual(a[0]['entry_fill'],b[0]['entry_fill'])
        self.assertGreater(b[0]['quantity'],a[0]['quantity'])


if __name__=='__main__':unittest.main()
