"""Regression tests for retrospective breakout quality: no future-outcome gating."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import json
import csv

from mexc_scanner.models import D
from scripts.research_breakout_quality import (
    analyze_quality, gate, bucket, BUCKETS, select_portfolio, save_quality,
    GATES,
)


def candidate(symbol,plan_id,signal,entry,exit_at,rr="1.7",net="-1",
              volume="2.5",ext2h="0.5",ext4h="1.0", h1="ALTA"):
    f={
        "asof_utc":signal, "M1_volume_vs_prev20":volume,
        "M1_body_fraction_of_range":"0.5",
        "M1_close_near_side_fraction":"0.75",
        "M1_range_over_M15_ATR":"0.2",
        "signed_1h_M1_extension_ATR":"0.2",
        "signed_4h_M1_extension_ATR":ext4h,
        "signed_2h_M15_extension_ATR":ext2h,
        "H1_structure":h1,"A_late":D(ext4h)>=2,"B_against_H1":False}
    def quote(key):
        return {
            "status":"FILLED_SIMULATED", "net_rr":rr, "net_r":net,
            "net_usdt":str(D(net)/10), "entry_at":entry,"exit_at":exit_at,
            "outcome":"ALVO" if D(net)>0 else "STOP",
            "entry_fill_estimate":"100",
        }
    return {
        "symbol":symbol,"plan_id":plan_id,"side":"LONG",
        "signal_at":signal,"stop":"99","target":"103",
        "turnover24":"12000000","historical_group":"core_liquidity",
        "exante_features":f,
        "causal_context":{"A_late":f["A_late"],"B_against_h1":False,"A_or_B":f["A_late"]},
        **{k:quote(k) for k in ("wallet_1usdt","wallet_1usdt_mid","wallet_1usdt_stress")},
    }


class BreakoutQualityTests(unittest.TestCase):
    def setUp(self):
        self.rows=[
            candidate("BTC_USDT","a","2026-11-02T12:00:00+00:00",
                     "2026-11-02T12:00:00+00:00","2026-11-02T12:30:00+00:00",
                     rr="1.8",net="-1",volume="0.5"),
            candidate("ETH_USDT","b","2026-11-02T12:05:00+00:00",
                     "2026-11-02T12:05:00+00:00","2026-11-02T12:25:00+00:00",
                     rr="2.2",net="2.0",volume="3.1",ext2h="1"),
            candidate("SOL_USDT","c","2026-11-02T12:31:00+00:00",
                     "2026-11-02T12:31:00+00:00","2026-11-02T13:31:00+00:00",
                     rr="1.3",net="-1",volume="4.2",ext2h="3"),
        ]

    def test_all_viable_deduplicates_before_analysis(self):
        duplicate=deepcopy(self.rows[0])
        duplicate["plan_id"]="z"
        duplicate["wallet_1usdt"]["net_r"]="100"
        d,ledger=analyze_quality([duplicate,*self.rows],"WK1")
        main=d["scenario_result"]["wallet_1usdt"]
        self.assertEqual(main["raw_filled_plans"],4)
        self.assertEqual(main["unique_viable_events"],3)
        self.assertEqual(main["duplicate_viable_plan_records"],1)
        self.assertEqual(len(ledger),3)
        first=next(x for x in ledger if x["symbol"]=="BTC_USDT")
        self.assertEqual(first["plan_id"],"a")
        self.assertEqual(first["net_R"],"-1")

    def test_same_slot_reallocated_only_to_causally_eligible_candidate(self):
        q,ledger=analyze_quality(self.rows,"WK1")
        options=q["scenario_result"]["wallet_1usdt"]["one_slot"]
        self.assertEqual(options["BASE"]["trades"],2)
        self.assertEqual(D(options["BASE"]["net_r_sum"]),D("-2"))
        self.assertEqual(options["RR15"]["trades"],1)
        self.assertEqual(D(options["RR15"]["net_r_sum"]),D("-1"))
        self.assertEqual(options["RR15_VOL2"]["trades"],1)
        self.assertEqual(D(options["RR15_VOL2"]["net_r_sum"]),D("2"))
        self.assertEqual(options["RR15_VOL2"]["removed_BASE_nonwinners"],2)
        self.assertEqual(options["RR15_VOL2"]["new_from_reallocation"],1)
        eth=next(x for x in ledger if x["symbol"]=="ETH_USDT")
        self.assertTrue(eth["selected_RR15_VOL2"])
        self.assertFalse(eth["selected_BASE"])

    def test_inverting_returns_does_not_change_candidate_selection_or_dedupe(self):
        prior,rows=analyze_quality(self.rows,"WK1")
        corrupted=deepcopy(self.rows)
        for row in corrupted:
            row["wallet_1usdt"]["net_r"]="999"
            row["wallet_1usdt"]["outcome"]="ALVO"
        other,ledger=analyze_quality(corrupted,"WK1")
        self.assertEqual(
            [(x["symbol"],x["selected_RR15_VOL2"]) for x in rows],
            [(x["symbol"],x["selected_RR15_VOL2"]) for x in ledger],
        )
        self.assertNotEqual(prior["scenario_result"]["wallet_1usdt"]["one_slot"]["BASE"]["net_r_sum"],
                            other["scenario_result"]["wallet_1usdt"]["one_slot"]["BASE"]["net_r_sum"])

    def test_closed_candle_asof_must_match_confirmation(self):
        wrong=deepcopy(self.rows)
        wrong[0]["exante_features"]["asof_utc"]="2026-11-02T13:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"causal feature stamp"):
            analyze_quality(wrong,"WK1")

    def test_missing_feature_cannot_be_passed_as_good(self):
        wrong=deepcopy(self.rows[1])
        wrong["exante_features"]["M1_volume_vs_prev20"]=None
        self.assertFalse(gate(wrong,"wallet_1usdt","RR15_VOL2"))
        wrong["exante_features"]["signed_2h_M15_extension_ATR"]=None
        self.assertFalse(gate(wrong,"wallet_1usdt","RR15_EXT2H"))

    def test_only_frozen_rules_accepted(self):
        with self.assertRaisesRegex(ValueError,"Unknown"):
            gate(self.rows[0],"wallet_1usdt","OPTIMIZED_FROM_OUTCOME")

    def test_volume_bucket_boundaries_are_exclusive(self):
        g=BUCKETS["M1_volume_vs_prev20"]
        self.assertEqual(bucket("0.999999",g),"below_1x")
        self.assertEqual(bucket("1",g),"1_to_2x")
        self.assertEqual(bucket("2",g),"2_to_4x")
        self.assertEqual(bucket("4",g),"at_least_4x")
        self.assertEqual(bucket(None,g),"UNKNOWN")

    def test_missing_cost_case_fails_without_silently_dropping_events(self):
        broken=deepcopy(self.rows)
        broken[0].pop("wallet_1usdt_mid")
        with self.assertRaisesRegex(ValueError,"missing frozen"):
            analyze_quality(broken,"WK1")

    def test_all_unfiltered_valid_events_can_overlap_and_are_labeled(self):
        q,rows=analyze_quality(self.rows,"WK1")
        one=q["scenario_result"]["wallet_1usdt"]
        self.assertEqual(one["all_unique_viable_events_including_overlaps"]["counts"]["n"],3)
        self.assertEqual(one["one_slot"]["BASE"]["trades"],2)
        self.assertIn("NOT independent", " ".join(q["limits"]))

    def test_csv_and_json_are_deterministic_and_sanitized(self):
        d,rows=analyze_quality(self.rows,"WK1")
        with tempfile.TemporaryDirectory() as temp:
            save_quality(d,rows,Path(temp))
            j=json.loads((Path(temp)/"breakout_quality_summary.json").read_text())
            with (Path(temp)/"one_usdt_viable_unique_events.csv").open(encoding="utf-8-sig") as f:
                table=list(csv.DictReader(f))
            self.assertEqual(len(table),3)
            self.assertEqual(j["window_start"],"WK1")
            self.assertEqual(set(GATES),set(j["predeclared_rules"]))
            self.assertNotIn("account", str(j).lower())
            self.assertNotIn("api_key", str(j).lower())

if __name__ == "__main__":
    unittest.main()
