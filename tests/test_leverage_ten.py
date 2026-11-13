from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from mexc_scanner.config import Config, load_config
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, DataError, jsonable
from mexc_scanner.reporting import movement_message
from mexc_scanner.state import atomic_json, initial_state, load_state, queue_message
from tests.test_finance import NOW, context
from tests.test_watch_notifications import candidate
from scripts.telegram_preview import preview_message


class LeverageTenTests(unittest.TestCase):
    def setUp(self):
        self.old = replace(Config(), minimum_rr='1').validate()
        self.new = replace(self.old, minimum_leverage=10).validate()

    def evaluate(self, cfg, side='LONG', stop=None, target=None, ceiling=None):
        p, v, c, t, b, f = context(side)
        if stop is not None:
            v.stop = D(stop)
        if target is not None:
            v.target = D(target)
        if ceiling is not None:
            c = replace(c, max_leverage=ceiling)
        return evaluate(p, v, c, D(1), t, b, f, NOW, cfg)

    def test_production_floor_and_cap_and_legacy_fingerprint(self):
        cfg = load_config('config/default.toml')
        self.assertEqual((cfg.minimum_leverage, cfg.max_leverage), (10, 20))
        self.assertEqual(self.old.fingerprint, 'be0d1a7ddb4e9d9aae15')
        for floor in (0, 21, True):
            with self.assertRaises(DataError):
                replace(self.old, minimum_leverage=floor).validate()
        with self.assertRaises(DataError):
            replace(self.old, minimum_leverage=10, max_leverage=5).validate()

    def test_floor_changes_margin_not_quantity_dollar_profit_or_dollar_risk(self):
        for side in ('LONG', 'SHORT'):
            old, new = self.evaluate(self.old, side), self.evaluate(self.new, side)
            self.assertEqual((old['status'], new['status']), ('VIAVEL_SIMULADO', 'VIAVEL_SIMULADO'))
            self.assertLess(old['leverage'], 10)
            self.assertEqual(new['leverage'], 10)
            for key in ('contracts', 'base_quantity', 'gain_usdt', 'loss_usdt', 'costs_usdt', 'net_rr', 'stop', 'target'):
                self.assertEqual(old[key], new[key], key)
            self.assertLess(new['margin_usdt'], old['margin_usdt'])
            self.assertLessEqual(new['loss_fraction'], D('.10'))

    def test_more_than_ten_is_used_only_when_margin_requires_it(self):
        old = self.evaluate(self.old, stop='99.5', target='102')
        new = self.evaluate(self.new, stop='99.5', target='102')
        self.assertEqual(new['status'], 'VIAVEL_SIMULADO')
        self.assertGreater(new['leverage'], 10)
        self.assertLessEqual(new['leverage'], 20)
        self.assertEqual(new['leverage'], old['leverage'])

    def test_contract_limit_is_not_raised_to_force_ten(self):
        result = self.evaluate(self.new, ceiling=5)
        self.assertEqual(result['status'], 'BLOQUEADA')
        self.assertIn('MARGEM_OU_TETO_DE_ALAVANCAGEM', result['reasons'])

    def test_wide_stop_is_blocked_when_ten_brings_liquidation_too_close(self):
        old = self.evaluate(self.old, stop='92', target='120')
        new = self.evaluate(self.new, stop='92', target='120')
        self.assertEqual(old['status'], 'VIAVEL_SIMULADO')
        self.assertEqual(new['status'], 'BLOQUEADA')
        self.assertIn('STOP_PROXIMO_DA_LIQUIDACAO', new['reasons'])
        self.assertEqual(new['stop'], D(92))

    def test_personal_real_gates_are_still_required(self):
        result = self.evaluate(replace(self.new, mode='real'))
        self.assertEqual(result['status'], 'BLOQUEADA')
        self.assertIn('VERIFICACOES_PARA_REAL_PENDENTES', result['reasons'])

    def test_movement_shows_gross_ten_x_as_illustrative_not_as_validated_roi(self):
        p = candidate()
        v = p.variants['ANTECIPADA']
        v.reference, v.stop, v.target = D(100), D('99.8'), D('100.5')
        before = deepcopy(jsonable(p))
        text = movement_message(p, 'paper', NOW, 1, NOW + 60, illustrative_leverage=10)
        self.assertIn('Stop do plano: 99.8 (-2.00% bruto em 10x)', text)
        self.assertIn('Alvo do plano: 100.5 (+5.00% bruto em 10x)', text)
        self.assertIn('custos e liquidação ainda não validados', text)
        self.assertIn('Movimento sem alavancagem: TP +0.50% • SL -0.20%.', text)
        self.assertEqual(before, jsonable(p))

    def test_telegram_preview_uses_configured_leverage_floor(self):
        text = preview_message(NOW)
        self.assertIn('• 10x', text)
        self.assertIn('líquido sobre a margem)', text)
        self.assertTrue(text.startswith('EXEMPLO FICTÍCIO'))


class LeverageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.old = replace(Config(), minimum_rr='1')
        self.new = replace(self.old, minimum_leverage=10).validate()
        self.state = initial_state(self.old)
        p, v, *_ = context()
        v.financial = {'status': 'VIAVEL_SIMULADO', 'leverage': 3}
        p.variants[v.kind] = v
        self.state['plans'][p.id] = jsonable(p)
        self.state['wallet'].update(balance='50', position={'recorded': True})
        self.state['journal'] = [{'event_id': 'old'}]
        self.state['journal_ids'] = ['old']
        self.state['minute_cursors'] = {'TEST_USDT': NOW - 60}
        queue_message(self.state, 'old-entry', 'old entry', NOW, NOW + 60, 'ENTRY', NOW)
        queue_message(self.state, 'old-movement', 'old movement', NOW, NOW + 60)
        self.state['outbox']['old-movement']['watch_symbol'] = 'TEST_USDT'
        queue_message(self.state, 'sent', 'sent entry', NOW, NOW + 60, 'ENTRY', NOW)
        self.state['outbox']['sent']['status'] = 'SENT'

    def load(self, state=None, cfg=None, migrate=True):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            atomic_json(path, self.state if state is None else state)
            return load_state(path, cfg or self.new, migrate_leverage_ten=migrate, migration_at=NOW)

    def test_requires_explicit_migration_flag(self):
        with self.assertRaises(DataError):
            self.load(migrate=False)

    def test_preserves_ledger_prices_cursors_and_sent_ids(self):
        old = deepcopy(self.state)
        new = self.load()
        for key in ('wallet', 'journal', 'journal_ids', 'minute_cursors'):
            self.assertEqual(new[key], old[key])
        for key, value in old['plans']['p'].items():
            if key != 'variants':
                self.assertEqual(new['plans']['p'][key], value)
        v0 = old['plans']['p']['variants']['ANTECIPADA']
        v1 = new['plans']['p']['variants']['ANTECIPADA']
        for key in v0.keys() - {'financial'}:
            self.assertEqual(v1[key], v0[key])
        self.assertEqual(new['outbox']['sent'], old['outbox']['sent'])
        self.assertEqual(new['outbox']['old-entry']['status'], 'EXPIRED')
        self.assertEqual(new['outbox']['old-movement']['status'], 'EXPIRED')
        self.assertEqual(v1['financial']['reasons'], ['POLITICA_ALAVANCAGEM_ATUALIZADA'])

    def test_idempotent_and_notify_loads_after_migration(self):
        first = self.load()
        self.assertEqual(first, self.load(state=first))
        self.assertEqual(first, self.load(state=first, migrate=False))
        self.assertEqual(len(first['config_migrations']), 1)

    def test_unrelated_configuration_and_real_mode_are_not_migrated(self):
        with self.assertRaises(DataError):
            self.load(cfg=replace(self.new, taker_fee='0'))
        with self.assertRaises(DataError):
            self.load(cfg=replace(self.new, mode='real'))

    def test_closed_historical_financial_result_is_preserved(self):
        self.state['plans']['p']['status'] = 'EXPIRADO'
        before = deepcopy(self.state['plans']['p'])
        self.assertEqual(self.load()['plans']['p'], before)


if __name__ == '__main__':
    unittest.main()
