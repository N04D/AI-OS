"""Plugin discovery + deterministic registry writing (no runtime execution)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.validate_plugin_manifest import validate_manifest

LOG = logging.getLogger(__name__)

DEFAULT_LOAD_PATHS = (Path("./plugins"), Path("/var/lib/ai-os/plugins"))
DEFAULT_REGISTRY_PATH = Path("state/plugins/registry.json")


@dataclass(frozen=True)
class PluginCandidate:
    plugin_id: str
    version: str
    api_version: int
    trust_tier: str
    path: str
    fingerprint: str


def _semver_key(version: str) -> tuple[int, int, int, int, tuple[Any, ...]]:
    """Return comparable key for semver-like versions.

    Higher tuple means newer.
    """
    m = re.fullmatch(
        r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$",
        version,
    )
    if not m:
        return (-1, -1, -1, -1, ())
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3))
    prerelease = m.group(4)
    if prerelease is None:
        # release beats prerelease
        return (major, minor, patch, 1, ())

    parts: list[Any] = []
    for token in prerelease.split("."):
        if token.isdigit():
            parts.append((0, int(token)))
        else:
            parts.append((1, token))
    return (major, minor, patch, 0, tuple(parts))


def _winner(existing: PluginCandidate, incoming: PluginCandidate) -> PluginCandidate:
    trust_rank = {"external": 0, "official": 1}
    ex_rank = trust_rank.get(existing.trust_tier, -1)
    in_rank = trust_rank.get(incoming.trust_tier, -1)

    if in_rank > ex_rank:
        LOG.info(
            "plugin_collision_resolved plugin_id=%s winner=%s reason=trust_tier",
            existing.plugin_id,
            incoming.path,
        )
        return incoming
    if in_rank < ex_rank:
        LOG.info(
            "plugin_collision_resolved plugin_id=%s winner=%s reason=trust_tier",
            existing.plugin_id,
            existing.path,
        )
        return existing

    # Same tier: highest semver wins; tie-breaker by path for determinism.
    ex_ver = _semver_key(existing.version)
    in_ver = _semver_key(incoming.version)
    if in_ver > ex_ver:
        LOG.info(
            "plugin_collision_resolved plugin_id=%s winner=%s reason=version",
            existing.plugin_id,
            incoming.path,
        )
        return incoming
    if in_ver < ex_ver:
        LOG.info(
            "plugin_collision_resolved plugin_id=%s winner=%s reason=version",
            existing.plugin_id,
            existing.path,
        )
        return existing

    chosen = min(existing, incoming, key=lambda c: c.path)
    LOG.info(
        "plugin_collision_resolved plugin_id=%s winner=%s reason=deterministic_path_tiebreak",
        existing.plugin_id,
        chosen.path,
    )
    return chosen


def _load_manifest_struct(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        # Validator already passed. For extraction in no-PyYAML environments,
        # use JSON-compatible fallback by importing private parser helper.
        from scripts.validate_plugin_manifest import _load_yaml  # type: ignore

        parsed = _load_yaml(str(path))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _scan_candidates(load_paths: tuple[Path, Path]) -> list[PluginCandidate]:
    found: list[PluginCandidate] = []
    official_root, external_root = load_paths

    for root in load_paths:
        if not root.exists() or not root.is_dir():
            continue
        for manifest_path in sorted(root.rglob("plugin.yaml"), key=lambda p: str(p)):
            verdict = validate_manifest(str(manifest_path))
            if verdict.get("allow") is not True:
                continue

            raw = manifest_path.read_bytes()
            fingerprint = hashlib.sha256(raw).hexdigest()
            manifest = _load_manifest_struct(manifest_path)
            if not manifest:
                continue

            plugin_id = str(manifest.get("plugin_id", ""))
            version = str(manifest.get("version", ""))
            api_version = manifest.get("api_version")
            if not plugin_id or not version or not isinstance(api_version, int):
                continue

            trust_tier = "official" if root.resolve() == official_root.resolve() else "external"
            found.append(
                PluginCandidate(
                    plugin_id=plugin_id,
                    version=version,
                    api_version=api_version,
                    trust_tier=trust_tier,
                    path=str(manifest_path),
                    fingerprint=fingerprint,
                )
            )
    return found


def build_registry(load_paths: tuple[str | Path, str | Path] | None = None) -> dict[str, Any]:
    roots = DEFAULT_LOAD_PATHS if load_paths is None else (Path(load_paths[0]), Path(load_paths[1]))
    candidates = _scan_candidates(roots)
    selected: dict[str, PluginCandidate] = {}
    for cand in sorted(candidates, key=lambda c: (c.plugin_id, c.path)):
        cur = selected.get(cand.plugin_id)
        selected[cand.plugin_id] = cand if cur is None else _winner(cur, cand)

    plugins = []
    for plugin_id in sorted(selected.keys()):
        c = selected[plugin_id]
        plugins.append(
            {
                "api_version": c.api_version,
                "enabled": False,
                "fingerprint": c.fingerprint,
                "path": c.path,
                "plugin_id": c.plugin_id,
                "trust_tier": c.trust_tier,
                "version": c.version,
            }
        )
    return {"plugins": plugins}


def write_registry(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    load_paths: tuple[str | Path, str | Path] | None = None,
) -> dict[str, Any]:
    registry = build_registry(load_paths=load_paths)
    out = Path(registry_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Fail closed if write fails (let exception propagate)
    out.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registry

