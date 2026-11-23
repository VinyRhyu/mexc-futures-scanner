import unittest
from types import SimpleNamespace as Bar

from scripts.research_liquid_holdout import (
    WEEKS, assign_week, retentive_copy, wallet_brief, wilson_95
)


class LiquidM1HoldoutTests(unittest.TestCase):
    def _row(self, signal=180):
        return {
            "id": "one", "symbol": "BTC_USDT", "side": "LONG",
            "M1": {"signal": signal - 60, "stop": "90", "target": "120"},
            "M1_SUSTENTADA": {"signal": signal, "outcome": "ALVO"}
        }

    def test_week_boundary_uses_brazil_time(self):
        self.assertEqual(assign_week("2026-11-14T23:59:00-03:00"), WEEKS[0])
        self.assertEqual(assign_week("2026-11-15T00:00:00-03:00"), WEEKS[1])

    def test_second_volume_equal_half_is_kept(self):
        mm = {"BTC_USDT": {
            60: Bar(ts=60, end=120, volume=10),
            120: Bar(ts=120, end=180, volume=5)
        }}
        rows, counts = retentive_copy([self._row()], mm)
        self.assertEqual(counts, {"accepted": 1})
        self.assertEqual(rows[0]["M1_SUSTENTADA"]["signal"], 180)

    def test_future_volume_cannot_change_volume_decision(self):
        mm = {"BTC_USDT": {
            60: Bar(ts=60, end=120, volume=10),
            120: Bar(ts=120, end=180, volume=4),
            180: Bar(ts=180, end=240, volume=1000000)
        }}
        rows, counts = retentive_copy([self._row()], mm)
        self.assertEqual(counts, {"volume_rejected": 1})
        self.assertNotIn("signal", rows[0]["M1_SUSTENTADA"])

    def test_original_row_is_not_mutated(self):
        original = self._row()
        mm = {"BTC_USDT": {
            60: Bar(ts=60, end=120, volume=0),
            120: Bar(ts=120, end=180, volume=100)
        }}
        rows, _ = retentive_copy([original], mm)
        self.assertEqual(original["M1_SUSTENTADA"]["signal"], 180)
        self.assertNotIn("signal", rows[0]["M1_SUSTENTADA"])

    def test_nonconsecutive_candles_cannot_create_signal(self):
        mm = {"BTC_USDT": {
            60: Bar(ts=60, end=119, volume=10),
            120: Bar(ts=120, end=180, volume=10)
        }}
        with self.assertRaises(ValueError):
            retentive_copy([self._row()], mm)

    def test_wilson_interval_is_bounded_not_a_guarantee(self):
        self.assertIsNone(wilson_95(0, 0))
        low, high = wilson_95(4, 5)
        self.assertLess(low, 0.8)
        self.assertGreater(high, 0.8)
        self.assertLessEqual(high, 1)

    def test_win_rate_not_confused_with_target_rate(self):
        result = {
            "initial_balance": "50", "final_balance": "51", "net_usdt": "1",
            "return_percent": "2", "entries": 2,
            "gains_usdt": "2", "losses_usdt": "1",
            "maximum_realized_drawdown_percent": "2",
            "skips": {},
            "trades": [
                {"outcome": "STOP", "net_usdt": "-1", "planned_risk": "1"},
                {"outcome": "ENCERRAMENTO_4H", "net_usdt": "2", "planned_risk": "1"}
            ]
        }
        brief = wallet_brief(result)
        self.assertEqual(brief["targets"], 0)
        self.assertEqual(brief["stops"], 1)
        self.assertEqual(brief["time_exits"], 1)
        self.assertEqual(brief["net_win_rate"], 0.5)
        self.assertEqual(brief["target_rate_closed"], 0.0)
        self.assertEqual(brief["sum_net_r"], "1")


if __name__ == "__main__":
    unittest.main()
