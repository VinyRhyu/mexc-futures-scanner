from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, jsonable
from mexc_scanner.reporting import (margin_return_line, movement_message,
                                    plan_message, price_return_percent)
from tests.test_finance import NOW, context
from tests.test_watch_notifications import candidate


class PercentageMessagesTests(unittest.TestCase):
    def ready(self):
        p, v, c, t, b, f = context()
        p.status = 'ATIVO'
        v.financial = evaluate(p, v, c, D(1), t, b, f, NOW, Config())
        p.variants[v.kind] = v
        return p, v

    def test_short_profit_has_positive_sign_when_price_falls(self):
        self.assertEqual(price_return_percent('SHORT', '100', '97'), '+3.00%')
        self.assertEqual(price_return_percent('SHORT', '100', '102'), '-2.00%')
        self.assertEqual(price_return_percent('LONG', '100', '103'), '+3.00%')
        self.assertEqual(price_return_percent('LONG', '100', '98'), '-2.00%')

    def test_early_movement_uses_first_trigger_reference_and_does_not_change_plan(self):
        p = candidate()
        original = deepcopy(jsonable(p))
        text = movement_message(p, 'paper', NOW, 1, NOW + 60)
        self.assertIn('Stop do plano: 98 (-2.00% sem alavancagem)', text)
        self.assertIn('Alvo do plano: 106 (+6.00% sem alavancagem)', text)
        self.assertIn('antes de custos', text)
        self.assertNotIn('ROI líquido estimado sobre a margem:', text)
        self.assertEqual(jsonable(p), original)

    def test_viable_signal_uses_worst_admissible_entry_not_first_trigger(self):
        p, v = self.ready()
        v.reference = D(99)
        self.assertEqual(v.financial['worst_entry'], D('100.05'))
        text = plan_message(p, 'paper', NOW, v)
        self.assertIn('Base dos percentuais: 100.05 (pior entrada)', text)
        self.assertIn('Stop: 98 (-2.05% sem alavancagem)', text)
        self.assertIn('Alvo: 106 (+5.95% sem alavancagem)', text)

    def test_net_margin_roi_uses_margin_not_wallet_or_gross_price_move(self):
        line = margin_return_line({'margin_usdt': '5', 'gain_usdt': '2', 'loss_usdt': '1',
                                   'gain_fraction': '.04', 'loss_fraction': '.02'})
        self.assertEqual(line, 'ROI líquido estimado sobre a margem: TP +40.00% • SL -20.00%.')

    def test_missing_or_zero_margin_does_not_invent_roi(self):
        for f in ({}, {'margin_usdt': '0', 'gain_usdt': '1', 'loss_usdt': '.5'},
                  {'margin_usdt': '5', 'gain_usdt': '1'}):
            self.assertIsNone(margin_return_line(f))

    def test_zero_reference_does_not_crash_or_look_like_zero_risk(self):
        self.assertEqual(price_return_percent('LONG', '0', '100'), 'indisponível')

    def test_small_positive_distance_is_not_rounded_to_zero(self):
        self.assertEqual(price_return_percent('LONG', '100', '100.000001'), '+0.0000010%')


if __name__ == '__main__':
    unittest.main()
