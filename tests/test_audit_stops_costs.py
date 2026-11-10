from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from scripts.audit_stops_costs import compare_quote, stop_case
from tests.test_audit_pullback import SIGNAL, candle, setup


class StopsCostAuditTests(unittest.TestCase):
    def test_stop_is_fixed_from_confirmation_candle_before_entry(self):
        p, c = setup()
        row = jsonable(p)
        original = deepcopy(row)
        q = [candle(-1, '101', '101.2', '100.4', '101'), candle(0)]
        adjusted, note = stop_case(row, q, c, 'CONFIRMACAO')
        self.assertTrue(note['changed'])
        self.assertEqual(D(adjusted['variants']['CONFIRMADA']['stop']), D('100.3'))
        self.assertEqual(adjusted['variants']['CONFIRMADA']['target'], row['variants']['CONFIRMADA']['target'])
        self.assertEqual(row, original)
        q[-1] = candle(0, '101', '120', '90', '100')
        self.assertEqual(adjusted, stop_case(row, q, c, 'CONFIRMACAO')[0])

    def test_short_stop_is_symmetric(self):
        p, c = setup('SHORT')
        q = [candle(-1, '99', '99.6', '98.8', '99')]
        r, note = stop_case(jsonable(p), q, c, 'CONFIRMACAO')
        self.assertTrue(note['changed'])
        self.assertEqual(D(r['stop']), D('99.7'))

    def test_wider_local_stop_does_not_silently_replace_original(self):
        p, c = setup()
        q = [candle(-1, '101', '101.2', '98', '101')]
        r, note = stop_case(jsonable(p), q, c, 'CONFIRMACAO')
        self.assertFalse(note['changed'])
        self.assertEqual(D(r['stop']), D(99))

    def test_local_stop_inside_entry_band_is_rejected(self):
        p, c = setup()
        q = [candle(-1, '101.2', '101.4', '101.1', '101.2')]
        _, note = stop_case(jsonable(p), q, c, 'CONFIRMACAO')
        self.assertEqual(note['reason'], 'STOP_LOCAL_DENTRO_DA_FAIXA')

    def test_initial_reaction_uses_its_own_bar(self):
        p, c = setup()
        p.reaction_at = SIGNAL - 900
        q = [candle(-2, '101', '101.2', '99.5', '101'),
             candle(-1, '101', '101.2', '100.4', '101')]
        r, note = stop_case(jsonable(p), q, c, 'REACAO')
        self.assertTrue(note['changed'])
        self.assertEqual(D(r['stop']), D('99.4'))

    def test_quote_check_reproduces_band_rejection_despite_viable_price(self):
        p, c = setup()
        v = p.variants['CONFIRMADA']
        v.entry_low, v.entry_high, v.target = map(D, ('99.05', '100.05', '104'))
        q = [candle(0, '99.99', '100.2', '99.9', '100')]
        r = compare_quote(jsonable(p), q, c, Config())
        self.assertTrue(r['comparable'])
        self.assertTrue(r['band_blocked_point_viable'])
        self.assertEqual(r['band_reasons'], ['CUSTO_RELATIVO_ELEVADO'])
        self.assertGreater(D(r['point_rr']), 3)
        self.assertLessEqual(D(r['point_risk']), D('0.10'))


if __name__ == '__main__':
    unittest.main()
