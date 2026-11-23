"""Offline coverage tests for expanded top-50 research. No network or orders."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import unittest
from http.client import IncompleteRead
from unittest.mock import patch
from mexc_scanner.mexc import MexcClient

from mexc_scanner.config import Config
from scripts.research_production_universe import (
    freeze_snapshot,validate_frozen,dedupe_viable_by_event,paired_cost_stress,ResearchMexcClient,
)


def synthetic_universe(n=43):
    contracts=[]
    tickers=[]
    assets=set()
    for i in range(n):
        name=f"X{i:02d}"
        symbol=f"{name}_USDT"
        assets.add(name)
        contracts.append({
            "symbol":symbol,"baseCoin":name,"state":0,"quoteCoin":"USDT",
            "settleCoin":"USDT","futureType":1,"preMarket":False,"typeLabel":0})
        tickers.append({"symbol":symbol,"amount24":str(5000000+(n-i)*500000)})
    return contracts,tickers,assets


def plan(symbol,plan_id,t="2026-11-10T11:00:00+00:00",profit="-1"):
    return {"symbol":symbol,"side":"LONG","signal_at":t,"plan_id":plan_id,
            "cost_base":{"status":"FILLED_SIMULATED","net_r":profit,
                         "entry_at":t,"exit_at":"2026-11-10T11:40:00+00:00"},
            "cost_stress":{"status":"FILLED_SIMULATED","net_r":str(Decimal(profit)-Decimal("0.3"))}}


class ExpandedUniverseTests(unittest.TestCase):
    def test_snapshot_uses_production_eligibility_and_freezes_order(self):
        contracts,tickers,assets=synthetic_universe()
        result=freeze_snapshot(contracts,tickers,assets,Config(),1795410000)
        names=validate_frozen(result)
        self.assertEqual(len(names),43)
        self.assertEqual(names[0],"X00_USDT")
        self.assertEqual(names[-1],"X42_USDT")
        self.assertEqual(result["symbols"][0]["rank_now"],1)
        self.assertIn("survivorship",result["critical_bias"])
        self.assertTrue(result["sha256_ordered_symbols"])

    def test_invalid_or_tampered_snapshot_rejected(self):
        c,t,a=synthetic_universe()
        snap=freeze_snapshot(c,t,a,Config(),1795410000)
        bad=deepcopy(snap)
        bad["symbols"][0]["symbol"]="BTC_USDT"
        with self.assertRaisesRegex(ValueError,"fingerprint"):
            validate_frozen(bad)
        bad=deepcopy(snap)
        bad["symbols"][1]["symbol"]=bad["symbols"][0]["symbol"]
        with self.assertRaisesRegex(ValueError,"duplicate"):
            validate_frozen(bad)

    def test_insufficient_universe_not_misreported_as_complete(self):
        c,t,a=synthetic_universe(19)
        with self.assertRaisesRegex(ValueError,"too few"):
            freeze_snapshot(c,t,a,Config(),1795410000)

    def test_dedupe_does_not_select_winner_after_the_fact(self):
        x=plan("ABC_USDT","a","2026-11-10T11:00:00+00:00","-1")
        y=plan("ABC_USDT","z","2026-11-10T11:00:00+00:00","1.5")
        z=plan("DEF_USDT","q")
        picks,duplicates=dedupe_viable_by_event([y,z,x])
        self.assertEqual(duplicates,1)
        got=next(r for r in picks if r["symbol"]=="ABC_USDT")
        self.assertEqual(got["plan_id"],"a")
        self.assertEqual(got["cost_base"]["net_r"],"-1")

    def test_research_get_retries_partial_stream_exactly_not_historical_data(self):
        path="/api/v1/contract/kline/BTC_USDT"
        with patch.object(MexcClient,"_get",side_effect=[
                  IncompleteRead(b"partial"),{"time":[1]}]) as stub, \
             patch("scripts.research_production_universe.time.sleep") as sleeper:
            result=ResearchMexcClient()._get(path,{"interval":"Min1"})
        self.assertEqual(result,{"time":[1]})
        self.assertEqual(stub.call_count,2)
        sleeper.assert_called_once()

    def test_research_get_fails_closed_after_three_corrupt_responses(self):
        with patch.object(MexcClient,"_get",side_effect=IncompleteRead(b"incomplete")) as stub, \
             patch("scripts.research_production_universe.time.sleep") as sleeper:
            with self.assertRaises(IncompleteRead):
                ResearchMexcClient()._get("/api/v1/contract/kline/BTC_USDT")
        self.assertEqual(stub.call_count,3)
        self.assertEqual(sleeper.call_count,2)

    def test_research_get_never_retries_a_candle_validation_error(self):
        with patch.object(MexcClient,"_get",side_effect=ValueError("incomplete Min1")) as stub, \
             patch("scripts.research_production_universe.time.sleep") as sleeper:
            with self.assertRaisesRegex(ValueError,"incomplete Min1"):
                ResearchMexcClient()._get("/api/v1/contract/kline/BTC_USDT")
        self.assertEqual(stub.call_count,1)
        sleeper.assert_not_called()

    def test_cost_stress_compares_exact_same_baseline_ids(self):
        a=plan("ABC_USDT","a","2026-11-10T11:00:00+00:00","2")
        b=plan("DEF_USDT","b","2026-11-10T11:42:00+00:00","-1")
        b["cost_stress"]={"status":"FINANCIAL_BLOCK"}
        result=paired_cost_stress([a,b])
        self.assertEqual(result["baseline_selected"],2)
        self.assertEqual(result["stress_still_filled"],1)
        self.assertEqual(result["stress_unfilled"],1)
        self.assertEqual(Decimal(result["paired_baseline_net_r"]),Decimal("2"))
        self.assertEqual(Decimal(result["paired_stress_net_r"]),Decimal("1.7"))


if __name__=="__main__":
    unittest.main()
