from __future__ import annotations

from datetime import UTC
from datetime import datetime

import pytest

from supervisor.capability_lifecycle import CapabilityLifecycleError
from supervisor.capability_lifecycle import DENY_CAPABILITY_NETWORK_REQUIRED
from supervisor.capability_lifecycle import DENY_CAPABILITY_SECRETS_MISSING
from supervisor.capability_lifecycle import DENY_CAPABILITY_TRANSITION_INVALID
from supervisor.capability_lifecycle import STATE_IMPLEMENTED_NOT_ACTIVE
from supervisor.capability_lifecycle import STATE_PROPOSAL_APPROVED
from supervisor.capability_lifecycle import STATE_PROPOSAL_REQUIRED
from supervisor.capability_lifecycle import activate_from_approval
from supervisor.capability_lifecycle import approve_proposal
from supervisor.capability_lifecycle import guarded_transition
from supervisor.capability_lifecycle import mark_implemented_not_active
from supervisor.capability_lifecycle import mark_implementation_pending


def _base_registry() -> dict[str, dict[str, object]]:
    return {
        "email.send": {
            "state": "NOT_PRESENT",
            "proposal_issue": None,
            "approved_by": None,
            "activated_by": None,
            "timestamps": {},
        }
    }


def test_illegal_transition_rejected() -> None:
    registry = _base_registry()
    with pytest.raises(CapabilityLifecycleError) as exc:
        guarded_transition(
            registry,
            capability="email.send",
            to_state=STATE_IMPLEMENTED_NOT_ACTIVE,
            actor="Don",
            issue_number=60,
            now_utc=datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        )
    assert exc.value.reason_code == DENY_CAPABILITY_TRANSITION_INVALID


def test_proposal_to_implementation_flow() -> None:
    registry = _base_registry()
    approve_proposal(
        registry,
        capability="email.send",
        issue_number=60,
        author_login="Don",
        body="APPROVE PROPOSAL email.send",
        now_utc=datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
    )
    assert registry["email.send"]["state"] == STATE_PROPOSAL_APPROVED
    mark_implementation_pending(
        registry,
        capability="email.send",
        actor="codex",
        issue_number=60,
        now_utc=datetime(2026, 3, 1, 0, 1, 0, tzinfo=UTC),
    )
    mark_implemented_not_active(
        registry,
        capability="email.send",
        actor="codex",
        issue_number=60,
        now_utc=datetime(2026, 3, 1, 0, 2, 0, tzinfo=UTC),
    )
    assert registry["email.send"]["state"] == STATE_IMPLEMENTED_NOT_ACTIVE
    assert registry["email.send"]["activated_by"] is None


def test_implementation_to_activation_flow() -> None:
    registry = {
        "email.send": {
            "state": STATE_IMPLEMENTED_NOT_ACTIVE,
            "proposal_issue": 60,
            "approved_by": "Don",
            "activated_by": None,
            "timestamps": {},
        }
    }
    result = activate_from_approval(
        registry,
        capability="email.send",
        issue_number=60,
        author_login="Don",
        body="APPROVE ACTIVATE email.send",
        env={
            "SMTP_HOST": "smtp.example",
            "SMTP_PORT": "587",
            "SMTP_USER": "user",
            "SMTP_PASS": "pass",
            "SMTP_FROM": "noreply@example.com",
            "NETWORK_ACCESS_ENABLED": "true",
        },
        now_utc=datetime(2026, 3, 1, 0, 3, 0, tzinfo=UTC),
    )
    assert result["state"] == "ACTIVE"
    assert result["activated_by"] == "Don"


def test_secrets_check_only_at_activation_phase() -> None:
    registry = _base_registry()
    approve_proposal(
        registry,
        capability="email.send",
        issue_number=60,
        author_login="Don",
        body="APPROVE PROPOSAL email.send",
        now_utc=datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
    )
    mark_implementation_pending(
        registry,
        capability="email.send",
        actor="codex",
        issue_number=60,
        now_utc=datetime(2026, 3, 1, 0, 1, 0, tzinfo=UTC),
    )
    mark_implemented_not_active(
        registry,
        capability="email.send",
        actor="codex",
        issue_number=60,
        now_utc=datetime(2026, 3, 1, 0, 2, 0, tzinfo=UTC),
    )
    assert registry["email.send"]["state"] == STATE_IMPLEMENTED_NOT_ACTIVE

    # No secrets checked during proposal/implementation transitions;
    # they are checked only at IMPLEMENTED_NOT_ACTIVE -> ACTIVE activation.
    with pytest.raises(CapabilityLifecycleError) as exc:
        activate_from_approval(
            registry,
            capability="email.send",
            issue_number=60,
            author_login="Don",
            body="APPROVE ACTIVATE email.send",
            env={"NETWORK_ACCESS_ENABLED": "false"},
            now_utc=datetime(2026, 3, 1, 0, 4, 0, tzinfo=UTC),
        )
    assert exc.value.reason_code in {DENY_CAPABILITY_SECRETS_MISSING, DENY_CAPABILITY_NETWORK_REQUIRED}
    # Atomic guarantee: failed activation does not modify state.
    assert registry["email.send"]["state"] == STATE_IMPLEMENTED_NOT_ACTIVE


def test_activation_requires_implemented_not_active_state() -> None:
    registry = {
        "email.send": {
            "state": STATE_PROPOSAL_REQUIRED,
            "proposal_issue": 60,
            "approved_by": None,
            "activated_by": None,
            "timestamps": {},
        }
    }
    with pytest.raises(CapabilityLifecycleError) as exc:
        activate_from_approval(
            registry,
            capability="email.send",
            issue_number=60,
            author_login="Don",
            body="APPROVE ACTIVATE email.send",
            env={
                "SMTP_HOST": "smtp.example",
                "SMTP_PORT": "587",
                "SMTP_USER": "user",
                "SMTP_PASS": "pass",
                "SMTP_FROM": "noreply@example.com",
                "NETWORK_ACCESS_ENABLED": "true",
            },
            now_utc=datetime(2026, 3, 1, 0, 5, 0, tzinfo=UTC),
        )
    assert exc.value.reason_code == DENY_CAPABILITY_TRANSITION_INVALID


def test_repeated_activation_is_idempotent_when_already_active() -> None:
    registry = {
        "email.send": {
            "state": "ACTIVE",
            "proposal_issue": 60,
            "approved_by": "Don",
            "activated_by": "Don",
            "timestamps": {"IMPLEMENTED_NOT_ACTIVE->ACTIVE": "2026-03-01T00:06:00Z"},
        }
    }
    before = dict(registry["email.send"])
    result = activate_from_approval(
        registry,
        capability="email.send",
        issue_number=60,
        author_login="Don",
        body="APPROVE ACTIVATE email.send",
        env={},
        now_utc=datetime(2026, 3, 1, 0, 7, 0, tzinfo=UTC),
    )
    assert result["state"] == "ACTIVE"
    assert registry["email.send"] == before
