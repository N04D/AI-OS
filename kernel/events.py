"""Minimal internal event bus routing kernel events via dispatch()."""

from __future__ import annotations

import json
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any

from kernel.dispatch import dispatch

EVENT_BUS_INVALID_ARGS = "EVENT_BUS_INVALID_ARGS"
EVENT_BUS_REGISTRY_UNREADABLE = "EVENT_BUS_REGISTRY_UNREADABLE"
EVENT_BUS_CONFIG_UNREADABLE = "EVENT_BUS_CONFIG_UNREADABLE"
EVENT_BUS_STATE_INVALID = "EVENT_BUS_STATE_INVALID"
EVENT_BUS_AUDIT_LOG_WRITE_FAILED = "EVENT_BUS_AUDIT_LOG_WRITE_FAILED"
EVENT_BUS_MANIFEST_UNREADABLE = "EVENT_BUS_MANIFEST_UNREADABLE"
EVENT_BUS_EXTERNAL_NOT_ALLOWED = "EVENT_BUS_EXTERNAL_NOT_ALLOWED"
EVENT_BUS_DISPATCH_FAILED = "EVENT_BUS_DISPATCH_FAILED"


def _now_rfc3339_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _base_result(ok: bool, event_id: str, event_type: str) -> dict[str, Any]:
    return {
        "ok": ok,
        "event_id": event_id,
        "event_type": event_type,
        "delivered": [],
        "failed": [],
    }


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_yaml(path: str | Path) -> Any:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        from scripts.validate_plugin_manifest import _load_yaml as _fallback  # type: ignore

        return _fallback(str(path))


