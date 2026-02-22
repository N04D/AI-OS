"""Pure secret injection validation scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

SecretInjectionMode = Literal["header", "body_field", "query_param", "url_path"]
ValidationResult = Literal["valid", "invalid", "review_required"]


@dataclass(frozen=True)
class SecretRef:
    provider: Literal["vault", "env", "keychain", "kms"]
    key: str
    version: str | None = None
    expires_at_required: bool = False
    rotation_ttl_seconds: int | None = None


class SecretInjectionValidator(Protocol):
    """Pure interface. No I/O and no secret material access."""

    def validate(
        self,
        secret_ref: SecretRef,
        injection_mode: SecretInjectionMode,
        policy_document: dict,
    ) -> ValidationResult: ...


def validate_secret_injection(
    *,
    secret_ref: SecretRef,
    injection_mode: SecretInjectionMode,
    disallowed_injection_modes: set[SecretInjectionMode],
    exception_modes: set[SecretInjectionMode] | None = None,
) -> ValidationResult:
    exception_modes = exception_modes or set()

    if not secret_ref.key:
        return "invalid"

    has_expiry_policy = secret_ref.expires_at_required or (
        secret_ref.rotation_ttl_seconds is not None and secret_ref.rotation_ttl_seconds > 0
    )
    if not has_expiry_policy:
        return "invalid"

    if injection_mode in disallowed_injection_modes:
        if injection_mode in exception_modes:
            return "review_required"
        return "invalid"

    return "valid"
