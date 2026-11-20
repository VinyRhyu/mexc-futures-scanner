"""Regression guards for frozen HYPE temporal transfer and watch timing."""
import unittest
from scripts.audit_confluence_v3 import FIVE_MS
from scripts.audit_hype_watch_transfer import (
    PERIODS, at_ms, check_regression, first_target_minutes, REGRESSION,
)
from scripts import audit_hype_two_stage_1617 as original
from scripts.audit_hype_watch_transfer import watch_at, score_direction, confirmation, execute


class WatchTransferTests(unittest.TestCase):
    def test_ref_no_overlap_other_windows(self):
        pair=[(at_ms(start),at_ms(end)) for name,(start,end) in PERIODS.items()
              if name!="REF"]
        self.assertEqual(len(pair),4)
        self.assertTrue(all((end-start)//(60*60*1000)==168 for start,end in pair))
        self.assertTrue(all(e==n for (_,e),(n,_) in zip(pair,pair[1:])))
        ref_start=at_ms(PERIODS["REF"][0])
        self.assertLessEqual(pair[-1][1],ref_start)

    def test_reuses_exact_original_functions(self):
        self.assertIs(watch_at,original.watch_at)
        self.assertIs(score_direction,original.score_direction)
        self.assertIs(confirmation,original.confirmation)
        self.assertIs(execute,original.execute)

    def test_direction_label_target_delay(self):
        rows=[[i*FIVE_MS,100,100.1,99.9,100,1,100] for i in range(25)]
        rows[1][2]=102.0
        self.assertTrue(score_direction(rows,0,"LONG"))
        self.assertEqual(first_target_minutes(rows,0,"LONG"),5)
        rows[1][3]=99.0
        self.assertFalse(score_direction(rows,0,"LONG"))
        self.assertIsNone(first_target_minutes(rows,0,"LONG"))

    def test_reference_guard_detects_mismatch(self):
        r={"union":{"n":73,"positive":18},"eligible_total":32,
           "portfolio":{"n":17,"outcomes":{"TP":1,"SL":6,"TIME":10},
                        "net_R_sum":-3.202,"return_pct_at_1pct_risk":-3.204}}
        self.assertEqual(check_regression(r),REGRESSION)
        r["union"]["n"]=74
        with self.assertRaises(AssertionError):
            check_regression(r)


if __name__=="__main__":
    unittest.main()
