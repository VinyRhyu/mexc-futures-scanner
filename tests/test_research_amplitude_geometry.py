import unittest
from mexc_scanner.models import Candle,D
from scripts.research_amplitude_geometry import barrier,funding_charge
from scripts.research_pre_breakout_dataset import label

def bar(t,op=100,hi=101,lo=99,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(5))

class GeometryTests(unittest.TestCase):
    def test_original_and_wider_target(self):
        b={t:bar(t) for t in range(60,14460,60)}
        b[120]=bar(120,100,103,99,102)
        b[180]=bar(180,102,105,101,104)
        a=barrier(b,0,D(2),"LONG","1.5",14460)
        original=label(b,0,D(2),"LONG",240,14460)
        for k in a:
            self.assertEqual(a[k],original[k])
        self.assertEqual(barrier(b,0,D(2),"LONG","2",14460)["exit_ts"],240)
        self.assertEqual(barrier(b,0,D(2),"LONG","3",14460)["outcome"],"TIMEOUT")
    def test_stop_first(self):
        b={t:bar(t) for t in range(60,14460,60)}
        b[60]=bar(60,100,107,97,100)
        self.assertEqual(barrier(b,0,D(2),"LONG","3",14460)["outcome"],"SL")
    def test_funding_boundary(self):
        l={"entry_ts":14340,"exit_ts":14400,"entry":"100"}
        self.assertAlmostEqual(funding_charge(l,2,.0005),.025)
        l["entry_ts"]=14400
        self.assertEqual(funding_charge(l,2,.0005),0)
