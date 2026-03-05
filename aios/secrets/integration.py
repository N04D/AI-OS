from __future__ import annotations

from pathlib import Path

from .context import SecretAccessContext
from .manager import SecretsManager
from .types import SecretKey


def resolve_gitea_token(
    *,
    explicit_token: str | None = None,
    context: SecretAccessContext,
    data_dir: Path | None = None,
) -> str:
    """Resolve Gitea token through the canonical secrets API.

    Explicit token input remains supported for controlled callsites/tests, but
    ambient process-environment reads are intentionally avoided.
    """
    token = (explicit_token or "").strip()
    if token:
        return token

    try:
        manager = SecretsManager(data_dir=data_dir)
        value = manager.get(SecretKey.parse("gitea.token"), context=context)
    except Exception:
        return ""
    if value is None:
        return ""
    return value.as_str().strip()
