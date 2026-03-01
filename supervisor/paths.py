from __future__ import annotations

import os
from pathlib import Path


LEGACY_INFRA_HOST_STATE_DIR = "/home/infra/night/state"


def repo_root() -> Path:
    override = os.environ.get("AIOS_REPO_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def default_host_state_dir() -> Path:
    return repo_root() / "state"


def resolve_host_state_dir(value: str | None = None) -> Path:
    candidate = (value or os.environ.get("HOST_STATE_DIR", "").strip() or str(default_host_state_dir())).strip()
    resolved = Path(candidate).expanduser()
    if resolved.as_posix().rstrip("/") == LEGACY_INFRA_HOST_STATE_DIR:
        raise RuntimeError("legacy_host_state_dir_forbidden")
    return resolved
