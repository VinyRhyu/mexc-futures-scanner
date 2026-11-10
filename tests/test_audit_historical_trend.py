from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from mexc_scanner.config import Config
from mexc_scanner.models import Candle, Contract, D
from mexc_scanner.strategies import process_symbol
from scripts.audit_historical_trend import collect_signals, midnight, summarize


START = 1793502000


def data():
    q = [Candle(START - (480 - i) * 900, 900, D(100), D(101), D(99), D(100)) for i in range(480)]
    q[-1] = Candle(START - 900, 900, D(100), D('101.5'), D('100.2'), D('101.4'))
    q += [Candle(START, 900, D('101.4'), D('101.7'), D('101.3'), D('101.5')),
          Candle(START + 900, 900, D('101.5'), D(104), D(98), D(100))]
    h = [Candle(START - (240 - i) * 3600, 3600, D(100), D(101), D(99), D(100)) for i in range(240)]
    h += [Candle(START, 3600, D(100), D(200), D(90), D(180))]
    c = Contract('TEST_USDT', D('0.001'), D(1), D(1), D('0.001'), 20, D('0.005'), D('0.0004'))
    return q, h, c


class HistoricalTrendTests(unittest.TestCase):
    def test_generation_passes_only_closed_rolling_windows_to_strategy(self):
        q, h, c = data()
        def checked(symbol, known_q, known_h, plans, cursor, now, tick, config):
            self.assertEqual(len(known_q), 480)
            self.assertEqual(len(known_h), 240)
            self.assertTrue(all(x.end < now for x in known_q + known_h))
            return process_symbol(symbol, known_q, known_h, plans, cursor, now, tick, config)
        with patch('scripts.audit_historical_trend.process_symbol', side_effect=checked):
            rows = collect_signals('TEST_USDT', q, h, c, Config(), START, START + 1800)
        self.assertTrue(rows)
        self.assertEqual({r['kind'] for r in rows}, {'ANTECIPADA', 'CONFIRMADA'})

    def test_future_extremes_cannot_change_first_signal_levels(self):
        q, h, c = data()
        first = collect_signals('TEST_USDT', q, h, c, Config(), START, START + 900)
        changed = deepcopy(q)
        changed[-1] = Candle(START + 900, 900, D(100), D(500), D(1), D(200))
        other = collect_signals('TEST_USDT', changed, h, c, Config(), START, START + 900)
        self.assertEqual(first, other)
        self.assertEqual({r['signal'] for r in first}, {START})

    def test_signal_snapshots_survive_later_plan_invalidation(self):
        q, h, c = data()
        short = collect_signals('TEST_USDT', q, h, c, Config(), START, START + 900)
        longer = collect_signals('TEST_USDT', q, h, c, Config(), START, START + 2700)
        early = next(r for r in longer if r['kind'] == 'ANTECIPADA')
        self.assertEqual(short[0], early)

    def test_end_is_exclusive_and_signals_are_not_duplicated(self):
        q, h, c = data()
        rows = collect_signals('TEST_USDT', q, h, c, Config(), START, START + 1800)
        self.assertTrue(all(START <= r['signal'] < START + 1800 for r in rows))
        self.assertEqual(len(rows), len({(r['plan_id'], r['kind']) for r in rows}))

    def test_insufficient_hourly_history_is_rejected(self):
        q, h, c = data()
        with self.assertRaisesRegex(ValueError, 'insuficiente'):
            collect_signals('TEST_USDT', q, h[1:], c, Config(), START, START + 900)

    def test_filter_summary_tracks_discarded_wins_as_well_as_avoided_losses(self):
        rows = [
            {'aligned': False, 'structure_1h': 'BAIXA', 'baseline': {'entered_at': 'x', 'outcome': 'ALVO', 'net_r': '2'}},
            {'aligned': False, 'structure_1h': 'INDEFINIDA', 'baseline': {'entered_at': 'x', 'outcome': 'STOP', 'net_r': '-1'}},
            {'aligned': True, 'structure_1h': 'ALTA', 'baseline': {'entered_at': 'x', 'outcome': 'ABERTO', 'mark_to_market_r': '0.3'}}]
        s = summarize(rows)
        self.assertEqual(s['models']['ATUAL']['entries'], 3)
        self.assertEqual(s['models']['FILTRO_1H']['entries'], 1)
        self.assertEqual((s['removed_winners'], s['avoided_stops']), (1, 1))
        self.assertEqual(s['models']['FILTRO_1H']['closed'], 0)
        self.assertIsNone(s['models']['FILTRO_1H']['win_rate_closed'])

    def test_dates_mean_midnight_in_brasilia(self):
        stamp = midnight('2026-11-01')
        self.assertEqual(datetime.fromtimestamp(stamp, timezone.utc).isoformat(), '2026-11-01T03:00:00+00:00')


if __name__ == '__main__':
    unittest.main()
