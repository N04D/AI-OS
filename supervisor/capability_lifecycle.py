from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

STATE_NOT_PRESENT = "NOT_PRESENT"
STATE_PROPOSAL_REQUIRED = "PROPOSAL_REQUIRED"
STATE_PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
STATE_IMPLEMENTATION_PENDING = "IMPLEMENTATION_PENDING"
STATE_IMPLEMENTED_NOT_ACTIVE = "IMPLEMENTED_NOT_ACTIVE"
STATE_ACTIVE = "ACTIVE"
STATE_SUSPENDED = "SUSPENDED"

STATES = {
    STATE_NOT_PRESENT,
    STATE_PROPOSAL_REQUIRED,
    STATE_PROPOSAL_APPROVED,
    STATE_IMPLEMENTATION_PENDING,
    STATE_IMPLEMENTED_NOT_ACTIVE,
    STATE_ACTIVE,
    STATE_SUSPENDED,
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    STATE_NOT_PRESENT: {STATE_PROPOSAL_REQUIRED},
    STATE_PROPOSAL_REQUIRED: {STATE_PROPOSAL_APPROVED},
    STATE_PROPOSAL_APPROVED: {STATE_IMPLEMENTATION_PENDING},
    STATE_IMPLEMENTATION_PENDING: {STATE_IMPLEMENTED_NOT_ACTIVE},
    STATE_IMPLEMENTED_NOT_ACTIVE: {STATE_ACTIVE},
    STATE_ACTIVE: {STATE_SUSPENDED},
    STATE_SUSPENDED: {STATE_ACTIVE},
}

DEFAULT_REGISTRY_PATH = Path("state/capabilities/enabled.json")

DENY_CAPABILITY_TRANSITION_INVALID = "DENY_CAPABILITY_TRANSITION_INVALID"
DENY_CAPABILITY_APPROVAL_INVALID = "DENY_CAPABILITY_APPROVAL_INVALID"
DENY_CAPABILITY_SECRETS_MISSING = "DENY_CAPABILITY_SECRETS_MISSING"
DENY_CAPABILITY_NETWORK_REQUIRED = "DENY_CAPABILITY_NETWORK_REQUIRED"
DENY_CAPABILITY_REGISTRY_INVALID = "DENY_CAPABILITY_REGISTRY_INVALID"

REQUIRED_SECRETS_EMAIL_SEND = ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM")


class CapabilityLifecycleError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


@dataclass(frozen=True)
class PrerequisiteStatus:
    missing_secrets: tuple[str, ...]
    network_enabled: bool


def _now_utc(now_utc: datetime | None = None) -> datetime:
    if isinstance(now_utc, datetime):
        return now_utc.astimezone(UTC)
    return datetime.now(UTC)


def _ts(now_utc: datetime | None = None) -> str:
    return _now_utc(now_utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _validate_registry_payload(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, "registry must be object")
    out: dict[str, dict[str, Any]] = {}
    for cap, meta in payload.items():
        if not isinstance(cap, str) or not cap.strip():
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, "capability key invalid")
        if not isinstance(meta, dict):
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"metadata invalid: {cap}")
        state = meta.get("state")
        if not isinstance(state, str) or state not in STATES:
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"state invalid: {cap}")
        proposal_issue = meta.get("proposal_issue")
        if proposal_issue is not None and not isinstance(proposal_issue, int):
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"proposal_issue invalid: {cap}")
        approved_by = meta.get("approved_by")
        if approved_by is not None and not isinstance(approved_by, str):
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"approved_by invalid: {cap}")
        activated_by = meta.get("activated_by")
        if activated_by is not None and not isinstance(activated_by, str):
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"activated_by invalid: {cap}")
        timestamps = meta.get("timestamps", {})
        if not isinstance(timestamps, dict):
            raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"timestamps invalid: {cap}")
        out[cap] = {
            "state": state,
            "proposal_issue": proposal_issue,
            "approved_by": approved_by,
            "activated_by": activated_by,
            "timestamps": dict(sorted((str(k), v) for k, v in timestamps.items())),
        }
    return dict(sorted(out.items(), key=lambda item: item[0]))


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, f"missing registry: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityLifecycleError(DENY_CAPABILITY_REGISTRY_INVALID, "invalid registry json") from exc
    return _validate_registry_payload(payload)


