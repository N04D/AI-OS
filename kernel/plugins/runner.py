"""Secure fail-closed IPC runner for enabled plugins."""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validate_plugin_manifest import validate_manifest

MAX_LINE_BYTES = 1_000_000
DEFAULT_RESTART_LIMIT = 3


class PluginRunnerError(Exception):
    def __init__(self, reason_code: str, details: list[str] | None = None):
        self.reason_code = reason_code
        self.details = details or []
        super().__init__(reason_code)


@dataclass
class ResolvedPlugin:
    plugin_id: str
    version: str
    api_version: int
    trust_tier: str
    path: str
    fingerprint: str
    timeout_seconds: int
    command: list[str]
    cwd: Path
    state_dir: Path


def _load_yaml(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        from scripts.validate_plugin_manifest import _load_yaml as _fallback  # type: ignore

        return _fallback(str(path))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


class PluginRunner:
    def __init__(
        self,
        registry_path: str | Path = "state/plugins/registry.json",
        config_path: str | Path = "state/plugins/config.json",
        audit_log_path: str | Path = "logs/control/plugin-runtime.jsonl",
        base_dir: str | Path = ".",
        restart_limit: int = DEFAULT_RESTART_LIMIT,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.registry_path = Path(registry_path)
        self.config_path = Path(config_path)
        self.audit_log_path = Path(audit_log_path)
        self.restart_limit = restart_limit

        self._procs: dict[str, subprocess.Popen] = {}
        self._failure_count: dict[str, int] = {}
        self._unhealthy: set[str] = set()

    def _audit(self, event: str, plugin_id: str, method: str | None = None, request_id: str | None = None, ok: bool | None = None, error_code: str | None = None, duration_ms: int | None = None) -> None:
        payload = {
            "duration_ms": duration_ms,
            "error_code": error_code,
            "event": event,
            "method": method,
            "ok": ok,
            "plugin_id": plugin_id,
            "request_id": request_id,
            "ts": int(time.time() * 1000),
        }
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.audit_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception as exc:
            raise PluginRunnerError("AUDIT_LOG_WRITE_FAILED", [str(exc)])

    def _ensure_audit_writable(self) -> None:
        """Fail closed before execution if audit sink is unavailable."""
        self._audit(event="audit_check", plugin_id="_runner", ok=True)

    def _load_registry(self) -> dict[str, Any]:
        try:
            payload = _read_json(self.registry_path)
        except Exception as exc:
            raise PluginRunnerError("REGISTRY_UNREADABLE", [str(exc)])
        if not isinstance(payload, dict) or not isinstance(payload.get("plugins"), list):
            raise PluginRunnerError("REGISTRY_INVALID")
        return payload

    def _load_config(self) -> dict[str, Any]:
        try:
            payload = _read_json(self.config_path)
        except Exception as exc:
            raise PluginRunnerError("CONFIG_UNREADABLE", [str(exc)])
        if not isinstance(payload, dict):
            raise PluginRunnerError("CONFIG_INVALID")
        if "unsafe_allow_external" in payload and not isinstance(payload["unsafe_allow_external"], bool):
            raise PluginRunnerError("CONFIG_INVALID")
        if "enabled" in payload:
            enabled = payload["enabled"]
            if not isinstance(enabled, list) or not all(isinstance(v, str) and v for v in enabled):
                raise PluginRunnerError("CONFIG_INVALID")
        plugins = payload.get("plugins")
        if plugins is not None:
            if not isinstance(plugins, dict):
                raise PluginRunnerError("CONFIG_INVALID")
            for plugin_id, plugin_cfg in plugins.items():
                if not isinstance(plugin_id, str) or not plugin_id:
                    raise PluginRunnerError("CONFIG_INVALID")
                if not isinstance(plugin_cfg, dict):
                    raise PluginRunnerError("CONFIG_INVALID")
                if "enabled" in plugin_cfg and not isinstance(plugin_cfg["enabled"], bool):
                    raise PluginRunnerError("CONFIG_INVALID")
        return payload

    def _entrypoint_command(self, plugin_dir: Path, command: list[str]) -> list[str]:
        if not command or not isinstance(command, list) or not all(isinstance(v, str) and v for v in command):
            raise PluginRunnerError("ENTRYPOINT_INVALID", ["entrypoint.command must be a non-empty string array"])

        cmd0 = command[0]
        cmd0_path = Path(cmd0)
        if not cmd0_path.is_absolute():
            candidate = (plugin_dir / cmd0_path).resolve()
        else:
            candidate = cmd0_path.resolve()

        if not _is_within(candidate, plugin_dir):
            raise PluginRunnerError("ENTRYPOINT_OUTSIDE_PLUGIN_DIR", [str(candidate)])

        if not candidate.exists() or not candidate.is_file():
            raise PluginRunnerError("ENTRYPOINT_MISSING", [str(candidate)])

        safe_command = [str(candidate)] + command[1:]
        return safe_command

    def resolve_enabled_plugin(self, plugin_id: str) -> ResolvedPlugin:
        registry = self._load_registry()
        config = self._load_config()

        plugin_entries = [p for p in registry["plugins"] if isinstance(p, dict) and p.get("plugin_id") == plugin_id]
        if not plugin_entries:
            raise PluginRunnerError("PLUGIN_NOT_DISCOVERED")
        entry = plugin_entries[0]

        plugin_cfg = {}
        if isinstance(config.get("plugins"), dict):
            plugin_cfg = config["plugins"].get(plugin_id, {})
        enabled_from_plugins = isinstance(plugin_cfg, dict) and plugin_cfg.get("enabled") is True
        enabled_from_list = isinstance(config.get("enabled"), list) and plugin_id in set(config.get("enabled", []))
        enabled = enabled_from_plugins or enabled_from_list
        if not enabled:
            self._audit(event="disable/refuse", plugin_id=plugin_id, ok=False, error_code="PLUGIN_NOT_ENABLED")
            raise PluginRunnerError("PLUGIN_NOT_ENABLED")

        trust_tier = str(entry.get("trust_tier", ""))
        if trust_tier == "external" and config.get("unsafe_allow_external", False) is not True:
            self._audit(event="disable/refuse", plugin_id=plugin_id, ok=False, error_code="EXTERNAL_NOT_ALLOWED")
            raise PluginRunnerError("EXTERNAL_NOT_ALLOWED")

        manifest_path = Path(str(entry.get("path", ""))).resolve()
        if not manifest_path.exists():
            raise PluginRunnerError("MANIFEST_MISSING")

        verdict = validate_manifest(str(manifest_path))
        if verdict.get("allow") is not True:
            raise PluginRunnerError("MANIFEST_INVALID", verdict.get("details", []))

        manifest = _load_yaml(manifest_path)
        if not isinstance(manifest, dict):
            raise PluginRunnerError("MANIFEST_INVALID")

        plugin_dir = manifest_path.parent.resolve()
        runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
        timeout_seconds = runtime.get("timeout_seconds")
        if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise PluginRunnerError("TIMEOUT_INVALID")

        entrypoint = manifest.get("entrypoint") if isinstance(manifest.get("entrypoint"), dict) else {}
        command = entrypoint.get("command")
        if not isinstance(command, list):
            raise PluginRunnerError("ENTRYPOINT_INVALID")
        safe_command = self._entrypoint_command(plugin_dir, command)

        state_dir = self.base_dir / "state" / "plugins" / "runtime" / plugin_id
        state_dir.mkdir(parents=True, exist_ok=True)

        return ResolvedPlugin(
            plugin_id=plugin_id,
            version=str(entry.get("version", "")),
            api_version=int(entry.get("api_version", 0)),
            trust_tier=trust_tier,
            path=str(manifest_path),
            fingerprint=str(entry.get("fingerprint", "")),
            timeout_seconds=timeout_seconds,
            command=safe_command,
            cwd=plugin_dir,
            state_dir=state_dir,
        )

    def _ensure_healthy(self, plugin_id: str) -> None:
        if self._failure_count.get(plugin_id, 0) >= self.restart_limit:
            self._unhealthy.add(plugin_id)
        if plugin_id in self._unhealthy:
            self._audit(event="disable/refuse", plugin_id=plugin_id, ok=False, error_code="PLUGIN_UNHEALTHY")
            raise PluginRunnerError("PLUGIN_UNHEALTHY")

    def _record_failure(self, plugin_id: str) -> None:
        self._failure_count[plugin_id] = self._failure_count.get(plugin_id, 0) + 1
        if self._failure_count[plugin_id] >= self.restart_limit:
            self._unhealthy.add(plugin_id)

    def _record_success(self, plugin_id: str) -> None:
        self._failure_count[plugin_id] = 0

    def spawn(self, plugin_id: str) -> subprocess.Popen:
        self._ensure_audit_writable()
        self._ensure_healthy(plugin_id)
        resolved = self.resolve_enabled_plugin(plugin_id)

        self._audit(event="spawn_attempt", plugin_id=plugin_id, ok=True)

        env = {
            "AIOS_API_VERSION": str(resolved.api_version),
            "AIOS_PLUGIN_ID": resolved.plugin_id,
            "AIOS_STATE_DIR": str(resolved.state_dir),
            "AIOS_TRUST_TIER": resolved.trust_tier,
        }

        try:
            proc = subprocess.Popen(
                args=resolved.command,
                cwd=str(resolved.cwd),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                shell=False,
            )
        except Exception as exc:
            self._record_failure(plugin_id)
            self._audit(event="spawn", plugin_id=plugin_id, ok=False, error_code="SPAWN_FAILED")
            raise PluginRunnerError("SPAWN_FAILED", [str(exc)])

        self._procs[plugin_id] = proc
        self._audit(event="spawn", plugin_id=plugin_id, ok=True)
        return proc

    def _kill_process(self, plugin_id: str, reason_code: str | None = None, request_id: str | None = None, method: str | None = None, duration_ms: int | None = None) -> None:
        if reason_code is not None:
            self._audit(
                event="kill",
                plugin_id=plugin_id,
                request_id=request_id,
                method=method,
                ok=False,
                error_code=reason_code,
                duration_ms=duration_ms,
            )
        proc = self._procs.pop(plugin_id, None)
        if proc is None:
            return
        try:
            proc.kill()
            proc.wait(timeout=1)
        except Exception:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream:
                    stream.close()
            except Exception:
                pass

    def _error_response(self, request_id: str, code: str, details: list[str] | None = None) -> dict[str, Any]:
        return {
            "error": {"code": code, "details": details or []},
            "id": request_id,
            "ok": False,
            "result": None,
            "type": "response",
        }

    def _validate_request(self, request_obj: dict[str, Any]) -> tuple[str, str]:
        if not isinstance(request_obj, dict):
            raise PluginRunnerError("REQUEST_INVALID", ["request must be object"])
        if request_obj.get("type") != "request":
            raise PluginRunnerError("REQUEST_INVALID", ["type must be request"])
        req_id = request_obj.get("id")
        method = request_obj.get("method")
        payload = request_obj.get("payload")
        if not isinstance(req_id, str) or not req_id:
            raise PluginRunnerError("REQUEST_INVALID", ["id must be non-empty string"])
        if not isinstance(method, str) or not method:
            raise PluginRunnerError("REQUEST_INVALID", ["method must be non-empty string"])
        if not isinstance(payload, dict):
            raise PluginRunnerError("REQUEST_INVALID", ["payload must be object"])
        return req_id, method

    def send_request(self, plugin_id: str, request_obj: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        req_id = request_obj.get("id") if isinstance(request_obj, dict) else ""
        req_id = req_id if isinstance(req_id, str) and req_id else "unknown"
        method = request_obj.get("method") if isinstance(request_obj, dict) else None
        method = method if isinstance(method, str) else None

        try:
            self._ensure_audit_writable()
            req_id, method = self._validate_request(request_obj)
            self._ensure_healthy(plugin_id)
            self._audit(event="request_start", plugin_id=plugin_id, request_id=req_id, method=method, ok=True)

            if plugin_id not in self._procs or self._procs[plugin_id].poll() is not None:
                self.spawn(plugin_id)
            proc = self._procs[plugin_id]
            resolved = self.resolve_enabled_plugin(plugin_id)

            req_line = json.dumps(request_obj, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
            if len(req_line) > MAX_LINE_BYTES:
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="REQUEST_TOO_LARGE", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="REQUEST_TOO_LARGE", duration_ms=duration_ms)
                return self._error_response(req_id, "REQUEST_TOO_LARGE")

            self._audit(event="request", plugin_id=plugin_id, request_id=req_id, method=method, ok=True)

            if proc.stdin is None or proc.stdout is None:
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="PLUGIN_PIPE_BROKEN", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_PIPE_BROKEN", duration_ms=duration_ms)
                return self._error_response(req_id, "PLUGIN_PIPE_BROKEN")

            proc.stdin.write(req_line)
            proc.stdin.flush()

            deadline = time.monotonic() + resolved.timeout_seconds
            line = b""
            while True:
                if proc.poll() is not None:
                    self._record_failure(plugin_id)
                    duration_ms = int((time.monotonic() - start) * 1000)
                    self._kill_process(plugin_id, reason_code="PLUGIN_CRASHED", request_id=req_id, method=method, duration_ms=duration_ms)
                    self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_CRASHED", duration_ms=duration_ms)
                    return self._error_response(req_id, "PLUGIN_CRASHED")
                if time.monotonic() > deadline:
                    self._record_failure(plugin_id)
                    duration_ms = int((time.monotonic() - start) * 1000)
                    self._kill_process(plugin_id, reason_code="PLUGIN_TIMEOUT", request_id=req_id, method=method, duration_ms=duration_ms)
                    self._audit(event="timeout", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_TIMEOUT", duration_ms=duration_ms)
                    self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_TIMEOUT", duration_ms=duration_ms)
                    return self._error_response(req_id, "PLUGIN_TIMEOUT")

                remaining = max(0.0, deadline - time.monotonic())
                wait_for = 0.1 if remaining > 0.1 else remaining
                ready, _, _ = select.select([proc.stdout], [], [], wait_for)
                if not ready:
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    continue
                line += chunk
                if len(line) > MAX_LINE_BYTES:
                    self._record_failure(plugin_id)
                    duration_ms = int((time.monotonic() - start) * 1000)
                    self._kill_process(plugin_id, reason_code="RESPONSE_TOO_LARGE", request_id=req_id, method=method, duration_ms=duration_ms)
                    self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="RESPONSE_TOO_LARGE", duration_ms=duration_ms)
                    return self._error_response(req_id, "RESPONSE_TOO_LARGE")
                newline_idx = line.find(b"\n")
                if newline_idx >= 0:
                    line = line[: newline_idx + 1]
                    break

            try:
                response = json.loads(line.decode("utf-8"))
            except Exception:
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="PLUGIN_INVALID_JSON_RESPONSE", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_INVALID_JSON_RESPONSE", duration_ms=duration_ms)
                return self._error_response(req_id, "PLUGIN_INVALID_JSON_RESPONSE")

            if not isinstance(response, dict):
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="PLUGIN_INVALID_RESPONSE_SCHEMA", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_INVALID_RESPONSE_SCHEMA", duration_ms=duration_ms)
                return self._error_response(req_id, "PLUGIN_INVALID_RESPONSE_SCHEMA")

            required = {"type", "id", "ok", "result", "error"}
            if not required.issubset(response.keys()):
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="PLUGIN_INVALID_RESPONSE_SCHEMA", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_INVALID_RESPONSE_SCHEMA", duration_ms=duration_ms)
                return self._error_response(req_id, "PLUGIN_INVALID_RESPONSE_SCHEMA")

            if response.get("type") != "response" or not isinstance(response.get("id"), str) or not isinstance(response.get("ok"), bool):
                self._record_failure(plugin_id)
                duration_ms = int((time.monotonic() - start) * 1000)
                self._kill_process(plugin_id, reason_code="PLUGIN_INVALID_RESPONSE_SCHEMA", request_id=req_id, method=method, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code="PLUGIN_INVALID_RESPONSE_SCHEMA", duration_ms=duration_ms)
                return self._error_response(req_id, "PLUGIN_INVALID_RESPONSE_SCHEMA")

            duration_ms = int((time.monotonic() - start) * 1000)
            self._record_success(plugin_id)
            self._audit(
                event="response",
                plugin_id=plugin_id,
                request_id=req_id,
                method=method,
                ok=bool(response.get("ok")),
                error_code=(response.get("error") or {}).get("code") if isinstance(response.get("error"), dict) else None,
                duration_ms=duration_ms,
            )
            self._audit(
                event="request_end",
                plugin_id=plugin_id,
                request_id=req_id,
                method=method,
                ok=bool(response.get("ok")),
                error_code=(response.get("error") or {}).get("code") if isinstance(response.get("error"), dict) else None,
                duration_ms=duration_ms,
            )
            return response
        except PluginRunnerError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            try:
                self._audit(event="disable/refuse", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code=exc.reason_code, duration_ms=duration_ms)
                self._audit(event="request_end", plugin_id=plugin_id, request_id=req_id, method=method, ok=False, error_code=exc.reason_code, duration_ms=duration_ms)
            except PluginRunnerError:
                return self._error_response(req_id, "AUDIT_LOG_WRITE_FAILED")
            return self._error_response(req_id, exc.reason_code, exc.details)

    def shutdown(self, plugin_id: str) -> None:
        self._kill_process(plugin_id)
        self._audit(event="disable/refuse", plugin_id=plugin_id, ok=True, error_code="SHUTDOWN")
