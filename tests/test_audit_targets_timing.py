from copy import deepcopy
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D, Pivot, Plan, jsonable
from mexc_scanner.strategies import make_variant
from scripts.audit_targets_timing import paired_diagnostics, target_options


SIGNAL = 1794240000


@contextmanager
def fixture(side='LONG', crossed=True):
    h = [Candle(SIGNAL - (240 - i) * 3600, 3600, D(100), D('100.5'), D('99.5'), D(100)) for i in range(240)]
    if crossed:
        value = D(102 if side == 'LONG' else 98)
        h[230] = Candle(h[230].ts, 3600, D(100), max(D('100.5'), value), min(D('99.5'), value), value)
    levels = [Pivot('HIGH' if side == 'LONG' else 'LOW', D(x), SIGNAL - age * 3600, SIGNAL - (age - 2) * 3600)
              for x, age in ([(101, 20), (104, 30)] if side == 'LONG' else [(99, 20), (96, 30)])]

    def known(bars, at):
        return [p for p in levels if p.known_at <= at] if bars and bars[0].tf == 3600 else []

    p = Plan('p', 'TEST_USDT', 'ROMPIMENTO', side, SIGNAL - 1800, SIGNAL, SIGNAL + 900,
             D(1), D(100), D(95 if side == 'LONG' else 100), D(100 if side == 'LONG' else 105),
             D(99 if side == 'LONG' else 101), 'family')
    c = Candle(SIGNAL - 900, 900, D(100), D('100.3'), D('99.7'), D(100))
    contract = Contract('TEST_USDT', D('0.001'), D(1), D(1), D('0.001'), 20, D('0.005'), D('0.0004'))
    with patch('mexc_scanner.strategies.pivots', side_effect=known), patch('scripts.audit_targets_timing.pivots', side_effect=known):
        p.variants['CONFIRMADA'] = make_variant(p, 'CONFIRMADA', c, h, contract.tick)
        yield jsonable(p), [c], h, contract


class TargetTimingAuditTests(unittest.TestCase):
    def test_crossed_pivot_is_identified_and_next_known_pivot_limits_trial(self):
        with fixture() as (row, q, h, c):
            old = deepcopy(row)
            r = target_options(row, 'CONFIRMADA', q, h, c)
            self.assertTrue(r['reconstructed'])
            self.assertTrue(r['selected']['crossed_before_signal'])
            self.assertEqual(D(r['registered']), D('100.9'))
            self.assertEqual(D(r['filtered']), D('103.9'))
            self.assertEqual(D(r['projected']), D(105))
            self.assertEqual(row, old)

    def test_uncrossed_pivot_is_preserved(self):
        with fixture(crossed=False) as (row, q, h, c):
            r = target_options(row, 'CONFIRMADA', q, h, c)
            self.assertFalse(r['selected']['crossed_before_signal'])
            self.assertEqual(r['filtered'], r['registered'])

    def test_short_pivot_filter_is_symmetric(self):
        with fixture('SHORT') as (row, q, h, c):
            r = target_options(row, 'CONFIRMADA', q, h, c)
            self.assertTrue(r['reconstructed'])
            self.assertTrue(r['selected']['crossed_before_signal'])
            self.assertEqual(D(r['registered']), D('99.1'))
            self.assertEqual(D(r['filtered']), D('96.1'))
            self.assertEqual(D(r['projected']), D(95))

    def test_future_close_cannot_invalidate_past_pivot(self):
        with fixture(crossed=False) as (row, q, h, c):
            original = target_options(row, 'CONFIRMADA', q, h, c)
            future = Candle(SIGNAL, 3600, D(100), D(200), D(99), D(200))
            changed = target_options(row, 'CONFIRMADA', q, h + [future], c)
            self.assertEqual(original, changed)

    def test_failed_reconstruction_is_explicit_and_not_used_as_valid_trial(self):
        with fixture() as (row, q, h, c):
            row['variants']['CONFIRMADA']['target'] = '101.5'
            r = target_options(row, 'CONFIRMADA', q, h, c)
            self.assertFalse(r['reconstructed'])
            self.assertNotIn('filtered', r)

    def test_pair_diagnostics_measure_waiting_without_counting_future_as_a_win(self):
        with fixture() as (row, q, h, c):
            row['variants']['ANTECIPADA'] = deepcopy(row['variants']['CONFIRMADA'])
            row['variants']['ANTECIPADA'].update(triggered_at=SIGNAL - 900, reference='99.8')
            variants = [{'plan_id': 'p', 'kind': kind, 'cases': {'REGISTRADO': {'outcome': 'BLOQUEADA', 'window_complete': True}}}
                        for kind in ('ANTECIPADA', 'CONFIRMADA')]
            r = paired_diagnostics([row], variants, {'TEST_USDT': c}, Config())
            self.assertEqual(r['pairs'], 1)
            self.assertEqual(r['price_advanced_in_trade_direction'], 1)
            self.assertEqual(r['early_viable_confirmed_not'], 0)
            self.assertEqual(r['records'][0]['wait_seconds'], 900)


if __name__ == '__main__':
    unittest.main()
