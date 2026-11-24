import unittest
from scripts.research_delayed_confirmation import confirmation,remaining,stats
from mexc_scanner.models import Candle,D

def c(t,op=100,hi=100.2,lo=99.8,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(1))

class ConfirmationTests(unittest.TestCase):
    def test_no_future_in_confirmation(self):
        b={t:c(t) for t in range(0,900,60)}
        b[840]=c(840,100,101,99.8,100.6)
        q=confirmation(b,0,D(1),D(100))
        self.assertEqual(q["side"],"UP")
        b[900]=c(900,100,104,99,104)
        self.assertEqual(confirmation(b,0,D(1),D(100)),q)
    def test_early_expansion(self):
        b={t:c(t) for t in range(0,900,60)}
        b[60]=c(60,100,104,99,100)
        self.assertEqual(confirmation(b,0,D(1),D(100))["status"],"already_expanded")
    def test_remaining_latency(self):
        b={t:c(t) for t in range(0,14400,60)}
        b[840]=c(840,100,101,99.8,100.6)
        b[900]=c(900,100.6,104,100,102)
        q=remaining(b,0,D(1),D(100),confirmation(b,0,D(1),D(100)))
        self.assertEqual(q["entry_ts"],960)
        self.assertTrue(q["latency_crossing"])
        self.assertLess(q["mfe"],1)
    def test_empty(self):
        self.assertIsNone(stats([])["event_rate"])
