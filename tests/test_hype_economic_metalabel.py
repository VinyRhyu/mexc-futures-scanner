"""Regression guards for economic meta-labeling on eligible HYPE trades."""
import copy
import unittest
from scripts.audit_confluence_v3 import FIVE_MS, HOUR_MS, iso
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_economic_metalabel import (
    FEATURES, features_at_confirmation, result, PURGE_MS, EVAL,
    BASELINE_GUARD,
)


class HypeEconomicMetaLabelTests(unittest.TestCase):
    def setUp(self):
        self.m=[[i*FIVE_MS,100.,100.25,99.75,100.,1.,100.]
                for i in range(750)]
        self.h=[[(i-30)*HOUR_MS,100.+i*.02,
                 101.+i*.02,99.+i*.02,100.+i*.02,1.,100.]
                for i in range(130)]
        self.i=600
        self.m[self.i][1]=99.9
        self.m[self.i][4]=100.3
        self.m[self.i][2]=100.5
        self.w={"at_ms":(self.i-2)*FIVE_MS,"family":"BREAK","side":"LONG"}
        self.c={"signal_index":self.i,"signal_at":iso((self.i+1)*FIVE_MS),
                "side":"LONG","stop_raw":99.0,"relative_quote_volume":1.35}

    def ctx(self,m,h):
        return {
            "m9":ema([float(x[4]) for x in m],9),
            "m21":ema([float(x[4]) for x in m],21),
            "h20":ema([float(x[4]) for x in h],20),
            "he":[int(x[0])+HOUR_MS for x in h],
        }

    def test_features_only_use_closed_m5_and_h1(self):
        old=features_at_confirmation(self.m,self.h,self.ctx(self.m,self.h),self.c,self.w)
        self.assertEqual(len(old),len(FEATURES))
        alt=copy.deepcopy(self.m)
        for bar in alt[self.i+1:]:
            bar[1],bar[2],bar[3],bar[4],bar[6]=200.,300.,1.,250.,99999.
        self.assertEqual(old,features_at_confirmation(
            alt,self.h,self.ctx(alt,self.h),self.c,self.w))
        self.assertEqual(old,features_at_confirmation(
            self.m[:self.i+1],self.h,self.ctx(self.m[:self.i+1],self.h),
            self.c,self.w))
        self.assertEqual(old,features_at_confirmation(
            self.m,self.h[:80],self.ctx(self.m,self.h[:80]),self.c,self.w))

    def test_only_timestamp_matched_signal(self):
        c={**self.c,"signal_at":iso((self.i+2)*FIVE_MS)}
        with self.assertRaises(AssertionError):
            features_at_confirmation(self.m,self.h,self.ctx(self.m,self.h),c,self.w)

    def test_stop_distance_is_as_of_confirm_not_fill(self):
        old=features_at_confirmation(self.m,self.h,self.ctx(self.m,self.h),self.c,self.w)
        different=copy.deepcopy(self.m)
        different[self.i+1][1]=120
        self.assertEqual(old,features_at_confirmation(
            different,self.h,self.ctx(different,self.h),self.c,self.w))
        c={**self.c,"stop_raw":99.5}
        self.assertNotEqual(old,features_at_confirmation(
            self.m,self.h,self.ctx(self.m,self.h),c,self.w))

    def test_positive_net_r_time_counts_as_positive(self):
        rows=[{"at_ms":1,"family":"BREAK","side":"LONG",
               "label":1,"net_r":0.2,
               "trade":{"symbol":"HYPE_USDT","side":"LONG",
                        "signal_at":"2026-01-01T00:00:00+00:00",
                        "exit_at":"2026-01-01T00:05:00+00:00",
                        "result":"TIME","net_r":0.2,
                        "relative_quote_volume":1.2}}]
        z=result(rows)
        self.assertEqual(z["economic_label_positive_events"],1)
        self.assertEqual(z["portfolio"]["TIME"],1)
        self.assertEqual(z["portfolio"]["TP"],0)
        self.assertGreater(z["portfolio"]["roi_pct"],0)

    def test_preregistered_folds_and_purge(self):
        self.assertEqual(EVAL,("U","V","W0"))
        self.assertEqual(PURGE_MS,120*60*1000)
        self.assertEqual(BASELINE_GUARD["U"]["selected"],311)


if __name__=="__main__":
    unittest.main()
