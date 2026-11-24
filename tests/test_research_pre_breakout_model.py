import unittest
from scripts.research_pre_breakout_model import partition,net_r,portfolio

class ModelTests(unittest.TestCase):
    def test_purge_and_embargo(self):
        self.assertEqual(partition(100,10000,20000),"train")
        self.assertIsNone(partition(9000,10000,20000))
        self.assertIsNone(partition(13000,10000,20000))
        self.assertEqual(partition(13600,10000,20000),"validation")
        self.assertIsNone(partition(20000,10000,20000))
        self.assertEqual(partition(23600,10000,20000),"test")

    def test_cost(self):
        label={"gross_r":"1.5","entry":"100","exit":"103"}
        self.assertAlmostEqual(net_r(label,2,.0016),1.4188)

    def test_portfolio_no_overlap(self):
        label={"gross_r":"1.5","entry":"100","exit":"103","exit_ts":"500"}
        sample=[{"t":t,"score":.6,"symbol":"X","side":"LONG","atr":2,"label":label}
                for t in [0,300]]
        self.assertEqual(portfolio(sample,.0016)["trades"],1)

if __name__=="__main__":
    unittest.main()
