import hashlib
import json
import os
import stat
import shutil
import tempfile
import unittest
from pathlib import Path

from kernel.plugins.runner import MAX_LINE_BYTES
from kernel.plugins.runner import PluginRunner


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(src: Path, dest_root: Path, name: str) -> Path:
    dest = dest_root / name
    shutil.copytree(src, dest)
    plugin_bin = dest / "bin" / "plugin"
    if plugin_bin.exists():
        os.chmod(plugin_bin, 0o755)
    return dest


class PluginRunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.official_root = self.tmp / "plugins"
        self.external_root = self.tmp / "external"
        self.state_dir = self.tmp / "state" / "plugins"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.state_dir / "registry.json"
        self.config_path = self.state_dir / "config.json"
        self.audit_log = self.tmp / "logs" / "control" / "plugin-runtime.jsonl"
        self.fixture_root = Path("tests/dummy_plugins")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_registry(self, entries):
        self.registry_path.write_text(json.dumps({"plugins": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _write_config(self, plugins: dict, unsafe_allow_external: bool = False):
        payload = {
            "plugins": plugins,
            "unsafe_allow_external": unsafe_allow_external,
        }
        self.config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _entry(self, plugin_id: str, plugin_yaml: Path, trust_tier: str = "official", version: str = "1.0.0", api_version: int = 1):
        return {
            "api_version": api_version,
            "enabled": False,
            "fingerprint": _sha256(plugin_yaml),
            "path": str(plugin_yaml),
            "plugin_id": plugin_id,
            "trust_tier": trust_tier,
            "version": version,
        }

    def _runner(self):
        return PluginRunner(
            registry_path=self.registry_path,
            config_path=self.config_path,
            audit_log_path=self.audit_log,
            base_dir=self.tmp,
        )

    def test_refuse_running_when_plugin_not_enabled(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": False}})
        runner = self._runner()

        resp = runner.send_request("echo-ok", {"type": "request", "id": "1", "method": "ping", "payload": {}})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "PLUGIN_NOT_ENABLED")

    def test_allow_running_official_enabled_plugin_and_get_ok_response(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest, trust_tier="official")])
        self._write_config({"echo-ok": {"enabled": True}})
        runner = self._runner()

        resp = runner.send_request("echo-ok", {"type": "request", "id": "r1", "method": "ping", "payload": {"x": 1}})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["id"], "r1")
        self.assertEqual(resp["type"], "response")
        runner.shutdown("echo-ok")

    def test_deny_external_plugin_unless_unsafe_allow_external_true(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.external_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest, trust_tier="external")])
        self._write_config({"echo-ok": {"enabled": True}}, unsafe_allow_external=False)
        runner = self._runner()

        resp = runner.send_request("echo-ok", {"type": "request", "id": "r1", "method": "ping", "payload": {}})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "EXTERNAL_NOT_ALLOWED")

        self._write_config({"echo-ok": {"enabled": True}}, unsafe_allow_external=True)
        runner2 = self._runner()
        resp2 = runner2.send_request("echo-ok", {"type": "request", "id": "r2", "method": "ping", "payload": {}})
        self.assertTrue(resp2["ok"])
        runner2.shutdown("echo-ok")

    def test_invalid_json_response_kills_plugin_and_returns_error(self):
        pdir = _copy_fixture(self.fixture_root / "bad_json", self.official_root, "badjson")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("bad-json", manifest)])
        self._write_config({"bad-json": {"enabled": True}})
        runner = self._runner()

        resp = runner.send_request("bad-json", {"type": "request", "id": "r1", "method": "ping", "payload": {}})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "PLUGIN_INVALID_JSON_RESPONSE")

    def test_timeout_kills_plugin_and_returns_timeout_error(self):
        pdir = _copy_fixture(self.fixture_root / "hang", self.official_root, "hang")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("hang-plugin", manifest)])
        self._write_config({"hang-plugin": {"enabled": True}})
        runner = self._runner()

        resp = runner.send_request("hang-plugin", {"type": "request", "id": "r1", "method": "ping", "payload": {}})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "PLUGIN_TIMEOUT")

    def test_enforces_max_line_size(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": True}})
        runner = self._runner()

        huge = "x" * (MAX_LINE_BYTES + 100)
        req = {"type": "request", "id": "r1", "method": "ping", "payload": {"blob": huge}}
        resp = runner.send_request("echo-ok", req)
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "REQUEST_TOO_LARGE")

    def test_entrypoint_path_traversal_denied(self):
        plugin_root = self.official_root / "escape"
        plugin_root.mkdir(parents=True, exist_ok=True)
        (self.official_root / "outside.sh").write_text("#!/bin/sh\necho nope\n", encoding="utf-8")
        (plugin_root / "plugin.yaml").write_text(
            """\
plugin_id: traversal-plugin
version: 1.0.0
api_version: 1
entrypoint:
  command:
    - ../outside.sh
  protocol: stdin_stdout_json
runtime:
  mode: subprocess
  timeout_seconds: 5
permissions:
  capabilities:
    - plugin:test
""",
            encoding="utf-8",
        )
        manifest = plugin_root / "plugin.yaml"
        self._write_registry([self._entry("traversal-plugin", manifest)])
        self._write_config({"traversal-plugin": {"enabled": True}})
        runner = self._runner()

        resp = runner.send_request("traversal-plugin", {"type": "request", "id": "r1", "method": "ping", "payload": {}})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "ENTRYPOINT_OUTSIDE_PLUGIN_DIR")

    def test_no_newline_large_output_denied_not_hang(self):
        pdir = _copy_fixture(self.fixture_root / "no_newline_large", self.official_root, "nonl")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("no-newline-large", manifest)])
        self._write_config({"no-newline-large": {"enabled": True}})
        runner = self._runner()

        resp = runner.send_request(
            "no-newline-large",
            {"type": "request", "id": "r1", "method": "ping", "payload": {}},
        )
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "RESPONSE_TOO_LARGE")

    def test_audit_unwritable_refuses_before_spawn(self):
        pdir = _copy_fixture(self.fixture_root / "echo_ok", self.official_root, "echo")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("echo-ok", manifest)])
        self._write_config({"echo-ok": {"enabled": True}})

        locked_dir = self.tmp / "locked"
        locked_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(locked_dir, stat.S_IREAD | stat.S_IEXEC)
        runner = PluginRunner(
            registry_path=self.registry_path,
            config_path=self.config_path,
            audit_log_path=locked_dir / "plugin-runtime.jsonl",
            base_dir=self.tmp,
        )
        try:
            resp = runner.send_request("echo-ok", {"type": "request", "id": "r1", "method": "ping", "payload": {}})
            self.assertFalse(resp["ok"])
            self.assertEqual(resp["error"]["code"], "AUDIT_LOG_WRITE_FAILED")
            self.assertEqual(runner._procs, {})
        finally:
            os.chmod(locked_dir, stat.S_IRWXU)

    def test_unhealthy_after_threshold_and_new_runner_can_attempt(self):
        pdir = _copy_fixture(self.fixture_root / "bad_json", self.official_root, "badjson")
        manifest = pdir / "plugin.yaml"
        self._write_registry([self._entry("bad-json", manifest)])
        self._write_config({"bad-json": {"enabled": True}})
        runner = self._runner()

        for i in range(3):
            resp = runner.send_request("bad-json", {"type": "request", "id": f"r{i}", "method": "ping", "payload": {}})
            self.assertFalse(resp["ok"])
            self.assertEqual(resp["error"]["code"], "PLUGIN_INVALID_JSON_RESPONSE")

        refused = runner.send_request("bad-json", {"type": "request", "id": "rX", "method": "ping", "payload": {}})
        self.assertFalse(refused["ok"])
        self.assertEqual(refused["error"]["code"], "PLUGIN_UNHEALTHY")

        # In-memory state reset on new runner instance.
        runner2 = self._runner()
        retry = runner2.send_request("bad-json", {"type": "request", "id": "rY", "method": "ping", "payload": {}})
        self.assertFalse(retry["ok"])
        self.assertEqual(retry["error"]["code"], "PLUGIN_INVALID_JSON_RESPONSE")


if __name__ == "__main__":
    unittest.main()
