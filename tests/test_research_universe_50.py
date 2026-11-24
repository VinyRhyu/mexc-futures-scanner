import unittest
from scripts.research_universe_50 import choose,FIXED,LIMIT

class Universe50Tests(unittest.TestCase):
    def test_limit_and_fixed_reference(self):
        rows=[{"symbol":s} for s in FIXED]+[{"symbol":f"X{i}_USDT"} for i in range(100)]
        extra=choose(rows)
        self.assertEqual(len(extra),LIMIT-len(FIXED))
        self.assertEqual(extra[0],"X0_USDT")
        self.assertFalse(set(extra)&set(FIXED))
    def test_no_duplicate_or_padding(self):
        self.assertEqual(choose([{"symbol":FIXED[0]},{"symbol":"X"},{"symbol":"X"}]),["X"])
    def test_preserve_rank(self):
        self.assertEqual(choose([{"symbol":"B"},{"symbol":"A"}],len(FIXED)+1),["B"])
