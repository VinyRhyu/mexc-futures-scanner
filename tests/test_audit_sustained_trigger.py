from copy import deepcopy
from dataclasses import replace
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D, Plan
from scripts.audit_sustained_trigger import MODE, metrics, read_dataset, summary, sustained


START=1793502000


def bar(ts,op='101.3',hi='101.5',lo='101.25',cl='101.3'):
    return Candle(ts,60,*map(D,(op,hi,lo,cl)))


class SustainedTriggerTests(unittest.TestCase):
    def setUp(self):
        self.p=Plan('p','TEST_USDT','ROMPIMENTO','LONG',START,START,START+1800,
                    D(2),D(101),D(99),D(101),D(100),'p')
        self.c=Contract('TEST_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
        self.first={'signal':START+60,'reference':'101.3','entry_low':'101.21','entry_high':'101.8',
                    'stop':'100','target':'103','target_origin':'PROJECAO_DA_FAIXA',
                    'outcome':'BLOQUEADA','reasons':['RETORNO_RISCO_INSUFICIENTE']}
        self.m={START+i*60:bar(START+i*60) for i in range(1,242)}
        self.quote={'status':'VIAVEL_SIMULADO','base_quantity':'1','net_rr':'2.5','loss_usdt':'.1'}

    def test_same_close_is_enough_without_a_new_high_and_levels_are_frozen(self):
        def checked(p,v,c,price,now,cfg):
            self.assertEqual(v.stop,D(100))
            self.assertEqual(v.target,D(103))
            self.assertEqual(v.reference,D('101.3'))
            self.assertEqual(v.entry_low,D('101.21'))
            self.assertEqual(v.triggered_at,START+60)
            self.assertEqual(p.expires_at,START+60+1800)
            self.assertEqual(now,START+121)
            return self.quote
        with patch('scripts.audit_sustained_trigger.paper_quote',side_effect=checked):
            r=sustained(self.p,self.first,self.m,self.c,Config())
        self.assertEqual(r['entered_at'],'2026-11-01T03:02:00+00:00')
        self.assertEqual(r['outcome'],'ABERTO')
        self.assertEqual(r['target'],'103')
        self.assertEqual(r['signal'],START+120)

    def test_only_immediate_next_candle_is_allowed_no_later_replacement(self):
        self.m[START+60]=bar(START+60,lo='101',cl='101.1')
        self.m[START+120]=bar(START+120,hi='102',cl='101.5')
        with patch('scripts.audit_sustained_trigger.paper_quote') as quote:
            r=sustained(self.p,self.first,self.m,self.c,Config())
        self.assertEqual(r['outcome'],'NAO_SUSTENTOU_SEGUNDO_FECHAMENTO')
        quote.assert_not_called()

    def test_stop_or_target_touched_while_waiting_cancels_before_entry(self):
        cases=[('103','101.25','ALVO_ANTES_DA_ENTRADA'),
               ('101.5','100','STOP_ANTES_DA_ENTRADA'),
               ('103','100','STOP_E_ALVO_ANTES_DA_ENTRADA')]
        for hi,lo,expected in cases:
            with self.subTest(expected=expected):
                self.m[START+60]=bar(START+60,hi=hi,lo=lo)
                with patch('scripts.audit_sustained_trigger.paper_quote') as quote:
                    r=sustained(self.p,self.first,self.m,self.c,Config())
                self.assertEqual(r['outcome'],expected)
                quote.assert_not_called()

    def test_financial_rejection_after_confirmation_is_respected(self):
        with patch('scripts.audit_sustained_trigger.paper_quote',return_value={'status':'BLOQUEADA','reasons':['PRECO_FORA_DO_PLANO']}):
            r=sustained(self.p,self.first,self.m,self.c,Config())
        self.assertEqual(r['outcome'],'BLOQUEADA')
        self.assertEqual(r['reasons'],['PRECO_FORA_DO_PLANO'])
        self.assertNotIn('entered_at',r)

    def test_short_mirrors_long(self):
        p=replace(self.p,side='SHORT',level=D(99))
        first=dict(self.first,reference='98.7',entry_low='98.2',entry_high='98.79',target='97')
        m={t:replace(c,open=200-c.open,high=200-c.low,low=200-c.high,close=200-c.close) for t,c in self.m.items()}
        with patch('scripts.audit_sustained_trigger.paper_quote',return_value=self.quote):
            r=sustained(p,first,m,self.c,Config())
        self.assertEqual(r['outcome'],'ABERTO')
        self.assertEqual(r['target'],'97')
        self.assertEqual(r['signal'],START+120)

    def test_missing_minutes_cannot_produce_an_entry(self):
        del self.m[START+180]
        with patch('scripts.audit_sustained_trigger.paper_quote') as quote:
            r=sustained(self.p,self.first,self.m,self.c,Config())
        self.assertEqual(r['outcome'],'SEM_DADOS')
        quote.assert_not_called()

    def test_absent_first_trigger_does_not_search_for_a_new_one(self):
        self.assertEqual(sustained(self.p,{'outcome':'SEM_GATILHO'},self.m,self.c,Config()),{'outcome':'SEM_GATILHO'})

    def test_future_candle_does_not_move_frozen_target(self):
        with patch('scripts.audit_sustained_trigger.paper_quote',return_value=self.quote):
            a=sustained(self.p,self.first,self.m,self.c,Config())
            self.m[START+180]=bar(START+180,hi='150')
            b=sustained(self.p,self.first,self.m,self.c,Config())
        self.assertEqual(a['outcome'],'ABERTO')
        self.assertEqual(b['outcome'],'ALVO')
        self.assertEqual(a['target'],b['target'])
        self.assertEqual(a['stop'],b['stop'])

    def test_source_checksum_is_mandatory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'raw').mkdir()
            (root/'raw'/'TEST_USDT.json.gz').write_bytes(gzip.compress(b'{}'))
            with self.assertRaisesRegex(ValueError,'checksum'):
                read_dataset(root,{'symbol':'TEST_USDT','sha256_uncompressed':'invalid'})

    def test_paired_summary_counts_both_avoided_losses_and_lost_winners(self):
        row={'symbol':'TEST_USDT','side':'LONG','M1':dict(self.first,entered_at='x',outcome='STOP',net_r='-1'),
             MODE:{'outcome':'NAO_SUSTENTOU_SEGUNDO_FECHAMENTO'}}
        winner=deepcopy(row)
        winner['M1'].update(signal=START+120,outcome='ALVO',net_r='2.5')
        s=summary([row,deepcopy(row),winner])
        self.assertEqual(s['M1']['all_entries']['entries'],3)
        self.assertEqual(s['M1']['unique']['entries'],2)
        self.assertEqual(s['paired_baseline_unique']['baseline_stops_not_entered'],1)
        self.assertEqual(s['paired_baseline_unique']['baseline_targets_not_entered'],1)
        self.assertEqual(s[MODE]['unique']['entries'],0)

    def test_open_positions_are_not_profit_and_r_is_net_of_closed_losses(self):
        m=metrics([{'outcome':'ALVO','net_r':'2.5'},{'outcome':'STOP','net_r':'-1'},{'outcome':'ABERTO'}])
        self.assertEqual(m['net_r'],'1.5')
        self.assertEqual(m['open'],1)
        self.assertEqual(m['win_rate_closed'],'0.5')


if __name__=='__main__':
    unittest.main()
