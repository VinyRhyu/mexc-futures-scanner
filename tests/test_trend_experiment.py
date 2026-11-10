from pathlib import Path
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, D, jsonable
from mexc_scanner.state import atomic_json
from scripts import state_branch
from scripts.trend_experiment import BRANCH, RESERVED_SINCE, direction_at, eligible_variants, initialize, result, summarize, update
from tests.test_audit_pullback import setup


SIGNAL = 1794312000


def inputs(side='LONG', signal=SIGNAL):
    p, _ = setup(side)
    p.id = 'test-' + str(signal)
    p.formed_at, p.detected_at, p.expires_at = signal - 1800, signal, signal + 900
    p.variants['CONFIRMADA'].triggered_at = signal
    row = jsonable(p)
    h = [Candle(signal - (240 - i) * 3600, 3600, D(100), D(101), D(99), D(100)) for i in range(240)]
    # O update só lê candles diretamente; o validador é exercitado nos testes do scanner.
    snapshot = {'source_status': 'OK', 'market': {'TEST_USDT': {'hourly': jsonable(h), 'quarter': []}},
                'contracts': [{'symbol': 'TEST_USDT'}]}
    report = {'source_status': 'OK', 'analyzed_at': signal + 30, 'plans': [row]}
    return report, snapshot


