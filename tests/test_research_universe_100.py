import unittest
from scripts.research_universe_100 import choose,liquidity_band

class Universe100Tests(unittest.TestCase):
    def test_boundaries(self):
        for x,y in [("999999","below_1m"),("1000000","1m_to_2.5m"),("2499999","1m_to_2.5m"),("2500000","2.5m_to_5m"),("5000000","5m_plus")]:
            self.assertEqual(liquidity_band(x),y)
    def test_rank_cap(self):
        ref=[f"R{i}" for i in range(31)]
        rows=[{"symbol":s} for s in ref]+[{"symbol":f"X{i}"} for i in range(100)]
        result=choose(rows,ref)
        self.assertEqual(len(result),69)
        self.assertEqual(result[0],"X0")
        self.assertEqual(result[-1],"X68")
    def test_no_padding(self):
        self.assertEqual(choose([{"symbol":"R"},{"symbol":"X"},{"symbol":"X"}],["R"]),["X"])
