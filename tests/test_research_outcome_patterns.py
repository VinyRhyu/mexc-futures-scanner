import unittest
from scripts.research_outcome_patterns import pattern_features,train_phase,qualifies,MAX_LABEL,EMBARGO
from mexc_scanner.models import Candle,D

class PatternTests(unittest.TestCase):
    def test_causal_features(self):
        t=7200
        bars={u:Candle(u,60,D(100),D(102),D(99),D(101),D(2)) for u in range(0,t,60)}
        x=pattern_features(bars,t,D(1))
        self.assertEqual(len(x),20)
        self.assertAlmostEqual(x[0],1)
        self.assertAlmostEqual(x[3],1)
        bars[t]=Candle(t,60,D(101),D(500),D(1),D(200),D(900))
        self.assertEqual(x,pattern_features(bars,t,D(1)))
    def test_purge(self):
        b=100000
        self.assertEqual(train_phase(b-MAX_LABEL,b),"discovery")
        self.assertIsNone(train_phase(b,b))
        self.assertEqual(train_phase(b+EMBARGO,b),"calibration")
    def test_gate(self):
        fit={"n":500,"mean_stress_r":.1}
        cal={"n":100,"days":3,"mean_stress_r":.01}
        self.assertTrue(qualifies(fit,cal))
        self.assertFalse(qualifies(fit,{**cal,"mean_stress_r":0}))
        self.assertFalse(qualifies(fit,{**cal,"days":2}))
