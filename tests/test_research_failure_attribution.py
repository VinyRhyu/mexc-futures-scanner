import unittest
from scripts.research_failure_attribution import summarize,slot_diagnostic,rank_diagnostic,bins

def row(rank=1,gross=3,stress=2.4,symbol="A"):
    return {"t":10800,"symbol":symbol,"side":"LONG","rank":rank,"audit_pred":rank,
            "gross":gross,"y":[gross-.2,gross-.3],"funding":.1,"tier_net":stress,
            "label":{"entry_ts":10860,"exit_ts":10920,"outcome":"TP"}}
class AttributionTests(unittest.TestCase):
    def test_cost_identity(self):
        q=summarize([row()])
        self.assertAlmostEqual(q["gross_r"]-q["tier_friction_r"]-q["funding_r"],q["net_stress_r"])
    def test_slot(self):
        q=slot_diagnostic([row(),row(.5,-1,-1.5,"B")])
        self.assertEqual(q["multi_candidate_slots"],1)
        self.assertEqual(q["top_mean"],2.4)
        self.assertAlmostEqual(q["slot_average_mean"],.45)
    def test_bins(self):
        self.assertEqual(sum(b["n"] for b in bins([row()])),1)
    def test_rank_reproducible(self):
        r=[row(),row(.5,-1,-1.5,"B")]
        self.assertEqual(rank_diagnostic(r),rank_diagnostic(r))
