from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient, api_bars
from mexc_scanner.engine import run_scan
from mexc_scanner.minute_breakout import MODEL
from mexc_scanner.models import D
from mexc_scanner.observability import DecisionLog, Timings
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.telegram import drain_outbox
from tests.test_finance import NOW
from tests.test_minute_breakout import T, candle


class MinuteAuditClient(DemoClient):
    def __init__(self, late=False):
        self.now = T + (250 if late else 130)
        config = Config()
        q_count = config.quarter_bars + config.replay_bars
        self.quarter = [candle(T-(q_count-i)*900, 900) for i in range(q_count)]
        self.hourly = [candle(T-(config.hourly_bars+2-i)*3600, 3600)
                       for i in range(config.hourly_bars+2)]
        count = 4 if late else 2
        self.minute = [candle(T-(120-count-i)*60) for i in range(120-count)]
        self.minute += [candle(T, op='101', hi='101.4', lo='100.5', cl='101.3'),
                        candle(T+60, op='101.3', hi='101.5', lo='101.25', cl='101.35', vol='50')]
        if late:
            self.minute += [candle(T+120, op='101.35', hi='101.5', lo='101.2', cl='101.3'),
                            candle(T+180, op='101.3', hi='101.5', lo='101.2', cl='101.3')]

    def candles(self, symbol, interval, count, now):
        return api_bars({'Min60': self.hourly, 'Min15': self.quarter, 'Min1': self.minute}[interval])

    def ticker(self, symbol):
        return {**super().ticker(symbol), 'lastPrice': '101.35', 'bid1': '101.34', 'ask1': '101.36'}

    def depth(self, symbol):
        return {'asks': [['101.36', '1000000', 1]], 'bids': [['101.34', '1000000', 1]],
                'timestamp': self.now*1000}


