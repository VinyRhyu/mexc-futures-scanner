import unittest

from mexc_scanner.models import Candle,D
from scripts.audit_retest_m15_target import choose_target


def bar(i,high=100,low=98,close=99):
    return Candle(i*900,900,D(close),D(high),D(low),D(close))


class M15TargetTests(unittest.TestCase):
    def test_pivot_cannot_be_used_until_its_right_neighbours_are_available(self):
        bars=[bar(i,high=110 if i==2 else 100) for i in range(5)]
        self.assertIsNone(choose_target(bars,'LONG',D(100),4509,D('.01')))
        target=choose_target(bars,'LONG',D(100),4510,D('.01'))
        self.assertEqual(target['target'],D('109.99'))
        self.assertEqual(target['known_at'],4510)

    def test_future_closes_cannot_remove_a_historical_target(self):
        bars=[bar(i,high=110 if i==2 else 100) for i in range(5)]
        at=4510
        original=choose_target(bars,'LONG',D(100),at,D('.01'))
        future=bar(5,high=121,low=110,close=120)
        self.assertEqual(original,choose_target(bars+[future],'LONG',D(100),at,D('.01')))
        self.assertIsNone(choose_target(bars+[future],'LONG',D(100),5410,D('.01')))

    def test_nearest_level_is_kept_even_if_a_farther_target_might_pay_more(self):
        bars=[bar(i,high={2:110,7:105}.get(i,100)) for i in range(10)]
        target=choose_target(bars,'LONG',D(100),9010,D('.01'))
        self.assertEqual(target['level'],D(105))
        self.assertEqual(target['target'],D('104.99'))

    def test_short_targets_are_one_tick_above_the_known_low(self):
        bars=[bar(i,high=102,low=90 if i==2 else 98,close=100) for i in range(5)]
        target=choose_target(bars,'SHORT',D(100),4510,D('.01'))
        self.assertEqual(target['target'],D('90.01'))


if __name__=='__main__':
    unittest.main()
