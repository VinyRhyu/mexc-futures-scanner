import unittest
from scripts.research_pullback_confirmation import pullback_decision,pullback_barrier,dedupe,WAIT,DELAY,HORIZON
from mexc_scanner.models import Candle,D

def bar(t,op,hi,lo,cl):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(1))

class PullbackTests(unittest.TestCase):
    def setUp(self):
        self.t=DELAY
        self.b={u:bar(u,101,101,101,101) for u in range(self.t-60,self.t+WAIT,60)}
    def test_long_pullback_resume(self):
        t=self.t
        self.b[t]=bar(t,101,101,"100.4","100.4")
        self.b[t+60]=bar(t+60,"100.4","100.7","100.4","100.7")
        q=pullback_decision(self.b,t,D(100),D(1),"LONG")
        self.assertEqual((q["status"],q["decision_t"]),("triggered",t+120))
    def test_short_pullback_resume(self):
        t=self.t
        self.b[t-60]=bar(t-60,99,99,99,99)
        self.b[t]=bar(t,99,"99.6",99,"99.6")
        self.b[t+60]=bar(t+60,"99.6","99.6","99.3","99.3")
        self.assertEqual(pullback_decision(self.b,t,D(100),D(1),"SHORT")["decision_t"],t+120)
    def test_no_pullback(self):
        self.assertEqual(pullback_decision(self.b,self.t,D(100),D(1),"LONG")["status"],"no_pullback")
    def test_cancel_known_excursion(self):
        self.b[self.t]=bar(self.t,101,103,100,100)
        self.assertEqual(pullback_decision(self.b,self.t,D(100),D(1),"LONG")["status"],"original_excursion_before_trigger")
    def test_expiry_not_extended(self):
        t=self.t+120
        b={u:bar(u,100,100,100,100) for u in range(t+60,HORIZON,60)}
        q=pullback_barrier(b,t,D(1),"LONG",HORIZON,HORIZON)
        self.assertEqual((q["entry_ts"],q["exit_ts"]),(t+60,HORIZON))
    def test_dedupe(self):
        r={"t":100,"symbol":"X","side":"LONG","rank":.7,"forecast_t":0}
        self.assertEqual(dedupe([r,{**r,"rank":.6}]),[r])
