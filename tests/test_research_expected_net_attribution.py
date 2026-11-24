import unittest
from scripts.research_expected_net_attribution import enrich,summarize

class AttributionTests(unittest.TestCase):
    def test_exact_cost_identity(self):
        trade={"t":"0","exit_ts":"300","net_r_base_cost":"1.4192","net_r_adverse_cost":"1.3788"}
        label={"entry":"100","exit":"102","gross_r":"1.5","entry_ts":"60","exit_ts":"300","outcome":"TP"}
        result=enrich(trade,label,{"atr15":"2"})
        self.assertAlmostEqual(result["turnover_r"],50.5)
        s=summarize([result])
        self.assertAlmostEqual(s["gross_r"],1.5)
        self.assertAlmostEqual(s["base_cost_r"],.0808)
        self.assertAlmostEqual(s["break_even_cost_pct"],100*1.5/50.5)
    def test_reject_bad_cost(self):
        trade={"t":"0","exit_ts":"300","net_r_base_cost":"9","net_r_adverse_cost":"9"}
        label={"entry":"100","exit":"102","gross_r":"1.5","entry_ts":"60","exit_ts":"300","outcome":"TP"}
        with self.assertRaises(ValueError):
            enrich(trade,label,{"atr15":"2"})
    def test_empty(self):
        self.assertIsNone(summarize([])["break_even_cost_pct"])
