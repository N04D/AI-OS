import tempfile
import unittest
from pathlib import Path

from scripts.validate_plugin_manifest import main
from scripts.validate_plugin_manifest import validate_manifest


VALID_MANIFEST = """\
plugin_id: sample-plugin
version: 1.2.3
api_version: 1
entrypoint:
  command:
    - python
    - plugin.py
  protocol: stdin_stdout_json
runtime:
  mode: subprocess
  timeout_seconds: 30
permissions:
  capabilities:
    - notify:send
"""


class PluginManifestValidatorTests(unittest.TestCase):
    def _write_manifest(self, directory: Path, content: str) -> Path:
        path = directory / "plugin.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_minimal_manifest_allow_true(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self._write_manifest(Path(td), VALID_MANIFEST)
            verdict = validate_manifest(str(manifest))
            self.assertEqual(verdict, {"allow": True, "reason_code": None})

    def test_missing_required_field_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST.replace("api_version: 1\n", "")
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_unknown_top_level_field_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST + "extra_field: should_fail\n"
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_runtime_mode_not_subprocess_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST.replace("mode: subprocess", "mode: in_process")
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_protocol_not_stdin_stdout_json_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST.replace("protocol: stdin_stdout_json", "protocol: http")
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_forbidden_filesystem_path_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST + """\
  filesystem:
    paths:
      - governance/policy/plugins/plugin-boundary.v0.1.yaml
"""
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_FORBIDDEN_FILESYSTEM_PATH")

    def test_invalid_plugin_id_format_deny(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST.replace("plugin_id: sample-plugin", "plugin_id: Sample_Plugin")
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_methods_valid_list_passes(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST + """\
methods:
  - on_event
  - notify
"""
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertEqual(verdict, {"allow": True, "reason_code": None})

    def test_methods_non_list_fails(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST + "methods: on_event\n"
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_methods_empty_string_fails(self):
        with tempfile.TemporaryDirectory() as td:
            content = VALID_MANIFEST + """\
methods:
  - ""
"""
            manifest = self._write_manifest(Path(td), content)
            verdict = validate_manifest(str(manifest))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_VALIDATION")

    def test_cli_exit_code_success_and_failure(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self._write_manifest(Path(td), VALID_MANIFEST)
            self.assertEqual(main([str(manifest)]), 0)

            bad = self._write_manifest(Path(td), VALID_MANIFEST + "unknown: x\n")
            self.assertEqual(main([str(bad)]), 1)


if __name__ == "__main__":
    unittest.main()
