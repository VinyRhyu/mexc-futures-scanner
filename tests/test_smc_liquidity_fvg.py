"""SMC-R causal tests, not profit validation."""
import copy
import unittest

from scripts.audit_smc_liquidity_fvg import (
    detect_sweep, detect_signal_at, execute_short,
    h1_states, h1_is_down, replay_smc,
)


class SmcLiquidityFvgTests(unittest.TestCase):
    def setUp(self):
        self.hourly = [
            [(i-160)*3600_000, 240-i*0.5, 241-i*0.5,
             239-i*0.5, 240-i*0.5, 1000, 100000]
            for i in range(160)
        ]
        self.m5 = [
            [i*300_000, 100.0, 100.1, 99.9, 100.0, 10.0, 100.0]
            for i in range(110)
        ]
        self.j = 45
        self.i = 47
        self.m5[self.j] = [45*300_000,100.3,100.8,99.95,100.0,15,140]
        self.m5[46] = [46*300_000,100.0,100.05,99.65,99.7,10,100]
        self.m5[self.i] = [47*300_000,99.6,99.7,99.3,99.35,20,220]
        self.m5[48] = [48*300_000,99.35,99.6,99.25,99.4,10,100]

    def test_sweep_then_fvg_only_on_closing_candle(self):
        self.assertIsNotNone(detect_sweep(self.m5,self.j))
        self.assertIsNone(detect_signal_at(self.m5,self.hourly,self.j))
        self.assertIsNone(detect_signal_at(self.m5,self.hourly,46))
        signal = detect_signal_at(self.m5,self.hourly,self.i)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["sweep_index"],self.j)
        self.assertEqual(signal["signal_index"],self.i)
        self.assertEqual(signal["signal_ms"],self.m5[self.i][0]+300000)
        self.assertEqual(signal,detect_signal_at(self.m5[:self.i+1],self.hourly,self.i))

    def test_future_candles_do_not_change_decision(self):
        before=detect_signal_at(self.m5,self.hourly,self.i)
        future=copy.deepcopy(self.m5)
        for x in future[self.i+1:]:
            x[1],x[2],x[3],x[4],x[6]=500,510,490,500,9999
        self.assertEqual(before, detect_signal_at(future,self.hourly,self.i))

    def test_h1_future_does_not_change_decision(self):
        before=detect_signal_at(self.m5,self.hourly,self.i)
        future=copy.deepcopy(self.hourly)
        # This H1 finishes strictly after the decision.
        future.append([6*3600000,999,999,999,999,0,0])
        self.assertEqual(before, detect_signal_at(self.m5,future,self.i))

    def test_fvg_gap_must_be_real_and_displacement_bearish(self):
        altered=copy.deepcopy(self.m5)
        altered[self.i][2]=99.97
        self.assertIsNone(detect_signal_at(altered,self.hourly,self.i))
        altered=copy.deepcopy(self.m5)
        altered[self.i][4]=99.58  # bearish body too narrow vs ATR sweep
        self.assertIsNone(detect_signal_at(altered,self.hourly,self.i))

    def test_risk_levels_fixed_and_entry_after_signal(self):
        s=detect_signal_at(self.m5,self.hourly,self.i)
        trade=execute_short(self.m5,s)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["entry_at"],s["signal_at"])
        self.assertAlmostEqual(trade["stop"],s["stop_raw"])
        self.assertEqual(trade["result"],"TIME")

    def test_ambiguous_bar_cannot_count_as_tp(self):
        s=detect_signal_at(self.m5,self.hourly,self.i)
        changed=copy.deepcopy(self.m5)
        changed[self.i+1]=[48*300_000,99.35,102,94,99.35,100,999]
        trade=execute_short(changed,s)
        self.assertEqual(trade["result"],"AMBIGUOUS")
        self.assertIsNone(trade["net_r"])

    def test_no_sweep_on_future_centered_pivot(self):
        m=copy.deepcopy(self.m5)
        # The sweep is disallowed when its rejection doesn't close below level.
        m[self.j][4]=100.6
        self.assertIsNone(detect_sweep(m,self.j))
        self.assertIsNone(detect_signal_at(m,self.hourly,self.i))

    def test_replay_only_one_position_per_asset(self):
        trades,_=replay_smc(self.m5,self.hourly)
        self.assertEqual(len(trades),1)
        self.assertEqual(trades[0]["signal_at"],
                         detect_signal_at(self.m5,self.hourly,self.i)["signal_at"])


if __name__=="__main__":
    unittest.main()
