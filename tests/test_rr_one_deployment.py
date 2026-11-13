from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from mexc_scanner.config import Config, load_config
from mexc_scanner.finance import evaluate
from mexc_scanner.models import D, DataError, jsonable, stable_id
from mexc_scanner.state import atomic_json, initial_state, load_state, queue_message
from tests.test_finance import NOW, context


class RROneDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.old = Config()
        self.new = replace(self.old, minimum_rr="1").validate()
        self.state = initial_state(self.old)
        p, v, *_ = context()
        v.financial = {"status": "VIAVEL_SIMULADO", "net_rr": "2.1"}
        p.variants[v.kind] = v
        self.state["plans"][p.id] = jsonable(p)
        self.state["minute_cursors"] = {p.symbol: NOW - 30}
        self.state["minute_activation"] = {p.symbol: NOW - 5000}
        self.state["journal"] = [{"event_id": "old-record"}]
        self.state["journal_ids"] = ["old-record"]
        self.state["wallet"].update(balance="50", position={"recorded": True}, pending={"plan_id": "p"})
        queue_message(self.state, "entry", "old entry", NOW, NOW + 100, "ENTRY", NOW)
        obs = stable_id("p", v.kind, "OBSERVACAO")
        queue_message(self.state, obs, "old blocked observation", NOW, NOW + 100)
        queue_message(self.state, "sent", "delivered entry", NOW, NOW + 100, "ENTRY", NOW)
        self.state["outbox"]["sent"]["status"] = "SENT"
        queue_message(self.state, "other", "unrelated info", NOW, NOW + 100)

    def load(self, state=None, config=None, **kw):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.json"
            atomic_json(path, self.state if state is None else state)
            return load_state(path, config or self.new, **kw)

    def test_default_file_is_one_and_validation_does_not_allow_less(self):
        self.assertEqual(load_config("config/default.toml").minimum_rr, "1")
        for rr in ("1", "1.5", "2"):
            replace(self.old, minimum_rr=rr).validate()
        with self.assertRaises(DataError):
            replace(self.old, minimum_rr="0.99").validate()

    def test_one_to_one_admits_lower_rr_without_moving_prices_or_increasing_risk(self):
        for side in ("LONG", "SHORT"):
            p, v, c, t, b, f = context(side)
            v.target = D("102.7" if side == "LONG" else "97.3")
            levels = (v.entry_low, v.entry_high, v.stop, v.target)
            strict = evaluate(p, v, c, D(1), t, b, f, NOW, self.old)
            self.assertIn("RETORNO_RISCO_INSUFICIENTE", strict["reasons"])
            result = evaluate(p, v, c, D(1), t, b, f, NOW, self.new)
            self.assertEqual(result["status"], "VIAVEL_SIMULADO")
            self.assertGreaterEqual(result["net_rr"], 1)
            self.assertLess(result["net_rr"], 2)
            self.assertLessEqual(result["loss_fraction"], D("0.10"))
            self.assertLessEqual(result["leverage"], 20)
            self.assertEqual((v.entry_low, v.entry_high, v.stop, v.target), levels)

    def test_even_rr_one_cannot_release_unverified_real(self):
        p, v, c, t, b, f = context()
        v.target = D("102.7")
        result = evaluate(p, v, c, D(1), t, b, f, NOW, replace(self.new, mode="real"))
        self.assertEqual(result["status"], "BLOQUEADA")
        self.assertIn("VERIFICACOES_PARA_REAL_PENDENTES", result["reasons"])

    def test_migration_requires_explicit_flag(self):
        with self.assertRaises(DataError):
            self.load()

    def test_migration_preserves_wallet_journal_levels_and_cursors(self):
        original = deepcopy(self.state)
        migrated = self.load(migrate_rr_one=True, migration_at=NOW)
        for key in ("wallet", "journal", "journal_ids", "minute_cursors", "minute_activation"):
            self.assertEqual(migrated[key], original[key])
        before, after = original["plans"]["p"], migrated["plans"]["p"]
        for key in before.keys() - {"variants"}:
            self.assertEqual(after[key], before[key])
        v0, v1 = before["variants"]["ANTECIPADA"], after["variants"]["ANTECIPADA"]
        for key in v0.keys() - {"financial"}:
            self.assertEqual(v1[key], v0[key])
        self.assertEqual(v1["financial"]["reasons"], ["POLITICA_RR_ATUALIZADA"])
        self.assertEqual(migrated["config_fingerprint"], self.new.fingerprint)

    def test_old_pending_financial_messages_expire_but_sent_ids_are_preserved(self):
        migrated = self.load(migrate_rr_one=True, migration_at=NOW)
        self.assertEqual(migrated["outbox"]["entry"]["status"], "EXPIRED")
        obs = stable_id("p", "ANTECIPADA", "OBSERVACAO")
        self.assertEqual(migrated["outbox"][obs]["status"], "EXPIRED")
        self.assertEqual(migrated["outbox"]["sent"], self.state["outbox"]["sent"])
        self.assertEqual(migrated["outbox"]["other"]["status"], "PENDING")

    def test_migration_is_idempotent_and_notify_can_load_new_state(self):
        migrated = self.load(migrate_rr_one=True, migration_at=NOW)
        again = self.load(state=migrated, migrate_rr_one=True, migration_at=NOW + 1)
        self.assertEqual(again, migrated)
        self.assertEqual(len(again["config_migrations"]), 1)
        self.assertEqual(self.load(state=again), again)

    def test_unrelated_configuration_change_still_requires_its_own_migration(self):
        with self.assertRaises(DataError):
            self.load(config=replace(self.new, taker_fee="0"), migrate_rr_one=True, migration_at=NOW)

    def test_real_state_is_never_automatically_migrated(self):
        state = initial_state(replace(self.old, mode="real"))
        with self.assertRaises(DataError):
            self.load(state=state, config=replace(self.new, mode="real"), migrate_rr_one=True, migration_at=NOW)

    def test_closed_plan_and_its_historical_financial_result_remain_closed(self):
        self.state["plans"]["p"]["status"] = "EXPIRADO"
        before = deepcopy(self.state["plans"]["p"])
        migrated = self.load(migrate_rr_one=True, migration_at=NOW)
        self.assertEqual(migrated["plans"]["p"], before)

    def test_migration_requires_timestamp(self):
        with self.assertRaises(DataError):
            self.load(migrate_rr_one=True)


if __name__ == "__main__":
    unittest.main()
