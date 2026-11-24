import unittest
from scripts.research_universe_transfer import stress_cost,frequency,evaluate
class TransferTests(unittest.TestCase):
    def test_cost_bands(self):
        self.assertEqual(stress_cost(None),.0024)
        self.assertEqual(stress_cost("5m_plus"),.0024)
        self.assertEqual(stress_cost("2.5m_to_5m"),.0035)
        self.assertEqual(stress_cost("1m_to_2.5m"),.005)
    def test_frequency_empty_days(self):
        ts=list(range(10800,10800+86400,300))
        q=frequency([],[],ts)
        self.assertEqual(q["full_days"],1)
        self.assertEqual(q["days_zero"],1)
    def test_stress_does_not_change_entries(self):
        t=10800
        r={"t":t,"symbol":"X","side":"LONG","rank":1,"label":{"exit_ts":t+60,"outcome":"TP","gross_r":"3"},"y":[2.8,2.7],"funding":.1,"tier_net":2.4}
        q=evaluate([r],list(range(t,t+86400,300)),3)
        self.assertEqual(q["finance"]["trades"],1)
        self.assertAlmostEqual(q["common_adverse_funding"]["total_net_r"],2.6)
        self.assertAlmostEqual(q["tier_adverse_funding"]["total_net_r"],2.4)
