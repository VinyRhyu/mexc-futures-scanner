"""BRK-T deterministic synthetic causality and execution tests."""
import copy
import unittest
from scripts.audit_brkt_momentum import signal_at, execute, replay


class BreakoutMomentumTests(unittest.TestCase):
    def setUp(self):
        # 120 closed H1 candles before M5, strict uptrend.
        self.h=[[(-120+k)*3600000,100+k*.1,101+k*.1,99+k*.1,
                 100+k*.1,10,100] for k in range(120)]
        self.m=[[i*300000,100,100.1,99.9,100,10,100] for i in range(100)]
        self.i=45
        self.m[self.i]=[self.i*300000,100,100.5,99.95,100.45,40,400]
        self.m[self.i+1]=[(self.i+1)*300000,100.45,100.5,99.9,100.1,10,100]

    def test_signal_only_after_breakout_close(self):
        s=signal_at(self.m,self.h,self.i)
        self.assertIsNotNone(s)
        self.assertEqual(s["side"],"LONG")
        self.assertIsNone(signal_at(self.m,self.h,self.i-1))
        self.assertEqual(s["signal_at"],s["signal_at"])
        self.assertEqual(s,signal_at(self.m[:self.i+1],self.h,self.i))

    def test_no_future_candles_leak(self):
        original=signal_at(self.m,self.h,self.i)
        changed=copy.deepcopy(self.m)
        for row in changed[self.i+1:]:
            row[1:]=[200,220,180,210,99,999]
        self.assertEqual(original,signal_at(changed,self.h,self.i))

    def test_no_future_hourly_leak(self):
        original=signal_at(self.m,self.h,self.i)
        later=copy.deepcopy(self.h)
        later.append([20*3600000,10,11,9,10,10,100])
        self.assertEqual(original,signal_at(self.m,later,self.i))

    def test_volume_required(self):
        changed=copy.deepcopy(self.m)
        changed[self.i][6]=100
        self.assertIsNone(signal_at(changed,self.h,self.i))

    def test_compression_required(self):
        changed=copy.deepcopy(self.m)
        changed[self.i-5][2]=102
        self.assertIsNone(signal_at(changed,self.h,self.i))

    def test_next_open_and_ambiguous_is_loss(self):
        s=signal_at(self.m,self.h,self.i)
        t=execute(self.m,s)
        self.assertEqual(t["entry_at"],s["signal_at"])
        self.assertEqual(t["result"],"TIME")
        changed=copy.deepcopy(self.m)
        changed[self.i+1]=[(self.i+1)*300000,100.95,200,50,100.95,10,100]
        t=execute(changed,s)
        self.assertEqual(t["result"],"AMBIGUOUS")
        self.assertIsNone(t["net_r"])

    def test_no_overlapping_per_asset(self):
        trades,stats=replay(self.m,self.h)
        self.assertEqual(len(trades),1)
        self.assertEqual(stats["LONG"],1)


if __name__=="__main__":
    unittest.main()
