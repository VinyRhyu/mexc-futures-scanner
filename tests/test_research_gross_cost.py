import unittest
from scripts.research_gross_cost import expected_net

class GrossCostTests(unittest.TestCase):
    def test_causal_cost(self):
        self.assertAlmostEqual(expected_net(1,100,"LONG",.0024),1-.0024*100.5-.05)
        self.assertAlmostEqual(expected_net(1,100,"SHORT",.0024),1-.0024*99.5-.05)
    def test_gross_cap_and_cost(self):
        self.assertEqual(expected_net(9,100,"LONG",.0024),expected_net(3,100,"LONG",.0024))
        self.assertLess(expected_net(.1,100,"SHORT",.0024),0)
    def test_invalid(self):
        for args in [(1,0,"LONG",.0024),(1,100,"bad",.0024),(float("nan"),100,"LONG",.0024)]:
            with self.assertRaises(ValueError):
                expected_net(*args)
