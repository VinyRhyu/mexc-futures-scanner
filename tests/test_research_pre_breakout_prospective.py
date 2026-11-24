import unittest
from scripts.research_pre_breakout_prospective import load_model,probability,require_closed,END,trades,financial,START

class ProspectiveTests(unittest.TestCase):
    def test_frozen_hash_and_logistic(self):
        m=load_model()
        f=dict(zip(m["feature_order"],m["mean"]))
        self.assertAlmostEqual(probability(f,m),0.10061459102051769,places=5)
    def test_future_guard(self):
        with self.assertRaises(ValueError):
            require_closed(END)
        require_closed(END+31*60+10)
    def test_no_overlap(self):
        m=load_model()
        sample=[{"t":START+i,"symbol":"BTC_USDT","score":.6,"atr":2,
                 "label":{"entry":"100","exit":"97","gross_r":"1.5","exit_ts":START+300}} for i in (0,60)]
        selected=trades(sample,m)
        self.assertEqual(len(selected),1)
        self.assertEqual(financial(selected,.0016)["active_days"],1)
    def test_no_trades_inconclusive(self):
        self.assertIsNone(financial([],.0016)["mean_r_day_bootstrap_95"])
