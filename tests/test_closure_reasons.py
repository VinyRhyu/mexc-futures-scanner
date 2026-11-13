from copy import deepcopy
import unittest

from mexc_scanner.models import jsonable
from mexc_scanner.reporting import closed_plans_message, movement_message
from mexc_scanner.config import Config
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.telegram import drain_outbox
from tests.test_finance import NOW, context
from tests.test_watch_notifications import candidate


class ClosureReasonTests(unittest.TestCase):
    def closed(self, status, reason):
        p = context()[0]
        p.status, p.reason = status, reason
        before = deepcopy(jsonable(p))
        text = closed_plans_message([p], 'paper', NOW)
        self.assertEqual(jsonable(p), before)
        return text

    def test_weak_volume_is_not_mislabelled_as_timeout(self):
        text = self.closed('INVALIDADO', 'VOLUME_M1_INSUFICIENTE')
        self.assertIn('confirmação não aprovada', text)
        self.assertIn('volume do segundo candle', text)
        self.assertNotIn('prazo para nova entrada encerrado', text)

    def test_failed_breakout_shows_actual_reason(self):
        text = self.closed('INVALIDADO', 'SEGUNDO_M1_NAO_SUSTENTOU')
        self.assertIn('segundo fechamento M1 perdeu o nível', text)
        self.assertIn('confirmação não aprovada', text)

    def test_expiry_is_an_entry_deadline_not_an_exit_instruction(self):
        text = self.closed('EXPIRADO', 'PRAZO_ENCERRADO')
        self.assertIn('prazo para nova entrada encerrado', text)
        self.assertIn('A expiração não encerra uma posição já aberta', text)
        self.assertNotIn('plano invalidado', text)

    def test_target_touch_does_not_claim_an_executed_win(self):
        text = self.closed('EVENTO_PASSADO', 'ALVO_JA_ATINGIDO')
        self.assertIn('alvo do plano alcançado durante o acompanhamento', text)
        self.assertNotIn('lucro realizado', text)
        self.assertIn('Avisos de movimento não equivalem a entradas liberadas', text)

    def test_first_candle_message_makes_pending_confirmation_visible_in_title(self):
        p = candidate()
        text = movement_message(p, 'paper', NOW, 1, NOW + 60, illustrative_leverage=10)
        self.assertIn('AINDA SEM CONFIRMAÇÃO', text.splitlines()[0])

    def test_delivery_prioritizes_entry_then_fresh_movement_then_summary(self):
        state = initial_state(Config())
        queue_message(state, 'summary', 'summary', NOW - 10, NOW + 120)
        queue_message(state, 'movement', 'movement', NOW, NOW + 60)
        state['outbox']['movement']['movement_at'] = NOW
        queue_message(state, 'entry', 'entry', NOW, NOW + 60, 'ENTRY', NOW)
        sent = []
        def send(payload):
            sent.append(payload['text'])
            return {'ok': True, 'result': {'message_id': len(sent)}}
        drain_outbox(state, NOW, 'token', 'chat', send)
        self.assertEqual(sent, ['entry', 'movement', 'summary'])

    def test_expiry_is_rechecked_after_an_earlier_delivery_consumes_time(self):
        state = initial_state(Config())
        queue_message(state, 'movement', 'movement', NOW, NOW + 60)
        state['outbox']['movement']['movement_at'] = NOW
        queue_message(state, 'entry', 'entry', NOW, NOW + 120, 'ENTRY', NOW)
        current = [NOW]
        sent = []
        def send(payload):
            sent.append(payload['text'])
            current[0] += 61
            return {'ok': True, 'result': {'message_id': len(sent)}}
        result = drain_outbox(state, NOW, 'token', 'chat', send, clock=lambda: current[0])
        self.assertEqual(sent, ['entry'])
        self.assertEqual(result['expired'], 1)
        self.assertEqual(state['outbox']['movement']['attempts'], 0)
        self.assertEqual(state['outbox']['entry']['sent_at'], NOW + 61)


if __name__ == '__main__':
    unittest.main()
