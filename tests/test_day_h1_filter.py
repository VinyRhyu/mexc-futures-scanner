import unittest

from mexc_scanner.models import Candle, D
from scripts.audit_day_h1_filter import hourly_context, validate_aggregation


class H1FilterCausalityTests(unittest.TestCase):
    def bars(self, rising=True):
        closes = [D(100) + i * (1 if rising else -D('.1')) for i in range(241)]
        return [Candle(i*3600, 3600, c, c, c, c) for i, c in enumerate(closes)]

    def test_future_price_shock_cannot_change_a_past_decision(self):
        history = self.bars()
        at = history[-1].end + 10
        original = hourly_context(history, at)
        shock = Candle(history[-1].end, 3600, D(1), D(1), D(1), D(1))
        self.assertEqual(original, hourly_context(history+[shock], at))
        self.assertEqual(original['direction'], 'LONG')

    def test_unavailable_hour_is_excluded_until_the_availability_buffer_passes(self):
        history = self.bars()
        before = hourly_context(history, history[-1].end+9)
        after = hourly_context(history, history[-1].end+10)
        self.assertEqual(before['known_end'], history[-2].end)
        self.assertEqual(after['known_end'], history[-1].end)
        self.assertEqual(hourly_context(self.bars(False), history[-1].end+10)['direction'], 'SHORT')

    def test_inconsistent_hourly_prices_are_rejected(self):
        minute = [Candle(i*60, 60, D(100), D(100), D(100), D(100)) for i in range(60)]
        wrong = Candle(0, 3600, D(100), D(101), D(100), D(100))
        with self.assertRaisesRegex(ValueError, 'OHLC differ'):
            validate_aggregation([wrong], minute)


if __name__ == '__main__':
    unittest.main()
