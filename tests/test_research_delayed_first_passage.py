import unittest
from scripts.research_delayed_first_passage import bounded_barrier,DELAY,HORIZON
from mexc_scanner.models import Candle,D

def bar(t,op=100,hi=100,lo=100,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(1))

class FirstPassageTests(unittest.TestCase):
    def test_expiry_and_latency(self):
        t=DELAY
        b={u:bar(u) for u in range(t+60,HORIZON,60)}
        q=bounded_barrier(b,t,D(1),"LONG",HORIZON)
        self.assertEqual((q["entry_ts"],q["exit_ts"],q["outcome"]),(t+60,HORIZON,"TIMEOUT"))
    def test_sl_first_same_minute(self):
        t=DELAY
        b={u:bar(u) for u in range(t+60,HORIZON,60)}
        b[t+60]=bar(t+60,100,104,98,100)
        self.assertEqual(bounded_barrier(b,t,D(1),"LONG",HORIZON)["outcome"],"SL")
    def test_short_target(self):
        t=DELAY
        b={u:bar(u) for u in range(t+60,HORIZON,60)}
        b[t+60]=bar(t+60,100,100,96,97)
        self.assertEqual(bounded_barrier(b,t,D(1),"SHORT",HORIZON)["outcome"],"TP")
