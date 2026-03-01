import unittest
from unittest import mock

import requests

from kernel.channels.telegram_validation import validate_webhook_configuration


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TelegramWebhookValidationTests(unittest.TestCase):
    @mock.patch("kernel.channels.telegram_validation.requests.get")
    def test_valid_configuration_passes(self, get_mock):
        get_mock.return_value = _Resp(
            {
                "ok": True,
                "result": {
                    "url": "https://example.com/webhook/telegram",
                    "secret_token": "s3cr3t",
                },
            }
        )
        validate_webhook_configuration(
            bot_token="123:abc",
            expected_url="https://example.com/webhook/telegram",
            expected_secret="s3cr3t",
            timeout_seconds=5,
        )
        get_mock.assert_called_once()

    @mock.patch("kernel.channels.telegram_validation.requests.get")
    def test_url_mismatch_raises(self, get_mock):
        get_mock.return_value = _Resp(
            {
                "ok": True,
                "result": {
                    "url": "https://wrong.example/webhook/telegram",
                    "secret_token": "s3cr3t",
                },
            }
        )
        with self.assertRaises(RuntimeError):
            validate_webhook_configuration(
                bot_token="123:abc",
                expected_url="https://example.com/webhook/telegram",
                expected_secret="s3cr3t",
            )

    @mock.patch("kernel.channels.telegram_validation.requests.get")
    def test_secret_mismatch_raises(self, get_mock):
        get_mock.return_value = _Resp(
            {
                "ok": True,
                "result": {
                    "url": "https://example.com/webhook/telegram",
                    "secret_token": "wrong",
                },
            }
        )
        with self.assertRaises(RuntimeError):
            validate_webhook_configuration(
                bot_token="123:abc",
                expected_url="https://example.com/webhook/telegram",
                expected_secret="s3cr3t",
            )

    @mock.patch("kernel.channels.telegram_validation.requests.get")
    def test_ok_false_response_raises(self, get_mock):
        get_mock.return_value = _Resp({"ok": False, "result": {}})
        with self.assertRaises(RuntimeError):
            validate_webhook_configuration(
                bot_token="123:abc",
                expected_url="https://example.com/webhook/telegram",
                expected_secret="s3cr3t",
            )

    @mock.patch("kernel.channels.telegram_validation.requests.get")
    def test_timeout_raises(self, get_mock):
        get_mock.side_effect = requests.Timeout("timeout")
        with self.assertRaises(RuntimeError):
            validate_webhook_configuration(
                bot_token="123:abc",
                expected_url="https://example.com/webhook/telegram",
                expected_secret="s3cr3t",
            )


if __name__ == "__main__":
    unittest.main()
