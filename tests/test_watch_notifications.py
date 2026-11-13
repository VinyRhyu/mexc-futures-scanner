from copy import deepcopy
from dataclasses import replace
import unittest

from mexc_scanner.config import Config
from mexc_scanner.engine import _queue_transitions, run_scan
from mexc_scanner.mexc import SourceError
from mexc_scanner.minute_breakout import MODEL
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, jsonable, stable_id
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.watch_notifications import STRATEGY
from tests.test_finance import NOW, context


def candidate(side='LONG', symbol='TEST_USDT', phase='possible'):
    p, v, c, t, b, f = context(side)
    p.id = symbol + '-' + side
    p.symbol, p.strategy, p.status = symbol, STRATEGY, 'POSSIVEL'
    p.level = p.upper if side == 'LONG' else p.lower
    if phase == 'waiting':
        v.status = 'AGUARDANDO_CONFIRMACAO'
        p.entry_started_at = NOW - 5
        p.variants[v.kind] = v
    if phase in ('blocked', 'ready'):
        p.status, v.kind = 'ATIVO', 'CONFIRMADA'
        v.financial = (evaluate(p, v, c, D(1), t, b, f, NOW, Config()) if phase == 'ready'
                       else {'status': 'BLOQUEADA', 'reasons': ['PRECO_FORA_DO_PLANO']})
        p.variants[v.kind] = v
    return p


