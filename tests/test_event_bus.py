import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kernel.events import emit


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_fixture(src: Path, dest_root: Path, name: str) -> Path:
    dest = dest_root / name
    shutil.copytree(src, dest)
    plugin_bin = dest / "bin" / "plugin"
    if plugin_bin.exists():
        os.chmod(plugin_bin, 0o755)
    return dest


def _set_subscriptions(manifest_path: Path, items: list[str]) -> None:
    raw = manifest_path.read_text(encoding="utf-8").rstrip() + "\n"
    if "subscriptions:" in raw:
        head = raw.split("subscriptions:", 1)[0].rstrip() + "\n"
        raw = head
    if items:
        raw += "subscriptions:\n"
        for item in items:
            raw += f"  - {item}\n"
    manifest_path.write_text(raw, encoding="utf-8")


def _set_plugin_id(manifest_path: Path, plugin_id: str) -> None:
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    out = []
    replaced = False
    for line in lines:
        if line.startswith("plugin_id:"):
            out.append(f"plugin_id: {plugin_id}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.insert(0, f"plugin_id: {plugin_id}")
    manifest_path.write_text("\n".join(out) + "\n", encoding="utf-8")


class EventBusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.official_root = self.tmp / "plugins"
        self.external_root = self.tmp / "external"
        self.state_dir = self.tmp / "state" / "plugins"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.state_dir / "registry.json"
        self.config_path = self.state_dir / "config.json"
        self.audit_log = self.tmp / "logs" / "control" / "kernel-events.jsonl"
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

    def _emit(self, event_type: str, payload):
        return emit(
            event_type,
            payload,
            registry_path=str(self.registry_path),
            config_path=str(self.config_path),
            audit_log_path=str(self.audit_log),
        )

    def test_emit_invalid_args(self):
        out = self._emit("", {})
        self.assertFalse(out["ok"])
        self.assertEqual(out["event_type"], "")
        self.assertEqual(out["delivered"], [])
        self.assertEqual(out["failed"][0]["error_code"], "EVENT_BUS_INVALID_ARGS")

        out2 = self._emit("test.event", "bad")
        self.assertFalse(out2["ok"])
        self.assertEqual(out2["failed"][0]["error_code"], "EVENT_BUS_INVALID_ARGS")

    def test_emit_delivers_only_to_enabled_plugin_with_matching_subscription(self):
        pdir = _copy_fixture(self.fixture_root / "subscriber_ok", self.official_root, "sub")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "sub-ok")
        _set_subscriptions(manifest, ["test.event"])

        self._write_registry([self._entry("sub-ok", manifest)])
        self._write_config({"sub-ok": {"enabled": True}})

        out = self._emit("test.event", {"x": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(out["event_type"], "test.event")
        self.assertEqual(out["delivered"], [{"plugin_id": "sub-ok", "ok": True, "error_code": None}])
        self.assertEqual(out["failed"], [])

    def test_plugin_without_subscriptions_does_not_receive_event(self):
        pdir = _copy_fixture(self.fixture_root / "no_subscriptions", self.official_root, "nosub")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "no-subscriptions")

        self._write_registry([self._entry("no-subscriptions", manifest)])
        self._write_config({"no-subscriptions": {"enabled": True}})

        out = self._emit("test.event", {"x": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(out["delivered"], [])
        self.assertEqual(out["failed"], [])

    def test_disabled_plugin_does_not_receive_event(self):
        pdir = _copy_fixture(self.fixture_root / "subscriber_ok", self.official_root, "sub")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "sub-disabled")
        _set_subscriptions(manifest, ["test.event"])

        self._write_registry([self._entry("sub-disabled", manifest)])
        self._write_config({"sub-disabled": {"enabled": False}})

        out = self._emit("test.event", {"x": 1})
        self.assertTrue(out["ok"])
        self.assertEqual(out["delivered"], [])
        self.assertEqual(out["failed"], [])

    def test_external_plugin_denied_when_unsafe_allow_external_false(self):
        pdir = _copy_fixture(self.fixture_root / "subscriber_ok", self.external_root, "sub")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "sub-external")
        _set_subscriptions(manifest, ["test.event"])

        self._write_registry([self._entry("sub-external", manifest, trust_tier="external")])
        self._write_config({"sub-external": {"enabled": True}}, unsafe_allow_external=False)

        out = self._emit("test.event", {"x": 1})
        self.assertFalse(out["ok"])
        self.assertEqual(
            out["delivered"],
            [{"plugin_id": "sub-external", "ok": False, "error_code": "EVENT_BUS_EXTERNAL_NOT_ALLOWED"}],
        )
        self.assertEqual(out["failed"][0]["plugin_id"], "sub-external")
        self.assertEqual(out["failed"][0]["error_code"], "EVENT_BUS_EXTERNAL_NOT_ALLOWED")

    def test_dispatch_failure_recorded_in_failed(self):
        pdir = _copy_fixture(self.fixture_root / "bad_json", self.official_root, "bad")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "bad-json")
        _set_subscriptions(manifest, ["test.event"])

        self._write_registry([self._entry("bad-json", manifest)])
        self._write_config({"bad-json": {"enabled": True}})

        out = self._emit("test.event", {"x": 1})
        self.assertFalse(out["ok"])
        self.assertEqual(out["delivered"][0]["plugin_id"], "bad-json")
        self.assertEqual(out["delivered"][0]["ok"], False)
        self.assertEqual(out["failed"][0]["plugin_id"], "bad-json")
        self.assertEqual(out["failed"][0]["error_code"], "DISPATCH_RUNNER_ERROR")

    def test_deterministic_ordering_delivered_and_failed(self):
        ok_dir = _copy_fixture(self.fixture_root / "subscriber_ok", self.official_root, "ok")
        ok_manifest = ok_dir / "plugin.yaml"
        _set_plugin_id(ok_manifest, "b-plugin")
        _set_subscriptions(ok_manifest, ["test.event"])

        fail_dir = _copy_fixture(self.fixture_root / "bad_json", self.official_root, "fail")
        fail_manifest = fail_dir / "plugin.yaml"
        _set_plugin_id(fail_manifest, "a-plugin")
        _set_subscriptions(fail_manifest, ["test.event"])

        entries = [
            self._entry("b-plugin", ok_manifest),
            self._entry("a-plugin", fail_manifest),
        ]
        self._write_registry(entries)
        self._write_config({"a-plugin": {"enabled": True}, "b-plugin": {"enabled": True}})

        out = self._emit("test.event", {"x": 1})
        delivered_ids = [d["plugin_id"] for d in out["delivered"]]
        self.assertEqual(delivered_ids, sorted(delivered_ids))
        failed_ids = [f["plugin_id"] for f in out["failed"]]
        self.assertEqual(failed_ids, sorted(failed_ids))

    def test_event_bus_uses_fixed_on_event_method(self):
        pdir = _copy_fixture(self.fixture_root / "subscriber_ok", self.official_root, "fixed")
        manifest = pdir / "plugin.yaml"
        _set_plugin_id(manifest, "fixed-method-plugin")
        _set_subscriptions(manifest, ["test.event"])

        self._write_registry([self._entry("fixed-method-plugin", manifest)])
        self._write_config({"fixed-method-plugin": {"enabled": True}})

        calls: list[tuple[str, str, dict]] = []

        def _fake_dispatch(plugin_id, method, payload, **kwargs):
            calls.append((plugin_id, method, payload))
            return {
                "ok": True,
                "plugin_id": plugin_id,
                "request_id": "r1",
                "result": {"echo_method": method},
            }

        with mock.patch("kernel.events.dispatch", side_effect=_fake_dispatch):
            out = self._emit("test.event", {"x": 1})

        self.assertTrue(out["ok"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "fixed-method-plugin")
        self.assertEqual(calls[0][1], "on_event")


if __name__ == "__main__":
    unittest.main()
