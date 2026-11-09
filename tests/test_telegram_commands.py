import json
import tempfile
import unittest
from pathlib import Path
from mexc_scanner.telegram import TelegramError
from scripts.telegram_commands import HELP, process_commands


class CommandTests(unittest.TestCase):
    def test_help_replies_once_only_to_configured_private_chat(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            updates = [{'update_id': 4, 'message': {'chat': {'id': 42, 'type': 'private'}, 'text': '/ajuda'}},
                       {'update_id': 5, 'message': {'chat': {'id': 99, 'type': 'private'}, 'text': '/ajuda'}},
                       {'update_id': 6, 'message': {'chat': {'id': 42, 'type': 'private'}, 'text': '/ajuda'}}]
            sent = []
            def get(payload):
                return {'ok': True, 'result': [u for u in updates if u['update_id'] >= payload['offset']]}
            def send(payload):
                sent.append(payload)
                return {'ok': True, 'result': {'message_id': len(sent)}}
            self.assertEqual(process_commands(directory, 'token', '42', get, send), 2)
            self.assertEqual(process_commands(directory, 'token', '42', get, send), 0)
            self.assertEqual(len(sent), 2)
            self.assertEqual(json.loads((directory / 'telegram-cursor.json').read_text()), {'offset': 7})

    def test_failed_send_keeps_update_for_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            get = lambda p: {'ok': True, 'result': [{'update_id': 2, 'message': {
                'chat': {'id': 42, 'type': 'private'}, 'text': '/ajuda'}}]}
            with self.assertRaises(TelegramError):
                process_commands(directory, 'token', '42', get, lambda p: {'ok': False})
            self.assertFalse((directory / 'telegram-cursor.json').exists())

    def test_help_explains_estimate(self):
        self.assertIn('60%', HELP)
        self.assertIn('30%', HELP)
        self.assertIn('não garantem lucro', HELP)
