import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.channels.replay_cache import ReplayCache
from kernel.channels.telegram import parse_update
from kernel.channels.telegram import resolve_intent

try:
    from fastapi.testclient import TestClient
    from apps.telegram_webhook_app import app

    HAVE_FASTAPI = True
except ModuleNotFoundError:
    TestClient = None  # type: ignore
    app = None  # type: ignore
    HAVE_FASTAPI = False


def _text_update(chat_id: int = 111, text: str = "hello") -> dict:
    return {
        "update_id": 12345,
        "message": {
            "message_id": 9,
            "date": 1710000000,
            "chat": {"id": chat_id},
            "from": {"id": 222},
            "text": text,
        },
    }


class TelegramParseTests(unittest.TestCase):
    def test_parse_update_extracts_text_fields(self):
        out = parse_update(_text_update())
        self.assertEqual(
            out,
            {
                "update_id": 12345,
                "message_id": 9,
                "chat_id": 111,
                "from_user_id": 222,
                "text": "hello",
                "date": 1710000000,
            },
        )

    def test_parse_update_returns_none_for_non_text(self):
        update = {
            "update_id": 12345,
            "message": {
                "message_id": 9,
                "date": 1710000000,
                "chat": {"id": 111},
                "from": {"id": 222},
                "photo": [{"file_id": "x"}],
            },
        }
        self.assertIsNone(parse_update(update))


class IntentResolverTests(unittest.TestCase):
    def test_send_command_works(self):
        intent = resolve_intent("/send alice hello there")
        self.assertEqual(intent, ("send-message", {"recipient": "alice", "text": "hello there"}))

    def test_natural_language_intent_works(self):
        intent = resolve_intent("kun je dit later naar bob stuur")
        self.assertEqual(intent, ("send-message", {"text": "kun je dit later naar bob stuur", "recipient": "bob"}))

    def test_unknown_nl_does_not_execute(self):
        self.assertIsNone(resolve_intent("wat is het weer morgen"))

    def test_deterministic_behavior(self):
        first = resolve_intent("/send alice hello there")
        second = resolve_intent("/send alice hello there")
        self.assertEqual(first, second)
        self.assertIsNotNone(first)
        if first is not None:
            self.assertEqual(first[0], "send-message")
            self.assertEqual(list(first[1].keys()), ["recipient", "text"])


class ReplayCacheTests(unittest.TestCase):
    def test_first_update_id_allowed(self):
        cache = ReplayCache(max_size=10_000, ttl_seconds=600)
        with mock.patch("kernel.channels.replay_cache.time.monotonic", return_value=100.0):
            self.assertFalse(cache.seen(1))

    def test_same_update_id_rejected(self):
        cache = ReplayCache(max_size=10_000, ttl_seconds=600)
        with mock.patch("kernel.channels.replay_cache.time.monotonic", side_effect=[100.0, 101.0]):
            self.assertFalse(cache.seen(42))
            self.assertTrue(cache.seen(42))

    def test_expired_update_id_allowed(self):
        cache = ReplayCache(max_size=10_000, ttl_seconds=10)
        with mock.patch("kernel.channels.replay_cache.time.monotonic", side_effect=[100.0, 111.0]):
            self.assertFalse(cache.seen(7))
            self.assertFalse(cache.seen(7))

    def test_cache_eviction_works_at_max_size(self):
        cache = ReplayCache(max_size=2, ttl_seconds=600)
        with mock.patch("kernel.channels.replay_cache.time.monotonic", side_effect=[0.0, 1.0, 2.0, 3.0]):
            self.assertFalse(cache.seen(1))
            self.assertFalse(cache.seen(2))
            self.assertFalse(cache.seen(3))  # evicts 1
            self.assertFalse(cache.seen(1))  # no longer present => allowed

    def test_non_int_update_id_denied(self):
        cache = ReplayCache(max_size=10_000, ttl_seconds=600)
        self.assertTrue(cache.seen("x"))  # type: ignore[arg-type]


