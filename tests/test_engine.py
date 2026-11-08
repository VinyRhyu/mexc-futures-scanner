from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import io

from mexc_scanner.cli import main
from mexc_scanner.config import Config
from mexc_scanner.demo import DemoClient
from mexc_scanner.engine import run_scan
from mexc_scanner.mexc import MexcClient, SourceError
from mexc_scanner.models import DataError
from mexc_scanner.state import initial_state, queue_message
from mexc_scanner.replay import replay_snapshot
from tests.test_finance import NOW


class BrokenClient:
    def server_time(self):
        raise SourceError("SITE_UNAVAILABLE_TEST")


class EngineTests(unittest.TestCase):
    def test_demo_generates_both_modes_with_one_dollar(self):
        client = DemoClient(NOW)
        state = initial_state(Config())
        report, _ = run_scan(client, Config(), state, {"DEMO"}, now=client.now)
        active = [p for p in report["plans"] if p["side"] == "LONG" and p["status"] == "ATIVO"]
        self.assertTrue(active)
        self.assertEqual(set(active[-1]["variants"]), {"ANTECIPADA", "CONFIRMADA"})
        self.assertTrue(all(v["financial"]["status"] == "VIAVEL_SIMULADO" for v in active[-1]["variants"].values()))

    def test_identical_round_does_not_duplicate_plans_or_notifications(self):
        client, config = DemoClient(NOW), Config()
        state = initial_state(config)
        run_scan(client, config, state, {"DEMO"}, now=client.now)
        ids, events = set(state["plans"]), set(state["outbox"])
        run_scan(client, config, state, {"DEMO"}, now=client.now)
        self.assertEqual(set(state["plans"]), ids)
        self.assertEqual(set(state["outbox"]), events)

    def test_source_failure_produces_diagnostic_not_a_signal(self):
        state = initial_state(Config())
        queue_message(state, "old", "signal", NOW, NOW + 1000, "ENTRY", NOW)
        report, snapshot = run_scan(BrokenClient(), Config(), state, set(), now=NOW)
        self.assertEqual(report["source_status"], "FALHA")
        self.assertEqual(state["outbox"]["old"]["status"], "EXPIRED")
        with self.assertRaises(DataError):
            replay_snapshot(snapshot, Config())

    def test_non_json_page_is_not_parsed_as_market_data(self):
        fake = io.BytesIO(b"<html>Site Unavailable</html>")
        with patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(SourceError):
                MexcClient().server_time()

    def test_client_does_not_expose_order_endpoints(self):
        client = MexcClient(transport=lambda *_: self.fail("Não deve chamar transporte"))
        with self.assertRaises(DataError):
            client._get("/api/v1/contract/private/order/submit")

    def test_demo_does_not_send_to_telegram_even_with_credentials(self):
        with tempfile.TemporaryDirectory() as temp, patch("mexc_scanner.telegram.send_text") as send:
            self.assertEqual(main(["demo", "--output", temp]), 0)
            self.assertFalse(send.called)
