from copy import deepcopy
import unittest
from mexc_scanner.models import Candle,D
from scripts.audit_m1_trigger_features import trigger_features


class TriggerFeaturesTests(unittest.TestCase):
    def minute_data(self):
        return {i*60:Candle(i*60,60,D(100),D(102),D(99),D(101),D(10)) for i in range(30)}

    def test_no_future_candle_price_or_volume_can_change_features(self):
        m=self.minute_data();signal=22*60
        a=trigger_features(signal,'LONG',m,D(2),D(100))
        other=deepcopy(m)
        for t in other:
            if t>=signal:other[t]=Candle(t,60,D(1),D(999999),D('.01'),D(1),D(999999))
        self.assertEqual(a,trigger_features(signal,'LONG',other,D(2),D(100)))

    def test_progress_gate_is_symmetric_and_equality_passes(self):
        m=self.minute_data();s=22*60
        self.assertTrue(trigger_features(s,'LONG',m,D(2),D(100))['accepted'])
        m[s-60]=Candle(s-60,60,D(101),D(102),D(99),D(100),D(10))
        self.assertFalse(trigger_features(s,'LONG',m,D(2),D(100))['accepted'])
        self.assertTrue(trigger_features(s,'SHORT',m,D(2),D(100))['accepted'])

    def test_relative_volume_excludes_trigger_and_confirmation_from_reference(self):
        m=self.minute_data();s=22*60
        m[s-120]=Candle(s-120,60,D(100),D(102),D(99),D(101),D(100))
        m[s-60]=Candle(s-60,60,D(100),D(102),D(99),D(101),D(200))
        f=trigger_features(s,'LONG',m,D(2),D(100))
        self.assertEqual(f['volume_pair_relative20'],D(15))
        self.assertEqual(f['volume_retention'],D(2))
        self.assertEqual(f['known_at'],s)


if __name__=='__main__':unittest.main()
