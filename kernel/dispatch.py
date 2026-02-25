"""Internal plugin dispatch API backed by the secure plugin runner."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from kernel.errors import DISPATCH_INTERNAL_ERROR
from kernel.errors import DISPATCH_INVALID_ARGS
from kernel.errors import DISPATCH_RUNNER_ERROR
from kernel.errors import DISPATCH_RUNNER_REFUSED
from kernel.errors import build_error
from kernel.plugins.runner import PluginRunner

RUNNER_REFUSAL_CODES = {
    "AUDIT_LOG_WRITE_FAILED",
    "CONFIG_INVALID",
    "CONFIG_UNREADABLE",
    "ENTRYPOINT_INVALID",
    "ENTRYPOINT_MISSING",
    "ENTRYPOINT_OUTSIDE_PLUGIN_DIR",
    "EXTERNAL_NOT_ALLOWED",
    "MANIFEST_INVALID",
    "MANIFEST_MISSING",
    "PLUGIN_NOT_DISCOVERED",
    "PLUGIN_NOT_ENABLED",
    "PLUGIN_UNHEALTHY",
    "REGISTRY_INVALID",
    "REGISTRY_UNREADABLE",
    "REQUEST_INVALID",
    "TIMEOUT_INVALID",
}


def _normalize_request_id(request_id: str | None, plugin_id: str, method: str, payload: dict[str, Any]) -> str:
    if isinstance(request_id, str) and request_id:
        return request_id
    raw = json.dumps(
        {
            "method": method,
            "payload": payload,
            "plugin_id": plugin_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"req-{digest}"


def _failure(
    plugin_id: str,
    request_id: str,
    code: str,
    message: str,
    details: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "plugin_id": plugin_id,
        "request_id": request_id,
        "error": build_error(code, message, details),
    }


def _load_yaml(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        from scripts.validate_plugin_manifest import _load_yaml as _fallback  # type: ignore

        return _fallback(str(path))


def _resolve_allowed_methods(plugin_id: str, registry_path: str) -> list[str]:
    default = ["on_event"]
    try:
        registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
        if not isinstance(registry, dict) or not isinstance(registry.get("plugins"), list):
            return default
        entries = [p for p in registry["plugins"] if isinstance(p, dict) and p.get("plugin_id") == plugin_id]
        if not entries:
            return default
        raw_path = entries[0].get("path")
        if not isinstance(raw_path, str) or not raw_path:
            return default
        manifest_path = Path(raw_path)
        if manifest_path.is_dir():
            manifest_path = manifest_path / "plugin.yaml"
        parsed = _load_yaml(manifest_path)
        if not isinstance(parsed, dict):
            return default
        methods = parsed.get("methods")
        if not isinstance(methods, list):
            return default
        if not all(isinstance(m, str) and m.strip() for m in methods):
            return default
        return [m for m in methods]
    except Exception:
        return default


def dispatch(
    plugin_id: str,
    method: str,
    payload: dict,
    *,
    request_id: str | None = None,
    registry_path: str = "state/plugins/registry.json",
    config_path: str = "state/plugins/config.json",
    audit_log_path: str = "logs/control/plugin-runtime.jsonl",
    runner_state_dir_base: str = "state/plugins/runtime",
    timeout_override_seconds: int | None = None,
) -> dict[str, Any]:
    del runner_state_dir_base

    safe_plugin_id = plugin_id if isinstance(plugin_id, str) else ""
    safe_method = method if isinstance(method, str) else ""
    safe_payload = payload if isinstance(payload, dict) else {}
    safe_request_id = _normalize_request_id(request_id, safe_plugin_id, safe_method, safe_payload)

    if not isinstance(plugin_id, str) or not plugin_id.strip():
        return _failure(
            safe_plugin_id,
            safe_request_id,
            DISPATCH_INVALID_ARGS,
            "plugin_id must be a non-empty string",
            ["plugin_id"],
        )
    if not isinstance(method, str) or not method.strip():
        return _failure(
            plugin_id,
            safe_request_id,
            DISPATCH_INVALID_ARGS,
            "method must be a non-empty string",
            ["method"],
        )
    if not isinstance(payload, dict):
        return _failure(
            plugin_id,
            safe_request_id,
            DISPATCH_INVALID_ARGS,
            "payload must be an object",
            ["payload"],
        )
    if timeout_override_seconds is not None:
        if not isinstance(timeout_override_seconds, int) or timeout_override_seconds <= 0:
            return _failure(
                plugin_id,
                safe_request_id,
                DISPATCH_INVALID_ARGS,
                "timeout_override_seconds must be a positive integer",
                ["timeout_override_seconds"],
            )

    req_id = _normalize_request_id(request_id, plugin_id, method, payload)
    allowed_methods = _resolve_allowed_methods(plugin_id, registry_path)
    if method not in allowed_methods:
        return _failure(
            plugin_id,
            req_id,
            "METHOD_NOT_ALLOWED",
            "method is not allowed by plugin manifest capability gate",
            [f"allowed_methods={','.join(allowed_methods)}", f"requested_method={method}"],
        )

    request_obj = {
        "type": "request",
        "id": req_id,
        "method": method,
        "payload": payload,
    }

    runner = PluginRunner(
        registry_path=registry_path,
        config_path=config_path,
        audit_log_path=audit_log_path,
    )
    try:
        response = runner.send_request(plugin_id, request_obj)
        if not isinstance(response, dict):
            return _failure(
                plugin_id,
                req_id,
                DISPATCH_RUNNER_ERROR,
                "runner returned non-object response",
                ["RUNNER_RESPONSE_INVALID"],
            )
        if response.get("ok") is True:
            return {
                "ok": True,
                "plugin_id": plugin_id,
                "request_id": req_id,
                "result": response.get("result"),
            }

        err = response.get("error") if isinstance(response.get("error"), dict) else {}
        runner_code = err.get("code") if isinstance(err.get("code"), str) else "RUNNER_UNKNOWN_ERROR"
        runner_details = err.get("details") if isinstance(err.get("details"), list) else []
        mapped = DISPATCH_RUNNER_REFUSED if runner_code in RUNNER_REFUSAL_CODES else DISPATCH_RUNNER_ERROR
        return _failure(
            plugin_id,
            req_id,
            mapped,
            "runner refused request" if mapped == DISPATCH_RUNNER_REFUSED else "runner request failed",
            [runner_code] + [str(v) for v in runner_details],
        )
    except Exception as exc:
        return _failure(
            plugin_id,
            req_id,
            DISPATCH_INTERNAL_ERROR,
            "dispatch internal failure",
            [str(exc)],
        )
    finally:
        try:
            runner.shutdown(plugin_id)
        except Exception:
            pass
