"""Cash-at-entry checks must not include a future exit fee change."""
import unittest

from mexc_scanner.models import D
from scripts.audit_cost_correction import fee_reprice
from scripts.audit_wallet_entry import fixed_fill_stress


class CostSensitivityTests(unittest.TestCase):
    def wallet(self):
        trade = {key: D(value) for key, value in dict(
            quantity='1', entry='100', entry_mid='100', exit='200', tick='.001',
            margin='99', entry_cost='.2', exit_cost='.2', net='99.6').items()}
        trade.update(entry_kind='INTRABAR', limit_entry_no_slippage=True)
        return dict(initial=D(100), policy='LIMIT', trades=[trade])

    def test_fee_scenario_checks_cash_before_exit_fee(self):
        result = fee_reprice(self.wallet(), D(0), D('.01'))
        self.assertEqual(result['fixed_size_margin_violations'], 0)
        self.assertEqual(result['total_trading_fees'], D(2))
        self.assertEqual(result['final'], D('197.78'))

    def test_stress_checks_cash_before_exit_cost(self):
        protocol = dict(capital='100', costs=[dict(spread='.0002'),
            dict(taker_fee='.001', slippage_rate='.01', spread='.01')])
        result = fixed_fill_stress(self.wallet(), protocol)
        self.assertEqual(result['fixed_size_margin_violations'], 0)
        self.assertGreater(result['extra_cost'], D(2))
