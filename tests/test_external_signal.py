import unittest
from datetime import datetime, timezone

from mexc_scanner.external_signal import assess, evaluate
from mexc_scanner.mexc import MexcClient
from mexc_scanner.models import D, DataError


FIRST = 1_795_000_020 // 60 * 60
PUBLISHED = datetime.fromtimestamp(FIRST - 35, timezone.utc)
LONG_TARGETS = tuple(map(D, ("103", "105", "107", "109")))
SHORT_TARGETS = tuple(map(D, ("97", "95", "93", "91")))


def fake_client(rows=(), now=FIRST + 70):
    def transport(path, params):
        if path.endswith("/ping"):
            return {"success": True, "data": now}
        assert path.endswith("/BTC_USDT")
        assert params["interval"] == "Min1"
        fields = ("time", "open", "high", "low", "close", "vol")
        return {"success": True, "data": dict(zip(fields, zip(*rows)))}
    return MexcClient(transport=transport)


class ExternalSignalTests(unittest.TestCase):
    def run_signal(self, client, side="LONG", targets=LONG_TARGETS):
        return assess(client, "BTC_USDT", PUBLISHED, side, 30, targets)

    def test_risk_and_cost_match_the_replay_in_both_directions(self):
        long = evaluate("LONG", 30, D("100"), LONG_TARGETS)
        short = evaluate("SHORT", 30, D("100"), SHORT_TARGETS)
        for result in (long, short):
            self.assertEqual(result["motivos"], [])
            self.assertEqual(result["roi_liquido_estimado_no_tp1_pct"], D("84"))
        self.assertAlmostEqual(long["stop"], D("99.0333333333"))
        self.assertAlmostEqual(short["stop"], D("100.9666666667"))

    def test_waits_for_reference_candle_to_close(self):
        result = self.run_signal(fake_client(now=FIRST + 69))
        self.assertEqual(result["status"], "AGUARDANDO_FECHAMENTO_DO_CANDLE_DE_ENTRADA")
        self.assertNotIn("entrada_simulada", result)

    def test_uses_next_minute_open_and_ignores_forming_candle(self):
        rows = [(FIRST-60, 98, 100, 98, 100, 1),
                (FIRST, 100, 101, 100, 101, 1),
                (FIRST+60, 101, 104, 100, 103, 1)]
        result = self.run_signal(fake_client(rows))
        self.assertEqual(result["entrada_simulada"], D(100))
        self.assertEqual(result["status"], "ABERTO_EM_SIMULACAO")

    def test_stop_precedes_target_when_both_appear_in_the_same_candle(self):
        result = self.run_signal(fake_client([(FIRST, 100, 104, 98, 103, 1)]))
        self.assertEqual(result["status"], "STOP")
        self.assertAlmostEqual(result["roi_liquido_na_margem_pct"], D("-35"))

    def test_target_exits_the_entire_simulated_position(self):
        result = self.run_signal(fake_client([(FIRST, 100, 104, 100, 103, 1)]))
        self.assertEqual(result["status"], "TP1")
        self.assertEqual(result["roi_liquido_na_margem_pct"], D("84"))

    def test_stop_gap_uses_open_and_can_exceed_the_planned_loss(self):
        rows = [(FIRST, 100, 101, 100, 100, 1),
                (FIRST+60, 98, 104, 98, 103, 1)]
        result = self.run_signal(fake_client(rows, FIRST + 130))
        self.assertEqual(result["status"], "STOP_GAP")
        self.assertEqual(result["saida_simulada"], D(98))
        self.assertEqual(result["roi_liquido_na_margem_pct"], D("-66"))

    def test_refuses_missing_reference_candle(self):
        with self.assertRaises(DataError):
            self.run_signal(fake_client([(FIRST-60, 100, 101, 100, 100, 1)]))

    def test_rejects_advanced_entry_and_nonmatching_target_spacing(self):
        advanced = self.run_signal(fake_client([(FIRST, 102, 103, 101, 102, 1)]))
        self.assertEqual(advanced["status"], "DESCARTADO")
        self.assertEqual(advanced["motivos"], ["RETORNO_RISCO_INSUFICIENTE"])
        targets = tuple(map(D, ("103", "105", "115", "125")))
        uneven = self.run_signal(fake_client([(FIRST, 100, 101, 100, 101, 1)]), targets=targets)
        self.assertIn("ESPACAMENTO_DOS_ALVOS_FORA_DA_REGRA", uneven["motivos"])

    def test_requires_a_timezone(self):
        with self.assertRaises(DataError):
            assess(fake_client(), "BTC_USDT", PUBLISHED.replace(tzinfo=None), "LONG", 30, LONG_TARGETS)
