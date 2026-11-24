import unittest
from scripts.research_pooled_target import expected
from scripts.research_amplitude_240 import split,CUT1,MAX_LABEL

class PooledTests(unittest.TestCase):
    def test_target_cap_and_cost(self):
        self.assertAlmostEqual(expected(4,100,"LONG",.0024),3-.0024*101.5)
        self.assertAlmostEqual(expected(4,100,"SHORT",.0024),3-.0024*98.5)
    def test_cost_gate(self):
        self.assertGreater(expected(.3,100,"LONG",.0024),0)
        self.assertLess(expected(.3,100,"LONG",.005),0)
    def test_purge(self):
        self.assertEqual(split(CUT1-MAX_LABEL),"train")
        self.assertIsNone(split(CUT1-MAX_LABEL+1))
