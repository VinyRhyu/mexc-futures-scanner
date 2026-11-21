"""No-lookahead, fee gate, window and M1 trend guard tests."""
import copy
import unittest
from scripts.audit_confluence_v3 import FIVE_MS,HOUR_MS
from scripts.audit_hype_m1_trend import (
  ONE_MS,PERIODS,atr_m1_pre,contexts,candidate_minute,
  first_confirmation_m1,execute_m1,REF_REGRESSION,watches,
)
from scripts.audit_hype_two_stage_1617 import watch_at


class M1TrendTest(unittest.TestCase):
    def setUp(self):
        self.m1=[[i*ONE_MS,100,100.05,99.95,100,1,100]
                 for i in range(90)]
        self.m5=[[i*FIVE_MS,100,100.05,99.95,100,1,100]
                 for i in range(70)]
        self.h=[[(i-80)*HOUR_MS,100,101,99,100,1,100]
                 for i in range(80)]
        self.i=45
        self.m1[self.i]=[self.i*ONE_MS,100,100.9,99.99,100.8,1,250]

    def test_windows_do_not_overlap(self):
        def ms(s):
            from datetime import datetime
            return datetime.fromisoformat(s).timestamp()
        intervals=sorted((ms(a),ms(b)) for a,b in PERIODS.values())
        self.assertTrue(all(a<b for a,b in intervals))
        self.assertTrue(all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])))
        self.assertEqual(REF_REGRESSION["watch_count"],73)

    def test_causal_fast_signal(self):
        # M1 EMA9 slope from breakout candle should support LONG.
        state=contexts(self.m1,self.m5,self.h)
        s=candidate_minute(self.m1,self.m5,self.h,self.i,"LONG","M1_FAST",state)
        self.assertIsNotNone(s)
        other=copy.deepcopy(self.m1)
        for b in other[self.i+1:]:
            b[1],b[2],b[3],b[4],b[6]=500,600,1,550,999999
        self.assertEqual(s,candidate_minute(other,self.m5,self.h,self.i,
                                            "LONG","M1_FAST",
                                            contexts(other,self.m5,self.h)))
        self.assertEqual(s,candidate_minute(self.m1[:self.i+1],self.m5,self.h,self.i,
                                            "LONG","M1_FAST",
                                            contexts(self.m1[:self.i+1],self.m5,self.h)))

    def test_same_candle_stop_take_conservative(self):
        self.m1[self.i+1]=[(self.i+1)*ONE_MS,100,102,98,100,1,100]
        setup={"signal_index":self.i,"signal_at":"2026-11-16T10:00:00+00:00",
               "side":"LONG","stop_raw":98.9,"relative_quote_volume":2,
               "watch_ms":self.i*ONE_MS,"watch_family":"BREAK","arm":"M1_FAST"}
        more=self.m1+[[i*ONE_MS,100,100.05,99.95,100,1,100] for i in range(90,200)]
        t=execute_m1(more,setup)
        self.assertEqual(t["result"],"AMBIGUOUS_AS_SL")
        self.assertEqual(t["net_r"],-1.0)

    def test_gate_uses_completed_m5_only(self):
        state=contexts(self.m1,self.m5,self.h)
        orig=candidate_minute(self.m1,self.m5,self.h,self.i,"LONG","M1_M5_TREND",state)
        fut=copy.deepcopy(self.m5)
        for b in fut[10:]:
            b[1],b[2],b[3],b[4]=500,600,1,550
        # The large future M5 changes must never enter the decision.
        changed=candidate_minute(self.m1,fut,self.h,self.i,"LONG","M1_M5_TREND",
                                 contexts(self.m1,fut,self.h))
        self.assertEqual(orig,changed)

    def test_imported_frozen_watch(self):
        self.assertIs(watches.__globals__["watch_at"],watch_at)


if __name__=="__main__":
    unittest.main()
