import unittest
from scripts.research_path_failure_attribution import path_trace,describe,atr_band
from scripts.research_delayed_first_passage import bounded_barrier,DELAY,HORIZON
from mexc_scanner.models import Candle,D

def bar(t,op=100,hi=100,lo=100,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(1))

def make(b,side="LONG"):
    l=bounded_barrier(b,DELAY,D(1),side,HORIZON)
    return path_trace(b,{"label":l,"side":side},D(1),HORIZON)

class PathTests(unittest.TestCase):
    def setUp(self):
        self.t=DELAY+60
        self.b={u:bar(u) for u in range(self.t,HORIZON,60)}
    def test_stop_then_target(self):
        self.b[self.t]=bar(self.t,100,100,98,99)
        self.b[self.t+60]=bar(self.t+60,99,103,99,103)
        q=make(self.b)
        self.assertEqual(q["outcome"],"SL")
        self.assertTrue(q["later_target_after_stop"])
        self.assertEqual(q["pre_target_adverse_lower"],2.)
    def test_same_bar_not_recovery(self):
        self.b[self.t]=bar(self.t,100,104,98,100)
        q=make(self.b)
        self.assertEqual(q["outcome"],"SL")
        self.assertTrue(q["stop_bar_also_target"])
        self.assertFalse(q["later_target_after_stop"])
        self.assertEqual(q["pre_target_adverse_lower"],0.)
        self.assertEqual(q["pre_target_adverse_upper"],2.)
    def test_gap_target_before_stop(self):
        self.b[self.t+60]=bar(self.t+60,104,105,98,100)
        q=make(self.b)
        self.assertEqual(q["outcome"],"TP")
        self.assertEqual(q["pre_target_adverse_upper"],0.)
    def test_short_recovery(self):
        self.b[self.t]=bar(self.t,100,102,100,101)
        self.b[self.t+60]=bar(self.t+60,101,101,96,97)
        self.assertTrue(make(self.b,"SHORT")["later_target_after_stop"])
    def test_bins(self):
        self.assertEqual(atr_band(.005),"0.5_to_1pct")
        self.assertEqual(describe([]),{"n":0})
