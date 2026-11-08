import unittest
import urllib.error

from mexc_scanner.telegram import TelegramError
from scripts.telegram_chat_id import private_chat_ids


class TelegramSetupTests(unittest.TestCase):
    def test_extracts_only_private_ids_without_consuming_updates(self):
        def response(payload):
            self.assertNotIn('offset', payload)
            self.assertNotIn('allowed_updates', payload)
            return {'ok': True, 'result': [
                {'message': {'chat': {'type': 'private', 'id': 123}, 'text': 'private text'}},
                {'message': {'chat': {'type': 'private', 'id': 123}}},
                {'message': {'chat': {'type': 'supergroup', 'id': -456}}},
                {'callback_query': {}}]}
        self.assertEqual(private_chat_ids('secret', response), [123])

    def test_failure_does_not_expose_token(self):
        def fail(_):
            raise urllib.error.URLError('https://api.telegram.org/botTOPSECRET/getUpdates')
        with self.assertRaises(TelegramError) as error:
            private_chat_ids('TOPSECRET', fail)
        self.assertNotIn('TOPSECRET', str(error.exception))

    def test_no_token_does_not_attempt_request(self):
        with self.assertRaises(TelegramError):
            private_chat_ids('', lambda _: self.fail('Não deve consultar sem token'))
