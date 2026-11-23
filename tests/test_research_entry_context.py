"""Research A/B tests, fully synthetic and without MEXC network."""
import unittest
from decimal import Decimal
from unittest.mock import patch
from mexc_scanner.models import Candle, DataError
from scripts.research_entry_context import entry_context, passes_filter, pick_portfolio, portfolio_diagnostics


class CausalContextTests(unittest.TestCase):
    def fixtures(self):
        start = 900 * 2000
        minutes=[]
        for i in range(241):
            cl = Decimal("100") + (Decimal(10) if i == 240 else Decimal(0))
            minutes.append(Candle(start + i*60, 60, cl, cl+Decimal("0.2"),
                                  cl-Decimal("0.2"), cl, Decimal("10")))
        end=minutes[-1].end
        qend=(end//900)*900
        q=[Candle(qend-900*(14-i),900,D("100"),D("100.5"),D("99.5"),D("100"),D("10"))
           for i in range(14)]
        hend=(end//3600)*3600
        h=[Candle(hend-3600*(12-i),3600,D("100"),D("101"),D("99"),D("100"),D("100"))
           for i in range(12)]
        return q,h,minutes

    def test_A_only_looks_back_4h_and_blocks_extended_long(self):
        q,h,m=self.fixtures()
        with patch("scripts.research_entry_context.structure",return_value="INDEFINIDA"):
            r=entry_context(q,h,m,240,"LONG")
        self.assertEqual(r["asof"],m[-1].end)
        self.assertTrue(r["A_late"])
        self.assertFalse(r["B_against_h1"])
        self.assertGreater(Decimal(r["m1_signed_4h_extension_atr"]),2)

    def test_B_only_blocks_known_opposite_structure(self):
        q,h,m=self.fixtures()
        with patch("scripts.research_entry_context.structure",return_value="BAIXA"):
            r=entry_context(q,h,m,240,"LONG")
        self.assertTrue(r["B_against_h1"])
        with patch("scripts.research_entry_context.structure",return_value="DESCONHECIDA"):
            r=entry_context(q,h,m,240,"LONG")
        self.assertFalse(r["B_against_h1"])

    def test_future_m15_or_h1_bars_are_rejected(self):
        q,h,m=self.fixtures()
        bad_q=q+[Candle(m[-1].end,900,D(100),D(101),D(99),D(100),D(1))]
        with self.assertRaises(DataError):
            entry_context(bad_q,h,m,240,"LONG")
        bad_h=h+[Candle(m[-1].end,3600,D(100),D(101),D(99),D(100),D(1))]
        with self.assertRaises(DataError):
            entry_context(q,bad_h,m,240,"LONG")

    def test_gap_and_short_history_are_rejected(self):
        q,h,m=self.fixtures()
        with self.assertRaises(DataError):
            entry_context(q,h,m,239,"LONG")
        bad=m.copy()
        c=bad[87]
        bad[87]=Candle(c.ts+60,c.tf,c.open,c.high,c.low,c.close,c.volume)
        with self.assertRaises(DataError):
            entry_context(q,h,bad,240,"LONG")


class PortfolioReallocationTests(unittest.TestCase):
    def make(self, symbol, start, end, ret, late=False, opposite=False):
        return {"symbol": symbol, "plan_id":symbol, "side":"LONG", "signal_at":start,
                "causal_context":{"A_late":late,"B_against_h1":opposite,"A_or_B":late or opposite},
                "cost_base":{"status":"FILLED_SIMULATED","entry_at":start,"exit_at":end,
                             "outcome":"ALVO" if Decimal(ret)>0 else "STOP","net_r":ret}}

    def test_reallocate_slot_to_previously_blocked_signal(self):
        rows=[
            self.make("A_USDT","2026-11-01T00:00:00+00:00",
                      "2026-11-01T00:15:00+00:00","-1",late=True),
            self.make("B_USDT","2026-11-01T00:01:00+00:00",
                      "2026-11-01T00:05:00+00:00","1.3"),
            self.make("C_USDT","2026-11-01T00:16:00+00:00",
                      "2026-11-01T00:20:00+00:00","-1",opposite=True)
        ]
        self.assertEqual([x["symbol"] for x in pick_portfolio(rows,"BASE")],["A_USDT","C_USDT"])
        self.assertEqual([x["symbol"] for x in pick_portfolio(rows,"A")],["B_USDT","C_USDT"])
        self.assertEqual([x["symbol"] for x in pick_portfolio(rows,"B")],["A_USDT"])
        self.assertEqual([x["symbol"] for x in pick_portfolio(rows,"A+B")],["B_USDT"])
        results=portfolio_diagnostics(rows)
        self.assertEqual(results["BASE"]["trades"],2)
        self.assertEqual(Decimal(results["BASE"]["sum_net_r"]),Decimal("-2"))
        self.assertEqual(Decimal(results["A+B"]["sum_net_r"]),Decimal("1.3"))
        self.assertEqual(results["A+B"]["newly_available_ids"],1)

    def test_filters_cannot_see_trade_outcomes(self):
        r=self.make("D_USDT","2026-11-01T00:00:00+00:00","2026-11-01T01:00:00+00:00","-1",late=True)
        self.assertFalse(passes_filter(r,"A"))
        r["cost_base"]["net_r"]="10"
        self.assertFalse(passes_filter(r,"A"))


def D(x):
    return Decimal(str(x))


if __name__=="__main__":
    unittest.main()
