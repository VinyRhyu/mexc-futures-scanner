import unittest
from types import SimpleNamespace
from scripts.research_basis_funding import extra,PRICE_LAG,FUND_LAG
from scripts.research_external_oi import parse

class SourceTests(unittest.TestCase):
    def test_lagged_basis_and_funding(self):
        t=7200
        keys=[t-PRICE_LAG-j for j in (0,900,3600)]
        bars={k+240:SimpleNamespace(close=101) for k in keys}
        idx={k:[100]*4 for k in keys}
        fair={k:[100.5]*4 for k in keys}
        funding={0:{"rate":".001","cycle_hours":8},3600:{"rate":".002","cycle_hours":8},
                 t:{"rate":"9","cycle_hours":8}}
        z=extra(bars,idx,fair,funding,sorted(funding),t)
        self.assertAlmostEqual(z[0],.01)
        self.assertEqual(z[-3],.002)
        self.assertEqual(len(z),12)
    def test_missing_no_backfill(self):
        self.assertIsNone(extra({}, {}, {}, {}, [],7200))
    def test_external_symbol_and_range(self):
        p={"symbol":"BTCUSDT","category":"linear","list":[{"timestamp":"1792865100000","openInterest":"42"}]}
        self.assertEqual(parse(p,"BTCUSDT",1792865100,1792865400),{1792865100:"42"})
        with self.assertRaises(ValueError):
            parse(p,"ETHUSDT",1792865100,1792865400)
