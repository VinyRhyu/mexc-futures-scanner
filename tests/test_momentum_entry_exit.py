import unittest

from mexc_scanner.models import Candle,D
from scripts.audit_momentum_entry_exit import inspect_trade
from scripts.audit_momentum_week10x import simulate_week
from tests.test_relative_momentum_daily import market,DAY,HOUR


class EntryExitTests(unittest.TestCase):
    def fixture(self):
        m=market();at=20*DAY+HOUR
        m['hourly'][at]=Candle(at,HOUR,D(100),D(106),D(99),D(102))
        m['hourly'][at+HOUR]=Candle(at+HOUR,HOUR,D(102),D(150),D(90),D(140))
        m['fair']=dict(m['hourly'])
        t=dict(symbol='TEST_USDT',sign=1,opened_at=at,closed_at=at+2*HOUR,
               entry_mid=D(100),entry_fill=D('100.03'),quantity=D(1),contracts=D(100),
               entry_fee=D('.060018'),funding_cash=D(0),stop=D(95),planned_risk=D(5),
               initial_notional=D('100.03'),isolated_margin=D('10.003'),
               liquidation_price=D(90),net_pnl=D('-5.2'),exit_mid=D(95),reason='STOP')
        return t,m

    def test_stop_hour_does_not_create_a_false_observed_profit(self):
        t,m=self.fixture();row=inspect_trade(t,m)
        self.assertEqual(row['safe_completed_h1_count'],1)
        self.assertLess(row['best_completed_h1_net'],D(2))
        self.assertLess(row['mfe_safe_price_pct'],D(6))
        self.assertGreater(row['mfe_exit_hour_upper_price_pct'],D(49))

    def test_future_funding_cannot_affect_earlier_h1_profit(self):
        t,m=self.fixture();a=inspect_trade(t,m)
        m['funding']={t['closed_at']:D('-1')}
        b=inspect_trade(t,m)
        self.assertEqual(a['best_completed_h1_net'],b['best_completed_h1_net'])

    def test_stop_gap_keeps_the_full_hour_before_the_gap(self):
        t,m=self.fixture();t.update(reason='STOP_GAP',closed_at=t['opened_at']+HOUR)
        row=inspect_trade(t,m)
        self.assertEqual(row['safe_completed_h1_count'],1)
        self.assertGreater(row['best_completed_h1_net'],D(1))

    def test_short_extremes_use_low_for_favorable_and_high_for_adverse(self):
        t,m=self.fixture();t.update(sign=-1,reason='TIME',net_pnl=D(-40),exit_mid=D(140))
        row=inspect_trade(t,m)
        self.assertGreater(row['mfe_safe_price_pct'],D(10))
        self.assertLess(row['mae_price_pct'],D(-49))

    def test_six_hour_exit_keeps_daily_schedule_and_initial_sizing(self):
        data={'A_USDT':market('A_USDT'),'B_USDT':market('B_USDT',False)}
        for m in data.values():m['fair']=dict(m['hourly'])
        p=dict(reference_equity_usdt=100,evaluation_start_utc=20*DAY,
               evaluation_end_utc=21*DAY,portfolio_risk_fraction='.02',liquidation_stop_buffer='1.6')
        a=simulate_week(data,p,10);b=simulate_week(data,dict(p,holding_hours=6),10)
        aa=sorted(a['trades'],key=lambda t:t['symbol']);bb=sorted(b['trades'],key=lambda t:t['symbol'])
        self.assertEqual(len(aa),len(bb));self.assertTrue(aa)
        for x,y in zip(aa,bb):
            self.assertEqual(x['quantity'],y['quantity'])
            self.assertEqual(x['stop'],y['stop'])
            self.assertEqual(y['closed_at']-y['opened_at'],6*HOUR)
            self.assertEqual(x['closed_at']-x['opened_at'],24*HOUR)


if __name__=='__main__':unittest.main()
