from dataclasses import replace
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D
from scripts.audit_rejection_strategy import evaluate_setup, make_plan, setups, simulate, summary


def candle(ts, op='100', hi='101', lo='99', cl='100', tf=60):
    return Candle(ts,tf,*map(D,(op,hi,lo,cl)))


class RejectionTest(unittest.TestCase):
    def setUp(self):
        self.s={'symbol':'ETH_USDT','side':'SHORT','signal':0,'atr':D('2'),
                'reference':D('100'),'stop':D('102'),'level':D('98'),
                'levels':[D('94'),D('98')]}
        self.contract=Contract('ETH_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0002'))
        self.minutes=[candle(i*60) for i in range(300)]

    def test_targets_are_frozen_structural_levels(self):
        _,early=make_plan(self.s,'ANTECIPADA',0,D(100),D(102),D('.01'))
        _,confirmed=make_plan(self.s,'CONFIRMADA',60,D(97),D(99),D('.01'))
        self.assertEqual(early.target,D('98.2'))
        self.assertEqual(confirmed.target,D('94.2'))
        self.assertIsNone(make_plan(self.s,'CONFIRMADA',60,D(93),D(95),D('.01')))

    def test_long_mirrors_short_target_and_stop(self):
        long=dict(self.s,side='LONG',level=D(102),levels=[D(102),D(106)])
        _,v=make_plan(long,'ANTECIPADA',0,D(100),D('97.999'),D('.01'))
        self.assertEqual(v.target,D('101.8'))
        self.assertEqual(v.stop,D('97.99'))

    def test_missing_minutes_prevent_entries_and_confirmation(self):
        bad=self.minutes[:4]+self.minutes[5:]
        self.assertEqual(simulate(self.s,'ANTECIPADA',0,D(100),D(102),bad,self.contract,Config())['outcome'],'SEM_DADOS')
        r=evaluate_setup(self.s,bad,[],self.contract,Config())
        self.assertEqual(r['CONFIRMADA']['outcome'],'SEM_DADOS')

    def test_invalidation_precedes_confirmation_in_ambiguous_minute(self):
        m=list(self.minutes)
        m[0]=candle(0,'100','103','97','97.5')
        with patch('scripts.audit_rejection_strategy.simulate',return_value={'outcome':'BLOQUEADA'}):
            r=evaluate_setup(self.s,m,[],self.contract,Config())
        self.assertEqual(r['CONFIRMADA']['outcome'],'INVALIDADA_ANTES_DA_CONFIRMACAO')

    def test_confirmation_uses_closed_minutes_and_next_open_only(self):
        m=list(self.minutes)
        m[0]=candle(0,'100','101.5','99','100')
        m[1]=candle(60,'100','100.5','98','99')
        m[2]=candle(120,'99','99.5','97.5','97.5')
        seen=[]
        def fake(s,kind,signal,reference,stop,*args):
            seen.append((kind,signal,reference,stop))
            return {'outcome':'BLOQUEADA'}
        h=[candle(-3600,tf=3600),candle(0,tf=3600)]
        with patch('scripts.audit_rejection_strategy.simulate',side_effect=fake),patch('scripts.audit_rejection_strategy.structure',return_value='BAIXA') as trend:
            evaluate_setup(self.s,m,h,self.contract,Config())
            self.assertEqual(trend.call_args.args[0],[h[0]])
        self.assertEqual(seen[-1],('CONFIRMADA',180,D('97.5'),D('101.7')))
        # Future extreme must not change the selected stop or trigger.
        m[3]=candle(180,'97.5','150','50','100')
        with patch('scripts.audit_rejection_strategy.simulate',side_effect=fake),patch('scripts.audit_rejection_strategy.structure',return_value='BAIXA'):
            evaluate_setup(self.s,m,h,self.contract,Config())
        self.assertEqual(seen[-1],('CONFIRMADA',180,D('97.5'),D('101.7')))

    def test_setup_causal_and_mirrored(self):
        q=[candle(i*900,tf=900) for i in range(481)]
        q[478]=candle(478*900,'100','100','96','97',900)
        q[479]=candle(479*900,'97','99','96.5','98',900)
        q[480]=candle(480*900,'99','100','97.5','98',900)
        signal=q[-1].end
        with patch('scripts.audit_rejection_strategy.structure',return_value='BAIXA'):
            short=setups('ETH_USDT',q,[],signal,signal+1)
            future=q+[candle(signal,'98','150','50','100',900)]
            repeated=setups('ETH_USDT',future,[],signal,signal+1)
        self.assertEqual(len(short),1)
        self.assertEqual(short,repeated)
        mirrored=[replace(c,open=200-c.open,high=200-c.low,low=200-c.high,close=200-c.close) for c in q]
        with patch('scripts.audit_rejection_strategy.structure',return_value='ALTA'):
            long=setups('ETH_USDT',mirrored,[],signal,signal+1)
        self.assertEqual(len(long),1)
        self.assertAlmostEqual(long[0]['stop'],200-short[0]['stop'],places=20)
        self.assertEqual(long[0]['level'],200-short[0]['level'])

    def test_open_positions_are_not_wins(self):
        rows=[{'ANTECIPADA':{'outcome':'ABERTO','entered_at':'x'},'CONFIRMADA':{'outcome':'SEM_ALVO_ESTRUTURAL'}}]
        s=summary(rows)
        self.assertEqual(s['ANTECIPADA']['entries'],1)
        self.assertEqual(s['ANTECIPADA']['targets'],0)
        self.assertEqual(s['ANTECIPADA']['open'],1)


if __name__=='__main__':
    unittest.main()
