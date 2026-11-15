import unittest
from copy import deepcopy
from mexc_scanner.models import Candle,D
from scripts.audit_m1_trend_context import classify,known_context
from tests.test_relative_momentum_daily import market,DAY,HOUR


class M1TrendTests(unittest.TestCase):
    def test_joint_groups_are_symmetric_and_exhaustive(self):
        self.assertEqual(classify('LONG','ALTA','ALTA')['joint'],'A_FAVOR')
        self.assertEqual(classify('SHORT','BAIXA','BAIXA')['joint'],'A_FAVOR')
        self.assertEqual(classify('LONG','BAIXA','BAIXA')['joint'],'CONTRA')
        self.assertEqual(classify('SHORT','ALTA','ALTA')['joint'],'CONTRA')
        self.assertEqual(classify('LONG','ALTA','BAIXA')['joint'],'MISTO')
        self.assertEqual(classify('LONG','ALTA','INDEFINIDA')['joint'],'SEM_DIRECAO')

    def test_future_hourly_extremes_cannot_relabel_a_signal(self):
        m=market();at=20*DAY;before=known_context(list(m['hourly'].values()),at,'LONG')
        changed=deepcopy(m)
        for ts in changed['hourly']:
            if ts>=at:changed['hourly'][ts]=Candle(ts,HOUR,D(1),D(999999),D('.01'),D(1),D(1))
        self.assertEqual(before,known_context(list(changed['hourly'].values()),at,'LONG'))


if __name__=='__main__':unittest.main()
