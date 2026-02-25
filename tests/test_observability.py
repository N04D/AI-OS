import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
    import apps.telegram_webhook_app as webhook_app

    HAVE_FASTAPI = True
except ModuleNotFoundError:
    TestClient = None  # type: ignore
    webhook_app = None  # type: ignore
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


@unittest.skipUnless(HAVE_FASTAPI, "fastapi not installed in test environment")
class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(webhook_app.app)
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
            "AIOS_VALIDATE_WEBHOOK_ON_STARTUP": "false",
        }
        webhook_app.EVENTS_PROCESSED = 0
        webhook_app.REPLAYS_BLOCKED = 0

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_returns_ok_true(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "telegram-ingress")
        self.assertIn("timestamp", body)

    def test_metrics_returns_expected_keys(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.get("/metrics")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(
            list(body.keys()),
            ["uptime_seconds", "events_processed", "replays_blocked", "plugins_enabled", "plugins_unhealthy"],
        )

    def test_replay_increments_replays_blocked(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch("apps.telegram_webhook_app.replay_detected", return_value=True):
                resp = self.client.post(
                    "/webhook/telegram",
                    json=_text_update(chat_id=111, text="/send alice hello"),
                    headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                )
                self.assertEqual(resp.status_code, 200)
            metrics = self.client.get("/metrics")
        self.assertEqual(metrics.json()["replays_blocked"], 1)
        self.assertEqual(metrics.json()["events_processed"], 0)

    def test_event_increments_events_processed(self):
        skill_result = {"ok": True, "skill_id": "send-message", "result": {"ok": True}}
        with mock.patch.dict(os.environ, self.env, clear=False):
            with mock.patch("apps.telegram_webhook_app.replay_detected", return_value=False):
                with mock.patch("apps.telegram_webhook_app.run_skill", return_value=skill_result):
                    resp = self.client.post(
                        "/webhook/telegram",
                        json=_text_update(chat_id=111, text="/send alice hello"),
                        headers={"X-AIOS-TELEGRAM-SECRET": "secret123"},
                    )
                    self.assertEqual(resp.status_code, 200)
            metrics = self.client.get("/metrics")
        self.assertEqual(metrics.json()["events_processed"], 1)

    def test_metrics_does_not_expose_secrets(self):
        with mock.patch.dict(os.environ, self.env, clear=False):
            resp = self.client.get("/metrics")
        rendered = json.dumps(resp.json(), sort_keys=True)
        self.assertNotIn("secret123", rendered)
        self.assertNotIn("AIOS_TELEGRAM_WEBHOOK_SECRET", rendered)


if __name__ == "__main__":
    unittest.main()
