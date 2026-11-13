import unittest
from copy import deepcopy

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, D
from scripts.audit_rr_delivery import delayed
from tests.test_audit_minute_execution import minutes, plan
from tests.test_audit_pullback import SIGNAL


class DeliveryDelayTests(unittest.TestCase):
    def fixture(self):
        row, contract = plan()
        row['expires_at'] = SIGNAL + 120
        return row, contract, minutes()

    def test_one_minute_remains_within_expiry(self):
        row, contract, bars = self.fixture()
        self.assertIn('entered_at', delayed(row, bars, contract, Config(), 60))

    def test_two_minutes_expire_before_new_entry(self):
        row, contract, bars = self.fixture()
        self.assertEqual(delayed(row, bars, contract, Config(), 120), {'outcome': 'EXPIRADO_PRAZO_M1'})

    def test_three_minutes_expire_before_new_entry(self):
        row, contract, bars = self.fixture()
        self.assertEqual(delayed(row, bars, contract, Config(), 180), {'outcome': 'EXPIRADO_PRAZO_M1'})

    def test_counterfactual_is_explicit_and_does_not_mutate_plan(self):
        row, contract, bars = self.fixture()
        before = deepcopy(row)
        self.assertIn('entered_at', delayed(row, bars, contract, Config(), 180, enforce_expiry=False))
        self.assertEqual(row, before)

    def test_target_touched_in_wait_is_not_a_delayed_win(self):
        row, contract, bars = self.fixture()
        bars[0] = Candle(SIGNAL, 60, D(101), D(109), D('100.9'), D(108))
        r = delayed(row, bars, contract, Config(), 60)
        self.assertEqual(r['outcome'], 'SEM_ENTRADA_ALVO_ANTES')
        self.assertNotIn('entered_at', r)

    def test_stop_touched_in_wait_cancels(self):
        row, contract, bars = self.fixture()
        bars[0] = Candle(SIGNAL, 60, D(101), D('101.2'), D(98), D(100))
        self.assertEqual(delayed(row, bars, contract, Config(), 60)['outcome'], 'SEM_ENTRADA_STOP_ANTES')

    def test_missing_data_not_counted_as_an_opportunity(self):
        row, contract, bars = self.fixture()
        del bars[20]
        self.assertEqual(delayed(row, bars, contract, Config(), 60)['outcome'], 'SEM_DADOS')


if __name__ == '__main__':
    unittest.main()
