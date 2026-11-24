import unittest
from scripts.research_gate_stats import parse,coverage,collect,STEP,LEFT

class GateTests(unittest.TestCase):
    def test_missing_not_zero(self):
        rows=parse([{"time":LEFT,"open_interest":"42","long_liq_usd":0}])
        q=coverage(rows,LEFT,LEFT+2*STEP)
        self.assertEqual(q["observed"],1)
        self.assertEqual(q["fields_present"]["long_liq_usd"],1)
        self.assertEqual(q["fields_present"]["short_liq_usd"],0)
    def test_forward_range(self):
        def fetch(path,p):
            t=p["from"]
            return [{"time":t+i*STEP,"open_interest":"42"} for i in range(p["limit"])]
        r,a=collect(fetch,"BTC_USDT",LEFT,LEFT+105*STEP)
        self.assertEqual(len(r),105)
        self.assertEqual(a["mode"],"forward")
    def test_backward_range(self):
        def fetch(path,p):
            t=p["from"]
            return [{"time":t-i*STEP,"open_interest":"42"} for i in range(p["limit"])]
        r,a=collect(fetch,"BTC_USDT",LEFT,LEFT+105*STEP)
        self.assertEqual(len(r),105)
        self.assertEqual(a["mode"],"backward")
    def test_block(self):
        def fetch(path,p):
            raise PermissionError("forbidden")
        r,a=collect(fetch,"BTC_USDT",LEFT,LEFT+STEP)
        self.assertEqual(r,{})
        self.assertEqual(a["requests"],1)
