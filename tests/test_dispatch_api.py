import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from kernel.dispatch import dispatch


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(src: Path, dest_root: Path, name: str) -> Path:
    dest = dest_root / name
    shutil.copytree(src, dest)
    plugin_bin = dest / "bin" / "plugin"
    if plugin_bin.exists():
        os.chmod(plugin_bin, 0o755)
    return dest


def _set_methods(manifest_path: Path, methods: list[str]) -> None:
    raw = manifest_path.read_text(encoding="utf-8").rstrip() + "\n"
    if "methods:" in raw:
        raw = raw.split("methods:", 1)[0].rstrip() + "\n"
    raw += "methods:\n"
    for method in methods:
        raw += f"  - {method}\n"
    manifest_path.write_text(raw, encoding="utf-8")


class DispatchApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.official_root = self.tmp / "plugins"
        self.state_dir = self.tmp / "state" / "plugins"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.state_dir / "registry.json"
        self.config_path = self.state_dir / "config.json"
        self.audit_log = self.tmp / "logs" / "control" / "plugin-runtime.jsonl"
        self.fixture_root = Path("tests/dummy_plugins")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_registry(self, entries):
        self.registry_path.write_text(
            json.dumps({"plugins": entries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_config(self, plugins: dict, unsafe_allow_external: bool = False):
        payload = {
            "plugins": plugins,
            "unsafe_allow_external": unsafe_allow_external,
        }
        self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _entry(self, plugin_id: str, plugin_yaml: Path, trust_tier: str = "official"):
        return {
            "api_version": 1,
            "enabled": False,
            "fingerprint": _sha256(plugin_yaml),
            "path": str(plugin_yaml),
            "plugin_id": plugin_id,
            "trust_tier": trust_tier,
            "version": "1.0.0",
        }

    def _dispatch(self, plugin_id: str, method: str, payload):
        return dispatch(
            plugin_id,
            method,
            payload,
            registry_path=str(self.registry_path),
            config_path=str(self.config_path),
            audit_log_path=str(self.audit_log),
            runner_state_dir_base=str(self.tmp / "state" / "plugins" / "runtime"),
        )

    def test_valid_dispatch_returns_ok_true(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": True}})

        resp = self._dispatch("echo-ok", "on_event", {"x": 1})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["plugin_id"], "echo-ok")
        self.assertIsInstance(resp["request_id"], str)
        self.assertEqual(resp["result"]["echo_method"], "on_event")

    def test_dispatch_denies_non_dict_payload(self):
        resp = self._dispatch("echo-ok", "ping", "nope")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "DISPATCH_INVALID_ARGS")
        self.assertEqual(resp["error"]["details"], ["payload"])

    def test_dispatch_denies_plugin_not_enabled_with_runner_refusal(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": False}})

        resp = self._dispatch("echo-ok", "on_event", {})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "DISPATCH_RUNNER_REFUSED")
        self.assertEqual(resp["error"]["details"][0], "PLUGIN_NOT_ENABLED")

    def test_dispatch_returns_runner_error_for_invalid_json_plugin_response(self):
        pdir = _copy_fixture(self.fixture_root / "bad_json", self.official_root, "badjson")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("bad-json", manifest)])
        self._write_config({"bad-json": {"enabled": True}})

        resp = self._dispatch("bad-json", "on_event", {})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "DISPATCH_RUNNER_ERROR")
        self.assertEqual(resp["error"]["details"][0], "PLUGIN_INVALID_JSON_RESPONSE")

    def test_dispatch_returns_runner_error_on_timeout(self):
        pdir = _copy_fixture(self.fixture_root / "hang", self.official_root, "hang")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("hang-plugin", manifest)])
        self._write_config({"hang-plugin": {"enabled": True}})

        resp = self._dispatch("hang-plugin", "on_event", {})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "DISPATCH_RUNNER_ERROR")
        self.assertEqual(resp["error"]["details"][0], "PLUGIN_TIMEOUT")

    def test_deterministic_response_schema_keys_present(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": True}})

        resp = self._dispatch("echo-ok", "on_event", {"k": "v"})
        self.assertEqual(list(resp.keys()), ["ok", "plugin_id", "request_id", "result"])

        fail = self._dispatch("echo-ok", "", {})
        self.assertEqual(list(fail.keys()), ["ok", "plugin_id", "request_id", "error"])
        self.assertEqual(list(fail["error"].keys()), ["code", "message", "details"])

    def test_methods_allow_notify_and_deny_on_event_when_not_listed(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "notify")
        manifest = pdir / "plugin.yaml"
        _set_methods(manifest, ["notify"])
        self._write_registry([self._entry("notify-only", manifest)])
        self._write_config({"notify-only": {"enabled": True}})

        ok = self._dispatch("notify-only", "notify", {"x": 1})
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["result"]["echo_method"], "notify")

        denied = self._dispatch("notify-only", "on_event", {"x": 1})
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "METHOD_NOT_ALLOWED")
        self.assertEqual(list(denied.keys()), ["ok", "plugin_id", "request_id", "error"])
        self.assertEqual(list(denied["error"].keys()), ["code", "message", "details"])

    def test_methods_missing_defaults_to_on_event_only(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "default")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("default-methods", manifest)])
        self._write_config({"default-methods": {"enabled": True}})

        allowed = self._dispatch("default-methods", "on_event", {"x": 1})
        self.assertTrue(allowed["ok"])

        denied = self._dispatch("default-methods", "notify", {"x": 1})
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"]["code"], "METHOD_NOT_ALLOWED")


if __name__ == "__main__":
    unittest.main()
