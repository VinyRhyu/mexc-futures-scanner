import unittest
from scripts.research_gate_patterns import gate_features,REQUIRED

class GatePatternsTests(unittest.TestCase):
    def test_lag_and_units(self):
        t=9000;k=t-900
        r=dict.fromkeys(REQUIRED,"1")
        r.update(open_interest="100",long_taker_size="3",short_taker_size="1",long_liq_size="2")
        rows={k:r,k-900:{"open_interest":"50"},k-3600:{"open_interest":"25"}}
        x=gate_features(rows,t,900)
        self.assertEqual(len(x),9)
        self.assertAlmostEqual(x[6],.5)
        self.assertAlmostEqual(x[7],.02)
        rows[t]={**r,"open_interest":"999999"}
        self.assertEqual(x,gate_features(rows,t,900))
        self.assertIsNone(gate_features(rows,t,1800))
    def test_missing_and_zero(self):
        t=9000;k=t-900
        r=dict.fromkeys(REQUIRED,"1")
        rows={k:r,k-900:{"open_interest":"0"},k-3600:{"open_interest":"1"}}
        self.assertIsNone(gate_features(rows,t,900))
        with self.assertRaises(ValueError):
            gate_features(rows,t,0)
