"""Causal behavior and execution guards for pre-registered structural pilot."""
import copy
import unittest
from scripts.audit_confluence_v3 import candidate_f, candidate_g, execute


class StructuralPilotTests(unittest.TestCase):
    def setUp(self):
        self.hours = [
            [(i-160)*3_600_000, 240-.5*i, 241-.5*i, 239-.5*i, 240-.5*i,
             1000, 100000] for i in range(160)
        ]
        self.five = [[i*300_000, 100.0, 100.3, 99.7, 100.0, 10, 100]
                     for i in range(70)]

    def test_false_breakout_only_uses_closed_bars(self):
        i=35
        self.five[i] = [i*300_000,100.4,101.0,99.95,100.0,20,300]
        expected = candidate_f(self.five,self.hours,i)
        self.assertIsNotNone(expected)
        self.assertEqual(expected["signal_ms"], self.five[i][0]+300_000)
        changed=copy.deepcopy(self.five)
        for x in changed[i+1:]:
            x[1],x[2],x[3],x[4],x[6]=999,999,999,999,9999
        self.assertEqual(expected,candidate_f(changed,self.hours,i))
        self.assertEqual(expected,candidate_f(self.five[:i+1],self.hours,i))

    def test_retest_is_announced_only_after_rejection(self):
        i=35
        self.five[i] = [i*300_000,100,100,98.7,98.8,20,260]
        self.five[i+1] = [(i+1)*300_000,99.7,99.85,99.2,99.5,10,90]
        # The break is visible now, but the retest is NOT.
        self.assertIsNone(candidate_g(self.five,self.hours,i,through_index=i))
        expected=candidate_g(self.five,self.hours,i,through_index=i+1)
        self.assertIsNotNone(expected)
        self.assertEqual(expected["signal_index"],i+1)
        changed=copy.deepcopy(self.five)
        for x in changed[i+2:]:
            x[1],x[2],x[3],x[4],x[6]=500,500,500,500,9999
        self.assertEqual(expected,candidate_g(changed,self.hours,i))
        self.assertEqual(expected,candidate_g(self.five[:i+2],self.hours,i))

    def test_same_candle_sl_tp_is_not_a_win(self):
        i=35
        self.five[i] = [i*300_000,100.4,101.0,99.95,100.0,20,300]
        setup=candidate_f(self.five,self.hours,i)
        self.assertIsNotNone(setup)
        self.five[i+1] = [(i+1)*300_000,100,102,97,100,200,10000]
        result=execute(self.five,setup)
        self.assertIsNotNone(result)
        self.assertEqual(result["result"],"AMBIGUOUS")
        self.assertIsNone(result["net_r"])

    def test_no_open_hourly_information(self):
        i=35
        self.five[i] = [i*300_000,100.4,101.0,99.95,100.0,20,300]
        normal=candidate_f(self.five,self.hours,i)
        modified=copy.deepcopy(self.hours)
        modified.append([3*3_600_000,1,1,1,10000000,1,1])
        self.assertEqual(normal,candidate_f(self.five,modified,i))


if __name__=="__main__":
    unittest.main()
