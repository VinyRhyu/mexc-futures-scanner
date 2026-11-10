from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.models import D, jsonable
from scripts.audit_pullback import review_signal
from scripts.audit_rr import THRESHOLDS, review, summary
from tests.test_audit_pullback import SIGNAL, candle, setup


class RRAuditTests(unittest.TestCase):
    def test_no_minimum_can_accept_less_than_one_r_without_increasing_risk(self):
        p, c = setup()
        p.variants['CONFIRMADA'].target = D(102)
        row = jsonable(p)
        original = deepcopy(row)
        q = [candle(0, '101', '102.2', '100.5', '102')]
        cfg = Config()
        strict = review(row, q, c, cfg, SIGNAL + 900, '2')
        loose = review(row, q, c, cfg, SIGNAL + 900, '0')
        self.assertEqual(strict['outcome'], 'BLOQUEADA')
        self.assertEqual(loose['outcome'], 'ALVO')
        self.assertGreater(D(loose['net_r']), 0)
        self.assertLess(D(loose['net_r']), 1)
        self.assertLessEqual(D(loose['planned_loss_usdt']), D('0.10'))
        self.assertEqual(cfg.minimum_rr, '2')
        self.assertIs(cfg.validate(), cfg)
        self.assertEqual(row, original)

    def test_no_minimum_still_rejects_target_consumed_by_costs(self):
        p, c = setup()
        p.variants['CONFIRMADA'].target = D('101.01')
        q = [candle(0)]
        r = review(jsonable(p), q, c, Config(), SIGNAL + 900, '0')
        self.assertEqual(r['outcome'], 'BLOQUEADA')
        self.assertNotIn('entered_at', r)

    def test_no_minimum_preserves_stop_loss(self):
        p, c = setup()
        p.variants['CONFIRMADA'].target = D(102)
        q = [candle(0, '101', '101.2', '98.9', '99')]
        r = review(jsonable(p), q, c, Config(), SIGNAL + 900, '0')
        self.assertEqual(r['outcome'], 'STOP')
        self.assertEqual(D(r['net_r']), -1)

    def test_two_r_reproduces_previous_baseline(self):
        p, c = setup()
        p.variants['CONFIRMADA'].target = D(108)
        q = [candle(0), candle(1)]
        now = SIGNAL + 1800
        old = review_signal(jsonable(p), q, [], c, Config(), now)['A']
        new = review(jsonable(p), q, c, Config(), now, '2')
        for field in ('outcome', 'entered_at'):
            self.assertEqual(old.get(field), new.get(field))
        self.assertEqual(D(old['net_rr']), D(new['worst_band_rr']))

    def test_frozen_observation_cannot_see_later_target(self):
        p, c = setup()
        p.variants['CONFIRMADA'].target = D(108)
        q = [candle(0), candle(1, '101', '110', '100', '109')]
        r = review(jsonable(p), q, c, Config(), SIGNAL + 900, '0')
        self.assertEqual(r['outcome'], 'ABERTO')
        self.assertNotIn('net_r', r)
        self.assertIn('mark_to_market_r', r)

    def test_summary_does_not_count_marked_open_as_realized_win(self):
        values = {k: {'window_complete': True, 'outcome': 'ABERTO',
                      'entered_at': 'test', 'entry_net_rr': '0.8', 'mark_to_market_r': '0.2'} for k in THRESHOLDS}
        s = summary([{'scenarios': values}], complete_only=True)['scenarios']['0']
        self.assertEqual(s['entries'], 1)
        self.assertEqual(s['closed'], 0)
        self.assertIsNone(s['win_rate_closed'])
        self.assertEqual(D(s['sum_r_closed_independent']), 0)
        self.assertEqual(D(s['sum_r_with_open_marks_independent']), D('0.2'))


if __name__ == '__main__':
    unittest.main()
