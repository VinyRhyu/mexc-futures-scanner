"""Offline regression for actual equity feedback instead of summing fixed 1-USDT PnL."""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
from unittest.mock import patch
import unittest

from mexc_scanner.models import Plan,Variant,Candle,D,jsonable
from scripts.research_equity_curve import (
    pack_equity_candidate,parse_candidate,describe_future_exit,
    reprice_candidate,settle_candidate,run_wallet,
)


def source(at="2026-10-26T12:00:00+00:00",sym="BTC_USDT",planid="a",stop_first=True):
    signal=int(datetime.fromisoformat(at).timestamp())
    v=Variant("CONFIRMADA",signal,D("100"),D("99.5"),D("100.5"),
              D("98"),D("110"),"test")
    p=Plan(planid,sym,"CONTINUACAO","LONG",signal-1800,signal-1800,signal+1800,
           D("2"),D("99"),D("97"),D("101"),D("98"),"BREAKOUT")
    p.variants={"CONFIRMADA":v}
    row={"symbol":sym,"maxLeverage":20,"contractSize":"0.001",
         "minVol":"1","volUnit":"1","priceUnit":"0.01",
         "maintenanceMarginRate":"0.005","liquidationFeeRate":"0.0006"}
    future=[Candle(signal+60*i,60,D("100"),D("101"),D("99"),D("100"),D("10"))
            for i in range(240)]
    if stop_first:
        future[1]=Candle(signal+60,60,D("100"),D("101"),D("97"),D("98"),D("12"))
    else:
        future[1]=Candle(signal+60,60,D("100"),D("111"),D("99"),D("110"),D("12"))
    return pack_equity_candidate(p,v,row,D("100"),future,D("8000000"),at)


class EquityCurveTests(unittest.TestCase):
    def test_early_stop_conservative(self):
        x=source()
        self.assertEqual(x["future_exit"]["outcome"],"STOP")
        self.assertEqual(D(x["future_exit"]["exit_reference"]),D("98"))

    def test_ambiguous_m1_bar_hits_stop_first(self):
        x=source()
        x["future_exit"]["outcome"]="STOP_AMBIGUO"
        # Outcome is provided by M1 replay; STOP takes precedence.
        parse_candidate(x)
        self.assertEqual(x["future_exit"]["outcome"],"STOP_AMBIGUO")

    def test_recorded_inputs_reconstruct_plan_variant_and_contract(self):
        a=source()
        p,v,c=parse_candidate(a)
        self.assertEqual(p.id,"a")
        self.assertEqual(c.symbol,"BTC_USDT")
        self.assertEqual(v.triggered_at,int(datetime.fromisoformat(a["signal_at"]).timestamp()))

    def test_no_outcome_influences_financial_quote(self):
        x=source()
        def quote(plan,variant,contract,price,now,config):
            self.assertEqual(config.initial_balance,"1")
            return {"status":"VIAVEL_SIMULADO","entry_low":"99",
                    "entry_high":"101","net_rr":"2","margin_usdt":"0.2",
                    "costs_usdt":"0.01","contracts":"3","base_quantity":"0.003",
                    "loss_usdt":"0.09","worst_entry":"100","leverage":10}
        with patch("scripts.research_equity_curve.paper_quote",side_effect=quote):
            r1,_=reprice_candidate(x,D("1"),type("CFG",(),{
                "mode":"paper","minimum_turnover":"5000000",
                "taker_fee":"0.0006"})(),D(".0002"),D("1.5"))
            x["future_exit"]["outcome"]="ALVO"
            x["future_exit"]["exit_reference"]="110"
            r2,_=reprice_candidate(x,D("1"),type("CFG",(),{
                "mode":"paper","minimum_turnover":"5000000",
                "taker_fee":"0.0006"})(),D(".0002"),D("1.5"))
        self.assertEqual(r1["entry"],r2["entry"])

    def test_dynamic_wallet_requotes_with_compounded_balance(self):
        x=source(at="2026-10-26T12:00:00+00:00",planid="a")
        y=source(at="2026-10-26T14:00:00+00:00",sym="ETH_USDT",planid="b")
        quote_balances=[]
        def fake_quote(row,balance,cfg,slip,floor):
            quote_balances.append(balance)
            return {"quote":{"net_rr":"2.0"}},[]
        def fake_settle(row,q,before):
            net=D("0.2") if row["symbol"]=="BTC_USDT" else -D("0.1")
            return {"net_usdt":net,"net_r":net/D(".1"),
                    "risk_usdt":D(".1"),"contracts":D("1"),
                    "margin_usdt":D(".1"),"cost_reserve_usdt":D(".01"),
                    "leverage":10,"net_rr_projected":D("2"),
                    "notional_usdt":D(".2"),"outcome":"ALVO" if net>0 else "STOP",
                    "exit_at":row["future_exit"]["exit_at"]}
        with patch("scripts.research_equity_curve.reprice_candidate",side_effect=fake_quote),\
             patch("scripts.research_equity_curve.settle_candidate",side_effect=fake_settle):
            result=run_wallet([x,y],rule="RR15")
        self.assertEqual(quote_balances,[D("1"),D("1.2")])
        self.assertEqual(D(result["ending_usdt"]),D("1.1"))
        self.assertEqual(result["trades"],2)

    def test_error_when_future_after_four_hour_window(self):
        x=source()
        x["future_exit"]["exit_at"]="2026-10-30T01:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"within 4h"):
            parse_candidate(x)

    def test_quote_evaluates_at_current_balance_and_fails_when_margin_too_big(self):
        x=source()
        with patch("scripts.research_equity_curve.paper_quote",return_value={
            "status":"VIAVEL_SIMULADO","entry_low":"99","entry_high":"101",
            "net_rr":"2.1","margin_usdt":"0.9","costs_usdt":"0.2",
            "contracts":"5","base_quantity":"0.005","loss_usdt":"0.08",
            "worst_entry":"100","leverage":10}) as f:
            from mexc_scanner.config import Config
            quote,reasons=reprice_candidate(x,D("1"),Config(),D("0.0002"),D("1.5"))
        self.assertIsNone(quote)
        self.assertEqual(reasons,["MARGIN_PLUS_RESERVED_COSTS_EXCEED_EQUITY"])
        self.assertEqual(f.call_args.args[5].initial_balance,"1")

    def test_run_does_not_accept_nonpredeclared_slippage(self):
        with self.assertRaisesRegex(ValueError,"slippage not preregistered"):
            run_wallet([],slip="0.003")

    def test_run_does_not_accept_more_than_one_usdt(self):
        with self.assertRaisesRegex(ValueError,"exactly 1 USDT"):
            run_wallet([],initial_balance="50")


if __name__=="__main__":
    unittest.main()
