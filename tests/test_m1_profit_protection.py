import unittest
from mexc_scanner.models import Candle,D
from scripts.audit_m1_profit_protection import unit_values,net_unit,cost_covering_stop,walk,walk_failed_break


class ProfitProtectionTests(unittest.TestCase):
    def fixture(self,side='LONG'):
        return dict(side=side,stop='99' if side=='LONG' else '101',target='102' if side=='LONG' else '98',
                    result=dict(entry_mid='100')),D('.001'),dict(taker_fee='.0006',slippage_rate='.0002')

    def test_cost_covering_price_includes_fees_slippage_and_tick_rounding(self):
        for side in ('LONG','SHORT'):
            row,tick,cfg=self.fixture(side);v=unit_values(row,tick,cfg);price=cost_covering_stop(v,tick)
            self.assertGreaterEqual(net_unit(price,v,tick),D(0))
            self.assertLess(net_unit(price-v[0]*tick,v,tick),D(0))

    def test_stop_in_activation_candle_cannot_be_reclassified_as_protected(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('101.5'),D('98.5'),D(101))]
        r=walk(row,bars,tick,cfg,True)
        self.assertEqual(r['outcome'],'STOP');self.assertIsNone(r['armed_at'])
        self.assertEqual(r['net_r'],D(-1))

    def test_protection_only_begins_next_minute_and_stop_wins_target_ambiguity(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('101.2'),D(100),D(101)),
              Candle(60,60,D(101),D(103),D(100),D('101.5'))]
        r=walk(row,bars,tick,cfg,True)
        self.assertEqual(r['armed_at'],60);self.assertEqual(r['closed_at'],120)
        self.assertEqual(r['outcome'],'PROTEGIDA');self.assertTrue(r['ambiguity'])
        self.assertGreaterEqual(r['net_r'],D(0))

    def test_adverse_gap_can_lose_money_even_after_protection(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('101.2'),D(100),D(101)),
              Candle(60,60,D('98.5'),D(99),D(98),D('98.5'))]
        r=walk(row,bars,tick,cfg,True)
        self.assertEqual(r['outcome'],'PROTEGIDA');self.assertTrue(r['gap'])
        self.assertLess(r['net_r'],D(0))

    def test_failed_break_exits_at_next_open_without_using_its_later_high(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('100.5'),D('99.8'),D(100)),
              Candle(60,60,D('100.05'),D(103),D('99.8'),D(102))]
        r=walk_failed_break(row,bars,D('100.1'),tick,cfg)
        self.assertEqual(r['outcome'],'FALHA_ROMPIMENTO')
        self.assertEqual(r['closed_at'],60);self.assertEqual(r['exit_mid'],D('100.05'))

    def test_original_stop_wins_before_failed_break_can_schedule_exit(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('100.5'),D(98),D('99.5'))]
        self.assertEqual(walk_failed_break(row,bars,D('100.1'),tick,cfg)['outcome'],'STOP')

    def test_failed_break_exit_still_honors_adverse_gap_through_original_stop(self):
        row,tick,cfg=self.fixture()
        bars=[Candle(0,60,D(100),D('100.5'),D('99.8'),D(100)),
              Candle(60,60,D('98.5'),D('98.8'),D(98),D('98.5'))]
        r=walk_failed_break(row,bars,D('100.1'),tick,cfg)
        self.assertEqual(r['outcome'],'STOP');self.assertTrue(r['gap'])
        self.assertLess(r['net_r'],D(-1))


if __name__=='__main__':unittest.main()
