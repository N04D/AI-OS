"""Registry helpers for operator and dispatch surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PluginRegistryError(Exception):
    pass


REQUIRED_KEYS = {"plugin_id", "version", "api_version", "trust_tier", "path", "fingerprint"}


def load_registry(registry_path: str | Path) -> dict[str, Any]:
    path = Path(registry_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PluginRegistryError("REGISTRY_UNREADABLE") from exc

    if not isinstance(payload, dict):
        raise PluginRegistryError("REGISTRY_INVALID")
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        raise PluginRegistryError("REGISTRY_INVALID")

    normalized: list[dict[str, Any]] = []
    for entry in plugins:
        if not isinstance(entry, dict):
            raise PluginRegistryError("REGISTRY_INVALID")
        if not REQUIRED_KEYS.issubset(entry.keys()):
            raise PluginRegistryError("REGISTRY_INVALID")
        if not isinstance(entry.get("plugin_id"), str) or not entry["plugin_id"]:
            raise PluginRegistryError("REGISTRY_INVALID")
        normalized.append(entry)

    return {"plugins": sorted(normalized, key=lambda x: str(x["plugin_id"]))}


def get_plugin(registry: dict[str, Any], plugin_id: str) -> dict[str, Any] | None:
    if not isinstance(plugin_id, str) or not plugin_id:
        return None
    for entry in registry.get("plugins", []):
        if isinstance(entry, dict) and entry.get("plugin_id") == plugin_id:
            return entry
    return None


def list_plugins_sorted(registry: dict[str, Any]) -> list[dict[str, Any]]:
    plugins = registry.get("plugins", [])
    out = [p for p in plugins if isinstance(p, dict) and isinstance(p.get("plugin_id"), str)]
    return sorted(out, key=lambda x: str(x["plugin_id"]))


# Backward-compatible alias.
def list_plugins(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return list_plugins_sorted(registry)