def write_registry(registry: dict[str, dict[str, Any]], path: Path = DEFAULT_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _validate_registry_payload(registry)
    path.write_text(_canonical_json(normalized), encoding="utf-8")


def _ensure_capability(registry: dict[str, dict[str, Any]], capability: str) -> dict[str, Any]:
    item = registry.get(capability)
    if item is None:
        registry[capability] = {
            "state": STATE_NOT_PRESENT,
            "proposal_issue": None,
            "approved_by": None,
            "activated_by": None,
            "timestamps": {},
        }
        item = registry[capability]
    return item


def guarded_transition(
    registry: dict[str, dict[str, Any]],
    *,
    capability: str,
    to_state: str,
    actor: str | None = None,
    issue_number: int | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if to_state not in STATES:
        raise CapabilityLifecycleError(DENY_CAPABILITY_TRANSITION_INVALID, f"unknown target state: {to_state}")
    item = _ensure_capability(registry, capability)
    from_state = str(item.get("state", STATE_NOT_PRESENT))
    allowed = ALLOWED_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise CapabilityLifecycleError(
            DENY_CAPABILITY_TRANSITION_INVALID,
            f"invalid transition {from_state} -> {to_state}",
        )
    item["state"] = to_state
    ts = _ts(now_utc)
    timestamps = item.setdefault("timestamps", {})
    if isinstance(timestamps, dict):
        timestamps[f"{from_state}->{to_state}"] = ts
    if issue_number is not None:
        item["proposal_issue"] = int(issue_number)
    if actor and to_state == STATE_PROPOSAL_APPROVED:
        item["approved_by"] = actor
    if actor and to_state == STATE_ACTIVE:
        item["activated_by"] = actor
    return item


def approve_proposal(
    registry: dict[str, dict[str, Any]],
    *,
    capability: str,
    issue_number: int,
    author_login: str,
    body: str,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    expected = f"APPROVE PROPOSAL {capability}"
    if body.strip() != expected:
        raise CapabilityLifecycleError(DENY_CAPABILITY_APPROVAL_INVALID, "proposal approval text mismatch")
    item = _ensure_capability(registry, capability)
    if item.get("state") == STATE_NOT_PRESENT:
        guarded_transition(
            registry,
            capability=capability,
            to_state=STATE_PROPOSAL_REQUIRED,
            actor=author_login,
            issue_number=issue_number,
            now_utc=now_utc,
        )
    return guarded_transition(
        registry,
        capability=capability,
        to_state=STATE_PROPOSAL_APPROVED,
        actor=author_login,
        issue_number=issue_number,
        now_utc=now_utc,
    )


def mark_implementation_pending(
    registry: dict[str, dict[str, Any]],
    *,
    capability: str,
    actor: str,
    issue_number: int,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    return guarded_transition(
        registry,
        capability=capability,
        to_state=STATE_IMPLEMENTATION_PENDING,
        actor=actor,
        issue_number=issue_number,
        now_utc=now_utc,
    )


def mark_implemented_not_active(
    registry: dict[str, dict[str, Any]],
    *,
    capability: str,
    actor: str,
    issue_number: int,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    return guarded_transition(
        registry,
        capability=capability,
        to_state=STATE_IMPLEMENTED_NOT_ACTIVE,
        actor=actor,
        issue_number=issue_number,
        now_utc=now_utc,
    )


def collect_activation_prerequisites(env: dict[str, str], *, capability: str) -> PrerequisiteStatus:
    if capability != "email.send":
        return PrerequisiteStatus(missing_secrets=tuple(), network_enabled=True)
    missing = tuple(sorted(key for key in REQUIRED_SECRETS_EMAIL_SEND if not (env.get(key, "") or "").strip()))
    network_enabled = (env.get("NETWORK_ACCESS_ENABLED", "") or "").strip().lower() == "true"
    return PrerequisiteStatus(missing_secrets=missing, network_enabled=network_enabled)


def activate_from_approval(
    registry: dict[str, dict[str, Any]],
    *,
    capability: str,
    issue_number: int,
    author_login: str,
    body: str,
    env: dict[str, str],
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    expected = f"APPROVE ACTIVATE {capability}"
    if body.strip() != expected:
        raise CapabilityLifecycleError(DENY_CAPABILITY_APPROVAL_INVALID, "activation approval text mismatch")
    item = _ensure_capability(registry, capability)
    if item.get("state") == STATE_ACTIVE:
        # Idempotent activation: already active, no mutation.
        return item
    if item.get("state") != STATE_IMPLEMENTED_NOT_ACTIVE:
        raise CapabilityLifecycleError(
            DENY_CAPABILITY_TRANSITION_INVALID,
            f"activation requires state {STATE_IMPLEMENTED_NOT_ACTIVE}",
        )

    # Model A atomic activation: validate all prerequisites before mutating state.
    prereq = collect_activation_prerequisites(env, capability=capability)
    if prereq.missing_secrets:
        raise CapabilityLifecycleError(
            DENY_CAPABILITY_SECRETS_MISSING,
            f"missing secrets: {','.join(prereq.missing_secrets)}",
        )
    if not prereq.network_enabled:
        raise CapabilityLifecycleError(DENY_CAPABILITY_NETWORK_REQUIRED, "NETWORK_ACCESS_ENABLED must be true")

    return guarded_transition(
        registry,
        capability=capability,
        to_state=STATE_ACTIVE,
        actor=author_login,
        issue_number=issue_number,
        now_utc=now_utc,
    )


def state_transition_table() -> dict[str, list[str]]:
    return {key: sorted(values) for key, values in sorted(ALLOWED_TRANSITIONS.items(), key=lambda item: item[0])}
