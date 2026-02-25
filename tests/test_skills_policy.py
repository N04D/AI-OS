import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from kernel.skills import _reset_runtime_state
from kernel.skills import run_skill


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(src: Path, dest_root: Path, name: str) -> Path:
    dest = dest_root / name
    shutil.copytree(src, dest)
    plugin_bin = dest / "bin" / "plugin"
    if plugin_bin.exists():
        os.chmod(plugin_bin, 0o755)
    return dest


class SkillPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

        self.official_root = self.tmp / "plugins"
        self.fixture_root = Path("tests/dummy_plugins")

        self.state_dir = self.tmp / "state" / "plugins"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.state_dir / "registry.json"
        self.config_path = self.state_dir / "config.json"

        self.audit_path = self.tmp / "logs" / "control" / "skills.jsonl"
        self.policy_path = self.tmp / "governance" / "policy" / "skills" / "skills.v0.1.yaml"
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)

        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"

        self.registry_path.write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "api_version": 1,
                            "enabled": False,
                            "fingerprint": _sha256(manifest),
                            "path": str(manifest),
                            "plugin_id": "echo-ok",
                            "trust_tier": "official",
                            "version": "1.0.0",
                        }
                    ]
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self.config_path.write_text(
            json.dumps({"plugins": {"echo-ok": {"enabled": True}}, "unsafe_allow_external": False}, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        _reset_runtime_state()
        self._write_policy()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_policy(
        self,
        *,
        include_unknown_top_level: bool = False,
        cooldown_seconds: int | None = None,
        allowed_recipients: list[str] | None = None,
        per_user_per_hour: int | None = None,
    ) -> None:
        skill_def: dict[str, object] = {
            "description": "Send message through echo plugin",
            "target": {"plugin_id": "echo-ok", "method": "on_event"},
            "input_schema": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string"},
                    "recipient": {"type": "string"},
                },
            },
            "safe_defaults": {"source": "skills"},
        }
        if cooldown_seconds is not None:
            skill_def["rate_limit"] = {"cooldown_seconds": cooldown_seconds}
        if allowed_recipients is not None:
            skill_def["allowed_recipients"] = list(allowed_recipients)

        channel_def: dict[str, object] = {
            "allowed_users": ["111"],
            "allowed_skills": ["send-message"],
        }
        if per_user_per_hour is not None:
            channel_def["quotas"] = {"per_user_per_hour": per_user_per_hour}

        policy: dict[str, object] = {
            "version": "0.1",
            "default_decision": "deny",
            "skills": {
                "send-message": skill_def,
            },
            "channels": {
                "telegram": channel_def,
            },
        }
        if include_unknown_top_level:
            policy["unknown_key"] = "boom"

        self.policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _run(
        self,
        *,
        channel_id: str,
        user_id: str,
        skill_id: str,
        payload: dict,
        now: float | None = None,
    ) -> dict:
        kwargs = {}
        if now is not None:
            kwargs["now_fn"] = lambda: now
        return run_skill(
            channel_id,
            user_id,
            skill_id,
            payload,
            policy_path=str(self.policy_path),
            registry_path=str(self.registry_path),
            config_path=str(self.config_path),
            audit_log_path=str(self.audit_path),
            **kwargs,
        )

    def test_valid_policy_allows_telegram_chat_for_allowed_skill(self):
        result = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["skill_id"], "send-message")
        self.assertTrue(result["result"]["ok"])

    def test_deny_unknown_skill(self):
        result = self._run(channel_id="telegram", user_id="111", skill_id="unknown-skill", payload={"text": "hello"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_DENIED")
        self.assertIn("skill_not_allowed", result["error"]["details"])

    def test_deny_user_not_in_allowed_users(self):
        result = self._run(channel_id="telegram", user_id="999", skill_id="send-message", payload={"text": "hello"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_DENIED")
        self.assertIn("user_not_allowed", result["error"]["details"])

    def test_deny_channel_not_defined(self):
        result = self._run(channel_id="discord", user_id="111", skill_id="send-message", payload={"text": "hello"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_DENIED")
        self.assertIn("channel_not_allowed", result["error"]["details"])

    def test_deny_invalid_payload_missing_required_field(self):
        result = self._run(channel_id="telegram", user_id="111", skill_id="send-message", payload={})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_INVALID_ARGS")
        self.assertIn("missing_required:text", result["error"]["details"])

    def test_fail_closed_when_policy_has_unknown_top_level_key(self):
        self._write_policy(include_unknown_top_level=True)
        result = self._run(channel_id="telegram", user_id="111", skill_id="send-message", payload={"text": "hello"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_POLICY_INVALID")

    def test_cooldown_blocks_rapid_repeat(self):
        self._write_policy(cooldown_seconds=10)
        first = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello"},
            now=1000.0,
        )
        second = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello"},
            now=1005.0,
        )
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"]["code"], "SKILL_RATE_LIMITED")

    def test_cooldown_allows_after_time_passes(self):
        self._write_policy(cooldown_seconds=10)
        first = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello"},
            now=1000.0,
        )
        second = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello"},
            now=1011.0,
        )
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])

    def test_quota_blocks_after_threshold(self):
        self._write_policy(per_user_per_hour=2)
        first = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "one"},
            now=1000.0,
        )
        second = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "two"},
            now=1100.0,
        )
        third = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "three"},
            now=1200.0,
        )
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertFalse(third["ok"])
        self.assertEqual(third["error"]["code"], "SKILL_QUOTA_EXCEEDED")

    def test_scope_violation_denies_unauthorized_recipient(self):
        self._write_policy(allowed_recipients=["alice", "bob"])
        result = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello", "recipient": "mallory"},
            now=1000.0,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "SKILL_SCOPE_VIOLATION")

    def test_deterministic_error_response_shape(self):
        self._write_policy(allowed_recipients=["alice"])
        result = self._run(
            channel_id="telegram",
            user_id="111",
            skill_id="send-message",
            payload={"text": "hello", "recipient": "mallory"},
            now=1000.0,
        )
        self.assertEqual(list(result.keys()), ["ok", "skill_id", "error"])
        self.assertEqual(list(result["error"].keys()), ["code", "details"])

    def test_deterministic_response_keys_ordering(self):
        ok_result = self._run(channel_id="telegram", user_id="111", skill_id="send-message", payload={"text": "hello"})
        self.assertEqual(list(ok_result.keys()), ["ok", "skill_id", "result"])

        deny_result = self._run(channel_id="telegram", user_id="111", skill_id="unknown", payload={"text": "hello"})
        self.assertEqual(list(deny_result.keys()), ["ok", "skill_id", "error"])
        self.assertEqual(list(deny_result["error"].keys()), ["code", "details"])


if __name__ == "__main__":
    unittest.main()