def _audit_write(audit_log_path: str | Path, event: dict[str, Any]) -> None:
    p = Path(audit_log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _manifest_path_from_entry(entry: dict[str, Any]) -> Path | None:
    raw = entry.get("path")
    if not isinstance(raw, str) or not raw:
        return None
    p = Path(raw)
    if p.is_dir():
        return p / "plugin.yaml"
    return p


def _extract_enabled_plugin_ids(registry: dict[str, Any], config: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    entries = registry.get("plugins")
    if not isinstance(entries, list):
        raise ValueError("registry.plugins must be array")

    unsafe_allow_external = config.get("unsafe_allow_external")
    if unsafe_allow_external is None:
        unsafe_allow_external = False
    if not isinstance(unsafe_allow_external, bool):
        raise ValueError("unsafe_allow_external must be bool")

    enabled_ids: set[str] = set()
    cfg_plugins = config.get("plugins")
    if isinstance(cfg_plugins, dict):
        for plugin_id, plugin_cfg in cfg_plugins.items():
            if not isinstance(plugin_id, str) or not plugin_id:
                continue
            if isinstance(plugin_cfg, dict) and plugin_cfg.get("enabled") is True:
                enabled_ids.add(plugin_id)

    cfg_enabled = config.get("enabled")
    if isinstance(cfg_enabled, list):
        for plugin_id in cfg_enabled:
            if isinstance(plugin_id, str) and plugin_id:
                enabled_ids.add(plugin_id)

    selected: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        plugin_id = entry.get("plugin_id")
        if not isinstance(plugin_id, str) or not plugin_id:
            continue
        if plugin_id not in enabled_ids:
            continue
        selected.append(entry)

    selected.sort(key=lambda x: str(x.get("plugin_id", "")))
    return selected, unsafe_allow_external


def _subscriptions_for(entry: dict[str, Any]) -> set[str]:
    manifest_path = _manifest_path_from_entry(entry)
    if manifest_path is None:
        raise ValueError("missing manifest path")
    parsed = _read_yaml(manifest_path)
    if not isinstance(parsed, dict):
        raise ValueError("manifest not mapping")
    subs = parsed.get("subscriptions")
    if not isinstance(subs, list):
        return set()
    return {s for s in subs if isinstance(s, str) and s}


def emit(
    event_type: str,
    payload: dict,
    *,
    registry_path: str = "state/plugins/registry.json",
    config_path: str = "state/plugins/config.json",
    audit_log_path: str = "logs/control/kernel-events.jsonl",
) -> dict:
    event_id = str(uuid.uuid4())
    safe_event_type = event_type if isinstance(event_type, str) else ""

    if not isinstance(event_type, str) or not event_type.strip():
        out = _base_result(False, event_id, safe_event_type)
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_INVALID_ARGS, "details": ["event_type"]})
        return out
    if not isinstance(payload, dict):
        out = _base_result(False, event_id, event_type)
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_INVALID_ARGS, "details": ["payload"]})
        return out

    event_obj = {
        "event_id": event_id,
        "type": event_type,
        "payload": payload,
        "ts": _now_rfc3339_utc(),
    }
    out = _base_result(True, event_id, event_type)

    try:
        _audit_write(
            audit_log_path,
            {
                "event": "emit_start",
                "event_id": event_id,
                "event_type": event_type,
                "ts": _now_rfc3339_utc(),
            },
        )
    except Exception as exc:
        fail = _base_result(False, event_id, event_type)
        fail["failed"].append(
            {"plugin_id": None, "error_code": EVENT_BUS_AUDIT_LOG_WRITE_FAILED, "details": [str(exc)]}
        )
        return fail

    try:
        registry = _read_json(registry_path)
    except Exception as exc:
        out["ok"] = False
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_REGISTRY_UNREADABLE, "details": [str(exc)]})
        return out

    try:
        config = _read_json(config_path)
    except Exception as exc:
        out["ok"] = False
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_CONFIG_UNREADABLE, "details": [str(exc)]})
        return out

    try:
        selected, unsafe_allow_external = _extract_enabled_plugin_ids(registry, config)
    except Exception as exc:
        out["ok"] = False
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_STATE_INVALID, "details": [str(exc)]})
        return out

    for entry in selected:
        plugin_id = str(entry.get("plugin_id"))
        trust_tier = str(entry.get("trust_tier", ""))

        if trust_tier == "external" and not unsafe_allow_external:
            item = {"plugin_id": plugin_id, "ok": False, "error_code": EVENT_BUS_EXTERNAL_NOT_ALLOWED}
            out["delivered"].append(item)
            out["failed"].append(
                {
                    "plugin_id": plugin_id,
                    "error_code": EVENT_BUS_EXTERNAL_NOT_ALLOWED,
                    "details": [],
                }
            )
            out["ok"] = False
            try:
                _audit_write(
                    audit_log_path,
                    {
                        "duration_ms": 0,
                        "error_code": EVENT_BUS_EXTERNAL_NOT_ALLOWED,
                        "event": "deliver",
                        "event_id": event_id,
                        "event_type": event_type,
                        "ok": False,
                        "plugin_id": plugin_id,
                        "ts": _now_rfc3339_utc(),
                    },
                )
            except Exception as exc:
                out["ok"] = False
                out["failed"].append(
                    {
                        "plugin_id": plugin_id,
                        "error_code": EVENT_BUS_AUDIT_LOG_WRITE_FAILED,
                        "details": [str(exc)],
                    }
                )
                return out
            continue

        try:
            subscriptions = _subscriptions_for(entry)
        except Exception as exc:
            out["ok"] = False
            out["delivered"].append({"plugin_id": plugin_id, "ok": False, "error_code": EVENT_BUS_MANIFEST_UNREADABLE})
            out["failed"].append(
                {"plugin_id": plugin_id, "error_code": EVENT_BUS_MANIFEST_UNREADABLE, "details": [str(exc)]}
            )
            continue

        if event_type not in subscriptions:
            continue

        start = monotonic()
        resp = dispatch(
            plugin_id,
            "on_event",
            event_obj,
            registry_path=registry_path,
            config_path=config_path,
        )
        duration_ms = int((monotonic() - start) * 1000)

        if resp.get("ok") is True:
            out["delivered"].append({"plugin_id": plugin_id, "ok": True, "error_code": None})
            try:
                _audit_write(
                    audit_log_path,
                    {
                        "duration_ms": duration_ms,
                        "error_code": None,
                        "event": "deliver",
                        "event_id": event_id,
                        "event_type": event_type,
                        "ok": True,
                        "plugin_id": plugin_id,
                        "ts": _now_rfc3339_utc(),
                    },
                )
            except Exception as exc:
                out["ok"] = False
                out["failed"].append(
                    {
                        "plugin_id": plugin_id,
                        "error_code": EVENT_BUS_AUDIT_LOG_WRITE_FAILED,
                        "details": [str(exc)],
                    }
                )
                return out
            continue

        err = resp.get("error") if isinstance(resp.get("error"), dict) else {}
        err_code = err.get("code") if isinstance(err.get("code"), str) else EVENT_BUS_DISPATCH_FAILED
        err_details = err.get("details") if isinstance(err.get("details"), list) else []
        out["ok"] = False
        out["delivered"].append({"plugin_id": plugin_id, "ok": False, "error_code": err_code})
        out["failed"].append({"plugin_id": plugin_id, "error_code": err_code, "details": [str(v) for v in err_details]})
        try:
            _audit_write(
                audit_log_path,
                {
                    "duration_ms": duration_ms,
                    "error_code": err_code,
                    "event": "deliver",
                    "event_id": event_id,
                    "event_type": event_type,
                    "ok": False,
                    "plugin_id": plugin_id,
                    "ts": _now_rfc3339_utc(),
                },
            )
        except Exception as exc:
            out["ok"] = False
            out["failed"].append(
                {
                    "plugin_id": plugin_id,
                    "error_code": EVENT_BUS_AUDIT_LOG_WRITE_FAILED,
                    "details": [str(exc)],
                }
            )
            return out

    out["ok"] = len(out["failed"]) == 0

    try:
        _audit_write(
            audit_log_path,
            {
                "delivered_count": len(out["delivered"]),
                "event": "emit_end",
                "event_id": event_id,
                "event_type": event_type,
                "failed_count": len(out["failed"]),
                "ok": out["ok"],
                "ts": _now_rfc3339_utc(),
            },
        )
    except Exception as exc:
        out["ok"] = False
        out["failed"].append({"plugin_id": None, "error_code": EVENT_BUS_AUDIT_LOG_WRITE_FAILED, "details": [str(exc)]})
        return out

    out["delivered"] = sorted(out["delivered"], key=lambda x: (str(x.get("plugin_id")), str(x.get("error_code"))))
    out["failed"] = sorted(
        out["failed"],
        key=lambda x: (
            str(x.get("plugin_id")),
            str(x.get("error_code")),
            json.dumps(x.get("details", []), sort_keys=True),
        ),
    )
    return out
