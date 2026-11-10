import unittest
from mexc_scanner.models import D
from mexc_scanner.models import Contract,Variant
from mexc_scanner.config import Config
from scripts.audit_tp_extension import extended_target,mark_open

class TargetTests(unittest.TestCase):
    def test_distance_not_nominal_price(self):
        t=extended_target(D(100),D(104),'LONG',D('.01'))
        self.assertEqual(t,D(105))
        self.assertNotEqual(t,D(130))
    def test_short_moves_lower_and_rounds_away(self):
        self.assertEqual(extended_target(D(100),D(96),'SHORT',D('.01')),D(95))
    def test_rejects_wrong_side(self):
        with self.assertRaises(ValueError):extended_target(D(100),D(99),'LONG',D('.01'))
    def test_marking_open_does_not_make_it_a_target(self):
        c=Contract('TEST_USDT',D('.001'),D(1),D(1),D('.01'),20,D('.005'),D('.0004'))
        v=Variant('ANTECIPADA',0,D(100),D(99),D(101),D(98),D(104),'TEST')
        result=mark_open({'outcome':'ABERTO'},D(102),D(100),'LONG',v,c,Config())
        self.assertEqual(result['outcome'],'ABERTO')
        self.assertGreater(D(result['mark_to_market_r']),0)
