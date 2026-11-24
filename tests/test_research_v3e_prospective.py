import unittest
from scripts.research_v3e_prospective import load_model,score,frequency,require_closed,START,END,TAIL

class ProspectiveTests(unittest.TestCase):
    def test_hash_and_score(self):
        m=load_model()
        for side in ("LONG","SHORT"):
            p=m["models"][side]
            actual=score(p["mean"],100,side,m)
            from scripts.research_amplitude_240 import predicted_net
            expected=predicted_net(p["intercept"],100,side)
            self.assertEqual(actual,expected)
    def test_time_guard(self):
        with self.assertRaises(ValueError):
            require_closed(END+TAIL)
        require_closed(END+TAIL+10)
    def test_frequency_zeros_and_partial_dates(self):
        r=[{"t":START+10800},{"t":START+11100}]
        f=frequency(r,r)
        self.assertEqual(f["complete_days"],13)
        self.assertEqual(f["two_or_more"],1)
        self.assertEqual(f["zero"],12)
        self.assertFalse(f["target_met_every_complete_day"])
    def test_duplicate_candidates_count_slots(self):
        r=[{"t":START+10800},{"t":START+10800}]
        f=frequency(r,r[:1])
        day=next(d for d in f["daily"] if d["eligible_directional"])
        self.assertEqual(day["eligible_directional"],2)
        self.assertEqual(day["eligible_decision_slots"],1)
