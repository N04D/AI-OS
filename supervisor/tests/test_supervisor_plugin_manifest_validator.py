from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_plugin_manifest import validate_manifest


class PluginManifestValidatorTests(unittest.TestCase):
    def _write_common_files(self, tmp: Path) -> tuple[Path, Path]:
        schema = tmp / "plugin-schema.yaml"
        policy = tmp / "plugin-policy.yaml"
        schema.write_text(
            """{
  "version":"plugin-manifest.v0.1",
  "required":[
    "api_version","name","version","trust_tier","execution.out_of_process",
    "capabilities","permissions.filesystem.allow","permissions.network.allow_hosts","signing.registry_signed"
  ],
  "types":{
    "api_version":"str","name":"str","version":"str","trust_tier":"str","execution.out_of_process":"bool",
    "capabilities":"list","permissions.filesystem.allow":"list","permissions.network.allow_hosts":"list","signing.registry_signed":"bool"
  },
  "enums":{
    "api_version":["plugin-manifest.v0.1"],
    "trust_tier":["official","community","local"]
  },
  "const":{"execution.out_of_process":true}
}""",
            encoding="utf-8",
        )
        policy.write_text(
            """{
  "version":"plugin-boundary.v0.1",
  "forbidden_capabilities":["kernel:modify","network:any","secrets:control"],
  "forbidden_filesystem_paths":["kernel/**","governance/core/**","executor/runtime/**"],
  "require_explicit_network_allowlist":true,
  "deny_secrets_control_tier":true,
  "signed_registry_required_for_official":true
}""",
            encoding="utf-8",
        )
        return schema, policy

    def test_valid_manifest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            schema, policy = self._write_common_files(tmp)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """api_version: plugin-manifest.v0.1
name: good-plugin
version: 1.0.0
trust_tier: official
execution:
  out_of_process: true
capabilities:
  - telemetry:read
permissions:
  filesystem:
    allow:
      - logs/**
  network:
    allow_hosts:
      - api.example.com
signing:
  registry_signed: true
""",
                encoding="utf-8",
            )
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertTrue(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "ALLOW_MANIFEST_VALID")

    def test_forbidden_capability_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            schema, policy = self._write_common_files(tmp)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """{
  "api_version":"plugin-manifest.v0.1",
  "name":"bad-cap-plugin",
  "version":"1.0.0",
  "trust_tier":"community",
  "execution":{"out_of_process":true},
  "capabilities":["kernel:modify"],
  "permissions":{"filesystem":{"allow":["logs/**"]},"network":{"allow_hosts":["example.com"]}},
  "signing":{"registry_signed":false}
}""",
                encoding="utf-8",
            )
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_FORBIDDEN_CAPABILITY")

    def test_forbidden_path_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            schema, policy = self._write_common_files(tmp)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """{
  "api_version":"plugin-manifest.v0.1",
  "name":"bad-path-plugin",
  "version":"1.0.0",
  "trust_tier":"community",
  "execution":{"out_of_process":true},
  "capabilities":["telemetry:read"],
  "permissions":{"filesystem":{"allow":["kernel/**"]},"network":{"allow_hosts":["example.com"]}},
  "signing":{"registry_signed":false}
}""",
                encoding="utf-8",
            )
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_FORBIDDEN_FILESYSTEM_PATH")

    def test_missing_allowlist_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            schema, policy = self._write_common_files(tmp)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """{
  "api_version":"plugin-manifest.v0.1",
  "name":"missing-network-allowlist",
  "version":"1.0.0",
  "trust_tier":"community",
  "execution":{"out_of_process":true},
  "capabilities":["telemetry:read"],
  "permissions":{"filesystem":{"allow":["logs/**"]},"network":{"allow_hosts":[]}},
  "signing":{"registry_signed":false}
}""",
                encoding="utf-8",
            )
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_NETWORK_ALLOWLIST_REQUIRED")


    def test_ambiguous_schema_contract_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """{
  "api_version":"plugin-manifest.v0.1",
  "name":"good-plugin",
  "version":"1.0.0",
  "trust_tier":"community",
  "execution":{"out_of_process":true},
  "capabilities":["telemetry:read"],
  "permissions":{"filesystem":{"allow":["logs/**"]},"network":{"allow_hosts":["example.com"]}},
  "signing":{"registry_signed":false}
}""",
                encoding="utf-8",
            )
            schema = tmp / "ambiguous-schema.yaml"
            schema.write_text(
                """{
  "required":["name"],
  "types":{"name":"str"},
  "required_top_level":["plugin_id"],
  "fields":{}
}""",
                encoding="utf-8",
            )
            policy = tmp / "policy.yaml"
            policy.write_text(json.dumps({"forbidden_capabilities": []}), encoding="utf-8")
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_INVALID")

    def test_unknown_schema_contract_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            manifest = tmp / "plugin.yaml"
            manifest.write_text(
                """{
  "api_version":"plugin-manifest.v0.1",
  "name":"good-plugin",
  "version":"1.0.0",
  "trust_tier":"community",
  "execution":{"out_of_process":true},
  "capabilities":["telemetry:read"],
  "permissions":{"filesystem":{"allow":["logs/**"]},"network":{"allow_hosts":["example.com"]}},
  "signing":{"registry_signed":false}
}""",
                encoding="utf-8",
            )
            schema = tmp / "unknown-schema.yaml"
            schema.write_text("{}", encoding="utf-8")
            policy = tmp / "policy.yaml"
            policy.write_text(json.dumps({"forbidden_capabilities": []}), encoding="utf-8")
            verdict = validate_manifest(str(manifest), str(schema), str(policy))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_SCHEMA_INVALID")


if __name__ == "__main__":
    unittest.main()
