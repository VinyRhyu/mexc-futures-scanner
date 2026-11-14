from copy import deepcopy
import unittest

from mexc_scanner.models import Candle, D
from scripts.audit_structure_retest_day import advance_retest


class StructureRetestCausalityTests(unittest.TestCase):
    def waiting(self):
        return dict(sign=1, level=D(100), atr=D(2), break_at=300,
                    wait_low=None,wait_high=None,impulse_high=D(104),impulse_low=D(99))

    def test_breakout_candle_cannot_be_its_own_retest(self):
        wait=self.waiting();before=deepcopy(wait)
        stage,setup=advance_retest(wait,Candle(0,300,D(99),D(104),D(99),D(102)),D('.01'))
        self.assertEqual(stage,'WAIT');self.assertIsNone(setup);self.assertEqual(wait,before)

    def test_target_is_known_before_reaction_not_its_future_high(self):
        stage,setup=advance_retest(self.waiting(),Candle(300,300,D(102),D(110),D('99.9'),D(101)),D('.01'))
        self.assertEqual(stage,'REACTION');self.assertEqual(setup['target'],D(104))
        self.assertEqual(setup['stop'],D('99.7'));self.assertEqual(setup['signal'],600)

    def test_retest_cannot_be_resurrected_after_invalidation(self):
        stage,setup=advance_retest(self.waiting(),Candle(300,300,D(102),D(103),D(98),D(99)),D('.01'))
        self.assertEqual(stage,'CANCELLED');self.assertIsNone(setup)

    def test_expired_reaction_is_rejected(self):
        stage,setup=advance_retest(self.waiting(),Candle(2100,300,D(102),D(103),D(100),D(101)),D('.01'))
        self.assertEqual(stage,'EXPIRED');self.assertIsNone(setup)

    def test_short_is_the_price_mirror_of_long(self):
        wait=self.waiting();wait.update(sign=-1,impulse_low=D(96),impulse_high=D(101))
        stage,setup=advance_retest(wait,Candle(300,300,D(98),D('100.1'),D(95),D(99)),D('.01'))
        self.assertEqual(stage,'REACTION');self.assertEqual(setup['target'],D(96))
        self.assertEqual(setup['stop'],D('100.3'))


if __name__=='__main__':
    unittest.main()
