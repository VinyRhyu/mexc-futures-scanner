from dataclasses import replace
import unittest
from mexc_scanner.models import Candle,D
from scripts.audit_trigger_volume import features

class TriggerVolumeTests(unittest.TestCase):
    def setUp(self):
        self.m={t:Candle(t,60,D(1),D(2),D(1),D(1),D(10)) for t in range(0,1440,60)}
    def test_causal_baseline_excludes_both_trigger_candles(self):
        self.m[1200]=replace(self.m[1200],volume=D(30))
        self.m[1260]=replace(self.m[1260],volume=D(50))
        a=features(1260,self.m)
        self.assertEqual(a['prior_mean'],D(10))
        self.assertEqual(a['rvol_pair'],D(4))
        self.assertEqual(a['known_at'],1320)
        self.m[1320]=replace(self.m[1320],volume=D(10000))
        self.assertEqual(features(1260,self.m),a)
    def test_missing_and_zero_history_not_imputed(self):
        self.assertEqual(features(120,self.m)['status'],'HISTORICO_1M_INSUFICIENTE')
        m={t:replace(c,volume=D(0)) for t,c in self.m.items()}
        self.assertEqual(features(1260,m)['status'],'MEDIA_VOLUME_ZERO')
    def test_predefined_bucket_boundaries(self):
        self.assertEqual(features(1260,self.m)['bucket'],'1X_A_2X')
        self.m[1200]=replace(self.m[1200],volume=D(20))
        self.m[1260]=replace(self.m[1260],volume=D(20))
        self.assertEqual(features(1260,self.m)['bucket'],'2X_OU_MAIS')
