import unittest
from scripts.research_amplitude_horizons import split,predicted_net,inputs,CUT1,CUT2,FEATURES

class AmplitudeTests(unittest.TestCase):
    def test_longer_horizon_purge(self):
        self.assertEqual(split(CUT1-3660),"train")
        self.assertIsNone(split(CUT1-3659))
        self.assertIsNone(split(CUT2+3599))
        self.assertEqual(split(CUT2+3600),"test")
    def test_amplitude_cost(self):
        self.assertLess(predicted_net(.5,200,"SHORT")[1],predicted_net(.5,50,"SHORT")[1])
        self.assertLess(predicted_net(.5,50,"LONG")[1],predicted_net(.5,50,"SHORT")[1])
    def test_tp_cap(self):
        self.assertEqual(predicted_net(10,100,"LONG"),predicted_net(1.5,100,"LONG"))
    def test_causal_input(self):
        f={k:"1" for k in FEATURES}
        f["atr15"]="2"
        f["entry"]="10000"
        x,n=inputs(f,100)
        self.assertAlmostEqual(x[-1],.02)
        self.assertEqual(n,50)
