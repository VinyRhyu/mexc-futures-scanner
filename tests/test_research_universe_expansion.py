import unittest
from scripts.research_universe_expansion import alignment,TIER1,TIER2,SYMBOLS

class ExpansionTests(unittest.TestCase):
    def test_missing_and_unexpected(self):
        v=alignment({60:1,180:1},{60:1,120:1})
        self.assertEqual(v["missing"],1)
        self.assertEqual(v["unexpected"],1)
        self.assertEqual(v["coverage_pct"],50)
    def test_full_alignment(self):
        self.assertEqual(alignment({60:1,120:1},{60:1,120:1})["coverage_pct"],100)
    def test_disjoint_fixed_baskets(self):
        self.assertEqual(len(set((*SYMBOLS,*TIER1,*TIER2))),18)
