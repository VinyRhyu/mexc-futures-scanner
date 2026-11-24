import unittest
from scripts.research_cost_selection import causal_cost_r,cost_band,MAX_COST_R
from mexc_scanner.models import D

class CostSelectionTests(unittest.TestCase):
    def test_known_notional(self):
        self.assertAlmostEqual(causal_cost_r(D(100),D(1),.0024),.24)
    def test_cost_band(self):
        self.assertEqual(cost_band(MAX_COST_R),"le_0.25R")
        self.assertEqual(cost_band(.251),"0.25_to_0.5R")
        self.assertEqual(cost_band(1.1),"gt_1R")
    def test_invalid_geometry(self):
        with self.assertRaises(ValueError):
            causal_cost_r(D(100),D(0),.0024)
