"""Regression tests for 35% MEXC-like initial-margin ROI experiment."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch
import unittest

from mexc_scanner.models import D
from scripts.research_equity_curve import run_wallet
from tests.test_research_equity_curve import source


def fake_selected_settlement(row,quoted,balance_before):
    """Only the selected trade can see its prior stored OHLC outcome."""
    gain=D("0.10") if row["future_exit"]["outcome"]=="ALVO" else -D("0.05")
    return {
        "net_usdt":gain,"net_r":gain/D("0.05"),
        "risk_usdt":D("0.05"),"contracts":D("1"),"margin_usdt":D("0.8"),
        "cost_reserve_usdt":D("0.01"),"leverage":10,
        "net_rr_projected":D("2"),"notional_usdt":D("8"),
        "outcome":row["future_exit"]["outcome"],
        "exit_at":row["future_exit"]["exit_at"],
    }


class LeverageMarginROI35Tests(unittest.TestCase):
    def test_35_pct_gate_checks_projected_tp_only_before_realization(self):
        a=source(at="2026-10-26T12:00:00+00:00",sym="BTC_USDT",planid="a",stop_first=False)
        b=source(at="2026-10-26T14:00:00+00:00",sym="ETH_USDT",planid="b",stop_first=False)
        def fake_quote(row,balance,cfg,slip,floor):
            # Selection uses a PRETRADING objective, not future_exit outcome.
            projected=D("0.30") if row["symbol"]=="BTC_USDT" else D("0.20")
            return {"quote":{
                "net_rr":"2","gain_usdt":str(projected),
                "margin_usdt":"0.8"}},[]
        with patch("scripts.research_equity_curve.reprice_candidate",side_effect=fake_quote),\
             patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_selected_settlement):
            first=run_wallet([a,b],rule="RR15",fixed_leverage=10,
                             min_projected_tp_roi_pct="35")
        self.assertEqual(first["trades"],1)
        self.assertEqual(first["trades_detail"][0]["symbol"],"BTC_USDT")
        self.assertEqual(first["skipped_or_blocked_counts"]["ROI35_PROJECTED_AT_TP_VETO"],1)
        b["future_exit"]["outcome"]="STOP"
        b["future_exit"]["exit_reference"]="98"
        with patch("scripts.research_equity_curve.reprice_candidate",side_effect=fake_quote),\
             patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_selected_settlement):
            repeat=run_wallet([a,b],rule="RR15",fixed_leverage=10,
                              min_projected_tp_roi_pct="35")
        self.assertEqual(first["trades_detail"],repeat["trades_detail"])

    def test_fixed_leverage_propagates_to_existing_financial_evaluator(self):
        row=source(at="2026-10-26T12:00:00+00:00",stop_first=False)
        for lev in (10,15,20):
            captured=[]
            def fake_quote(row,balance,cfg,slip,floor):
                captured.append((cfg.minimum_leverage,cfg.max_leverage))
                return {"quote":{"net_rr":"2","gain_usdt":"0.5",
                                 "margin_usdt":"0.8"}},[]
            with patch("scripts.research_equity_curve.reprice_candidate",side_effect=fake_quote),\
                 patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_selected_settlement):
                result=run_wallet([row],rule="RR15",fixed_leverage=lev,
                                  min_projected_tp_roi_pct="35")
            self.assertEqual(captured,[(lev,lev)])
            self.assertEqual(result["trades"],1)
            self.assertEqual(result["trades_detail"][0]["net_realized_roi_pct_of_margin"],"12.500")

    def test_invalid_leverage_rejected_before_quotes(self):
        with self.assertRaisesRegex(ValueError,"predeclared"):
            run_wallet([],fixed_leverage=30)
        with self.assertRaisesRegex(ValueError,"predeclared"):
            run_wallet([],fixed_leverage=5)
        with self.assertRaisesRegex(ValueError,"only predeclared"):
            run_wallet([],rule="BASE",fixed_leverage=10,min_projected_tp_roi_pct="35")
        with self.assertRaisesRegex(ValueError,"only predeclared"):
            run_wallet([],rule="RR15",fixed_leverage=10,min_projected_tp_roi_pct="40")

    def test_35pct_projected_does_not_guarantee_realized_profit(self):
        row=source(at="2026-10-26T12:00:00+00:00",stop_first=True)
        with patch("scripts.research_equity_curve.reprice_candidate",return_value=(
               {"quote":{"net_rr":"2","gain_usdt":"0.4","margin_usdt":"0.8"}},[])),\
             patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_selected_settlement):
            result=run_wallet([row],rule="RR15",fixed_leverage=10,min_projected_tp_roi_pct="35")
        self.assertEqual(result["trades"],1)
        self.assertLess(D(result["trades_detail"][0]["net_realized_roi_pct_of_margin"]),0)

    def test_wallet_accounting_reconciles_and_isolates_no_new_money(self):
        row=source(at="2026-10-26T12:00:00+00:00",stop_first=True)
        with patch("scripts.research_equity_curve.reprice_candidate",return_value=(
               {"quote":{"net_rr":"2","gain_usdt":"0.4","margin_usdt":"0.8"}},[])),\
             patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_selected_settlement):
            result=run_wallet([row],rule="RR15",fixed_leverage=20,min_projected_tp_roi_pct="35")
        self.assertEqual(D(result["ending_usdt"]),D("1")+D(result["trades_detail"][0]["net_usdt"]))


if __name__ == "__main__":
    unittest.main()
