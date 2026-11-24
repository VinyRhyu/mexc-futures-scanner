import unittest
from scripts.research_amplitude_frequency import local_day,select_daily

class FrequencyTests(unittest.TestCase):
    def test_sao_paulo_midnight(self):
        self.assertEqual(local_day(0),"1969-12-31")
        self.assertEqual(local_day(10800),"1970-01-01")
    def test_cap_no_future_rank(self):
        sample=[{"t":t,"rank":rank,"symbol":"X","side":"LONG","label":{"exit_ts":t+60}}
                for t,rank in [(10800,.1),(11100,.2),(11400,99),(97200,.1)]]
        self.assertEqual([r["t"] for r in select_daily(sample,2)],[10800,11100,97200])
    def test_no_overlap(self):
        a={"t":10800,"rank":.1,"symbol":"X","side":"LONG","label":{"exit_ts":11200}}
        b={**a,"t":11100,"rank":.9}
        self.assertEqual(select_daily([a,b],2),[a])
