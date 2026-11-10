import unittest
from mexc_scanner.models import D
from scripts.audit_volume_retention import keep_volume,summarize

class RetentionTests(unittest.TestCase):
    def test_fixed_boundary(self):
        self.assertTrue(keep_volume(D(100),D(50)))
        self.assertFalse(keep_volume(D(100),D('49.999')))
        self.assertTrue(keep_volume(D(100),D(120)))
    def test_zero_first_volume_not_imputed(self):
        self.assertFalse(keep_volume(D(0),D(100)))
    def test_removed_targets_and_stops_both_count(self):
        rows=[]
        for i,(outcome,r,accepted) in enumerate([('ALVO','2.5',False),('STOP','-1',False),('ALVO','2',True),('ABERTO',None,True)]):
            v={'outcome':outcome}
            if r is not None:v['net_r']=r
            rows.append({'symbol':'TEST','side':'LONG','signal':i,'accepted':accepted,'baseline':v})
        s=summarize(rows)
        self.assertEqual(s['removed'],{'ALVO':1,'STOP':1})
        self.assertEqual(s['filtered']['net_r'],'2')
        self.assertEqual(s['filtered']['open'],1)
        self.assertEqual(s['filtered']['win_rate_closed'],'1')
