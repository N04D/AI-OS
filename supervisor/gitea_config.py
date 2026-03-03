from __future__ import annotations

import os

GITEA_BASE_URL_ENV = "GITEA_BASE_URL"
GITEA_BASE_URL_CONFIG_KEY = "gitea.base_url"


def resolve_gitea_base_url(*, explicit_base_url: str | None = None) -> str:
    """Resolve non-secret Gitea API base URL through one central path."""
    value = (explicit_base_url or "").strip()
    if value:
        return value
    return str(os.environ.get(GITEA_BASE_URL_ENV, "")).strip()
