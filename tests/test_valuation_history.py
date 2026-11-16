import unittest
from scripts.collect_valuation_history import parse_fair


class FairHistoryTests(unittest.TestCase):
    def test_exact_window_and_zero_fair_volume_are_valid(self):
        data=dict(time=[0,60,120],open=[100]*3,high=[101]*3,low=[99]*3,close=[100]*3)
        rows=parse_fair(data,0,120)
        self.assertEqual([r['ts'] for r in rows],[0,60])
        self.assertTrue(all(r['volume']=='0' for r in rows))

    def test_missing_bar_is_not_silently_zero_filled(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            parse_fair(dict(time=[0],open=[100],high=[101],low=[99],close=[100]),0,120)

    def test_conflicting_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            parse_fair(dict(time=[0,0],open=[100,100],high=[101,102],low=[99,99],close=[100,100]),0,60)
