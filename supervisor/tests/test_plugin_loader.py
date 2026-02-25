from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from supervisor.plugin_loader import PluginLoaderError
from supervisor.plugin_loader import PluginRuntime
from supervisor.plugin_loader import discover_plugins
from supervisor.plugin_loader import load_registry


class PluginLoaderTests(unittest.TestCase):
    def _manifest_json(self, plugin_id: str, command: list[str], trust_tier: str = "community") -> str:
        return json.dumps(
            {
                "api_version": "plugin-manifest.v0.1",
                "plugin_id": plugin_id,
                "name": plugin_id,
                "version": "1.0.0",
                "trust_tier": trust_tier,
                "execution": {"out_of_process": True, "command": command},
                "capabilities": ["notify:escalation"],
                "permissions": {"filesystem": {"allow": ["logs/**"]}, "network": {"allow_hosts": ["example.com"]}},
                "signing": {"registry_signed": trust_tier == "official"},
            },
            sort_keys=True,
        )

    def _write_legacy_contract(self, tmp: Path) -> tuple[str, str]:
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
        return str(schema), str(policy)

    def test_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo_plugins = tmp / "repo-plugins"
            external_plugins = tmp / "external-plugins"
            repo_plugins.mkdir()
            external_plugins.mkdir()
            schema_path, policy_path = self._write_legacy_contract(tmp)

            good_dir = repo_plugins / "good"
            bad_dir = repo_plugins / "bad"
            good_dir.mkdir()
            bad_dir.mkdir()

            (good_dir / "plugin.py").write_text(
                "import json,sys\nfor line in sys.stdin:\n req=json.loads(line)\n print(json.dumps({'id':req['id'],'ok':True}))\n sys.stdout.flush()\n",
                encoding="utf-8",
            )
            (good_dir / "plugin.yaml").write_text(
                self._manifest_json("good", ["python", str(good_dir / "plugin.py")]),
                encoding="utf-8",
            )
            (bad_dir / "plugin.yaml").write_text(
                json.dumps(
                    {
                        "api_version": "plugin-manifest.v0.1",
                        "plugin_id": "bad",
                        "name": "bad",
                        "version": "1.0.0",
                        "trust_tier": "community",
                        "execution": {"out_of_process": True, "command": ["python", "missing.py"]},
                        "capabilities": ["network:any"],
                        "permissions": {"filesystem": {"allow": ["logs/**"]}, "network": {"allow_hosts": ["*"]}},
                        "signing": {"registry_signed": False},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            registry_path = tmp / "state" / "plugins" / "registry.json"
            payload = discover_plugins(
                scan_dirs=(str(repo_plugins), str(external_plugins)),
                schema_path=schema_path,
                policy_path=policy_path,
                registry_path=registry_path,
            )
            plugins = {p["plugin_id"]: p for p in payload["plugins"]}
            self.assertTrue(plugins["good"]["valid"])
            self.assertFalse(plugins["bad"]["valid"])
            self.assertEqual(plugins["bad"]["reason_code"], "DENY_FORBIDDEN_CAPABILITY")

    def test_collision_resolution_repo_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo_plugins = tmp / "plugins"
            external_plugins = tmp / "external"
            repo_plugins.mkdir()
            external_plugins.mkdir()
            schema_path, policy_path = self._write_legacy_contract(tmp)

            repo_p = repo_plugins / "dup"
            ext_p = external_plugins / "dup"
            repo_p.mkdir()
            ext_p.mkdir()
            (repo_p / "plugin.py").write_text("print('')\n", encoding="utf-8")
            (ext_p / "plugin.py").write_text("print('')\n", encoding="utf-8")
            (repo_p / "plugin.yaml").write_text(
                self._manifest_json("same-id", ["python", str(repo_p / "plugin.py")], trust_tier="official"),
                encoding="utf-8",
            )
            (ext_p / "plugin.yaml").write_text(
                self._manifest_json("same-id", ["python", str(ext_p / "plugin.py")], trust_tier="community"),
                encoding="utf-8",
            )

            registry_path = tmp / "state" / "plugins" / "registry.json"
            payload = discover_plugins(
                scan_dirs=(str(repo_plugins), str(external_plugins)),
                schema_path=schema_path,
                policy_path=policy_path,
                registry_path=registry_path,
            )
            self.assertEqual(len(payload["plugins"]), 1)
            only = payload["plugins"][0]
            self.assertEqual(only["plugin_id"], "same-id")
            self.assertEqual(only["source"], "repo")

    def test_deny_entry_prefers_manifest_plugin_id_when_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo_plugins = tmp / "plugins"
            external_plugins = tmp / "external"
            repo_plugins.mkdir()
            external_plugins.mkdir()
            schema_path, policy_path = self._write_legacy_contract(tmp)

            plugin_dir = repo_plugins / "folder-name"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.yaml").write_text(
                json.dumps(
                    {
                        "api_version": "plugin-manifest.v0.1",
                        "plugin_id": "manifest-id",
                        "name": "manifest-id",
                        "version": "1.0.0",
                        "trust_tier": "community",
                        "execution": {"out_of_process": True, "command": ["python", "missing.py"]},
                        "capabilities": ["network:any"],
                        "permissions": {"filesystem": {"allow": ["logs/**"]}, "network": {"allow_hosts": ["example.com"]}},
                        "signing": {"registry_signed": False},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            registry_path = tmp / "state" / "plugins" / "registry.json"
            payload = discover_plugins(
                scan_dirs=(str(repo_plugins), str(external_plugins)),
                schema_path=schema_path,
                policy_path=policy_path,
                registry_path=registry_path,
            )
            self.assertEqual(len(payload["plugins"]), 1)
            only = payload["plugins"][0]
            self.assertEqual(only["plugin_id"], "manifest-id")
            self.assertFalse(only["valid"])
            self.assertEqual(only["reason_code"], "DENY_FORBIDDEN_CAPABILITY")

    def test_ipc_happy_path_with_dummy_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo_plugins = tmp / "plugins"
            external_plugins = tmp / "external"
            repo_plugins.mkdir()
            external_plugins.mkdir()
            schema_path, policy_path = self._write_legacy_contract(tmp)
            plugin_dir = repo_plugins / "dummy"
            plugin_dir.mkdir()
            script = plugin_dir / "plugin.py"
            script.write_text(
                "import json,sys\n"
                "for line in sys.stdin:\n"
                " req=json.loads(line)\n"
                " resp={'id':req['id'],'ok':True,'artifact_path':'alerts/out.json'}\n"
                " print(json.dumps(resp,sort_keys=True))\n"
                " sys.stdout.flush()\n",
                encoding="utf-8",
            )
            (plugin_dir / "plugin.yaml").write_text(
                self._manifest_json("dummy", ["python", str(script)]),
                encoding="utf-8",
            )
            registry_path = tmp / "state" / "plugins" / "registry.json"
            discover_plugins(
                scan_dirs=(str(repo_plugins), str(external_plugins)),
                schema_path=schema_path,
                policy_path=policy_path,
                registry_path=registry_path,
            )
            runtime = PluginRuntime(registry_path=registry_path, request_timeout_s=1.0, max_retries=0, failure_limit=2)
            try:
                response = runtime.dispatch("dummy", "notify:escalation", {"text": "hello"})
                self.assertTrue(response["ok"])
                self.assertEqual(response["artifact_path"], "alerts/out.json")
            finally:
                runtime.close()

    def test_timeout_handling_auto_disables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            repo_plugins = tmp / "plugins"
            external_plugins = tmp / "external"
            repo_plugins.mkdir()
            external_plugins.mkdir()
            schema_path, policy_path = self._write_legacy_contract(tmp)
            plugin_dir = repo_plugins / "slow"
            plugin_dir.mkdir()
            script = plugin_dir / "plugin.py"
            script.write_text(
                "import time,sys\nfor _line in sys.stdin:\n time.sleep(5)\n",
                encoding="utf-8",
            )
            (plugin_dir / "plugin.yaml").write_text(
                self._manifest_json("slow", ["python", str(script)]),
                encoding="utf-8",
            )
            registry_path = tmp / "state" / "plugins" / "registry.json"
            discover_plugins(
                scan_dirs=(str(repo_plugins), str(external_plugins)),
                schema_path=schema_path,
                policy_path=policy_path,
                registry_path=registry_path,
            )
            runtime = PluginRuntime(registry_path=registry_path, request_timeout_s=0.1, max_retries=0, failure_limit=1)
            try:
                with self.assertRaises(PluginLoaderError):
                    runtime.dispatch("slow", "notify:escalation", {"text": "timeout"})
                time.sleep(0.05)
                payload = load_registry(registry_path=registry_path)
                plugin = payload["plugins"][0]
                self.assertFalse(plugin["enabled"])
                self.assertEqual(plugin["reason_code"], "DENY_PLUGIN_REPEATED_FAILURE")
            finally:
                runtime.close()


if __name__ == "__main__":
    unittest.main()
