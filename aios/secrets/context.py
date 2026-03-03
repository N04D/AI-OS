from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import ClassVar

from .types import AccessDenied


@dataclass(frozen=True)
class SecretAccessContext:
    context_id: str
    trust_level: str
    elevated: bool = False
    agent_id: str = "default-agent"
    epoch_id: str = "1970-01-01"
    approval_token: str | None = None


class ContextFactory:
    _REGISTRY: ClassVar[dict[str, tuple[str, bool]]] = {
        "interactive_cli": ("standard", False),
        "ui.test_connection": ("standard", False),
        "supervisor.autonomy_promotion_gate": ("elevated", True),
        "supervisor.autonomy_review_intake_gate": ("elevated", True),
        "supervisor.autonomy_task_materializer": ("elevated", True),
        "supervisor.agent_workspace.push_pr": ("elevated", True),
        "supervisor.cli.night_run": ("elevated", True),
        "supervisor.supervisor.auth_headers": ("elevated", True),
    }

    @classmethod
    def from_id(
        cls,
        context_id: str,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        selected = cls._REGISTRY.get(str(context_id or "").strip())
        if selected is None:
            raise AccessDenied(f"Unknown capability context '{context_id}'.")
        trust_level, elevated = selected
        resolved_agent = str(agent_id or "default-agent").strip() or "default-agent"
        resolved_epoch = str(epoch_id or datetime.now(UTC).strftime("%Y-%m-%d")).strip()
        return SecretAccessContext(
            context_id=context_id,
            trust_level=trust_level,
            elevated=elevated,
            agent_id=resolved_agent,
            epoch_id=resolved_epoch,
            approval_token=approval_token,
        )

    @classmethod
    def validate(cls, context: SecretAccessContext) -> None:
        if context.trust_level not in {"low", "standard", "elevated"}:
            raise AccessDenied("Invalid trust level in context")
        if context.elevated and context.trust_level != "elevated":
            raise AccessDenied("Elevated contexts must use elevated trust level")
        expected = cls._REGISTRY.get(context.context_id)
        if expected is None:
            raise AccessDenied(f"Unknown capability context '{context.context_id}'.")
        if expected != (context.trust_level, context.elevated):
            raise AccessDenied("Context shape does not match registered context definition")
        if not context.agent_id.strip():
            raise AccessDenied("Context agent_id is required")
        if not context.epoch_id.strip():
            raise AccessDenied("Context epoch_id is required")

    @classmethod
    def interactive_cli(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id("interactive_cli", agent_id=agent_id, epoch_id=epoch_id, approval_token=approval_token)

    @classmethod
    def ui_test_connection(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id("ui.test_connection", agent_id=agent_id, epoch_id=epoch_id, approval_token=approval_token)

    @classmethod
    def supervisor_autonomy_promotion_gate(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.autonomy_promotion_gate",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )

    @classmethod
    def supervisor_autonomy_review_intake_gate(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.autonomy_review_intake_gate",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )

    @classmethod
    def supervisor_autonomy_task_materializer(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.autonomy_task_materializer",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )

    @classmethod
    def supervisor_agent_workspace_push_pr(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.agent_workspace.push_pr",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )

    @classmethod
    def supervisor_cli_night_run(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.cli.night_run",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )

    @classmethod
    def supervisor_auth_headers(
        cls,
        *,
        agent_id: str | None = None,
        epoch_id: str | None = None,
        approval_token: str | None = None,
    ) -> SecretAccessContext:
        return cls.from_id(
            "supervisor.supervisor.auth_headers",
            agent_id=agent_id,
            epoch_id=epoch_id,
            approval_token=approval_token,
        )
