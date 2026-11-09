from datetime import datetime, timezone
import unittest

from mexc_scanner.models import Candle, D
from scripts.audit_continuation import Case, outcome, review_case


def bar(i, op='100', hi='100.2', lo='99.8', cl='100'):
    c = Candle(i * 900, 900, D(op), D(hi), D(lo), D(cl), D(1))
    c.validate()
    return c


class AuditTests(unittest.TestCase):
    def test_ambiguous_candle_counts_stop_first(self):
        c = bar(0, hi='101', lo='99')
        self.assertEqual(outcome([c], 'LONG', D('99.5'), D('100.5')), 'AMBIGUO_STOP_PRIMEIRO')

    def test_outside_next_open_cannot_be_claimed_as_trade(self):
        q = [bar(i) for i in range(30)] + [bar(30, '102', '103', '101', '102')]
        stamp = datetime.fromtimestamp(q[29].end, timezone.utc).isoformat()
        c = Case('TEST_USDT', stamp, 'LONG', '99.9', '100.1', '99', '101')
        result = review_case(c, q, D('0.01'))
        self.assertEqual(result['original'], 'SEM_FILL_NA_ABERTURA_SEGUINTE')

    def test_continuation_levels_use_only_candles_known_at_trigger(self):
        q = [bar(i) for i in range(30)]
        q += [bar(30, '100', '100.7', '99.9', '100.5'),
              bar(31, '100.5', '100.7', '100.3', '100.4'),
              bar(32, '100.4', '100.6', '100.2', '100.5')]
        stamp = datetime.fromtimestamp(q[29].end, timezone.utc).isoformat()
        c = Case('TEST_USDT', stamp, 'LONG', '99.9', '100.1', '99', '100.3')
        first = review_case(c, q, D('0.001'))
        changed_future = q[:32] + [bar(32, '100.4', '120', '90', '100.5')]
        second = review_case(c, changed_future, D('0.001'))
        self.assertEqual(first['continuation_entry'], second['continuation_entry'])
        self.assertEqual(first['continuation_stop'], second['continuation_stop'])
        self.assertEqual(first['continuation_target'], second['continuation_target'])
        self.assertIn(first['continuation'], {'ABERTO_AO_FIM_DA_JANELA', 'RR_LIQUIDO_INSUFICIENTE'})
