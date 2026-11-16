import unittest
from scripts.collect_momentum_minutes import minute_window,verify_hour
from tests.test_multihour import T


class MomentumMinuteTests(unittest.TestCase):
    def payload(self):
        return dict(time=[T+i*60 for i in range(60)],open=['100']*60,high=['101']*60,
            low=['99']*60,close=['100']*60,vol=['1']*60)

    def test_minute_reconstruction_matches_frozen_hour(self):
        bars=minute_window(self.payload(),T,T+3600)
        verify_hour(bars,dict(open='100',high='101',low='99',close='100'))
        with self.assertRaises(ValueError):verify_hour(bars,dict(open='100',high='102',low='99',close='100'))

    def test_missing_minute_is_rejected(self):
        p=self.payload()
        for v in p.values():v.pop()
        with self.assertRaises(ValueError):minute_window(p,T,T+3600)
