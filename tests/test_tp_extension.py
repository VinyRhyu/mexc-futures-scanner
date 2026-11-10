import unittest
from mexc_scanner.models import D
from scripts.audit_tp_extension import extended_target

class TargetTests(unittest.TestCase):
    def test_distance_not_nominal_price(self):
        t=extended_target(D(100),D(104),'LONG',D('.01'))
        self.assertEqual(t,D(105))
        self.assertNotEqual(t,D(130))
    def test_short_moves_lower_and_rounds_away(self):
        self.assertEqual(extended_target(D(100),D(96),'SHORT',D('.01')),D(95))
    def test_rejects_wrong_side(self):
        with self.assertRaises(ValueError):extended_target(D(100),D(99),'LONG',D('.01'))
