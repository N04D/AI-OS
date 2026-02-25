"""Operator plugin config helpers (canonical config shape)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class PluginConfigError(Exception):
    """Raised for fail-closed config parsing/validation errors."""


def _normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PluginConfigError("CONFIG_INVALID")

    unsafe = raw.get("unsafe_allow_external", False)
    if not isinstance(unsafe, bool):
        raise PluginConfigError("CONFIG_INVALID")

    enabled = raw.get("enabled", [])
    if not isinstance(enabled, list):
        raise PluginConfigError("CONFIG_INVALID")
    if not all(isinstance(v, str) and v for v in enabled):
        raise PluginConfigError("CONFIG_INVALID")

    # Legacy shape support: plugins.<id>.enabled booleans.
    plugins = raw.get("plugins")
    if plugins is not None and not isinstance(plugins, dict):
        raise PluginConfigError("CONFIG_INVALID")

    enabled_set = set(enabled)
    if isinstance(plugins, dict):
        for plugin_id, plugin_cfg in plugins.items():
            if not isinstance(plugin_id, str) or not plugin_id:
                raise PluginConfigError("CONFIG_INVALID")
            if not isinstance(plugin_cfg, dict):
                raise PluginConfigError("CONFIG_INVALID")
            is_enabled = plugin_cfg.get("enabled", False)
            if not isinstance(is_enabled, bool):
                raise PluginConfigError("CONFIG_INVALID")
            if is_enabled:
                enabled_set.add(plugin_id)

    return {
        "enabled": sorted(enabled_set),
        "unsafe_allow_external": unsafe,
    }


def load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {
            "enabled": [],
            "unsafe_allow_external": False,
        }

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PluginConfigError("CONFIG_UNREADABLE") from exc
    return _normalize_config(raw)


def save_config_atomic(config_path: str | Path, config_dict: dict[str, Any]) -> None:
    normalized = _normalize_config(config_dict)
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_fd = None
    tmp_name = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=".config.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            tmp_fd = None
            f.write(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except Exception:
                pass
        if tmp_name is not None and Path(tmp_name).exists():
            try:
                Path(tmp_name).unlink()
            except Exception:
                pass


def enable_plugin(config: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    return set_enabled(config, plugin_id, True)


def disable_plugin(config: dict[str, Any], plugin_id: str) -> dict[str, Any]:
    return set_enabled(config, plugin_id, False)


def set_enabled(config: dict[str, Any], plugin_id: str, enabled_bool: bool) -> dict[str, Any]:
    if not isinstance(plugin_id, str) or not plugin_id:
        raise PluginConfigError("CONFIG_INVALID")
    if not isinstance(enabled_bool, bool):
        raise PluginConfigError("CONFIG_INVALID")
    normalized = _normalize_config(config)
    enabled = set(normalized["enabled"])
    if enabled_bool:
        enabled.add(plugin_id)
    else:
        enabled.discard(plugin_id)
    normalized["enabled"] = sorted(enabled)
    return _normalize_config(normalized)
