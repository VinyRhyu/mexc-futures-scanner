"""One-bar M5 confirmation tests: causal, frozen levels and cancellation."""
import copy
import unittest
from scripts.audit_confluence_v3 import candidate_f
from scripts.audit_confluence_v4 import confirmation_at, replay_confirm


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.hours=[
            [(i-160)*3_600_000,240-.5*i,241-.5*i,
             239-.5*i,240-.5*i,1000,100000] for i in range(160)]
        self.five=[
            [i*300_000,100.0,100.3,99.7,100.0,10,100] for i in range(90)]
        self.sweep=35
        self.five[35]=[35*300_000,100.4,101.0,99.95,100.0,20,300]
        self.five[36]=[36*300_000,100.0,100.5,99.1,99.3,20,120]

    def test_only_next_closed_m5_confirms(self):
        self.assertIsNotNone(candidate_f(self.five,self.hours,35))
        self.assertIsNone(confirmation_at(self.five,self.hours,35))
        self.assertIsNone(confirmation_at(self.five[:36],self.hours,36))
        res=confirmation_at(self.five,self.hours,36)
        self.assertIsNotNone(res)
        self.assertEqual(res["signal_index"],36)
        self.assertEqual(res["signal_ms"],self.five[36][0]+300_000)

    def test_never_changes_original_stop(self):
        old=candidate_f(self.five,self.hours,35)
        accepted=confirmation_at(self.five,self.hours,36)
        self.assertAlmostEqual(old["stop_raw"],accepted["stop_raw"])

    def test_future_does_not_change_signal(self):
        orig=confirmation_at(self.five,self.hours,36)
        mod=copy.deepcopy(self.five)
        for c in mod[37:]:
            c[1],c[2],c[3],c[4],c[6] = 10000,11000,9000,10000,99999
        self.assertEqual(orig,confirmation_at(mod,self.hours,36))
        self.assertEqual(orig,confirmation_at(self.five[:37],self.hours,36))

    def test_cancel_if_next_candle_reaches_stop(self):
        orig=candidate_f(self.five,self.hours,35)
        self.five[36][2]=orig["stop_raw"]+0.01
        self.assertIsNone(confirmation_at(self.five,self.hours,36))

    def test_cancel_without_lower_low_close(self):
        self.five[36][4]=99.96
        self.assertIsNone(confirmation_at(self.five,self.hours,36))

    def test_cancel_without_bearish_confirmation(self):
        self.five[36][1]=99.2
        self.assertIsNone(confirmation_at(self.five,self.hours,36))

    def test_replay_entry_is_after_confirmation(self):
        result=replay_confirm(self.five,self.hours)
        t=[x for x in result["trades"] if x["signal_at"].endswith("03:05:00+00:00")]
        self.assertEqual(len(t),1)
        self.assertTrue(t[0]["entry_at"].endswith("03:05:00+00:00"))
        self.assertEqual(t[0]["result"],"TIME")


if __name__=="__main__":
    unittest.main()
