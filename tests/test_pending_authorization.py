from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient
from mexc_scanner.engine import run_scan, _reconcile_pending_entries
from mexc_scanner.mexc import SourceError
from mexc_scanner.observability import Timings
from mexc_scanner.state import initial_state
from tests.test_finance import NOW


class OutsidePrice(DemoClient):
    def ticker(self, symbol):
        return {**super().ticker(symbol), 'bid1': '90', 'ask1': '90.01', 'lastPrice': '90'}


class MissingCandles(DemoClient):
    def candles(self, *args):
        raise SourceError('MISSING_CANDLES_TEST')


class MissingSource:
    def server_time(self):
        raise SourceError('MISSING_SOURCE_TEST')


class PendingAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.state = initial_state(self.config)
        self.client = DemoClient(NOW)
        self.events = []
        self.scan(self.client)
        self.entries = [m for m in self.state['outbox'].values() if m['category'] == 'ENTRY']
        self.assertTrue(self.entries)
        self.assertTrue(all(m['status'] == 'PENDING' for m in self.entries))

    def scan(self, client):
        def observer(event, **fields):
            self.events.append(deepcopy({'event': event, **fields}))
        report, _ = run_scan(client, self.config, self.state, {'DEMO'}, now=self.client.now,
            observer=observer, timings=Timings(emit=lambda _: None))
        return report

    def test_price_outside_plan_withdraws_even_a_still_fresh_pending_authorization(self):
        original_quotes = [m['quote_at'] for m in self.entries]
        report = self.scan(OutsidePrice(NOW))
        self.assertEqual(report['source_status'], 'OK')
        self.assertTrue(all(0 <= self.client.now-q < 60 for q in original_quotes))
        self.assertTrue(all(m['status'] == 'EXPIRED' for m in self.entries))
        self.assertTrue(any(e['event'] == 'authorization_withdrawn' for e in self.events))

    def test_partial_collection_failure_records_gate_and_withdraws_legacy_messages(self):
        for message in self.entries:
            for key in ('plan_id', 'variant', 'signal_at', 'symbol', 'side'):
                message.pop(key, None)
        report = self.scan(MissingCandles(NOW))
        self.assertEqual(report['source_status'], 'PARCIAL')
        self.assertTrue(all(m['status'] == 'EXPIRED' for m in self.entries))
        gates = [e for e in self.events if e['event'] == 'source_gate']
        self.assertTrue(gates)
        self.assertTrue(all(e['financial']['reasons'] == ['COLETA_NAO_VALIDADA_NESTA_RODADA'] for e in gates))
        self.assertTrue(any(e['event'] == 'financial_evaluation' and
            e['financial']['status'] == 'VIAVEL_SIMULADO' for e in self.events))

    def test_complete_source_failure_records_gate_and_withdraws_entries(self):
        report = self.scan(MissingSource())
        self.assertEqual(report['source_status'], 'FALHA')
        self.assertTrue(all(m['status'] == 'EXPIRED' for m in self.entries))
        gates = [e for e in self.events if e['event'] == 'source_gate']
        self.assertTrue(gates)
        self.assertTrue(all(e['financial']['reasons'] == ['FALHA_DA_FONTE_NESTA_RODADA'] for e in gates))

    def test_current_viable_pending_authorization_remains_available(self):
        _reconcile_pending_entries(self.state, self.client.now)
        self.assertTrue(all(m['status'] == 'PENDING' for m in self.entries))

    def test_previously_sent_message_is_never_reclassified_as_not_delivered(self):
        self.entries[0].update(status='SENT', sent_at=self.client.now)
        self.scan(OutsidePrice(NOW))
        self.assertEqual(self.entries[0]['status'], 'SENT')
        self.assertEqual(self.entries[0]['sent_at'], self.client.now)

    def test_unattempted_wallet_indication_is_released_when_withdrawn(self):
        message = self.entries[0]
        self.state['wallet']['pending'] = {'delivery_event_id': message['id']}
        self.scan(OutsidePrice(NOW))
        self.assertIsNone(self.state['wallet']['pending'])

    def test_ambiguous_prior_attempt_is_retained_for_reconciliation(self):
        message = self.entries[0]
        message['attempts'] = 1
        self.state['wallet']['pending'] = {'delivery_event_id': message['id']}
        self.scan(OutsidePrice(NOW))
        self.assertEqual(message['status'], 'EXPIRED')
        self.assertEqual(self.state['wallet']['pending']['delivery_event_id'], message['id'])