class ObservabilityTests(unittest.TestCase):
    def audit_minute_confirmation(self, late):
        client, config = MinuteAuditClient(late), Config(minimum_rr='1')
        state = initial_state(config)
        state.update(active_signal_model=MODEL, minute_activation={'DEMO_USDT': T})
        with tempfile.TemporaryDirectory() as temp:
            log = DecisionLog(temp, mode='paper', fingerprint=config.fingerprint)
            report, _ = run_scan(client, config, state, {'DEMO'}, now=client.now,
                signal_model=MODEL, observer=log.record, timings=Timings(emit=lambda _: None))
            self.assertEqual(report['source_status'], 'OK', report['diagnostics'])
            return log.pending

    def test_m1_late_confirmation_is_recorded_before_any_financial_overwrite(self):
        rows = self.audit_minute_confirmation(True)
        confirmed = [r for r in rows if r['event'] == 'technical_transition' and r['variant'] == 'CONFIRMADA']
        self.assertTrue(confirmed)
        self.assertEqual(confirmed[0]['reason'], 'GATILHO_M1_ATRASADO')
        self.assertEqual(confirmed[0]['signal_at'], T+120)
        self.assertEqual(D(confirmed[0]['stop']), D('100'))
        self.assertEqual(D(confirmed[0]['target']), D('103'))
        self.assertFalse(any(r['event'] == 'entry_queued' for r in rows))

    def test_m1_timely_confirmation_records_technical_and_financial_decisions(self):
        rows = self.audit_minute_confirmation(False)
        confirmed = [r for r in rows if r['variant'] == 'CONFIRMADA']
        self.assertTrue(any(r['event'] == 'technical_transition' for r in confirmed))
        self.assertTrue(any(r['event'] == 'financial_evaluation' for r in confirmed))
        for row in confirmed:
            self.assertEqual(row['signal_at'], T+120)
            self.assertEqual(D(row['stop']), D('100'))
            self.assertEqual(D(row['target']), D('103'))

    def test_monotonic_duration_survives_wall_clock_correction(self):
        rows = []
        wall = iter([NOW, NOW - 30])
        ticks = iter([100, 102.5])
        timings = Timings(clock=lambda: next(wall), monotonic=lambda: next(ticks), emit=rows.append)
        with timings.phase('test'):
            pass
        self.assertEqual(rows[-1]['duration_s'], 2.5)
        self.assertEqual(rows[-1]['status'], 'OK')

    def test_failed_phase_is_emitted_and_exception_is_preserved_without_message(self):
        rows = []
        timings = Timings(emit=rows.append)
        with self.assertRaisesRegex(RuntimeError, 'private-data'):
            with timings.phase('test'):
                raise RuntimeError('private-data')
        self.assertEqual(rows[-1]['status'], 'ERROR')
        self.assertEqual(rows[-1]['error_type'], 'RuntimeError')
        self.assertNotIn('private-data', json.dumps(rows))

    def test_default_phase_logger_flushes_each_event(self):
        with patch('builtins.print') as output:
            with Timings().phase('test'):
                pass
        self.assertEqual(output.call_count, 2)
        self.assertTrue(all(call.kwargs['flush'] for call in output.call_args_list))

    def test_ledger_snapshots_mutable_financial_values_and_appends(self):
        with tempfile.TemporaryDirectory() as temp:
            log = DecisionLog(temp, mode='paper', fingerprint='test', clock=lambda: NOW)
            decision = {'status': 'BLOQUEADA', 'reasons': ['RETORNO_RISCO_INSUFICIENTE'],
                        'entry_vwap': '100', 'private_payload': 'never-store'}
            log.record('financial_evaluation', plan_id='p', financial=decision)
            decision['reasons'].clear()
            decision['status'] = 'VIAVEL_SIMULADO'
            log.flush()
            path = next(Path(temp).glob('*.jsonl'))
            first_bytes = path.read_bytes()
            log.record('financial_evaluation', plan_id='p', financial=decision)
            log.flush()
            self.assertTrue(path.read_bytes().startswith(first_bytes))
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[0]['financial']['reasons'], ['RETORNO_RISCO_INSUFICIENTE'])
            self.assertEqual(rows[0]['financial']['status'], 'BLOQUEADA')
            self.assertEqual(rows[1]['financial']['status'], 'VIAVEL_SIMULADO')
            self.assertNotIn('never-store', path.read_text())
            self.assertFalse(log.pending)

    def test_ledger_rejects_message_and_recipient_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            log = DecisionLog(temp, mode='paper', fingerprint='test')
            for key in ('text', 'chat_id', 'telegram_ids', 'token', 'balance'):
                with self.assertRaises(ValueError):
                    log.record('test', **{key: 'private'})
            self.assertFalse(log.pending)
            self.assertFalse(list(Path(temp).iterdir()))

    def test_observer_preserves_scan_decisions_and_keeps_original_financial_evaluation(self):
        config = Config()
        with tempfile.TemporaryDirectory() as temp:
            audit = DecisionLog(temp, mode='paper', fingerprint=config.fingerprint)
            baseline, observed = initial_state(config), initial_state(config)
            quiet = lambda: Timings(emit=lambda _: None)
            run_scan(DemoClient(NOW), config, baseline, {'DEMO'}, now=NOW, timings=quiet())
            run_scan(DemoClient(NOW), config, observed, {'DEMO'}, now=NOW,
                     timings=quiet(), observer=audit.record)
            self.assertEqual(baseline, observed)
            for plan in observed['plans'].values():
                for variant in plan['variants'].values():
                    variant['financial'] = {'status': 'BLOQUEADA', 'reasons': ['LATER_ROUND']}
            audit.flush()
            rows = [json.loads(line) for line in next(Path(temp).glob('*.jsonl')).read_text().splitlines()]
            evaluations = [r for r in rows if r['event'] == 'financial_evaluation']
            self.assertTrue(evaluations)
            self.assertTrue(any(r['financial']['status'] == 'VIAVEL_SIMULADO' for r in evaluations))
            self.assertTrue(any(r['event'] == 'entry_queued' for r in rows))

    def test_delivery_audit_records_expiry_attempt_success_without_message_contents(self):
        state = initial_state(Config())
        from tests.test_closure_reasons import authorized_entry_text
        queue_message(state, 'expired', authorized_entry_text(), NOW, NOW, 'ENTRY', NOW)
        queue_message(state, 'entry', authorized_entry_text(), NOW, NOW+100, 'ENTRY', NOW)
        for key in ('expired', 'entry'):
            state['outbox'][key]['notification_format'] = 'entry_only_v2'
        with tempfile.TemporaryDirectory() as temp:
            audit = DecisionLog(temp, mode='paper', fingerprint='test')
            result = drain_outbox(state, NOW, 'fake-token', 'private-chat',
                transport=lambda _: {'ok': True, 'result': {'message_id': 123}}, observer=audit.record)
            audit.flush()
            text = next(Path(temp).glob('*.jsonl')).read_text()
            events = [json.loads(line)['event'] for line in text.splitlines()]
            self.assertEqual(events, ['delivery_expired', 'delivery_attempt', 'delivery_sent'])
            self.assertEqual(result['sent'], 1)
            for private in ('secret message', 'fake-token', 'private-chat', 'telegram_ids'):
                self.assertNotIn(private, text)

    def test_delivery_failure_retains_retry_and_records_only_sanitized_type(self):
        state = initial_state(Config())
        from tests.test_closure_reasons import authorized_entry_text
        queue_message(state, 'entry', authorized_entry_text(), NOW, NOW+100, 'ENTRY', NOW)
        state['outbox']['entry']['notification_format'] = 'entry_only_v2'
        with tempfile.TemporaryDirectory() as temp:
            audit = DecisionLog(temp, mode='paper', fingerprint='test')
            def failed(_):
                raise TimeoutError('private remote URL')
            result = drain_outbox(state, NOW, 'fake', 'fake', transport=failed, observer=audit.record)
            audit.flush()
            text = next(Path(temp).glob('*.jsonl')).read_text()
            self.assertEqual(result['failed'], 1)
            self.assertEqual(state['outbox']['entry']['status'], 'PENDING')
            self.assertEqual(state['outbox']['entry']['attempts'], 1)
            self.assertIn('delivery_failed', text)
            self.assertNotIn('private remote URL', text)


if __name__ == '__main__':
    unittest.main()
