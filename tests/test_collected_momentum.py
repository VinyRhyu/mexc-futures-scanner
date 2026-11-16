from copy import deepcopy
import unittest

from mexc_scanner.models import D
from scripts.audit_collected_momentum import consistency_checks,data_comparison
from scripts.audit_multihour import allocation_risk
from tests.test_multihour import market,T,bar


class ExpandedMomentumTests(unittest.TestCase):
    def test_prior_continuous_loss_cannot_pass_positive_subperiods(self):
        wallet=dict(summary=dict(final=D(101),max_drawdown_pct=D(1)),
            temporal_blocks=dict(development_return_pct=D(1),verification_return_pct=D(1)))
        p=dict(initial_equity='100',variants=[dict(name='A')],
            blocks=[dict(name=n) for n in ['first','second','third','continuous_all']])
        e={n:{'A':{'base':deepcopy(wallet),'stress':deepcopy(wallet)}} for n in ['first','second','third','continuous_all']}
        e['continuous_all']['A']['stress']['summary']['final']=D(99)
        self.assertFalse(consistency_checks(p,e)['A']['passed'])
        e['continuous_all']['A']['stress']['summary']['final']=D(101)
        self.assertTrue(consistency_checks(p,e)['A']['passed'])

    def test_source_comparison_distinguishes_last_candle_from_fair(self):
        old={'A':market()};fresh=deepcopy(old)
        fresh['A']['fair'][T]=bar(T,hi='102')
        self.assertFalse(any(data_comparison(old,fresh)['A']['hourly_changes'].values()))
        fresh['A']['hourly'][T]=bar(T,hi='102')
        self.assertEqual(data_comparison(old,fresh)['A']['hourly_changes']['high'],1)

    def test_drawdown_guard_has_hysteresis_and_uses_known_equity(self):
        p=dict(kind='DRAWDOWN_HYSTERESIS',normal='.02',reduced='.005',trigger='.05',restore='.025')
        r,g=allocation_risk(p,D(95),D(100),False,'.02')
        self.assertEqual((r,g),(D('.005'),True))
        self.assertEqual(allocation_risk(p,D(96),D(100),g,'.02'),(D('.005'),True))
        self.assertEqual(allocation_risk(p,D('97.5'),D(100),g,'.02'),(D('.02'),False))

    def test_fixed_risk_does_not_inherit_a_guard(self):
        self.assertEqual(allocation_risk(dict(kind='FIXED',fraction='.01'),D(50),D(100),True,'.02'),(D('.01'),False))
