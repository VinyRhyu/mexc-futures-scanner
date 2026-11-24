import unittest
from scripts.research_expected_net_return import target, selected, passes_gate, vector, portfolio_stats, FEATURES

class ExpectedReturnTests(unittest.TestCase):
    def test_cost_and_timeout(self):
        l={"gross_r":".25","entry":"100","exit":"99.5","outcome":"TIMEOUT"}
        a,b=target(l,2)
        self.assertAlmostEqual(a,.1702)
        self.assertLess(b,a)
    def test_no_future_features(self):
        f={k:"1" for k in FEATURES}
        f.update(entry="999",outcome="TP",gross_r="100")
        self.assertEqual(vector(f),[1.]*len(FEATURES))
    def test_gate_requires_both_positive(self):
        self.assertTrue(passes_gate([.3,.1]))
        self.assertFalse(passes_gate([.3,-.01]))
        self.assertFalse(passes_gate([0,0]))
    def test_rank_and_no_overlap(self):
        a={"t":0,"symbol":"BTC","side":"LONG","rank":.1,"label":{"exit_ts":300},"y":[1.,.8]}
        b={**a,"symbol":"ETH","rank":.2}
        c={**a,"t":300,"rank":.9}
        self.assertEqual(selected([a,b,c]),[b])
        result,_=portfolio_stats([a,b,c],["1970-01-01"])
        self.assertEqual(result["trades"],1)
        self.assertAlmostEqual(result["0.0016"]["total_net_r"],1.)
    def test_empty_portfolio(self):
        stats,_=portfolio_stats([],["1970-01-01"])
        self.assertEqual(stats["trades"],0)
        self.assertIsNone(stats["0.0024"]["mean_r_day_bootstrap_95"])
