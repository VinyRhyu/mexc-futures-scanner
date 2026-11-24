import unittest
from scripts.research_amplitude_240 import split,CUT1,CUT2,MAX_LABEL,EMBARGO
from scripts.research_pre_breakout_dataset import label
from mexc_scanner.models import Candle,D

def bar(t,op=100,hi=101,lo=99,cl=100):
    return Candle(t,60,D(op),D(hi),D(lo),D(cl),D(5))

class Horizon240Tests(unittest.TestCase):
    def test_purge_and_embargo(self):
        self.assertEqual(MAX_LABEL,14460)
        self.assertEqual(split(CUT1-MAX_LABEL),"train")
        self.assertIsNone(split(CUT1-MAX_LABEL+1))
        self.assertIsNone(split(CUT2+EMBARGO-1))
        self.assertEqual(split(CUT2+EMBARGO),"test")
    def test_timeout_becomes_tp(self):
        bars={t:bar(t) for t in range(60,14460,60)}
        bars[7200]=bar(7200,100,104,99,103)
        self.assertEqual(label(bars,0,D(2),"LONG",30,14460)["outcome"],"TIMEOUT")
        self.assertEqual(label(bars,0,D(2),"LONG",240,14460)["outcome"],"TP")
    def test_stop_unchanged(self):
        bars={t:bar(t) for t in range(60,14460,60)}
        bars[60]=bar(60,100,104,97,100)
        self.assertEqual(label(bars,0,D(2),"LONG",30,14460),label(bars,0,D(2),"LONG",240,14460))
    def test_tail_censor(self):
        bars={t:bar(t) for t in range(60,14400,60)}
        self.assertEqual(label(bars,0,D(2),"LONG",240,14400)["outcome"],"CENSORED")
