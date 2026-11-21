"""Guards for cross-period WATCH research without future-based signal decisions."""
import unittest
from scripts.audit_hype_watch_crossperiod import PERIODS, hit_delay, date_ms
from scripts.audit_hype_two_stage_1617 import confirmation, score_direction
from scripts.audit_confluence_v3 import FIVE_MS


class CrossPeriodWatchTests(unittest.TestCase):
    def test_windows_disjoint_and_prior_to_nov16(self):
        times=[(date_ms(a),date_ms(b)) for a,b in PERIODS.values()]
        self.assertEqual(len(times),4)
        self.assertTrue(all(a<b for a,b in times))
        self.assertTrue(all(b<=c for (_,b),(c,_) in zip(times,times[1:])))
        self.assertEqual(times[-1][1],date_ms("2026-11-16T03:00:00+00:00"))

    def test_hit_delay_favorable_then_bad(self):
        m=[[i*FIVE_MS,100,100.1,99.9,100,1,100] for i in range(100)]
        i=50
        m[i+1][2]=101.3
        self.assertEqual(hit_delay(m,i,"LONG"),5)
        self.assertTrue(score_direction(m,i,"LONG"))
        m[i+1][3]=99.0
        self.assertIsNone(hit_delay(m,i,"LONG"))
        self.assertFalse(score_direction(m,i,"LONG"))

    def test_confirmation_custom_cutoff_cannot_use_future(self):
        m=[[i*FIVE_MS,100,100.1,99.9,100,1,100] for i in range(90)]
        i=45
        m[i+1]=[(i+1)*FIVE_MS,100,101,99.9,100.8,1,300]
        watch={"i":i,"side":"LONG","at_ms":m[i][0]+FIVE_MS,"family":"BREAK"}
        self.assertIsNone(confirmation(m,watch,cutoff_ms=m[i+1][0]+FIVE_MS))
        # A confirmation is allowed only if its close < cutoff,
        # with next-bar entry time also inside cutoff on M5 grid.
        self.assertIsNotNone(confirmation(m,watch,cutoff_ms=m[i+2][0]+FIVE_MS))


if __name__=="__main__":
    unittest.main()
