from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .types import AccessDenied


@dataclass(frozen=True)
class SecretAccessContext:
    context_id: str
    trust_level: str
    elevated: bool = False


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
    def from_id(cls, context_id: str) -> SecretAccessContext:
        selected = cls._REGISTRY.get(str(context_id or "").strip())
        if selected is None:
            raise AccessDenied(f"Unknown capability context '{context_id}'.")
        trust_level, elevated = selected
        return SecretAccessContext(context_id=context_id, trust_level=trust_level, elevated=elevated)

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

    @classmethod
    def interactive_cli(cls) -> SecretAccessContext:
        return cls.from_id("interactive_cli")

    @classmethod
    def ui_test_connection(cls) -> SecretAccessContext:
        return cls.from_id("ui.test_connection")

    @classmethod
    def supervisor_autonomy_promotion_gate(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.autonomy_promotion_gate")

    @classmethod
    def supervisor_autonomy_review_intake_gate(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.autonomy_review_intake_gate")

    @classmethod
    def supervisor_autonomy_task_materializer(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.autonomy_task_materializer")

    @classmethod
    def supervisor_agent_workspace_push_pr(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.agent_workspace.push_pr")

    @classmethod
    def supervisor_cli_night_run(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.cli.night_run")

    @classmethod
    def supervisor_auth_headers(cls) -> SecretAccessContext:
        return cls.from_id("supervisor.supervisor.auth_headers")
