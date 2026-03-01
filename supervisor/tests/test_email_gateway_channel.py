from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.channels.email_gateway import DENY_ADDRESS_NOT_ALLOWED
from supervisor.channels.email_gateway import DENY_AGENT_CHANNEL_DISABLED
from supervisor.channels.email_gateway import DENY_AGENT_NOT_REGISTERED
from supervisor.channels.email_gateway import DENY_BODY_TOO_LARGE
from supervisor.channels.email_gateway import DENY_CAPABILITY_MISSING
from supervisor.channels.email_gateway import DENY_DOMAIN_NOT_ALLOWED
from supervisor.channels.email_gateway import DENY_POLICY_MISSING
from supervisor.channels.email_gateway import EmailGatewayError
from supervisor.channels.email_gateway import _artifact_name
from supervisor.channels.email_gateway import poll_email_direct
from supervisor.channels.email_gateway import send_email_direct


class _FakeSMTPTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send_mail(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {"status": "sent"}


class _FakeIMAPTransport:
    def __init__(self) -> None:
        self.marked_uids: list[str] = []
        self.messages = [
            {
                "uid": "7",
                "from": "ops@example.com",
                "to": "codex@example.com",
                "subject": "hello",
                "body": "message body",
            }
        ]

    def poll_unseen(self, **kwargs):  # type: ignore[no-untyped-def]
        return list(self.messages)

    def mark_seen(self, **kwargs):  # type: ignore[no-untyped-def]
        self.marked_uids = sorted(list(kwargs.get("uids", [])))


class EmailGatewayChannelTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    def _bootstrap_repo(
        self,
        root: Path,
        *,
        module_enabled: bool = True,
        agent_registered: bool = True,
        agent_enabled: bool = True,
        send_granted: bool = True,
        poll_granted: bool = False,
        max_body_bytes: int = 65536,
    ) -> None:
        config_agents = {"codex": {"enabled": agent_enabled}} if agent_registered else {}
        self._write_json(
            root / "config/channels/email_gateway.json",
            {
                "version": "v0.1",
                "enabled": module_enabled,
                "agents": config_agents,
            },
        )
        self._write_json(
            root / "governance/policy/email_gateway.v0.1.json",
            {
                "version": "v0.1",
                "default_action": "deny",
                "agents": {
                    "codex": {
                        "send_allowlist": ["ops@example.com"],
                        "receive_allowlist": ["ops@example.com"],
                        "domains_allowlist": ["example.com"],
                        "max_body_bytes": max_body_bytes,
                    }
                },
            },
        )
        self._write_json(
            root / "state/supervisor_capabilities.json",
            {
                "email.poll": {"granted": poll_granted, "state": "IMPLEMENTED_NOT_ACTIVE"},
                "email.send": {"granted": send_granted, "state": "ACTIVE"},
            },
        )

    def test_send_denies_when_policy_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root)
            (root / "governance/policy/email_gateway.v0.1.json").unlink()
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@example.com",
                    subject="s",
                    body="b",
                    transport=_FakeSMTPTransport(),
                )
            self.assertEqual(ctx.exception.reason_code, DENY_POLICY_MISSING)

    def test_send_denies_when_agent_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, agent_registered=False)
            transport = _FakeSMTPTransport()
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@example.com",
                    subject="s",
                    body="b",
                    transport=transport,
                )
            self.assertEqual(ctx.exception.reason_code, DENY_AGENT_NOT_REGISTERED)
            self.assertEqual(transport.calls, 0)
            audit_path = root / "logs/control/email_gateway_audit.jsonl"
            self.assertTrue(audit_path.is_file())
            self.assertIn("DENY_AGENT_NOT_REGISTERED", audit_path.read_text(encoding="utf-8"))

    def test_send_denies_when_agent_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, agent_enabled=False)
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@example.com",
                    subject="s",
                    body="b",
                    transport=_FakeSMTPTransport(),
                )
            self.assertEqual(ctx.exception.reason_code, DENY_AGENT_CHANNEL_DISABLED)

    def test_send_denies_when_capability_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, send_granted=False)
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@example.com",
                    subject="s",
                    body="b",
                    transport=_FakeSMTPTransport(),
                )
            self.assertEqual(ctx.exception.reason_code, DENY_CAPABILITY_MISSING)

    def test_send_denies_non_allowlisted_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root)
            transport = _FakeSMTPTransport()
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@blocked.invalid",
                    subject="s",
                    body="b",
                    transport=transport,
                )
            self.assertEqual(ctx.exception.reason_code, DENY_DOMAIN_NOT_ALLOWED)
            self.assertEqual(transport.calls, 0)
            audit_path = root / "logs/control/email_gateway_audit.jsonl"
            self.assertTrue(audit_path.is_file())
            self.assertIn("DENY_DOMAIN_NOT_ALLOWED", audit_path.read_text(encoding="utf-8"))

    def test_send_denies_when_body_too_large(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, max_body_bytes=3)
            with self.assertRaises(EmailGatewayError) as ctx:
                send_email_direct(
                    repo_root=root,
                    agent="codex",
                    to="ops@example.com",
                    subject="s",
                    body="body-too-large",
                    transport=_FakeSMTPTransport(),
                )
            self.assertEqual(ctx.exception.reason_code, DENY_BODY_TOO_LARGE)

    def test_send_success_writes_deterministic_outbox_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root)
            transport = _FakeSMTPTransport()
            result_a = send_email_direct(
                repo_root=root,
                agent="codex",
                to="ops@example.com",
                subject="AI-OS",
                body="hello",
                epoch="2026-03-01",
                transport=transport,
            )
            result_b = send_email_direct(
                repo_root=root,
                agent="codex",
                to="ops@example.com",
                subject="AI-OS",
                body="hello",
                epoch="2026-03-01",
                transport=transport,
            )
            self.assertEqual(result_a["status"], "ok")
            self.assertEqual(result_a["artifact_path"], result_b["artifact_path"])
            self.assertEqual(transport.calls, 2)
            artifact = Path(result_a["artifact_path"])
            self.assertTrue(artifact.is_file())
            self.assertRegex(artifact.name, r"^2026-03-01__codex__[a-f0-9]{64}\.json$")
            payload = json.loads(artifact.read_text(encoding="utf-8"))
            self.assertEqual(payload["to"], "ops@example.com")
            self.assertNotIn("SMTP_PASS", json.dumps(payload, sort_keys=True))

    def test_poll_denies_when_capability_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, poll_granted=False)
            with self.assertRaises(EmailGatewayError) as ctx:
                poll_email_direct(
                    repo_root=root,
                    agent="codex",
                    max_messages=1,
                    transport=_FakeIMAPTransport(),
                )
            self.assertEqual(ctx.exception.reason_code, DENY_CAPABILITY_MISSING)

    def test_poll_success_writes_inbox_and_marks_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, poll_granted=True)
            transport = _FakeIMAPTransport()
            result = poll_email_direct(
                repo_root=root,
                agent="codex",
                max_messages=5,
                epoch="2026-03-01",
                transport=transport,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["messages"], 1)
            self.assertEqual(transport.marked_uids, ["7"])
            artifact = Path(result["artifacts"][0])
            self.assertTrue(artifact.is_file())

    def test_poll_filters_by_sender_and_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, poll_granted=True)
            transport = _FakeIMAPTransport()
            transport.messages = [
                {"uid": "7", "from": "ops@example.com", "to": "codex@example.com", "subject": "status report", "body": "ok"},
                {"uid": "8", "from": "alerts@example.com", "to": "codex@example.com", "subject": "ai-os signal", "body": "signal"},
            ]
            result = poll_email_direct(
                repo_root=root,
                agent="codex",
                max_messages=5,
                epoch="2026-03-01",
                from_contains="alerts@",
                subject_contains="ai-os",
                transport=transport,
            )
            self.assertEqual(result["messages"], 1)
            self.assertEqual(transport.marked_uids, ["8"])

    def test_poll_denied_message_writes_audit_and_skips_seen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._bootstrap_repo(root, poll_granted=True)
            transport = _FakeIMAPTransport()
            transport.messages = [
                {"uid": "7", "from": "blocked@other.invalid", "to": "codex@example.com", "subject": "x", "body": "hello"},
            ]
            result = poll_email_direct(
                repo_root=root,
                agent="codex",
                max_messages=5,
                epoch="2026-03-01",
                transport=transport,
            )
            self.assertEqual(result["messages"], 0)
            self.assertEqual(transport.marked_uids, [])
            audit_path = root / "logs/control/email_gateway_audit.jsonl"
            self.assertTrue(audit_path.is_file())
            self.assertIn("DENY_DOMAIN_NOT_ALLOWED", audit_path.read_text(encoding="utf-8"))

    def test_artifact_name_is_stable(self) -> None:
        payload = {
            "action": "send",
            "agent": "codex",
            "body": "hello",
            "epoch": "2026-03-01",
            "subject": "AI-OS",
            "to": "ops@example.com",
        }
        one = _artifact_name("2026-03-01", "codex", payload)
        two = _artifact_name("2026-03-01", "codex", payload)
        self.assertEqual(one, two)
        self.assertRegex(one, r"^2026-03-01__codex__[a-f0-9]{64}\.json$")


if __name__ == "__main__":
    unittest.main()