@unittest.skipUnless(HAVE_FASTAPI, "fastapi not installed in test environment")
class TelegramWebhookTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.registry_path = self.base / "state" / "plugins" / "registry.json"
        self.config_path = self.base / "state" / "plugins" / "config.json"
        self.event_audit_path = self.base / "logs" / "control" / "kernel-events.jsonl"
        self.ingress_audit_path = self.base / "logs" / "control" / "channel-telegram.jsonl"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps({"plugins": []}, sort_keys=True), encoding="utf-8")
        self.config_path.write_text(
            json.dumps({"enabled": [], "unsafe_allow_external": False}, sort_keys=True),
            encoding="utf-8",
        )
        self.env = {
            "AIOS_TELEGRAM_WEBHOOK_SECRET": "secret123",
            "AIOS_TELEGRAM_ALLOWED_CHAT_IDS": "111,222",
            "AIOS_REGISTRY_PATH": str(self.registry_path),
            "AIOS_CONFIG_PATH": str(self.config_path),
            "AIOS_EVENT_AUDIT_LOG_PATH": str(self.event_audit_path),
            "AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH": str(self.ingress_audit_path),
        }
        import kernel.channels.telegram as telegram_mod

        self._original_replay_cache = telegram_mod.REPLAY_CACHE
        telegram_mod.REPLAY_CACHE = ReplayCache(max_size=10_000, ttl_seconds=600)

    def tearDown(self):
        import kernel.channels.telegram as telegram_mod

        telegram_mod.REPLAY_CACHE = self._original_replay_cache
        self.tmp.cleanup()

    def test_missing_secret_header_denied(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.post("/webhook/telegram", json=_text_update())
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["reason_code"], "DENY_SECRET_INVALID")

    def test_wrong_secret_denied(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.post(
                "/webhook/telegram",
                json=_text_update(),
                headers={"X-AIOS-TELEGRAM-SECRET": "wrong"},
            )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["reason_code"], "DENY_SECRET_INVALID")

    def test_chat_not_allowed_denied(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.post(
                "/webhook/telegram",
                json=_text_update(chat_id=999),
                headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
            )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["reason_code"], "DENY_CHAT_NOT_ALLOWED")

    def test_telegram_allowed_skill_executes_successfully(self):
        fake_skill_result = {
            "ok": True,
            "skill_id": "send-message",
            "result": {"ok": True, "plugin_id": "echo-ok", "request_id": "req-1", "result": {"text": "hello"}},
        }
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch("apps.telegram_webhook_app.run_skill", return_value=fake_skill_result) as run_skill_mock:
                resp = self.client.post(
                    "/webhook/telegram",
                    json=_text_update(chat_id=111, text="/send alice hello"),
                    headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(list(body.keys()), ["ok", "executed", "skill_id", "reply", "result", "error"])
        self.assertTrue(body["ok"])
        self.assertTrue(body["executed"])
        self.assertEqual(body["skill_id"], "send-message")
        self.assertIsNone(body["error"])
        run_skill_mock.assert_called_once()

    def test_telegram_cannot_trigger_plugin_without_policy(self):
        env = dict(self.env)
        env["AIOS_SKILLS_POLICY_PATH"] = str(self.base / "missing-policy.yaml")
        with mock.patch.dict(os.environ, env, clear=False):
            resp = self.client.post(
                "/webhook/telegram",
                json=_text_update(chat_id=111, text="/send alice hello"),
                headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(list(body.keys()), ["ok", "executed", "skill_id", "reply", "result", "error"])
        self.assertFalse(body["ok"])
        self.assertFalse(body["executed"])
        self.assertEqual(body["skill_id"], "send-message")
        self.assertEqual(body["error"]["code"], "SKILL_POLICY_INVALID")

    def test_unknown_nl_message_does_not_execute(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch("apps.telegram_webhook_app.run_skill") as run_skill_mock:
                resp = self.client.post(
                    "/webhook/telegram",
                    json=_text_update(chat_id=111, text="hallo hoe gaat het"),
                    headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["executed"])
        self.assertIsNone(body["skill_id"])
        self.assertIsNone(body["result"])
        self.assertIsNone(body["error"])
        run_skill_mock.assert_not_called()

    def test_ingress_audit_unwritable_denies_before_execution(self):
        locked = self.base / "locked"
        locked.mkdir(parents=True, exist_ok=True)
        os.chmod(locked, stat.S_IREAD | stat.S_IEXEC)
        env = dict(self.env)
        env["AIOS_TELEGRAM_INGRESS_AUDIT_LOG_PATH"] = str(locked / "channel-telegram.jsonl")
        try:
            with mock.patch.dict(os.environ, env, clear=False):
                with mock.patch("apps.telegram_webhook_app.run_skill") as run_skill_mock:
                    resp = self.client.post(
                        "/webhook/telegram",
                        json=_text_update(chat_id=111, text="/send alice hello"),
                        headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                    )
            self.assertEqual(resp.status_code, 403)
            self.assertEqual(resp.json()["reason_code"], "DENY_AUDIT_WRITE_FAILED")
            run_skill_mock.assert_not_called()
        finally:
            os.chmod(locked, stat.S_IRWXU)

    def test_duplicate_update_id_ignored(self):
        fake_skill_result = {
            "ok": True,
            "skill_id": "send-message",
            "result": {"ok": True, "plugin_id": "echo-ok", "request_id": "req-1", "result": {"text": "hello"}},
        }
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch("apps.telegram_webhook_app.run_skill", return_value=fake_skill_result) as run_skill_mock:
                first = self.client.post(
                    "/webhook/telegram",
                    json=_text_update(chat_id=111, text="/send alice hello"),
                    headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                )
                second = self.client.post(
                    "/webhook/telegram",
                    json=_text_update(chat_id=111, text="/send alice hello"),
                    headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["ok"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"ok": True, "ignored": True})
        self.assertEqual(run_skill_mock.call_count, 1)

    def test_direct_dispatch_usage_is_absent(self):
        source = Path("apps/telegram_webhook_app.py").read_text(encoding="utf-8")
        self.assertNotIn("dispatch(", source)
        self.assertNotIn("emit_telegram_message(", source)
        self.assertNotIn("events.emit(", source)


if __name__ == "__main__":
    unittest.main()
