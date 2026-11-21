"""Offline guardrails for the TAO pilot, never a proof of profitability."""
import copy
import json
import unittest
from pathlib import Path

from scripts.audit_confluence_pilot import Parameters, replay, scan_at, validate_source


FIXTURE = Path(__file__).parent / "fixtures" / "tao_okx_20261120.json"


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_tao_case_prealert_before_trigger(self):
        result = replay(self.data)
        self.assertTrue(any(p["at"] == "2026-11-20T01:15:00+00:00"
                            for p in result["prealerts"]))
        trades = [x for x in result["trades"]
                  if x["signal_at"] == "2026-11-20T01:40:00+00:00"]
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade["entry_at"], "2026-11-20T01:40:00+00:00")
        self.assertEqual(trade["result"], "TP")
        self.assertEqual(trade["exit_at"], "2026-11-20T01:50:00+00:00")
        self.assertAlmostEqual(trade["entry"], 191.53)
        self.assertGreater(trade["net_rr_ex_ante"], 1.0)
        self.assertLess(trade["net_rr_ex_ante"], 1.2)

    def test_future_candles_do_not_change_existing_trigger(self):
        five, hourly = validate_source(self.data)
        i = next(i for i, x in enumerate(five) if x[0] == 1795138500000)
        expected = scan_at(five, hourly, i)
        self.assertTrue(expected["trigger"])
        modified_five = copy.deepcopy(five)
        modified_hours = copy.deepcopy(hourly)
        for x in modified_five[i+1:]:
            x[1] += 1000
            x[2] += 1000
            x[3] += 1000
            x[4] += 1000
        for x in modified_hours:
            if x[0] + 3600000 > five[i][0] + 300000:
                for col in (1, 2, 3, 4):
                    x[col] += 1000
        self.assertEqual(expected, scan_at(modified_five, modified_hours, i))
        self.assertEqual(expected, scan_at(five[:i+1], hourly, i))

    def test_ambiguous_bar_cannot_be_counted_as_win(self):
        modified = copy.deepcopy(self.data)
        five = modified["candles"]["5m"]
        k = next(k for k, x in enumerate(five) if x[0] == 1795138800000)
        five[k][2] = 200  # after signal, same candle touches stop
        five[k][3] = 180  # and target; the order is unknowable with M5 OHLC
        result = replay(modified)
        at = "2026-11-20T01:40:00+00:00"
        chosen = [x for x in result["trades"] if x["signal_at"] == at]
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["result"], "AMBIGUOUS")
        self.assertIsNone(chosen[0]["net_r"])

    def test_repeatable(self):
        self.assertEqual(replay(self.data), replay(self.data))

    def test_reject_partial_or_gapped_data(self):
        modified = copy.deepcopy(self.data)
        modified["closed_candles_only"] = False
        with self.assertRaises(ValueError):
            validate_source(modified)
        modified = copy.deepcopy(self.data)
        del modified["candles"]["5m"][5]
        with self.assertRaises(ValueError):
            validate_source(modified)


if __name__ == "__main__":
    unittest.main()
