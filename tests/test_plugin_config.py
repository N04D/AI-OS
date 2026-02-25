import json
import tempfile
import unittest
from pathlib import Path

from kernel.plugins.config import PluginConfigError
from kernel.plugins.config import load_config
from kernel.plugins.config import save_config_atomic
from kernel.plugins.config import set_enabled


class PluginConfigTests(unittest.TestCase):
    def test_default_config_on_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state" / "plugins" / "config.json"
            cfg = load_config(path)
            self.assertEqual(cfg["enabled"], [])
            self.assertFalse(cfg["unsafe_allow_external"])

    def test_legacy_config_read_normalizes_to_canonical(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "plugins": {
                            "alpha": {"enabled": True},
                            "beta": {"enabled": False},
                        },
                        "unsafe_allow_external": False,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            cfg = load_config(path)
            self.assertEqual(cfg, {"enabled": ["alpha"], "unsafe_allow_external": False})

    def test_invalid_config_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text('{"enabled":"nope","unsafe_allow_external":false}', encoding="utf-8")
            with self.assertRaises(PluginConfigError):
                load_config(path)

    def test_atomic_save_writes_deterministic_json(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "state" / "plugins" / "config.json"
            cfg = {
                "enabled": ["beta", "alpha"],
                "unsafe_allow_external": False,
            }
            save_config_atomic(path, cfg)
            text = path.read_text(encoding="utf-8")
            self.assertEqual(
                text,
                '{\n'
                '  "enabled": [\n'
                '    "alpha",\n'
                '    "beta"\n'
                '  ],\n'
                '  "unsafe_allow_external": false\n'
                "}\n",
            )
            loaded = json.loads(text)
            self.assertEqual(loaded["enabled"], ["alpha", "beta"])

    def test_set_enabled_mutation(self):
        cfg = {"enabled": [], "unsafe_allow_external": False}
        cfg = set_enabled(cfg, "alpha", True)
        self.assertEqual(cfg["enabled"], ["alpha"])

        cfg = set_enabled(cfg, "alpha", False)
        self.assertEqual(cfg["enabled"], [])


if __name__ == "__main__":
    unittest.main()
