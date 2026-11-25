from copy import deepcopy
from unittest import TestCase

from mexc_scanner.minute_breakout import STRATEGY
from mexc_scanner.models import D
from mexc_scanner.native_signal import screen_native_plans


def plan(side="LONG", target="103.2", key="test"):
    return {
        "id": key, "strategy": STRATEGY, "symbol": "BTC_USDT", "side": side,
        "status": "ATIVO", "expires_at": 180,
        "variants": {"CONFIRMADA": {
            "status": "VALIDA", "triggered_at": 60, "target": target,
            "financial": {"status": "VIAVEL_SIMULADO", "worst_entry": "100", "leverage": 20},
        }},
    }


class NativeSignalTests(TestCase):
    def test_own_plan_produces_four_levels_and_stop_without_mutation(self):
        for side, tp in (("LONG", "103.2"), ("SHORT", "96.8")):
            row = plan(side, tp)
            original = deepcopy(row)
            result = screen_native_plans([row], 110)
            self.assertEqual(row, original)
            self.assertEqual(result["modo"], "SIMULACAO")
            signal = result["candidatos"][0]
            self.assertEqual(signal["status"], "ELEGIVEL_EM_SIMULACAO")
            self.assertEqual(len(signal["alvos_projetados"]), 4)
            self.assertEqual(signal["alvos_projetados"][0], D(tp))
            self.assertEqual(signal["roi_liquido_estimado_no_tp1_pct"], D(60))
            self.assertEqual(signal["risco_estimado_na_margem_pct"], D(35))
            self.assertEqual(signal["stop"], D("98.45" if side == "LONG" else "101.55"))

    def test_rejects_low_reward_and_preserves_the_technical_tp1(self):
        result = screen_native_plans([plan(target="101.3")], 110)["candidatos"][0]
        self.assertEqual(result["status"], "DESCARTADO")
        self.assertEqual(result["tp1"], D("101.3"))
        self.assertEqual(result["motivos"], ["RETORNO_RISCO_INSUFICIENTE"])

    def test_expired_future_unconfirmed_and_non_scanner_plans_are_ignored(self):
        inactive = plan()
        inactive["status"] = "EXPIRADO"
        external = plan()
        external["strategy"] = "EXTERNO"
        unconfirmed = plan()
        unconfirmed["variants"] = {}
        self.assertEqual(screen_native_plans([inactive, external, unconfirmed], 110)["candidatos"], [])
        self.assertEqual(screen_native_plans([plan()], 59)["candidatos"], [])
        self.assertEqual(screen_native_plans([plan()], 180)["candidatos"], [])

    def test_prefers_eligible_duplicate_and_refuses_missing_finance(self):
        blocked = plan(key="blocked")
        blocked["variants"]["CONFIRMADA"]["financial"] = {"status": "BLOQUEADA"}
        result = screen_native_plans([blocked], 110)["candidatos"][0]
        self.assertEqual(result["motivos"], ["PLANO_FINANCEIRO_INDISPONIVEL"])
        result = screen_native_plans([blocked, plan()], 110)["candidatos"]
        self.assertEqual([x["plano"] for x in result], ["test"])
