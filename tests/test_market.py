import unittest

from mexc_scanner.market import aggregate_two_hours, atr, parse_candles, pivots, select_universe
from mexc_scanner.models import Candle, D, DataError
from mexc_scanner.demo import api_bars


def bar(ts, tf=900, high="101", low="99"):
    return Candle(ts, tf, D(100), D(high), D(low), D(100), D(10))


class MarketTests(unittest.TestCase):
    def test_open_candle_excluded_and_closure_tolerance(self):
        rows = api_bars([bar(0), bar(900)])
        self.assertEqual(len(parse_candles(rows, 900, 1809)), 1)
        self.assertEqual(len(parse_candles(rows, 900, 1810)), 2)

    def test_conflicting_duplicate_rejected(self):
        rows = api_bars([bar(0), bar(0, high="102")])
        with self.assertRaises(DataError):
            parse_candles(rows, 900, 910)

    def test_identical_duplicate_is_idempotent(self):
        self.assertEqual(len(parse_candles(api_bars([bar(0), bar(0)]), 900, 910)), 1)

    def test_gap_not_filled(self):
        with self.assertRaises(DataError):
            parse_candles(api_bars([bar(0), bar(1800)]), 900, 2710)

    def test_stale_last_closed_bar_rejected(self):
        with self.assertRaises(DataError):
            parse_candles(api_bars([bar(0)]), 900, 2710)

    def test_two_hours_only_complete_utc_pairs(self):
        result = aggregate_two_hours([bar(3600, 3600), bar(7200, 3600), bar(10800, 3600)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ts, 7200)
        self.assertEqual(result[0].volume, 20)

    def test_pivot_is_unknown_until_two_future_bars_close(self):
        rows = [bar(i * 3600, 3600, str(100 + h)) for i, h in enumerate([1, 2, 5, 2, 1])]
        self.assertEqual(pivots(rows, 4 * 3600), [])
        known = pivots(rows, 5 * 3600)
        self.assertEqual(known[0].price, 105)
        self.assertEqual(known[0].known_at, 5 * 3600)

    def test_wilder_atr_warmup(self):
        result = atr([bar(i * 900) for i in range(16)])
        self.assertTrue(all(x is None for x in result[:13]))
        self.assertEqual(result[13], 2)

    def test_turnover_not_contract_count_orders_universe(self):
        contracts = [{"symbol": f"{s}_USDT", "baseCoin": s, "state": 0, "settleCoin": "USDT", "quoteCoin": "USDT"} for s in ["A", "B", "GOLD"]]
        tickers = [{"symbol": "A_USDT", "amount24": "6000000", "volume24": "10000000"},
                   {"symbol": "B_USDT", "amount24": "9000000", "volume24": "1"},
                   {"symbol": "GOLD_USDT", "amount24": "999999999"}]
        chosen, excluded = select_universe(contracts, tickers, {"A", "B"}, D(5000000), 1)
        self.assertEqual(chosen[0]["symbol"], "B_USDT")
        self.assertIn("CLASSIFICACAO_PENDENTE", [r["reason"] for r in excluded])
