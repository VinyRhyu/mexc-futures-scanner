"""No-network regression checks for the explorative liquidity report."""
import unittest
from decimal import Decimal

from scripts.research_liquidity_cohort import wilson, summarize, portfolio_one_position, append_unseen_plans


class LiquidityCohortTests(unittest.TestCase):
    def test_wilson_not_invented_without_trades(self):
        self.assertIsNone(wilson(0, 0))
        self.assertEqual(wilson(10, 10)[1], 1.0)
        self.assertLess(wilson(1, 2)[0], 0.5)
        self.assertGreater(wilson(1, 2)[1], 0.5)

    def test_retired_plan_never_resurrects_after_pruning(self):
        from types import SimpleNamespace
        active, known = [], set()
        first = SimpleNamespace(id="formation_1")
        self.assertEqual(append_unseen_plans(active, [first], known), 1)
        self.assertEqual(len(active), 1)
        active.clear()  # production plan is expired and pruned
        self.assertEqual(append_unseen_plans(active, [first], known), 0)
        self.assertEqual(active, [])
        self.assertEqual(append_unseen_plans(
            active, [SimpleNamespace(id="formation_2")], known), 1)
        self.assertEqual({p.id for p in active}, {"formation_2"})

    def test_zero_signals_report_no_hit_probability(self):
        r = summarize([], "cost_base")
        self.assertEqual(r["confirmed"], 0)
        self.assertEqual(r["resolved"], 0)
        self.assertIsNone(r["positive_rate"])
        self.assertIsNone(r["mean_net_r"])

    def test_one_position_blocks_concurrent_signals(self):
        def sample(symbol, entry, exit, net_r, group):
            v = {"status": "FILLED_SIMULATED", "outcome": "ALVO" if net_r > 0 else "STOP",
                 "entry_at": entry, "exit_at": exit, "net_r": str(net_r)}
            return {"symbol": symbol, "plan_id": symbol,
                    "historical_group": group, "cost_base": v}

        rows = [
            sample("B_USDT", "2026-11-10T12:00:00+00:00",
                   "2026-11-10T12:05:00+00:00", -1, "lower_liquidity"),
            sample("A_USDT", "2026-11-10T12:00:00+00:00",
                   "2026-11-10T12:02:00+00:00", 2, "core_liquidity"),
            sample("C_USDT", "2026-11-10T12:03:00+00:00",
                   "2026-11-10T12:06:00+00:00", 1, "lower_liquidity"),
        ]
        r = portfolio_one_position(rows)
        self.assertEqual(r["trades"], 2)
        self.assertEqual(r["skipped_overlap"], 1)
        self.assertEqual(r["sum_net_r"], 3.0)
        self.assertEqual(r["wins"], 2)
        self.assertEqual(r["max_realized_drawdown_r"], 0)

    def test_summary_excludes_unfilled_and_counts_time_profit(self):
        rows = [
            {"cost_base": {"status": "FINANCIAL_BLOCK", "reasons": ["GATE"]}},
            {"cost_base": {"status": "FILLED_SIMULATED", "outcome": "TIME_4H",
                           "net_r": ".2", "net_usdt": "1", "exit_at": "2026-01-01"}},
            {"cost_base": {"status": "FILLED_SIMULATED", "outcome": "STOP",
                           "net_r": "-1", "net_usdt": "-2", "exit_at": "2026-01-01"}}
        ]
        r = summarize(rows, "cost_base")
        self.assertEqual(r["confirmed"], 3)
        self.assertEqual(r["financially_viable_and_filled"], 2)
        self.assertEqual(r["net_profitable"], 1)
        self.assertEqual(r["positive_rate"], .5)
        self.assertEqual(r["mean_net_r"], -.4)


if __name__ == "__main__":
    unittest.main()
