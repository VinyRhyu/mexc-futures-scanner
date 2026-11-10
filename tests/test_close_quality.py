import unittest
from dataclasses import replace
from mexc_scanner.models import Candle,D
from scripts.audit_close_quality import favorable,apply_filter,MODE

class QualityTests(unittest.TestCase):
    def test_boundary_and_mirror(self):
        c=Candle(0,60,D(1),D(4),D(1),D(3))
        self.assertTrue(favorable(c,'LONG'))
        self.assertFalse(favorable(replace(c,close=D('2.99')),'LONG'))
        self.assertTrue(favorable(replace(c,close=D(2)),'SHORT'))
        self.assertFalse(favorable(replace(c,close=D('2.01')),'SHORT'))
    def test_zero_range_rejected(self):
        self.assertFalse(favorable(Candle(0,60,*[D(1)]*4),'LONG'))
    def test_filter_uses_only_confirmation_and_preserves_trade_levels(self):
        c=Candle(60,60,D(1),D(4),D(1),D(3))
        row={'side':'LONG','M1':{'signal':60},MODE:{'signal':120,'entered_at':'x','target':'5','stop':'.5'}}
        self.assertEqual(apply_filter(row,{60:c}),row[MODE])
        self.assertEqual(apply_filter(row,{60:replace(c,close=D(2))})['outcome'],'FECHAMENTO_FORA_TERCO')
    def test_cancelled_setup_is_not_replaced(self):
        row={'side':'LONG','M1':{},MODE:{'outcome':'SEM_GATILHO'}}
        self.assertEqual(apply_filter(row,{}),row[MODE])
