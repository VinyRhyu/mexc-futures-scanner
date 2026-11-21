"""Forensic features must be observable at trigger close or next-bar entry open."""
import copy
import unittest
from scripts.audit_confluence_v3 import candidate_f, execute
from scripts.audit_f_forensic import compute_features, auc_tp_vs_sl, outcome_summary, FEATURES


class ForensicTests(unittest.TestCase):
    def setUp(self):
        self.hours=[
            [(i-160)*3_600_000,240-.5*i,241-.5*i,239-.5*i,240-.5*i,
             1000,100000] for i in range(160)
        ]
        self.five=[[i*300_000,100.0,100.3,99.7,100.0,10,100] for i in range(72)]
        self.i=35
        self.five[self.i]=[self.i*300_000,100.4,101.0,99.95,100.0,20,300]
        self.setup=candidate_f(self.five,self.hours,self.i)
        self.trade=execute(self.five,self.setup)

    def test_causal_feature_extraction(self):
        self.assertIsNotNone(self.trade)
        feats=compute_features(self.five,self.hours,self.trade,index=self.i)
        self.assertEqual(set(feats),set(FEATURES))
        self.assertAlmostEqual(feats["vol_ratio"],3.0)
        self.assertGreater(feats["stop_pct"],0)
        self.assertGreater(feats["wick_frac"],0.4)
        self.assertGreater(feats["h1_below_ema20_pct"],0)

    def test_cannot_leak_future_after_next_open(self):
        a=compute_features(self.five,self.hours,self.trade,index=self.i)
        later=copy.deepcopy(self.five)
        for b in later[self.i+2:]:
            b[1],b[2],b[3],b[4],b[6]=200,250,150,220,99999
        self.assertEqual(a,compute_features(later,self.hours,self.trade,index=self.i))

    def test_no_open_hourly_used(self):
        a=compute_features(self.five,self.hours,self.trade,index=self.i)
        changed=copy.deepcopy(self.hours)
        changed.append([4*3_600_000,1,1,1,1,100,10000])
        self.assertEqual(a,compute_features(self.five,changed,self.trade,index=self.i))

    def test_entry_open_does_change_stop_distance_but_not_volume(self):
        a=compute_features(self.five,self.hours,self.trade,index=self.i)
        changed=copy.deepcopy(self.five)
        changed[self.i+1][1]+=0.2
        b=compute_features(changed,self.hours,self.trade,index=self.i)
        self.assertNotEqual(a["stop_pct"],b["stop_pct"])
        self.assertEqual(a["vol_ratio"],b["vol_ratio"])

    def test_auc_has_no_profit_claim(self):
        rows=[
            {"result":"TP","features":{"atr_pct":3.}},
            {"result":"TP","features":{"atr_pct":4.}},
            {"result":"SL","features":{"atr_pct":2.}},
            {"result":"SL","features":{"atr_pct":1.}},
            {"result":"TIME","features":{"atr_pct":99.}},
        ]
        self.assertEqual(auc_tp_vs_sl(rows,"atr_pct"),1.0)
        self.assertEqual(outcome_summary([{"result":"TP","net_r":1.6},
                                          {"result":"SL","net_r":-1.}])["n"],2)


if __name__=="__main__":
    unittest.main()
