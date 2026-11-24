import unittest

from mexc_scanner.models import DataError
from scripts.research_pre_breakout_coverage import collect, coverage, parse_window


def payload(times):
    n = len(times)
    return {"time": times, "open": [100]*n, "high": [102]*n,
            "low": [99]*n, "close": [101]*n, "vol": [5]*n}


class CoverageTests(unittest.TestCase):
    def test_window_excludes_padding_and_end(self):
        bars, repeats = parse_window(payload([0,60,120,180]),60,180)
        self.assertEqual(set(bars), {60,120})
        self.assertEqual(repeats,0)

    def test_identical_duplicate(self):
        bars,repeats = parse_window(payload([60,60]),60,120)
        self.assertEqual((len(bars),repeats),(1,1))

    def test_conflicting_duplicate(self):
        data = payload([60,60])
        data["close"][1] = 100
        with self.assertRaises(DataError):
            parse_window(data,60,120)

    def test_gap_and_synchronization(self):
        r = coverage({0,60,180},0,86400,{0,180})
        self.assertEqual(r["missing"],1437)
        self.assertEqual(r["gap_count"],2)
        self.assertEqual(r["longest_gap_minutes"],1436)
        self.assertEqual(r["btc_synchronized"],2)

    def test_collect_keeps_partial_data_and_logs_failed_chunk(self):
        class Fake:
            def candles(self,symbol,interval,count,now):
                if now == 250:
                    raise ValueError("failure")
                return payload([0,60,120])
        bars,errors,_ = collect(Fake(),"BTC_USDT",0,240,2)
        self.assertEqual(set(bars),{0,60})
        self.assertEqual(len(errors),1)


if __name__ == "__main__":
    unittest.main()
