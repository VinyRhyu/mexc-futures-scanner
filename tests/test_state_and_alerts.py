from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import urllib.error

from mexc_scanner.config import Config
from mexc_scanner.models import D, DataError, jsonable
from mexc_scanner.state import atomic_json, initial_state, journal_event, load_state, queue_message
from mexc_scanner.telegram import TelegramError, drain_outbox, send_text
from tests.test_finance import NOW, context


class StateTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.state = initial_state(self.config)
        p, v, c, *_ = context()
        v.financial = {"contract_size": c.size, "loss_usdt": D("0.30")}
        p.variants["ANTECIPADA"] = v
        self.state["plans"][p.id] = jsonable(p)

    def test_missing_and_corrupt_state_do_not_reset_wallet(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "state.json"
            with self.assertRaises(DataError):
                load_state(p, self.config)
            p.write_text('{"wallet":')
            with self.assertRaises(DataError):
                load_state(p, self.config, initialize=True)

    def test_config_change_requires_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "state.json"
            atomic_json(p, self.state)
            with self.assertRaises(DataError):
                load_state(p, replace(self.config, taker_fee="0"))

    def test_journal_is_idempotent_and_does_not_double_count_entry_fee(self):
        args = {"plan_id": "p", "price": "100", "contracts": "100", "fees": "0.01"}
        journal_event(self.state, self.config, "enter", "e1", NOW, **args)
        result = journal_event(self.state, self.config, "enter", "e1", NOW, **args)
        self.assertEqual(result["status"], "ALREADY_RECORDED")
        self.assertEqual(D(self.state["wallet"]["balance"]), D("0.99"))
        result = journal_event(self.state, self.config, "close", "e2", NOW + 100,
                               plan_id="p", price="106", fees="0.01")
        self.assertEqual(D(result["net_usdt"]), D("0.58"))
        self.assertEqual(D(self.state["wallet"]["balance"]), D("1.58"))

    def test_stop_consuming_full_budget_sets_24_hour_pause(self):
        self.state["plans"]["p"]["variants"]["ANTECIPADA"]["stop"] = "97"
        journal_event(self.state, self.config, "enter", "e1", NOW, plan_id="p", price="100", contracts="100")
        journal_event(self.state, self.config, "close", "e2", NOW + 100, plan_id="p", price="97")
        self.assertEqual(self.state["wallet"]["pause_until"], NOW + 100 + 86400)
        self.assertEqual(D(self.state["wallet"]["balance"]), D("0.70"))

    def test_second_position_is_rejected(self):
        journal_event(self.state, self.config, "enter", "e1", NOW, plan_id="p", price="100", contracts="100")
        with self.assertRaises(DataError):
            journal_event(self.state, self.config, "enter", "e2", NOW, plan_id="p", price="100", contracts="100")

    def test_pending_indication_is_not_assumed_skipped(self):
        self.state["wallet"]["pending"] = {"plan_id": "p"}
        with self.assertRaises(DataError):
            journal_event(self.state, self.config, "skip", "s1", NOW, plan_id="other")
        self.assertIsNotNone(self.state["wallet"]["pending"])

    def test_capital_adjustment_is_not_profit_and_triggers_phase_review(self):
        result = journal_event(self.state, self.config, "balance", "b1", NOW, balance="100")
        self.assertEqual(result["classification"], "RECONCILIACAO_NAO_E_LUCRO")
        self.assertTrue(self.state["wallet"]["review_required"])

    def test_public_real_journal_rejected(self):
        with self.assertRaises(DataError):
            journal_event(self.state, replace(self.config, mode="real"), "balance", "r1", NOW, balance="10")

    def test_late_registration_uses_actual_execution_time(self):
        result = journal_event(self.state, self.config, "enter", "e1", NOW + 7200,
            plan_id="p", price="100", contracts="100", executed_at=NOW)
        self.assertEqual(result["recorded_at"], NOW + 7200)
        self.assertEqual(result["entered_at"], NOW)
        self.assertEqual(result["time_source"], "INFORMADO")
        self.assertNotIn("EXECUCAO_APOS_VALIDADE", result["deviations"])

    def test_future_execution_and_exit_before_entry_are_rejected(self):
        with self.assertRaises(DataError):
            journal_event(self.state, self.config, "enter", "future", NOW,
                plan_id="p", price="100", contracts="100", executed_at=NOW + 61)
        journal_event(self.state, self.config, "enter", "e1", NOW,
            plan_id="p", price="100", contracts="100")
        with self.assertRaises(DataError):
            journal_event(self.state, self.config, "close", "e2", NOW + 100,
                plan_id="p", price="101", executed_at=NOW - 1)


class AlertTests(unittest.TestCase):
    def test_expired_entry_never_sent(self):
        state = initial_state(Config())
        queue_message(state, "a", "signal", NOW, NOW + 500, "ENTRY", NOW - 61)
        calls = []
        result = drain_outbox(state, NOW, "token", "chat", lambda p: calls.append(p))
        self.assertEqual(result["expired"], 1)
        self.assertFalse(calls)

    def test_delivered_event_not_queued_again(self):
        state = initial_state(Config())
        queue_message(state, "a", "signal", NOW, NOW + 500)
        result = drain_outbox(state, NOW, "token", "chat", lambda p: {"ok": True, "result": {"message_id": 7}})
        self.assertEqual(result["sent"], 1)
        queue_message(state, "a", "signal", NOW + 1, NOW + 500)
        self.assertEqual(state["outbox"]["a"]["status"], "SENT")

    def test_missing_secret_does_not_attempt_delivery(self):
        state = initial_state(Config())
        queue_message(state, "a", "signal", NOW, NOW + 500)
        result = drain_outbox(state, NOW, "", "", lambda p: self.fail("Não deve enviar"))
        self.assertEqual(result["configuration"], "TELEGRAM_NAO_CONFIGURADO")

    def test_transport_errors_never_print_token(self):
        def fail(_):
            raise urllib.error.URLError("https://api.telegram.org/botTOPSECRET/sendMessage")
        with self.assertRaises(TelegramError) as error:
            send_text("TOPSECRET", "chat", "msg", fail)
        self.assertNotIn("TOPSECRET", str(error.exception))
