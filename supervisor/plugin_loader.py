from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validate_plugin_manifest import _load_yaml
from scripts.validate_plugin_manifest import validate_manifest


DEFAULT_SCAN_DIRS = ("plugins", "/var/lib/ai-os/plugins")
DEFAULT_REGISTRY_PATH = Path("state/plugins/registry.json")
DEFAULT_SCHEMA_PATH = "governance/schema/plugins/plugin-manifest.v0.1.yaml"
DEFAULT_POLICY_PATH = "governance/policy/plugins/plugin-boundary.v0.1.yaml"


class PluginLoaderError(RuntimeError):
    pass


def _ensure_readable(path: str, deny_code: str) -> None:
    p = Path(path)
    if not p.exists():
        raise PluginLoaderError(deny_code)
    if not p.is_file():
        raise PluginLoaderError(deny_code)
    try:
        p.read_text(encoding="utf-8")
    except Exception as exc:
        raise PluginLoaderError(deny_code) from exc


def _safe_under_root(root: Path, candidate: Path) -> bool:
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve()
    except Exception:
        return False
    return resolved_candidate == resolved_root or resolved_root in resolved_candidate.parents


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = _load_yaml(str(path))
    if not isinstance(payload, dict):
        raise PluginLoaderError("DENY_MANIFEST_NOT_MAPPING")
    return payload


def _entry_command(manifest: dict[str, Any], plugin_dir: Path) -> list[str]:
    execution = manifest.get("execution", {})
    command = None
    if isinstance(execution, dict):
        command = execution.get("command")
    if command is None:
        runtime = manifest.get("runtime", {})
        if isinstance(runtime, dict):
            command = runtime.get("command")
    if isinstance(command, str):
        return [command]
    if isinstance(command, list) and all(isinstance(item, str) for item in command):
        return [str(item) for item in command]
    # Safe default for tests/dev: optional sibling executable.
    default_script = plugin_dir / "plugin.py"
    if default_script.exists():
        return ["python", str(default_script)]
    raise PluginLoaderError("DENY_PLUGIN_COMMAND_MISSING")


def _source_for(path: Path, repo_plugins_dir: Path) -> str:
    return "repo" if _safe_under_root(repo_plugins_dir, path) else "external"




