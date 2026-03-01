import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "aios_plugins.py"),
        *args,
    ]
    return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)


def _write_registry(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"plugins": entries}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_config(path: Path, *, enabled: list[str], unsafe: bool, plugins: dict[str, dict] | None = None) -> None:
    payload = {
        "enabled": enabled,
        "unsafe_allow_external": unsafe,
    }
    if plugins is not None:
        payload["plugins"] = plugins
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class AiosPluginsCliTests(unittest.TestCase):
    def _entry(self, plugin_id: str, trust_tier: str = "official") -> dict:
        return {
            "api_version": 1,
            "enabled": False,
            "fingerprint": "fp",
            "path": "tests/dummy_plugins/echo_ok/plugin.yaml",
            "plugin_id": plugin_id,
            "trust_tier": trust_tier,
            "version": "1.0.0",
        }

    def test_list_renders_expected_rows(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state" / "plugins" / "registry.json"
            cfg = tmp / "state" / "plugins" / "config.json"
            audit = tmp / "logs" / "control" / "plugin-events.jsonl"
            _write_registry(reg, [self._entry("alpha"), self._entry("beta", "external")])
            _write_config(cfg, enabled=["alpha", "beta"], unsafe=False)

            p = _run_cli(
                [
                    "--registry-path",
                    str(reg),
                    "--config-path",
                    str(cfg),
                    "--audit-log-path",
                    str(audit),
                    "list",
                ]
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("plugin_id | version | trust_tier | enabled_effective", p.stdout)
            self.assertIn("alpha | 1.0.0 | official | true", p.stdout)
            self.assertIn("beta | 1.0.0 | external | false", p.stdout)

    def test_enable_denies_unknown_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            audit = tmp / "logs/control/plugin-events.jsonl"
            _write_registry(reg, [])
            _write_config(cfg, enabled=[], unsafe=False)

            p = _run_cli(["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "enable", "missing"])
            self.assertEqual(p.returncode, 1)
            self.assertIn("PLUGIN_NOT_DISCOVERED", p.stdout)

    def test_enable_denies_external_when_unsafe_false(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            audit = tmp / "logs/control/plugin-events.jsonl"
            _write_registry(reg, [self._entry("ext", "external")])
            _write_config(cfg, enabled=[], unsafe=False)

            p = _run_cli(["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "enable", "ext"])
            self.assertEqual(p.returncode, 1)
            self.assertIn("EXTERNAL_NOT_ALLOWED", p.stdout)

    def test_enable_allows_external_when_unsafe_true(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            audit = tmp / "logs/control/plugin-events.jsonl"
            _write_registry(reg, [self._entry("ext", "external")])
            _write_config(cfg, enabled=[], unsafe=True)

            p = _run_cli(["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "enable", "ext"])
            self.assertEqual(p.returncode, 0, p.stdout)
            new_cfg = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertIn("ext", new_cfg["enabled"])
            self.assertEqual(new_cfg.keys(), {"enabled", "unsafe_allow_external"})

    def test_enable_audit_unwritable_denies_and_config_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            locked = tmp / "locked"
            locked.mkdir(parents=True, exist_ok=True)
            os.chmod(locked, stat.S_IREAD | stat.S_IEXEC)
            audit = locked / "plugin-events.jsonl"
            _write_registry(reg, [self._entry("alpha", "official")])
            _write_config(cfg, enabled=[], unsafe=False)
            before = cfg.read_text(encoding="utf-8")
            try:
                p = _run_cli(["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "enable", "alpha"])
                self.assertEqual(p.returncode, 1)
                self.assertIn("AUDIT_LOG_WRITE_FAILED", p.stdout)
                after = cfg.read_text(encoding="utf-8")
                self.assertEqual(before, after)
            finally:
                os.chmod(locked, stat.S_IRWXU)

    def test_disable_writes_audit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            audit = tmp / "logs/control/plugin-events.jsonl"
            _write_registry(reg, [self._entry("alpha")])
            _write_config(cfg, enabled=["alpha"], unsafe=False)

            p = _run_cli(["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "disable", "alpha"])
            self.assertEqual(p.returncode, 0)
            rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(rows[-1]["action"], "disable")
            self.assertEqual(rows[-1]["result"], "ok")

    def test_set_unsafe_external_writes_audit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            reg = tmp / "state/plugins/registry.json"
            cfg = tmp / "state/plugins/config.json"
            audit = tmp / "logs/control/plugin-events.jsonl"
            _write_registry(reg, [])
            _write_config(cfg, enabled=[], unsafe=False)

            p = _run_cli(
                ["--registry-path", str(reg), "--config-path", str(cfg), "--audit-log-path", str(audit), "set-unsafe-external", "true"]
            )
            self.assertEqual(p.returncode, 0, p.stdout)
            loaded = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertTrue(loaded["unsafe_allow_external"])
            rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(rows[-1]["action"], "set_unsafe_external")
            self.assertEqual(rows[-1]["result"], "ok")


if __name__ == "__main__":
    unittest.main()
