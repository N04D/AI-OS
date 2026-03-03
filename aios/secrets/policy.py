from __future__ import annotations

from collections.abc import Mapping

from .context import SecretAccessContext
from .types import SecretKey


UI_EDITABLE_KEYS: frozenset[str] = frozenset(
    {
        "openai.api_key",
        "gitea.token",
        "openai.critical_api_key",
    }
)

# Default-deny capability policy: every context must be explicitly allowlisted.
CAPABILITY_ALLOWLIST: dict[str, frozenset[str]] = {
    "ui.test_connection": frozenset({"openai.api_key", "gitea.token", "openai.critical_api_key"}),
    "interactive_cli": frozenset({"openai.api_key", "gitea.token", "openai.critical_api_key"}),
    "supervisor.mail_worker.transport": frozenset({"smtp.pass"}),
    "supervisor.autonomy_promotion_gate": frozenset({"gitea.token"}),
    "supervisor.autonomy_review_intake_gate": frozenset({"gitea.token"}),
    "supervisor.autonomy_task_materializer": frozenset({"gitea.token"}),
    "supervisor.agent_workspace.push_pr": frozenset({"gitea.token"}),
    "supervisor.cli.night_run": frozenset({"gitea.token"}),
    "supervisor.supervisor.auth_headers": frozenset({"gitea.token"}),
}

# Only explicit key/context pairs may search fallback when keyring misses.
FALLBACK_SEARCH_ALLOWLIST: dict[str, frozenset[str]] = {
    "interactive_cli": frozenset({"openai.api_key", "gitea.token", "openai.critical_api_key"}),
    "supervisor.mail_worker.transport": frozenset({"smtp.pass"}),
}

CRITICAL_SECRET_KEYS: frozenset[str] = frozenset({"openai.critical_api_key"})


def can_ui_edit(key: SecretKey) -> bool:
    return key.as_str() in UI_EDITABLE_KEYS


def is_capability_allowed(
    key: SecretKey,
    context: SecretAccessContext,
    *,
    mapping: Mapping[str, frozenset[str]] | None = None,
) -> bool:
    selected = CAPABILITY_ALLOWLIST if mapping is None else dict(mapping)
    allowed = selected.get(context.context_id)
    if not allowed:
        return False
    return key.as_str() in allowed


def allow_fallback_lookup(key: SecretKey, context: SecretAccessContext) -> bool:
    allowed = FALLBACK_SEARCH_ALLOWLIST.get(context.context_id)
    return bool(allowed and key.as_str() in allowed)


def requires_approval_token(key: SecretKey) -> bool:
    return key.as_str() in CRITICAL_SECRET_KEYS
