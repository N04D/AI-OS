import json
import tempfile
import unittest
from pathlib import Path

from kernel.plugins.discovery import build_registry
from kernel.plugins.discovery import write_registry


def _manifest(plugin_id: str, version: str = "1.0.0", api_version: int = 1, extra: str = "") -> str:
    return f"""\
plugin_id: {plugin_id}
version: {version}
api_version: {api_version}
entrypoint:
  command:
    - python
    - plugin.py
  protocol: stdin_stdout_json
runtime:
  mode: subprocess
  timeout_seconds: 10
permissions:
  capabilities:
    - notify:send
{extra}"""


def _write_plugin(root: Path, rel: str, content: str) -> Path:
    p = root / rel / "plugin.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class PluginDiscoveryTests(unittest.TestCase):
    def test_single_valid_official_plugin_registry_contains_one_entry(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(official, "p1", _manifest("alpha-plugin", "1.2.3"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual(len(registry["plugins"]), 1)
            entry = registry["plugins"][0]
            self.assertEqual(entry["plugin_id"], "alpha-plugin")
            self.assertEqual(entry["trust_tier"], "official")
            self.assertFalse(entry["enabled"])

    def test_single_valid_external_plugin_registry_contains_one_entry(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(external, "p1", _manifest("beta-plugin", "1.0.0"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual(len(registry["plugins"]), 1)
            entry = registry["plugins"][0]
            self.assertEqual(entry["plugin_id"], "beta-plugin")
            self.assertEqual(entry["trust_tier"], "external")
            self.assertFalse(entry["enabled"])

    def test_invalid_plugin_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(official, "bad", _manifest("bad-plugin", "1.0.0", extra="unknown_top: nope\n"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual(registry, {"plugins": []})

    def test_collision_official_vs_external_official_kept(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(external, "p1", _manifest("shared-plugin", "9.9.9"))
            _write_plugin(official, "p2", _manifest("shared-plugin", "1.0.0"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual(len(registry["plugins"]), 1)
            entry = registry["plugins"][0]
            self.assertEqual(entry["plugin_id"], "shared-plugin")
            self.assertEqual(entry["trust_tier"], "official")
            self.assertEqual(entry["version"], "1.0.0")

    def test_collision_same_tier_highest_version_kept(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(official, "v1", _manifest("gamma-plugin", "1.2.0"))
            _write_plugin(official, "v2", _manifest("gamma-plugin", "1.10.0"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual(len(registry["plugins"]), 1)
            entry = registry["plugins"][0]
            self.assertEqual(entry["plugin_id"], "gamma-plugin")
            self.assertEqual(entry["version"], "1.10.0")
            self.assertEqual(entry["trust_tier"], "official")

    def test_registry_deterministic_order(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(official, "zeta", _manifest("zeta-plugin", "1.0.0"))
            _write_plugin(official, "alpha", _manifest("alpha-plugin", "1.0.0"))

            registry = build_registry(load_paths=(official, external))
            self.assertEqual([p["plugin_id"] for p in registry["plugins"]], ["alpha-plugin", "zeta-plugin"])

    def test_registry_file_created(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            official = base / "plugins"
            external = base / "external"
            _write_plugin(official, "p1", _manifest("delta-plugin", "1.0.0"))
            out = base / "state" / "plugins" / "registry.json"

            registry = write_registry(registry_path=out, load_paths=(official, external))
            self.assertTrue(out.exists())
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(loaded, registry)
            self.assertEqual(len(loaded["plugins"]), 1)
            self.assertFalse(loaded["plugins"][0]["enabled"])


if __name__ == "__main__":
    unittest.main()