class WatchNotificationsTests(unittest.TestCase):
    def state(self, *plans):
        state = initial_state(Config())
        state['plans'] = {p.id: jsonable(p) for p in plans}
        return state

    def pending(self, state, category=None):
        return [m for m in state['outbox'].values() if m['status'] == 'PENDING'
                and (category is None or m['category'] == category)]

    def test_opposite_plans_become_one_conditional_watch_without_touching_analysis(self):
        state = self.state(candidate(), candidate('SHORT'))
        before = deepcopy(state['plans'])
        _queue_transitions(state, {}, Config(), NOW)
        messages = self.pending(state)
        self.assertEqual(len(messages), 1)
        text = messages[0]['text']
        self.assertTrue(text.startswith('👀 AGUARDANDO ENTRADA'))
        self.assertIn('Direção indefinida', text)
        self.assertIn('LONG somente se', text)
        self.assertIn('SHORT somente se', text)
        self.assertIn('Sem entrada liberada', text)
        self.assertNotIn('GATILHO VÁLIDO PARA SIMULAR', text)
        self.assertEqual(messages[0]['category'], 'INFO')
        self.assertEqual(state['plans'], before)

    def test_existing_active_plans_also_get_the_new_watch(self):
        state = self.state(candidate(), candidate('SHORT'))
        _queue_transitions(state, deepcopy(state['plans']), Config(), NOW)
        self.assertEqual(len(self.pending(state)), 1)

    def test_sent_watch_does_not_repeat_every_scan(self):
        state = self.state(candidate(), candidate('SHORT'))
        _queue_transitions(state, {}, Config(), NOW)
        for m in self.pending(state):
            m['status'] = 'SENT'
        _queue_transitions(state, deepcopy(state['plans']), Config(), NOW + 1)
        self.assertEqual(self.pending(state), [])

    def test_global_limit_does_not_starve_later_symbols(self):
        state = self.state(*(candidate(symbol=f'COIN{i}_USDT') for i in range(5)))
        cfg = replace(Config(), max_alerts=2)
        totals = []
        for _ in range(3):
            _queue_transitions(state, deepcopy(state['plans']), cfg, NOW)
            totals.append(len(self.pending(state)))
            for m in self.pending(state):
                m['status'] = 'SENT'
        self.assertEqual(totals, [2, 2, 1])
        self.assertEqual(len(state['outbox']), 5)

    def test_first_m1_is_only_a_watch_and_shows_missing_confirmation(self):
        state = self.state(candidate(phase='waiting'), candidate('SHORT'))
        _queue_transitions(state, {}, Config(), NOW)
        m = self.pending(state)[0]
        self.assertIn('Possível LONG', m['text'])
        self.assertIn('Falta o segundo fechamento', m['text'])
        self.assertNotIn('SHORT somente se', m['text'])
        self.assertIn('Stop do plano:', m['text'])
        self.assertEqual(self.pending(state, 'ENTRY'), [])

    def test_blocked_confirmation_remains_information_not_an_entry(self):
        state = self.state(candidate(phase='blocked'), candidate('SHORT'))
        _queue_transitions(state, {}, Config(), NOW)
        m = self.pending(state)[0]
        self.assertIn('entrada bloqueada', m['text'])
        self.assertIn('preço está fora da faixa', m['text'])
        self.assertEqual(self.pending(state, 'ENTRY'), [])

    def test_actual_viable_entry_keeps_its_original_event_and_suppresses_watch(self):
        p = candidate(phase='ready')
        state = self.state(p, candidate('SHORT'))
        _queue_transitions(state, {}, Config(), NOW)
        m = self.pending(state, 'ENTRY')
        self.assertEqual(len(m), 1)
        self.assertEqual(m[0]['id'], stable_id(p.id, 'CONFIRMADA', 'GATILHO', 'paper'))
        self.assertIn('GATILHO VÁLIDO PARA SIMULAR', m[0]['text'])
        self.assertEqual(self.pending(state, 'INFO'), [])

    def test_unverified_symbol_does_not_generate_a_watch(self):
        state = self.state(candidate())
        _queue_transitions(state, {}, Config(), NOW, watch_symbols=set())
        self.assertEqual(self.pending(state), [])

    def test_source_failure_cannot_deliver_old_pending_watches(self):
        state = self.state(candidate())
        state['active_signal_model'] = MODEL
        _queue_transitions(state, {}, Config(), NOW)
        watch_id = self.pending(state)[0]['id']
        class FailedSource:
            def server_time(self):
                raise SourceError('Synthetic source failure')
        report, _ = run_scan(FailedSource(), Config(), state, {'TEST'}, now=NOW, signal_model=MODEL)
        self.assertEqual(report['source_status'], 'FALHA')
        self.assertEqual(state['outbox'][watch_id]['status'], 'EXPIRED')

    def test_old_pending_individual_messages_expire_but_sent_ones_remain(self):
        a, b = candidate(), candidate('SHORT')
        state = self.state(a, b)
        old_a, old_b = stable_id(a.id, 'POSSIVEL'), stable_id(b.id, 'POSSIVEL')
        for key in (old_a, old_b):
            queue_message(state, key, 'old format', NOW, NOW + 500)
        state['outbox'][old_b]['status'] = 'SENT'
        _queue_transitions(state, {}, Config(), NOW)
        self.assertEqual(state['outbox'][old_a]['status'], 'EXPIRED')
        self.assertEqual(state['outbox'][old_b]['status'], 'SENT')
        self.assertEqual(len(self.pending(state)), 1)

    def test_new_watch_stage_retires_older_pending_watch(self):
        p = candidate()
        state = self.state(p)
        _queue_transitions(state, {}, Config(), NOW)
        old = self.pending(state)[0]['id']
        state['plans'][p.id] = jsonable(candidate(phase='waiting'))
        _queue_transitions(state, {}, Config(), NOW + 1)
        self.assertEqual(state['outbox'][old]['status'], 'EXPIRED')
        self.assertEqual(len(self.pending(state)), 1)
        self.assertIn('primeiro fechamento', self.pending(state)[0]['text'])

    def test_group_watch_closure_is_still_reported(self):
        state = self.state(candidate(), candidate('SHORT'))
        _queue_transitions(state, {}, Config(), NOW)
        for m in self.pending(state):
            m['status'] = 'SENT'
        previous = deepcopy(state['plans'])
        for p in state['plans'].values():
            p['status'], p['reason'] = 'EXPIRADO', 'PRAZO_ENCERRADO'
        _queue_transitions(state, previous, Config(), NOW + 1)
        self.assertEqual(len(self.pending(state)), 1)
        self.assertIn('ATUALIZAÇÃO DOS PLANOS', self.pending(state)[0]['text'])

    def test_closed_and_time_expired_plans_are_not_reintroduced(self):
        a, b = candidate(), candidate('SHORT')
        a.status, b.expires_at = 'INVALIDADO', NOW
        state = self.state(a, b)
        _queue_transitions(state, {}, Config(), NOW)
        self.assertEqual(self.pending(state), [])

    def test_all_watch_stages_fit_a_single_telegram_message(self):
        for phase in ('possible', 'waiting', 'blocked'):
            state = self.state(candidate(phase=phase), candidate('SHORT', phase=phase))
            _queue_transitions(state, {}, Config(), NOW)
            self.assertLess(len(self.pending(state)[0]['text']), 3500)


if __name__ == '__main__':
    unittest.main()
