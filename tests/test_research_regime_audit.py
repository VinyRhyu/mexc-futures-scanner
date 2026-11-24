import unittest
from types import SimpleNamespace
from scripts.research_regime_audit import normalized_move,regime,leave_one
class RegimeTests(unittest.TestCase):
    def test_causal_closed_price(self):
        b={0:SimpleNamespace(close=100),60:SimpleNamespace(close=110),120:SimpleNamespace(close=121),180:SimpleNamespace(close=1)}
        self.assertEqual(regime(normalized_move(b,180,2)),"UP")
        b[180].close=10000
        self.assertEqual(regime(normalized_move(b,180,2)),"UP")
    def test_boundaries(self):
        self.assertEqual([regime(x) for x in [-1,-.99,0,.99,1]],["DOWN","NEUTRAL","NEUTRAL","NEUTRAL","UP"])
    def test_leave_one(self):
        self.assertEqual(leave_one({"x":{"net_stress":6},"y":{"net_stress":-2}},4),{"x":-2,"y":6})