def _plugin_id_from_manifest_on_deny(manifest_path: Path) -> str:
    """Best-effort manifest identity read for deny entries; never implies validity."""
    fallback = manifest_path.parent.name
    try:
        payload = _load_yaml(str(manifest_path))
    except Exception:
        return fallback
    if not isinstance(payload, dict):
        return fallback
    for key in ("plugin_id", "name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def _collision_priority(entry: dict[str, Any]) -> tuple[int, int, str]:
    source_priority = 2 if entry.get("source") == "repo" else 1
    trust_priority = 2 if entry.get("trust_tier") == "official" else 1
    return (source_priority, trust_priority, str(entry.get("manifest_path", "")))


def _build_registry_payload(plugins: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "plugin-registry.v0.1",
        "plugins": sorted(plugins, key=lambda item: (str(item.get("plugin_id", "")), str(item.get("source", "")))),
    }


def write_registry(payload: dict[str, Any], registry_path: Path = DEFAULT_REGISTRY_PATH) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_registry(registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    if not registry_path.exists():
        return _build_registry_payload([])
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return _build_registry_payload([])
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        return _build_registry_payload([])
    return _build_registry_payload([p for p in plugins if isinstance(p, dict)])


def discover_plugins(
    *,
    scan_dirs: tuple[str, ...] = DEFAULT_SCAN_DIRS,
    schema_path: str = DEFAULT_SCHEMA_PATH,
    policy_path: str = DEFAULT_POLICY_PATH,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, Any]:
    _ensure_readable(schema_path, "DENY_SCHEMA_MISSING")
    _ensure_readable(policy_path, "DENY_POLICY_MISSING")

    repo_plugins_dir = Path(scan_dirs[0]).resolve()
    all_entries: list[dict[str, Any]] = []
    for scan_dir in scan_dirs:
        root = Path(scan_dir)
        if not root.exists():
            continue
        for manifest_path in sorted(root.glob("**/plugin.yaml")):
            if not manifest_path.is_file():
                continue
            if not _safe_under_root(root, manifest_path):
                continue
            verdict = validate_manifest(str(manifest_path), schema_path, policy_path)
            if not verdict.get("allow", False):
                all_entries.append(
                    {
                        "plugin_id": _plugin_id_from_manifest_on_deny(manifest_path),
                        "manifest_path": str(manifest_path),
                        "source": _source_for(manifest_path, repo_plugins_dir),
                        "enabled": False,
                        "valid": False,
                        "reason_code": verdict.get("reason_code", "DENY_UNKNOWN"),
                    }
                )
                continue
            manifest = _read_manifest(manifest_path)
            plugin_id = str(manifest.get("plugin_id") or manifest.get("name") or manifest_path.parent.name)
            command = _entry_command(manifest, manifest_path.parent)
            all_entries.append(
                {
                    "plugin_id": plugin_id,
                    "name": str(manifest.get("name", plugin_id)),
                    "version": str(manifest.get("version", "")),
                    "trust_tier": str(manifest.get("trust_tier", "")),
                    "manifest_path": str(manifest_path),
                    "source": _source_for(manifest_path, repo_plugins_dir),
                    "enabled": True,
                    "valid": True,
                    "reason_code": "ALLOW_MANIFEST_VALID",
                    "capabilities": sorted({str(v) for v in (manifest.get("capabilities") or [])}),
                    "command": command,
                    "working_dir": str(manifest_path.parent.resolve()),
                }
            )

    chosen: dict[str, dict[str, Any]] = {}
    for entry in sorted(all_entries, key=lambda item: (str(item.get("plugin_id", "")), str(item.get("manifest_path", "")))):
        plugin_id = str(entry.get("plugin_id", ""))
        current = chosen.get(plugin_id)
        if current is None or _collision_priority(entry) > _collision_priority(current):
            chosen[plugin_id] = entry
    payload = _build_registry_payload(list(chosen.values()))
    write_registry(payload, registry_path=registry_path)
    return payload


def set_plugin_enabled(plugin_id: str, enabled: bool, registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    payload = load_registry(registry_path=registry_path)
    found = False
    for plugin in payload["plugins"]:
        if str(plugin.get("plugin_id")) == plugin_id:
            plugin["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        raise PluginLoaderError(f"DENY_PLUGIN_NOT_FOUND:{plugin_id}")
    write_registry(payload, registry_path=registry_path)
    return payload


def _sanitize_artifact_path(raw: str, artifacts_dir: Path) -> str:
    if not raw:
        return raw
    p = Path(raw)
    if p.is_absolute():
        raise PluginLoaderError("DENY_ARTIFACT_PATH_ESCAPE")
    norm = Path(os.path.normpath(str(p)))
    if str(norm).startswith(".."):
        raise PluginLoaderError("DENY_ARTIFACT_PATH_ESCAPE")
    resolved = (artifacts_dir / norm).resolve()
    if artifacts_dir.resolve() not in resolved.parents and resolved != artifacts_dir.resolve():
        raise PluginLoaderError("DENY_ARTIFACT_PATH_ESCAPE")
    return str(norm).replace("\\", "/")


@dataclass
class _PluginProc:
    process: subprocess.Popen[str]
    out_queue: queue.Queue[str]
    lock: threading.Lock


class PluginRuntime:
    def __init__(
        self,
        *,
        registry_path: Path = DEFAULT_REGISTRY_PATH,
        request_timeout_s: float = 5.0,
        max_retries: int = 1,
        failure_limit: int = 3,
        artifacts_dir: Path = Path("state/plugins/artifacts"),
    ) -> None:
        self.registry_path = registry_path
        self.request_timeout_s = request_timeout_s
        self.max_retries = max_retries
        self.failure_limit = failure_limit
        self.artifacts_dir = artifacts_dir
        self._procs: dict[str, _PluginProc] = {}
        self._failures: dict[str, int] = {}

    def _spawn(self, plugin: dict[str, Any]) -> _PluginProc:
        command = plugin.get("command")
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise PluginLoaderError("DENY_PLUGIN_COMMAND_INVALID")
        proc = subprocess.Popen(
            command,
            cwd=str(plugin.get("working_dir", ".")),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        out_q: queue.Queue[str] = queue.Queue()

        def _reader() -> None:
            for line in proc.stdout:
                out_q.put(line.rstrip("\n"))

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        return _PluginProc(process=proc, out_queue=out_q, lock=threading.Lock())

    def _load_plugin(self, plugin_id: str) -> dict[str, Any]:
        payload = load_registry(registry_path=self.registry_path)
        for plugin in payload["plugins"]:
            if str(plugin.get("plugin_id")) == plugin_id:
                return plugin
        raise PluginLoaderError(f"DENY_PLUGIN_NOT_FOUND:{plugin_id}")

    def _disable_plugin(self, plugin_id: str, reason: str) -> None:
        payload = load_registry(registry_path=self.registry_path)
        for plugin in payload["plugins"]:
            if str(plugin.get("plugin_id")) == plugin_id:
                plugin["enabled"] = False
                plugin["valid"] = False
                plugin["reason_code"] = reason
                break
        write_registry(payload, registry_path=self.registry_path)

    def _terminate(self, plugin_id: str) -> None:
        proc = self._procs.pop(plugin_id, None)
        if proc is None:
            return
        try:
            if proc.process.poll() is None:
                proc.process.kill()
            proc.process.wait(timeout=1)
        except Exception:
            pass
        for handle in (proc.process.stdin, proc.process.stdout, proc.process.stderr):
            try:
                if handle is not None:
                    handle.close()
            except Exception:
                pass

    def close(self) -> None:
        for plugin_id in list(self._procs.keys()):
            self._terminate(plugin_id)

    def dispatch(self, plugin_id: str, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
        if capability != "notify:escalation":
            raise PluginLoaderError("DENY_CAPABILITY_NOT_ALLOWED")
        plugin = self._load_plugin(plugin_id)
        if not plugin.get("enabled", False) or not plugin.get("valid", False):
            raise PluginLoaderError("DENY_PLUGIN_DISABLED")
        if capability not in {str(v) for v in plugin.get("capabilities", [])}:
            raise PluginLoaderError("DENY_CAPABILITY_NOT_DECLARED")

        attempts = self.max_retries + 1
        for _attempt in range(attempts):
            proc_wrap = self._procs.get(plugin_id)
            if proc_wrap is None or proc_wrap.process.poll() is not None:
                proc_wrap = self._spawn(plugin)
                self._procs[plugin_id] = proc_wrap

            req_id = str(uuid.uuid4())
            request = {"type": "request", "id": req_id, "capability": capability, "payload": payload}
            with proc_wrap.lock:
                try:
                    assert proc_wrap.process.stdin is not None
                    proc_wrap.process.stdin.write(json.dumps(request, sort_keys=True) + "\n")
                    proc_wrap.process.stdin.flush()
                    line = proc_wrap.out_queue.get(timeout=self.request_timeout_s)
                    response = json.loads(line)
                    if not isinstance(response, dict) or response.get("id") != req_id:
                        raise PluginLoaderError("DENY_PLUGIN_PROTOCOL")
                    if "artifact_path" in response:
                        response["artifact_path"] = _sanitize_artifact_path(
                            str(response["artifact_path"]),
                            artifacts_dir=self.artifacts_dir,
                        )
                    self._failures[plugin_id] = 0
                    return response
                except queue.Empty:
                    self._terminate(plugin_id)
                    self._failures[plugin_id] = self._failures.get(plugin_id, 0) + 1
                except Exception:
                    self._terminate(plugin_id)
                    self._failures[plugin_id] = self._failures.get(plugin_id, 0) + 1

            if self._failures.get(plugin_id, 0) >= self.failure_limit:
                self._disable_plugin(plugin_id, "DENY_PLUGIN_REPEATED_FAILURE")
                raise PluginLoaderError("DENY_PLUGIN_REPEATED_FAILURE")

        raise PluginLoaderError("DENY_PLUGIN_TIMEOUT")

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
