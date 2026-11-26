from unittest import TestCase
from unittest.mock import patch

from mexc_scanner.models import Candle, D
from mexc_scanner import paper_btc_reversal as paper


class PaperReversalTests(TestCase):
    t = 10 * paper.CADENCE
    contract = {
        "priceUnit": ".01", "contractSize": "1", "volUnit": ".01", "minVol": ".01",
        "maintenanceMarginRate": ".006", "liquidationFeeRate": ".001",
    }
    candidate = {"symbol": "ETH_USDT", "side": 1, "stop_distance": .02, "score": 2.}

    def candle(self, t, o=100, h=101, l=99, c=100):
        return Candle(t, paper.HOUR, D(o), D(h), D(l), D(c))

    def decision(self, t=None):
        t = self.t if t is None else t
        return {**self.candidate, "decision": t, "entry_at": t + paper.HOUR,
                "observed_at": t + 500, "status": "REGISTRADO", "contract": self.contract}

    def test_only_frozen_direction_and_recovery_are_selected(self):
        btc = [self.candle(i * paper.HOUR) for i in range(paper.HISTORY)]
        eth = btc.copy()
        eth[-25] = self.candle(eth[-25].ts, 115, 117, 114, 116)
        eth[-5] = self.candle(eth[-5].ts, 99, 100, 98, 99)
        series = {"BTC": btc, "ETH": eth}
        self.assertEqual(paper.choose_candidate(series, {"BTC": 8e6, "ETH": 9e6})["side"], 1)
        self.assertIsNone(paper.choose_candidate(series, {"BTC": 8e6, "ETH": 3e6}))

    def test_marked_at_stop_before_same_bar_target(self):
        signal = self.decision()
        position = signal | paper.setup(signal, 100, self.contract, 1000)
        t = position["entry_at"]
        result, _ = paper.outcome(position, [self.candle(t, 100, 104, 97, 100)],
                                  [self.candle(t)], {})
        self.assertEqual(result[2], "STOP")
        self.assertEqual(result[0], t + paper.HOUR)
        self.assertLess(result[1], -.02)
        self.assertLessEqual(position["notional"] * .023, 8)

    def test_funding_is_counted_only_during_the_position(self):
        signal = self.decision()
        position = signal | paper.setup(signal, 100, self.contract, 1000)
        t = signal["entry_at"]
        price = [self.candle(t), self.candle(t + paper.HOUR, 100, 104, 99, 100)]
        fair = [self.candle(t), self.candle(t + paper.HOUR)]
        result, _ = paper.outcome(position, price, fair, {t:.05, t + paper.HOUR:.001})
        self.assertEqual(result[2], "ALVO")
        self.assertAlmostEqual(result[3], .001)

    def test_past_decision_never_runs_market_discovery(self):
        state = paper.new_state(self.t + 20)
        with patch.object(paper, "discover") as discover:
            paper.advance(state, None, self.t + paper.HOUR)
        discover.assert_not_called()
        self.assertEqual(state["decisions"][0]["status"], "PERDIDO_POR_ATRASO")

    def test_signal_is_recorded_once_before_the_entry(self):
        state = paper.new_state(self.t + 20)
        market = type("Market", (), {"server_time": lambda _: self.t + 50})()
        with patch.object(paper, "discover", return_value=self.candidate) as discover, \
                patch.object(paper, "snapshot_contract", return_value=self.contract):
            paper.advance(state, market, self.t + 40)
            paper.advance(state, market, self.t + 40)
        discover.assert_called_once_with(market, self.t)
        [row] = state["decisions"]
        self.assertEqual(row["status"], "REGISTRADO")
        self.assertLess(row["observed_at"], row["entry_at"])
        self.assertIsNone(state["position"])

    def test_entry_candle_must_close_and_reconciliation_is_idempotent(self):
        test = self

        class Market:
            def closed_hours(self, symbol, count, end, fair=False):
                assert symbol == "ETH_USDT" and count == 1
                t = end - paper.HOUR
                return [test.candle(t)] if fair else [test.candle(t, 100, 104, 99, 100)]

            def funding_rates(self, symbol, start, end):
                return {}

        state = paper.new_state(self.t + 20)
        state["decisions"].append(self.decision())
        market = Market()
        paper.reconcile(state, market, self.t + paper.HOUR + 100)
        self.assertEqual(state["trades"], [])
        paper.reconcile(state, market, self.t + paper.HOUR * 2 + 20)
        paper.reconcile(state, market, self.t + paper.HOUR * 2 + 20)
        self.assertEqual(len(state["trades"]), 1)
        self.assertEqual(state["trades"][0]["reason"], "ALVO")
        self.assertEqual(state["decisions"][0]["status"], "ENTRADA_SIMULADA")
        self.assertGreater(state["balance"], 1000)

    def test_oldest_registered_entry_is_reconciled_first(self):
        state = paper.new_state(self.t + 20)
        older = self.decision()
        newer = self.decision(self.t + paper.CADENCE)
        state["decisions"].extend((older, newer))
        test = self

        class Market:
            def closed_hours(self, symbol, count, end, fair=False):
                result = [test.candle(end - (count-i) * paper.HOUR, h=104 if i == 0 else 101)
                          for i in range(count)]
                return result

            def funding_rates(self, symbol, start, end):
                return {}

        paper.reconcile(state, Market(), self.t + paper.CADENCE + 2 * paper.HOUR + 20)
        self.assertEqual([row["status"] for row in state["decisions"]],
                         ["ENTRADA_SIMULADA", "IGNORADO_LIMITE_DA_CARTEIRA"])
        self.assertEqual(state["trades"][0]["entry_at"], older["entry_at"])
