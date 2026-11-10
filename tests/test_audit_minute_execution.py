import unittest

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, D, jsonable
from scripts.audit_minute_execution import audit_delay, candle_consistency, summarize
from tests.test_audit_pullback import SIGNAL, setup


def minutes():
    return [Candle(SIGNAL + i * 60, 60, D(101), D('101.2'), D('100.9'), D(101)) for i in range(240)]


def plan():
    p, c = setup()
    p.variants['CONFIRMADA'].target = D(108)
    return jsonable(p), c


class MinuteAuditTests(unittest.TestCase):
    def test_stop_in_waiting_minute_cancels_delayed_entry(self):
        row, contract = plan()
        m = minutes()
        m[0] = Candle(SIGNAL, 60, D(101), D('101.2'), D(98), D(100))
        self.assertEqual(audit_delay(row, m, contract, Config(), 0)['outcome'], 'STOP')
        r = audit_delay(row, m, contract, Config(), 60)
        self.assertEqual(r['outcome'], 'SEM_ENTRADA_STOP_ANTES')
        self.assertNotIn('entered_at', r)

    def test_target_before_delayed_entry_is_not_a_winner(self):
        row, contract = plan()
        m = minutes()
        m[0] = Candle(SIGNAL, 60, D(101), D(109), D('100.9'), D(108))
        self.assertEqual(audit_delay(row, m, contract, Config(), 120)['outcome'], 'SEM_ENTRADA_ALVO_ANTES')

    def test_same_minute_ambiguity_keeps_stop_first(self):
        row, contract = plan()
        m = minutes()
        m[0] = Candle(SIGNAL, 60, D(101), D(109), D(98), D(101))
        self.assertEqual(audit_delay(row, m, contract, Config(), 0)['outcome'], 'STOP_AMBIGUO')

    def test_delayed_price_outside_original_band_is_rejected(self):
        row, contract = plan()
        m = minutes()
        m[1] = Candle(SIGNAL + 60, 60, D(100), D('100.2'), D('99.8'), D(100))
        r = audit_delay(row, m, contract, Config(), 60)
        self.assertEqual(r['outcome'], 'BLOQUEADA')
        self.assertIn('PRECO_FORA_DO_PLANO', r['reasons'])

    def test_aggregate_consistency_detects_different_price_path(self):
        m = minutes()
        q = [Candle(SIGNAL + i*900, 900, D(101), D('101.2'), D('100.9'), D(101)) for i in range(16)]
        self.assertEqual(candle_consistency(q, m, SIGNAL), [])
        m[1] = Candle(SIGNAL + 60, 60, D(101), D(110), D('100.9'), D(101))
        self.assertEqual(len(candle_consistency(q, m, SIGNAL)), 1)

    def test_missing_minute_cannot_be_silently_ignored(self):
        row, contract = plan()
        m = minutes()
        del m[10]
        self.assertEqual(audit_delay(row, m, contract, Config(), 0)['outcome'], 'SEM_DADOS')


if __name__ == '__main__':
    unittest.main()
