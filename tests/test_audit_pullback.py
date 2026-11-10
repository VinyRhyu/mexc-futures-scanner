from copy import deepcopy
from datetime import datetime
import unittest

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D, Plan, Variant, jsonable
from scripts.audit_pullback import pullback_variant, review_signal, summarize


SIGNAL = 1794240000


def candle(i, op='101', hi='101.2', lo='100.1', cl='100.2'):
    c = Candle(SIGNAL + 900 * i, 900, *map(D, (op, hi, lo, cl)), D(1))
    c.validate()
    return c


def setup(side='LONG'):
    p = Plan('test', 'TEST_USDT', 'ROMPIMENTO', side, SIGNAL - 1800, SIGNAL, SIGNAL + 900,
             D(1), D(100), D(98), D(100), D(99), 'family')
    v = Variant('CONFIRMADA', SIGNAL, D(101), D('100.9'), D('101.1'), D(99), D(105), 'TEST')
    if side == 'SHORT':
        p.stop, p.level, p.lower, p.upper = D(101), D(100), D(100), D(102)
        v.reference, v.entry_low, v.entry_high = D(99), D('98.9'), D('99.1')
        v.stop, v.target = D(101), D(95)
    p.variants['CONFIRMADA'] = v
    c = Contract('TEST_USDT', D('0.001'), D(1), D(1), D('0.001'), 20, D('0.005'), D('0.0004'))
    return p, c


class PullbackAuditTests(unittest.TestCase):
    def review(self, q, side='LONG', plan=None):
        p, c = setup(side)
        return review_signal(jsonable(plan or p), q, [], c, Config(), SIGNAL + 20000)

    def test_blocked_immediate_can_enter_on_next_check_with_same_stop_target(self):
        q = [candle(0), candle(1, '100.2', '100.5', '100.1', '100.3'),
             candle(2, '100.3', '105.2', '100.1', '105')]
        r = self.review(q)
        self.assertEqual(r['A']['outcome'], 'BLOQUEADA')
        self.assertEqual(r['B']['outcome'], 'ALVO')
        self.assertEqual((r['stop'], r['target']), ('99', '105'))
        self.assertGreaterEqual(D(r['B']['net_rr']), 2)
        self.assertGreater(D(r['B']['net_r']), 2)
        self.assertEqual(int(datetime.fromisoformat(r['B']['entered_at']).timestamp()), SIGNAL + 900)

    def test_short_retrace_is_symmetric(self):
        q = [candle(0, '99', '99.9', '98.8', '99.8'),
             candle(1, '99.8', '99.9', '99.5', '99.7'),
             candle(2, '99.7', '99.9', '94.8', '95')]
        r = self.review(q, 'SHORT')
        self.assertEqual(r['B']['outcome'], 'ALVO')
        self.assertGreaterEqual(D(r['B']['net_rr']), 2)
        self.assertEqual((r['stop'], r['target']), ('101', '95'))

    def test_intrabar_touch_does_not_become_retroactive_entry(self):
        q = [candle(0, '101', '101.2', '100.2', '101'),
             candle(1, '101', '101.2', '100.2', '101'), candle(2)]
        r = self.review(q)
        self.assertNotIn('entered_at', r['B'])
        self.assertEqual(r['B']['outcome'], 'SEM_RECUO_NA_CHECAGEM')

    def test_target_before_retrace_cancels_pending_entry(self):
        q = [candle(0, hi='106'), candle(1, '100.2', '100.5', '100.1', '100.3')]
        self.assertEqual(self.review(q)['B']['outcome'], 'CANCELADA_ALVO_ANTES_DA_ENTRADA')

    def test_stop_before_retrace_cancels_pending_entry(self):
        q = [candle(0, lo='98'), candle(1, '100.2', '100.5', '100.1', '100.3')]
        self.assertEqual(self.review(q)['B']['outcome'], 'CANCELADA_STOP_ANTES_DA_ENTRADA')

    def test_confirmation_future_cannot_move_band_or_change_entry(self):
        p, c = setup()
        original = deepcopy(p)
        v = pullback_variant(p, p.variants['CONFIRMADA'], c.tick)
        q = [candle(0), candle(1, '100.2', '100.5', '100.1', '100.3'), candle(2)]
        r = self.review(q)
        changed = q[:2] + [candle(2, '100.3', '120', '90', '100')]
        other = self.review(changed)
        self.assertEqual(r['pullback_band'], other['pullback_band'])
        self.assertEqual(r['B']['entered_at'], other['B']['entered_at'])
        self.assertEqual((v.stop, v.target), (D(99), D(105)))
        self.assertEqual(p, original)
        self.assertEqual(other['B']['outcome'], 'STOP_AMBIGUO')

    def test_final_plan_status_does_not_select_historical_winners(self):
        p, _ = setup()
        q = [candle(0), candle(1, '100.2', '100.5', '100.1', '100.3')]
        before = self.review(q, plan=p)
        p.status = 'INVALIDADO'
        p.variants['CONFIRMADA'].status = 'ENCERRADA'
        after = self.review(q, plan=p)
        self.assertEqual(before, after)

    def test_incomplete_window_is_not_counted_in_complete_summary(self):
        r = self.review([candle(0)])
        self.assertFalse(r['window_complete'])
        self.assertEqual(r['B']['outcome'], 'OBSERVACAO_INCOMPLETA')
        self.assertEqual(summarize([r], complete_only=True)['signals'], 0)

    def test_gap_through_stop_can_lose_more_than_one_r(self):
        q = [candle(0), candle(1, '100.2', '100.5', '100.1', '100.3'),
             candle(2, '97', '98', '96', '97')]
        r = self.review(q)
        self.assertEqual(r['B']['outcome'], 'STOP')
        self.assertLess(D(r['B']['net_r']), -1)


if __name__ == '__main__':
    unittest.main()