class TrendExperimentTests(unittest.TestCase):
    def test_direction_uses_only_closed_hourly_bars_at_signal(self):
        h = [Candle(SIGNAL - (240 - i) * 3600, 3600, D(100), D(101), D(99), D(100)) for i in range(240)]
        h += [Candle(SIGNAL, 3600, D(100), D(120), D(99), D(120))]
        with patch('scripts.trend_experiment.structure', return_value='ALTA') as classifier:
            self.assertEqual(direction_at(h, SIGNAL), 'ALTA')
            passed, at = classifier.call_args.args
            self.assertEqual(len(passed), 240)
            self.assertTrue(all(c.end <= SIGNAL for c in passed))
            self.assertEqual(at, SIGNAL)

    def test_alignment_is_symmetric_and_undefined_is_excluded(self):
        cfg = Config()
        for side, direction, expected in [('LONG', 'ALTA', True), ('LONG', 'BAIXA', False),
                ('SHORT', 'BAIXA', True), ('SHORT', 'ALTA', False), ('LONG', 'INDEFINIDA', False),
                ('SHORT', 'DESCONHECIDA', False)]:
            with self.subTest(side=side, direction=direction):
                report, snapshot = inputs(side)
                state = initialize(SIGNAL - 120, cfg, 'code')
                with patch('scripts.trend_experiment.direction_at', return_value=direction):
                    updated = update(state, report, snapshot, cfg, SIGNAL + 60, 'code')
                self.assertEqual(next(iter(updated['cases'].values()))['aligned'], expected)
                self.assertEqual(state['cases'], {})

    def test_protocol_separates_old_reserved_and_future_samples(self):
        cfg = Config()
        protocol = initialize(SIGNAL + 60, cfg, 'code')
        report, snapshot = inputs()
        with patch('scripts.trend_experiment.direction_at', return_value='ALTA'):
            updated = update(protocol, report, snapshot, cfg, SIGNAL + 100, 'code')
        c = next(iter(updated['cases'].values()))
        self.assertEqual(c['cohort'], 'RESERVADA_PRELIMINAR')
        report, snapshot = inputs(signal=SIGNAL + 900)
        with patch('scripts.trend_experiment.direction_at', return_value='ALTA'):
            updated = update(updated, report, snapshot, cfg, SIGNAL + 960, 'code')
        self.assertEqual(cohort_counts(updated), {'RESERVADA_PRELIMINAR': 1, 'PROSPECTIVA': 1})

    def test_levels_and_regime_are_not_rewritten_after_first_capture(self):
        cfg = Config()
        report, snapshot = inputs()
        state = initialize(SIGNAL - 120, cfg, 'code')
        with patch('scripts.trend_experiment.direction_at', return_value='ALTA'):
            first = update(state, report, snapshot, cfg, SIGNAL + 60, 'code')
        report['plans'][0]['variants']['CONFIRMADA']['target'] = '999'
        with patch('scripts.trend_experiment.direction_at', return_value='BAIXA') as changed:
            second = update(first, report, snapshot, cfg, SIGNAL + 100, 'code')
        a, b = next(iter(first['cases'].values())), next(iter(second['cases'].values()))
        self.assertEqual(a['plan'], b['plan'])
        self.assertEqual(a['structure_1h'], b['structure_1h'])
        changed.assert_not_called()

    def test_changed_calculator_pauses_instead_of_resetting_trial(self):
        cfg = Config()
        report, snapshot = inputs()
        state = initialize(SIGNAL - 120, cfg, 'old-code')
        with self.assertRaisesRegex(ValueError, 'pausado'):
            update(state, report, snapshot, cfg, SIGNAL + 60, 'new-code')
        self.assertEqual(state['protocol']['calculation_hash'], 'old-code')

    def test_only_new_breakouts_are_enrolled(self):
        report, _ = inputs(signal=RESERVED_SINCE)
        self.assertEqual(list(eligible_variants(report, SIGNAL + 900)), [])
        report, _ = inputs()
        report['plans'][0]['strategy'] = 'CONTINUACAO'
        self.assertEqual(list(eligible_variants(report, SIGNAL + 900)), [])

    def test_no_new_candidates_after_end(self):
        report, _ = inputs()
        self.assertEqual(list(eligible_variants(report, SIGNAL)), [])

    def test_summary_counts_both_removed_winners_and_avoided_losses(self):
        state = initialize(SIGNAL - 120, Config(), 'code')
        for name, outcome, value in [('winner', 'ALVO', '2.2'), ('loser', 'STOP', '-1')]:
            state['cases'][name] = {'cohort': 'PROSPECTIVA', 'kind': 'CONFIRMADA', 'timely_capture': True,
                'structure_1h': 'INDEFINIDA', 'aligned': False,
                'baseline': {'outcome': outcome, 'window_complete': True, 'entered_at': 'test', 'net_r': value}}
        s = summarize(state, 'PROSPECTIVA', 'CONFIRMADA', complete_only=True)
        self.assertEqual(s['models']['ATUAL']['entries'], 2)
        self.assertEqual(s['models']['FILTRO_1H']['entries'], 0)
        self.assertEqual((s['removed_winners'], s['avoided_stops']), (1, 1))

    def test_late_captures_are_separated_from_primary_prospective_results(self):
        state = initialize(SIGNAL - 120, Config(), 'code')
        state['cases']['late'] = {'cohort': 'PROSPECTIVA', 'kind': 'CONFIRMADA', 'timely_capture': False,
            'structure_1h': 'ALTA', 'aligned': True, 'baseline': {'outcome': 'BLOQUEADA', 'window_complete': True}}
        s = result(state)['summaries']['PROSPECTIVA']['CONFIRMADA']
        self.assertEqual(s['complete']['candidates'], 1)
        self.assertEqual(s['timely_complete']['candidates'], 0)

    def test_state_is_saved_only_to_dedicated_branch(self):
        from tests.test_git_persistence import GitPersistenceTests
        fixture = GitPersistenceTests('test_state_survives_new_checkout_without_using_cache')
        fixture.setUp()
        try:
            with patch.object(state_branch, 'BRANCH', BRANCH), patch.object(state_branch, 'BASE_FILE', Path('.trial-base')):
                directory = Path('.trial')
                state_branch.restore(directory)
                atomic_json(directory / 'state.json', initialize(SIGNAL, Config(), 'code'))
                state_branch.save(directory)
                self.assertTrue(state_branch.git('ls-remote', '--heads', 'origin', 'refs/heads/' + BRANCH).stdout)
                self.assertFalse(state_branch.git('ls-remote', '--heads', 'origin', 'refs/heads/scanner-state').stdout)
        finally:
            fixture.tearDown()


def cohort_counts(state):
    from collections import Counter
    return dict(Counter(c['cohort'] for c in state['cases'].values()))


if __name__ == '__main__':
    unittest.main()
