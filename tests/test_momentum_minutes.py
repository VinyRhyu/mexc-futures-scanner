import unittest
from scripts.collect_momentum_minutes import minute_window,verify_hour
from tests.test_multihour import T
from scripts.audit_multihour import find_exit
from tests.test_multihour import bar
from mexc_scanner.models import Candle,D


class MomentumMinuteTests(unittest.TestCase):
    def position(self):
        return dict(sign=1,quantity=D(1),entry=D(100),margin=D(10),mmr=D('.005'),
            liquidation_fee=D('.0006'),funding_paid=D(0),stop=D(96),entry_fee=D('.06'))
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

    def test_five_minute_resolution_is_explicit_and_complete(self):
        p=self.payload()
        for k,v in p.items():p[k]=v[::5]
        bars=minute_window(p,T,T+3600,tf=300)
        self.assertEqual(len(bars),12);self.assertEqual(bars[0].tf,300)
        verify_hour(bars,dict(open='100',high='101',low='99',close='100'))

    def test_minute_stop_precedes_a_later_liquidation_wick(self):
        position=self.position()
        last=bar(T,lo='80');fair=bar(T,lo='80')
        minute=[Candle(T,60,D(100),D(101),D(95),D(96),D(1)),
            Candle(T+60,60,D(96),D(97),D(80),D(90),D(1))]
        coarse,_,_=find_exit(position,last,fair,False)
        self.assertEqual(coarse[0],'LIQUIDACAO')
        fine,at,used=find_exit(position,last,fair,False,dict(last=minute,fair=minute))
        self.assertEqual(fine[0],'STOP');self.assertEqual(at,T+60);self.assertTrue(used)

    def test_same_minute_ambiguity_keeps_liquidation_first(self):
        position=self.position();last=bar(T,lo='80')
        minute=[Candle(T,60,D(100),D(101),D(80),D(90),D(1))]
        fine,_,_=find_exit(position,last,last,False,dict(last=minute,fair=minute))
        self.assertEqual(fine[0],'LIQUIDACAO');self.assertTrue(fine[2])
