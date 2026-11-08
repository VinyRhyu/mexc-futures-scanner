import unittest
from unittest.mock import patch

from mexc_scanner.models import Candle, D, Plan
from mexc_scanner.strategies import advance_plan, process_symbol
from mexc_scanner.config import Config


def candle(ts, op, hi, lo, cl):
    c = Candle(ts, 900, D(op), D(hi), D(lo), D(cl), D(100))
    c.validate()
    return c


def breakout_plan(side="LONG"):
    return Plan("p", "TEST_USDT", "ROMPIMENTO", side, 3600, 3600, 5400,
                D(1), D(102) if side == "LONG" else D(98), D(98), D(102),
                D("101.5") if side == "LONG" else D("98.5"), "family")


class BreakoutTests(unittest.TestCase):
    def test_confirmation_has_an_executable_window(self):
        p = breakout_plan()
        first = candle(3600, "101.9", "102.5", "101.4", "102.3")
        second = candle(4500, "102.3", "102.7", "102.1", "102.4")
        advance_plan(p, first, [first], [], D("0.01"))
        self.assertIn("ANTECIPADA", p.variants)
        advance_plan(p, second, [first, second], [], D("0.01"))
        self.assertIn("CONFIRMADA", p.variants)
        self.assertGreater(p.expires_at, second.end + 10)

    def test_first_breakout_wick_is_not_a_previous_stop(self):
        p = breakout_plan()
        first = candle(3600, "101", "102.5", "100.5", "102.3")
        advance_plan(p, first, [first], [], D("0.01"))
        self.assertEqual(p.status, "ATIVO")
        self.assertIn("ANTECIPADA", p.variants)

    def test_expired_plan_does_not_return(self):
        p = breakout_plan()
        late = candle(6300, "102", "102.5", "101.8", "102.3")
        advance_plan(p, late, [late], [], D("0.01"))
        self.assertEqual(p.status, "EXPIRADO")
        later = candle(7200, "102.3", "103", "102.2", "102.8")
        advance_plan(p, later, [late, later], [], D("0.01"))
        self.assertEqual(p.status, "EXPIRADO")

    def test_short_confirmation_uses_mirrored_trigger(self):
        p = breakout_plan("SHORT")
        first = candle(3600, "98.1", "99.0", "97.5", "97.7")
        second = candle(4500, "97.7", "97.9", "97.2", "97.6")
        advance_plan(p, first, [first], [], D("0.01"))
        advance_plan(p, second, [first, second], [], D("0.01"))
        self.assertEqual(set(p.variants), {"ANTECIPADA", "CONFIRMADA"})

    def test_stop_after_trigger_blocks_confirmation(self):
        p = breakout_plan()
        first = candle(3600, "101.9", "102.5", "101.4", "102.3")
        second = candle(4500, "102.3", "102.8", "101.4", "102.5")
        advance_plan(p, first, [first], [], D("0.01"))
        advance_plan(p, second, [first, second], [], D("0.01"))
        self.assertEqual(p.status, "INVALIDADO")
        self.assertNotIn("CONFIRMADA", p.variants)


class ContinuationTests(unittest.TestCase):
    def test_early_and_confirmed_can_be_discovered_in_one_scan(self):
        q = [candle(i * 900, "102", "103", "101", "102") for i in range(30)]
        q[-2] = candle(q[-2].ts, "101.2", "101.5", "99.8", "101.1")
        q[-1] = candle(q[-1].ts, "101.1", "102", "100.7", "101.7")
        with patch("mexc_scanner.strategies.structure", return_value="ALTA"), patch("mexc_scanner.strategies.latest_breakout", return_value=D(100)):
            plans, _ = process_symbol("TEST_USDT", q, [], [], 0, q[-1].end + 10, D("0.01"), Config())
        active = [p for p in plans if p.strategy == "CONTINUACAO" and not p.terminal]
        self.assertTrue(active)
        self.assertIn("ANTECIPADA", active[-1].variants)
        self.assertIn("CONFIRMADA", active[-1].variants)
        self.assertEqual(active[-1].variants["ANTECIPADA"].stop, active[-1].variants["CONFIRMADA"].stop)

    def test_ambiguous_bar_is_not_assigned_a_winning_outcome(self):
        p = breakout_plan()
        first = candle(3600, "101.9", "102.5", "101.4", "102.3")
        advance_plan(p, first, [first], [], D("0.01"))
        both = candle(4500, "102.3", "107", "101", "102.4")
        advance_plan(p, both, [first, both], [], D("0.01"))
        self.assertEqual(p.status, "AMBIGUO")


if __name__ == "__main__":
    unittest.main()
