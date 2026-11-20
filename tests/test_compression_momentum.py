"""Unit tests for fixed BCM-1 signal generation and causal paper execution."""
import copy
import unittest

from scripts.audit_compression_momentum import (
    detect_breakout, simulate_trade, replay_bcm,
)


def candle_fixture(direction="LONG"):
    h=[]
    for i in range(160):
        cl = (100 + i*.1) if direction=="LONG" else (150-i*.1)
        h.append([(i-159)*3_600_000,cl-.01,cl+.02,cl-.02,cl,1000,100000])
    m=[]
    for i in range(125):
        # Earlier period is volatile, last 12 before trigger are compressed.
        span = .1 if 58<=i<70 else 1.0
        m.append([i*300_000,100.0,100+span,100-span,100.0,10,100])
    if direction=="LONG":
        m[70]=[70*300_000,100.05,100.70,100.0,100.65,20,250]
        m[71]=[71*300_000,100.65,100.70,100.61,100.66,10,100]
        for i in range(72,100):
            m[i]=[i*300_000,100.65,100.70,100.61,100.66,10,100]
    else:
        m[70]=[70*300_000,99.95,100.0,99.30,99.35,20,250]
        m[71]=[71*300_000,99.35,99.39,99.30,99.34,10,100]
        for i in range(72,100):
            m[i]=[i*300_000,99.35,99.39,99.30,99.34,10,100]
    return m,h


class CompressionMomentumTests(unittest.TestCase):
    def test_long_causal_next_bar_open(self):
        m,h=candle_fixture()
        self.assertIsNone(detect_breakout(m,h,69))
        s=detect_breakout(m,h,70)
        self.assertIsNotNone(s)
        self.assertEqual(s["direction"],"LONG")
        self.assertEqual(s["signal_at"],"1970-01-01T05:55:00+00:00")
        self.assertEqual(s,detect_breakout(m[:71],h,70))
        t=simulate_trade(m,s)
        self.assertEqual(t["entry_at"],s["signal_at"])
        self.assertEqual(t["result"],"TIME")
        self.assertGreaterEqual(t["net_rr_ex_ante"],1.2)

    def test_short_causal_next_bar_open(self):
        m,h=candle_fixture("SHORT")
        s=detect_breakout(m,h,70)
        self.assertIsNotNone(s)
        self.assertEqual(s["direction"],"SHORT")
        t=simulate_trade(m,s)
        self.assertEqual(t["result"],"TIME")

    def test_no_future_candles_used_for_trigger(self):
        m,h=candle_fixture()
        baseline=detect_breakout(m,h,70)
        changed=copy.deepcopy(m)
        for k in range(71,len(changed)):
            changed[k][1:]=[10000,15000,1,5000,50000,600000]
        self.assertEqual(baseline,detect_breakout(changed,h,70))

    def test_current_open_hour_cannot_change_signal(self):
        m,h=candle_fixture()
        baseline=detect_breakout(m,h,70)
        expanded=copy.deepcopy(h)
        # Candle opens at 05:00 UTC, but closes at 06:00, after M5 signal.
        # Existing history ends at 01:00; add 02-05 plus an unclosed H1
        for t in range(1,6):
            z=115.9+t*.1
            expanded.append([t*3_600_000,z-.02,z+.03,z-.03,z,10,100])
        self.assertEqual(baseline,detect_breakout(m,expanded,70))

    def test_compression_condition_prevents_signal(self):
        m,h=candle_fixture()
        for k in range(58,70):
            m[k][2]=101
            m[k][3]=99
        self.assertIsNone(detect_breakout(m,h,70))

    def test_volume_gate_prevents_signal(self):
        m,h=candle_fixture()
        m[70][6]=70
        self.assertIsNone(detect_breakout(m,h,70))

    def test_ambiguous_short_bar_penalized_not_win(self):
        m,h=candle_fixture("SHORT")
        s=detect_breakout(m,h,70)
        m[71]=[71*300_000,99.35,102,95,99.35,10,100]
        t=simulate_trade(m,s)
        self.assertEqual(t["result"],"AMBIGUOUS")
        self.assertIsNone(t["net_r"])

    def test_ambiguous_long_bar_penalized_not_win(self):
        m,h=candle_fixture()
        s=detect_breakout(m,h,70)
        m[71]=[71*300_000,100.65,105,95,100.65,10,100]
        t=simulate_trade(m,s)
        self.assertEqual(t["result"],"AMBIGUOUS")
        self.assertIsNone(t["net_r"])

    def test_replay_only_one_position_per_symbol(self):
        m,h=candle_fixture()
        trades,diagnostics=replay_bcm(m,h)
        self.assertEqual(len(trades),1)
        self.assertEqual(trades[0]["direction"],"LONG")


if __name__=="__main__":
    unittest.main()
