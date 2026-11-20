"""Tests for causal regime gates. Not a profitability claim."""
import unittest
from scripts.audit_confluence_v2 import h4_bias_down, btc_bias_down, gate_for


class RegimeGateTests(unittest.TestCase):
    def setUp(self):
        # Continuous hourly bars; descending trend until index 159, so 40 H4 bars.
        self.hours = [
            [i * 3600_000, 240-i*.6, 241-i*.6,
             239-i*.6, 240-i*.6, 1000, 50000]
            for i in range(160)
        ]

    def test_h4_uses_only_completed_four_hour_candles(self):
        cutoff = 140 * 3600_000  # 35 complete H4 bars
        self.assertTrue(h4_bias_down(self.hours, cutoff))
        edited = [list(x) for x in self.hours]
        for x in edited:
            if x[0] + 3600_000 > cutoff:
                x[4] += 10000
        self.assertEqual(h4_bias_down(self.hours,cutoff), h4_bias_down(edited,cutoff))

    def test_btc_uses_only_completed_h1(self):
        cutoff = 125 * 3600_000
        self.assertTrue(btc_bias_down(self.hours, cutoff))
        future = [list(x) for x in self.hours]
        for x in future:
            if x[0] + 3600_000 > cutoff:
                x[4] += 10000
        self.assertEqual(btc_bias_down(self.hours,cutoff), btc_bias_down(future,cutoff))

    def test_fail_closed_on_inadequate_h4_history(self):
        self.assertFalse(h4_bias_down(self.hours, 40*3600_000))
        self.assertFalse(btc_bias_down(self.hours, 5*3600_000))

    def test_volume_filter_applies_without_future_bars(self):
        five = [[0,1,1,1,1,10,100]]*20+[[20*300_000,1,1,1,1,10,100]]
        bad={"relative_quote_volume":1.9,"range_to_prior_atr":1.5}
        good={"relative_quote_volume":2.0,"range_to_prior_atr":.8}
        self.assertFalse(gate_for("E_volume",self.hours)(bad,five,self.hours,20))
        self.assertTrue(gate_for("E_volume",self.hours)(good,five,self.hours,20))
        self.assertFalse(gate_for("E_volume",self.hours)(
            {"relative_quote_volume":2.5,"range_to_prior_atr":.5},five,self.hours,20))


if __name__ == "__main__":
    unittest.main()
