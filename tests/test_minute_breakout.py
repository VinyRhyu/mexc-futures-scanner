from copy import deepcopy
from dataclasses import replace
import unittest
from mexc_scanner.config import Config
from mexc_scanner.models import Candle,D,jsonable,stable_id
from mexc_scanner.minute_breakout import (MODEL,STRATEGY,form_plans,prepare_model,process_minutes,validate_minute_ohlc)
from mexc_scanner.state import initial_state
from mexc_scanner.reporting import plan_message

T=1793502000

def candle(ts,tf=60,op='100',hi='101',lo='99',cl='100',vol='100'):
    return Candle(ts,tf,*map(D,(op,hi,lo,cl,vol)))

class MinuteBreakoutTests(unittest.TestCase):
    def setUp(self):
        self.q=[candle(T-(480-i)*900,900) for i in range(480)]
        self.h=[candle(T-(240-i)*3600,3600) for i in range(240)]
        self.m=[candle(T,hi='101.4',lo='100.5',cl='101.3'),
                candle(T+60,op='101.3',hi='101.5',lo='101.25',cl='101.35',vol='50')]
    def run_model(self,m=None,now=None,plans=None,cursor=0,not_before=T):
        bars=self.m if m is None else m
        return process_minutes('TEST_USDT',self.q,self.h,bars,plans or [],cursor,
            now or bars[-1].end+10,D('.01'),Config(),not_before)
    def long(self,plans):return next(p for p in plans if p.side=='LONG')
    def test_confirmation_freezes_first_levels_and_accepts_half_volume(self):
        p=self.long(self.run_model()[0]);v=p.variants['CONFIRMADA']
        self.assertEqual(p.status,'ATIVO')
        self.assertEqual(v.triggered_at,T+120)
        self.assertEqual(v.reference,D('101.3'))
        self.assertEqual(v.target,D(103))
        self.assertEqual(v.stop,D(100))
        self.assertEqual(p.variants['ANTECIPADA'].status,'ENCERRADA')
        self.assertEqual(p.expires_at,T+240)
    def test_first_candle_cannot_release_entry(self):
        p=self.long(self.run_model(self.m[:1])[0])
        self.assertNotIn('CONFIRMADA',p.variants)
        self.assertNotEqual(p.variants['ANTECIPADA'].status,'VALIDA')
    def test_weak_volume_and_failed_close_are_not_replaced(self):
        for second in [replace(self.m[1],volume=D(49)),replace(self.m[1],close=D('101.1'),low=D('101'))]:
            p=self.long(self.run_model([self.m[0],second,candle(T+120,hi='102',lo='101.2',cl='101.7')])[0])
            self.assertEqual(p.status,'INVALIDADO')
            self.assertNotIn('CONFIRMADA',p.variants)
    def test_level_hit_during_confirmation_cancels(self):
        p=self.long(self.run_model([self.m[0],replace(self.m[1],high=D(104))])[0])
        self.assertEqual(p.status,'EVENTO_PASSADO')
        self.assertNotIn('CONFIRMADA',p.variants)
    def test_mirror_short(self):
        m=[replace(c,open=200-c.open,high=200-c.low,low=200-c.high,close=200-c.close) for c in self.m]
        p=next(p for p in self.run_model(m)[0] if p.side=='SHORT')
        self.assertEqual(p.variants['CONFIRMADA'].target,D(97))
        self.assertEqual(p.status,'ATIVO')
    def test_stale_signal_and_activation_cannot_release_history(self):
        p=self.long(self.run_model(now=T+241)[0])
        self.assertEqual(p.reason,'GATILHO_M1_ATRASADO')
        self.assertNotEqual(p.variants['CONFIRMADA'].status,'VALIDA')
        self.assertFalse(self.run_model(not_before=T+1)[0])
    def test_identical_round_is_idempotent(self):
        plans,cursor,_=self.run_model()
        before=jsonable(plans)
        other,_,_=self.run_model(plans=plans,cursor=cursor)
        self.assertEqual(before,jsonable(other))
    def test_formation_uses_only_closed_prior_bars(self):
        plans=form_plans('TEST_USDT',self.q,D('.01'),T,T)
        q=self.q+[candle(T,900,hi='150',lo='50')]
        other=[p for p in form_plans('TEST_USDT',q,D('.01'),T,T) if p.formed_at==T]
        self.assertEqual(jsonable(plans),jsonable(other))
    def test_hour_boundary_reconciliation_retains_240_bars_known_at_trigger(self):
        self.h=self.h+[candle(T,3600)]
        p=self.long(self.run_model(now=T+3610)[0])
        self.assertIn('CONFIRMADA',p.variants)
        # A 240-only fetch would lose one bar needed by this earlier trigger.
        self.h=self.h[-240:]
        with self.assertRaisesRegex(ValueError,'H1'):
            self.run_model(now=T+3610)
    def test_migration_preserves_ledger_and_balance_expires_pending_entries(self):
        cfg=Config();s=initial_state(cfg)
        s['wallet']['balance']='50';s['wallet']['position']={'plan_id':'old'}
        s['journal']=[{'event_id':'old'}]
        p=self.long(self.run_model()[0]);p.strategy='ROMPIMENTO'
        s['plans'][p.id]=jsonable(p)
        s['outbox']['pending']={'category':'ENTRY','status':'PENDING'}
        s['outbox']['sent']={'category':'ENTRY','status':'SENT'}
        info_id=stable_id(p.id,'POSSIVEL')
        s['outbox'][info_id]={'category':'INFO','status':'PENDING'}
        wallet,journal=deepcopy(s['wallet']),deepcopy(s['journal'])
        prepare_model(s,MODEL,T+130)
        self.assertEqual(s['wallet'],wallet);self.assertEqual(s['journal'],journal)
        self.assertEqual(s['outbox']['pending']['status'],'EXPIRED')
        self.assertEqual(s['outbox']['sent']['status'],'SENT')
        self.assertEqual(s['outbox'][info_id]['status'],'EXPIRED')
        self.assertEqual(s['plans'][p.id]['reason'],'MODELO_SUBSTITUIDO')
    def test_reporting_has_actual_timeframe(self):
        p=self.long(self.run_model()[0])
        text=plan_message(p,'paper',T+130,p.variants['CONFIRMADA'])
        self.assertIn('2 fechamentos M1',text)
        self.assertIn('50.0%',text)
        self.assertNotIn('Gatilho 15m',text)
    def test_ohlc_mismatch_is_rejected(self):
        m=[candle(i*60) for i in range(15)]
        validate_minute_ohlc([candle(0,900)],m)
        with self.assertRaises(ValueError):validate_minute_ohlc([candle(0,900,hi='105')],m)
