"""Causal separation tests for HYPE two-day WATCH and CONFIRM study."""
import copy
import unittest

from scripts.audit_confluence_v3 import FIVE_MS
from scripts.audit_hype_three_regimes import ema
from scripts.audit_hype_two_stage_1617 import (
    watch_at, score_direction, confirmation, execute, START, END, DATA_END,
)


class HypeTwoStageTests(unittest.TestCase):
    def setUp(self):
        self.m=[[i*FIVE_MS,100.0,100.1,99.9,100.0,1.0,100.0]
                for i in range(105)]
        self.i=45

    def ind(self,m=None):
        m=m if m is not None else self.m
        c=[float(x[4]) for x in m]
        return {"ema9":ema(c,9),"ema21":ema(c,21)}

    def test_causal_watch_does_not_use_future(self):
        self.m[self.i]=[self.i*FIVE_MS,100,101,99.95,100.8,1,200]
        a=watch_at(self.m,self.i,self.ind())
        self.assertTrue(any(w["family"]=="BREAK" and w["side"]=="LONG" for w in a))
        after=copy.deepcopy(self.m)
        for b in after[self.i+1:]:
            b[1],b[2],b[3],b[4],b[6]=200,250,150,220,9999
        self.assertEqual(a,watch_at(after,self.i,self.ind(after)))
        part=self.m[:self.i+1]
        self.assertEqual(a,watch_at(part,self.i,self.ind(part)))

    def test_label_uses_future_only_for_scoring(self):
        i=self.i
        self.m[i+1]=[(i+1)*FIVE_MS,100,101.30,100,100.8,1,100]
        self.assertTrue(score_direction(self.m,i,"LONG"))
        self.m[i+1][3]=99.1
        self.assertFalse(score_direction(self.m,i,"LONG"))
        self.assertTrue(score_direction(self.m,i,"SHORT") is False)

    def test_confirmation_starts_after_watch(self):
        w={"i":self.i,"side":"LONG","at_ms":self.m[self.i][0]+FIVE_MS,
           "family":"BREAK"}
        self.m[self.i]=[self.i*FIVE_MS,100,102,99.9,101.5,1,200]
        # At i+1, close above prior 6-bar high and passes volume/body.
        self.m[self.i+1]=[(self.i+1)*FIVE_MS,101.5,103,101.4,102.6,1,220]
        # The watch candle cannot confirm itself, only the following close.
        confirmed=confirmation(self.m,w)
        self.assertIsNotNone(confirmed)
        self.assertEqual(confirmed["signal_index"],self.i+1)
        self.assertGreater(confirmed["confirmation_ms"],w["at_ms"])

    def test_conservative_ambiguous_touch_is_stop(self):
        i=self.i
        self.m[i+1]=[(i+1)*FIVE_MS,100,103,98,100,1,100]
        setup={"signal_index":i,"signal_at":"2026-11-16T10:00:00+00:00",
               "side":"LONG","stop_raw":98.5,"relative_quote_volume":2.,
               "watch_ms":self.m[i][0],"family":"BREAK"}
        t=execute(self.m,setup)
        self.assertIsNotNone(t)
        self.assertEqual(t["result"],"AMBIGUOUS_AS_SL")
        self.assertEqual(t["net_r"],-1)

    def test_study_has_strict_two_day_entry_boundary(self):
        self.assertEqual((END-START)//(24*60*60*1000),2)
        self.assertEqual((DATA_END-END)//(60*60*1000),2)


if __name__=="__main__":
    unittest.main()
