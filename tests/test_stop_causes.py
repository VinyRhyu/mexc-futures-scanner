import unittest
from dataclasses import replace
from types import SimpleNamespace
from mexc_scanner.models import D,Candle,Contract
from mexc_scanner.config import Config
from scripts.audit_stop_causes import net,level_for_profit,walk

class StopCauseTests(unittest.TestCase):
    def setUp(self):
        self.c=Contract('TEST_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
        self.cfg=Config()
    def bar(self,t,hi,lo,cl):
        return Candle(t,60,D(100),D(hi),D(lo),D(cl))
    def test_net_target_solver_both_directions_with_costs(self):
        for side in ('LONG','SHORT'):
            for wanted in (D(0),D(1),D('1.5')):
                price=level_for_profit(D(100),wanted,side,self.c,self.cfg)
                value=net(price,D(100),side,self.c,self.cfg)
                self.assertGreaterEqual(value,wanted)
                self.assertLess(value-wanted,D('.02'))
    def test_ambiguous_bar_remains_stop(self):
        v=SimpleNamespace(stop=D(99),target=D(103))
        r=walk([self.bar(0,104,98,100)],D(100),'LONG',v,self.c,self.cfg)
        self.assertEqual(r['outcome'],'STOP')
        self.assertTrue(r['ambiguous'])
    def test_protection_uses_close_not_wick_and_only_next_minute(self):
        v=SimpleNamespace(stop=D(99),target=D(104))
        r=walk([self.bar(0,103,'99.5',100),self.bar(60,101,98,100)],D(100),'LONG',v,self.c,self.cfg,True)
        self.assertEqual(r['outcome'],'STOP')
        r=walk([self.bar(0,103,'99.5',102),replace(self.bar(60,103,'99.5',100),open=D(102))],D(100),'LONG',v,self.c,self.cfg,True)
        self.assertEqual(r['outcome'],'PROTECAO')
        self.assertGreaterEqual(D(r['net_r']),0)
