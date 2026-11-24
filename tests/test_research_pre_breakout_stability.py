import unittest
from scripts.research_pre_breakout_stability import metrics,bootstrap,calibration
class StabilityTests(unittest.TestCase):
    def test_perfect_ranking(self):
        r=[{"y":0,"p":.1,"base":.5},{"y":1,"p":.9,"base":.5}]
        self.assertEqual(metrics(r)["auc"],1)
        self.assertGreater(metrics(r)["brier_gain"],0)
    def test_single_class_auc(self):
        self.assertIsNone(metrics([{"y":0,"p":.1,"base":.5}])["auc"])
    def test_blocks_and_reproducibility(self):
        r=[{"t":t,"y":y,"p":.1 if y==0 else .9,"base":.5}
           for t in (0,86400,172800) for y in (0,1)]
        a=bootstrap(r,86400,20)
        self.assertEqual(a["blocks"],3)
        self.assertEqual(a,bootstrap(r,86400,20))
        self.assertEqual(a["auc_percentile_95"],[1,1])
    def test_calibration_conserves_rows(self):
        r=[{"y":0,"p":p} for p in (0,.05,.1,.15,.2,.3,.5,1)]
        self.assertEqual(sum(x["n"] for x in calibration(r)),len(r))
