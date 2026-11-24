import unittest
import numpy as np
from scripts.research_basis_direction import matrices
from scripts.research_pre_breakout_model import FEATURES
from scripts.research_bitget_oi import parse,coverage

class NewSourceTests(unittest.TestCase):
    def test_groups(self):
        x=np.zeros((3,len(FEATURES)+1));z=np.ones((3,12))
        a=matrices(x,z)
        self.assertEqual(a["volatility"].shape,(3,5))
        self.assertEqual(a["basis"].shape,(3,9))
        self.assertEqual(a["funding"].shape,(3,3))
        self.assertEqual(a["price_all"].shape,(3,len(FEATURES)+13))
    def test_bitget_end_timestamp(self):
        p={"data":{"list":[{"symbol":"BTCUSDT","timestamp":"1792865100000","openInterest":"42"}]}}
        r=parse(p,"BTCUSDT","5m")
        self.assertEqual(r[1792865100]["open_interest_base"],"42")
        self.assertEqual(coverage(r,300,1792865100,1792865700)["matched"],1)
    def test_bad_symbol(self):
        p={"data":{"list":[{"symbol":"BTCUSDT","timestamp":"1792865100000","openInterest":"42"}]}}
        with self.assertRaises(ValueError):
            parse(p,"ETHUSDT","5m")
