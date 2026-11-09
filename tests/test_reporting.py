from copy import deepcopy
import unittest

from mexc_scanner.config import Config
from mexc_scanner.engine import _queue_transitions
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, jsonable, stable_id
from mexc_scanner.reporting import plan_message
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.telegram import drain_outbox
from scripts.telegram_preview import preview_message
from tests.test_finance import NOW, context


class MessageTests(unittest.TestCase):
    def ready(self):
        p, v, c, ticker, book, funding = context()
        p.status = "ATIVO"
        v.financial = evaluate(p, v, c, D(1), ticker, book, funding, NOW, Config())
        p.variants[v.kind] = v
        return p, v

    def test_formats_estimates_without_changing_executable_prices_or_state(self):
        p, v = self.ready()
        v.entry_low = v.financial['entry_low'] = D('0.0000000123456789')
        before = deepcopy(jsonable(p))
        text = plan_message(p, 'paper', NOW, v)
        self.assertIn('0.0000000123456789', text)
        self.assertIn('Taxa por execução: 0.06%', text)
        self.assertIn('% da banca', text)
        self.assertIn('SIMULAÇÃO', text)
        self.assertNotIn('VIAVEL_SIMULADO', text)
        self.assertNotIn('TAXA_PESSOAL_NAO_VERIFICADA', text)
        self.assertEqual(before, jsonable(p))

    def test_blocked_signal_is_never_presented_as_ready(self):
        p, v = self.ready()
        v.financial = {'status': 'BLOQUEADA', 'reasons': ['PRECO_FORA_DO_PLANO']}
        text = plan_message(p, 'paper', NOW, v)
        self.assertIn('ENTRADA BLOQUEADA', text)
        self.assertIn('preço está fora da faixa', text)
        self.assertNotIn('GATILHO VÁLIDO', text)
        self.assertNotIn('PRECO_FORA_DO_PLANO', text)

    def test_real_wallet_restriction_overrides_ready_title(self):
        p, v = self.ready()
        v.financial['status'] = 'VIAVEL_REAL'
        text = plan_message(p, 'real', NOW, v, restriction='Já existe uma posição registrada.')
        self.assertIn('APENAS ACOMPANHAMENTO', text)
        self.assertNotIn('ENTRADA VALIDADA', text)
        self.assertNotIn('Quantidade:', text)

    def test_expiration_is_compact_and_does_not_ask_for_future_confirmation(self):
        p, v = self.ready()
        p.status, p.reason = 'EXPIRADO', 'PRAZO_ENCERRADO'
        text = plan_message(p, 'paper', NOW, v)
        self.assertIn('PLANO EXPIRADO', text)
        self.assertIn('não encerra uma posição', text)
        self.assertNotIn('Antecipada:', text)
        self.assertNotIn('Confirmada:', text)
        self.assertLess(len(text), 500)

    def test_short_preparation_uses_downward_reaction_and_approximate_region(self):
        p = context('SHORT')[0]
        p.lower, p.upper = D('0.065969071722553469786'), D('0.066170928277446530213')
        text = plan_message(p, 'paper', NOW)
        self.assertIn('≈ 0.0659691 a 0.0661709', text)
        self.assertIn('fecha além da mínima', text)
        self.assertIn('abaixo', text)
        self.assertIn('independente', text)

    def test_closures_only_notify_previously_seen_plans_in_one_message(self):
        state, config = initial_state(Config()), Config()
        previous = {}
        for index in range(3):
            p, _ = self.ready()
            p.id = 'p' + str(index)
            previous[p.id] = jsonable(p)
            p.status, p.reason = 'EXPIRADO', 'PRAZO_ENCERRADO'
            state['plans'][p.id] = jsonable(p)
            if index < 2:
                event = stable_id(p.id, 'POSSIVEL')
                queue_message(state, event, 'previous', NOW - 1, NOW + 500)
                state['outbox'][event]['status'] = 'SENT'
        _queue_transitions(state, previous, config, NOW)
        pending = [m for m in state['outbox'].values() if m['status'] == 'PENDING']
        self.assertEqual(len(pending), 1)
        self.assertIn('Plano: p0', pending[0]['text'])
        self.assertIn('Plano: p1', pending[0]['text'])
        self.assertNotIn('Plano: p2', pending[0]['text'])

    def test_entry_delivery_precedes_information_messages(self):
        state = initial_state(Config())
        queue_message(state, 'info', 'summary', NOW, NOW + 500)
        queue_message(state, 'entry', 'entry', NOW, NOW + 500, 'ENTRY', NOW)
        sent = []
        def transport(payload):
            sent.append(payload['text'])
            return {'ok': True, 'result': {'message_id': len(sent)}}
        drain_outbox(state, NOW, 'token', 'chat', transport)
        self.assertEqual(sent, ['entry', 'summary'])

    def test_preview_is_explicitly_fictional_and_fits_one_message(self):
        text = preview_message(NOW)
        self.assertTrue(text.startswith('EXEMPLO FICTÍCIO — NÃO OPERAR'))
        self.assertIn('DEMO/USDT', text)
        self.assertLess(len(text), 3500)
