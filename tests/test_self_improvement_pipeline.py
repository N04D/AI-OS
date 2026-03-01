from __future__ import annotations

from supervisor.pr_gate.evaluator import evaluate_pr


def _policy() -> dict:
    return {
        "targets": {"allowed_base_branches": []},
        "branch_rules": {
            "feature_to_develop_only": False,
            "patterns": {
                "si": {"regex": r"^self-improvement/.+$"},
                "feature": {"regex": r"^feature/.+$"},
            },
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": False, "allowed": []},
        "ci": {"required": False, "required_checks": []},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "system_evolution": {"detect_paths": [], "approvals": {}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr(*, labels: list[dict] | None = None, body: str = "") -> dict:
    return {
        "number": 404,
        "title": "self improvement proposal #404",
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "self-improvement/proposal-404"},
        "user": {"login": "codex"},
        "_open_prs": [],
        "labels": labels or [],
    }


def test_self_improvement_requires_label_when_context_active() -> None:
    result = evaluate_pr(_policy(), _pr(labels=[]), [], [], [], [])
    assert "self_improvement_label_required" in result["failed_gates"]


def test_self_improvement_requires_proposal_sections() -> None:
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body="# Empty"),
        [],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_proposal_template" in result["failed_gates"]


def test_self_improvement_requires_supervisor_approval_status() -> None:
    body = """
## Problem Statement
x
## Risk Tier
LOW
## Affected Components
docs/
## Determinism Impact
none
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(_policy(), _pr(labels=[{"name": "self-improvement"}], body=body), [], [], [], [])
    assert "self_improvement_supervisor_approval" in result["failed_gates"]


def test_self_improvement_pipeline_passes_with_complete_proposal() -> None:
    body = """
## Problem Statement
Need deterministic docs updates.
## Risk Tier
LOW
## Affected Components
docs/specs/
## Determinism Impact
No runtime behavior changed.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
not required for LOW; included for completeness
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_label_required" not in result["failed_gates"]
    assert "self_improvement_proposal_template" not in result["failed_gates"]
    assert "self_improvement_risk_tier" not in result["failed_gates"]
    assert "self_improvement_test_plan" not in result["failed_gates"]
    assert "self_improvement_checklist" not in result["failed_gates"]
    assert "self_improvement_supervisor_approval" not in result["failed_gates"]
    assert result["self_improvement_audit"]["risk_tier"] == "LOW"
    assert result["self_improvement_audit"]["decision"] == "allow"
    assert result["self_improvement_audit"]["halt_state"] == "awaiting_approval"
    assert result["self_improvement_audit"]["awaiting_approval_logged"] is True


def test_runtime_mutation_outside_governed_self_improvement_pr_is_denied() -> None:
    pr = _pr(
        labels=[],
        body=(
            "This is a self-improvement change, but not in governed PR context "
            "(no label and non self-improvement branch)."
        ),
    )
    pr["head"]["ref"] = "feature/runtime-refactor"
    result = evaluate_pr(
        _policy(),
        pr,
        [],
        ["supervisor/runtime_refactor.py", "tests/test_runtime_refactor.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_pr_only_mutation" in result["failed_gates"]


def test_self_improvement_mutation_cannot_bypass_governed_pr_flow() -> None:
    pr = _pr(
        labels=[],
        body=(
            "self-improvement mutation attempt without governed PR context; "
            "tries to change runtime logic."
        ),
    )
    pr["title"] = "self-improvement hotfix bypass attempt"
    pr["head"]["ref"] = "feature/self-improvement-bypass"
    result = evaluate_pr(
        _policy(),
        pr,
        [],
        ["supervisor/control_plane.py", "tests/test_control_plane.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_pr_only_mutation" in result["failed_gates"]


def test_self_improvement_requires_phase_acceptance_evidence() -> None:
    body = """
## Problem Statement
Need deterministic docs updates.
## Risk Tier
LOW
## Affected Components
docs/specs/
## Determinism Impact
No runtime behavior changed.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
not required for LOW
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_phase_acceptance_required" in result["failed_gates"]


def test_self_improvement_requires_halt_discipline_evidence() -> None:
    body = """
## Problem Statement
Need deterministic docs updates.
## Risk Tier
LOW
## Affected Components
docs/specs/
## Determinism Impact
No runtime behavior changed.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
not required for LOW
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_halt_discipline" in result["failed_gates"]


def test_self_improvement_blocks_post_proposal_commits_without_authorization() -> None:
    body = """
## Problem Statement
Need deterministic docs updates.
## Risk Tier
LOW
## Affected Components
docs/specs/
## Determinism Impact
No runtime behavior changed.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
not required for LOW
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [{"sha": "a"}, {"sha": "b"}],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_post_proposal_authorization" in result["failed_gates"]
    assert result["self_improvement_audit"]["halt_state"] == "unauthorized_post_proposal_commits"
    assert result["self_improvement_audit"]["awaiting_approval_logged"] is False


def test_self_improvement_allows_post_proposal_commits_with_authorization() -> None:
    body = """
## Problem Statement
Need deterministic docs updates.
## Risk Tier
LOW
## Affected Components
docs/specs/
## Determinism Impact
No runtime behavior changed.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
not required for LOW
## Approval Token
token://explicit-authorization
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [{"sha": "a"}, {"sha": "b"}],
        [],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_post_proposal_authorization" not in result["failed_gates"]
    assert result["self_improvement_audit"]["halt_state"] == "authorized_execution"


def test_self_improvement_disallowed_path_is_denied() -> None:
    body = """
## Problem Statement
Need runtime change.
## Risk Tier
MED
## Affected Components
kernel/
## Determinism Impact
Preserve behavior.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- docs/
- tests/
## Determinism Evidence
artifact://determinism-med.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["kernel/runtime.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_allowed_change_boundary" in result["failed_gates"]


def test_self_improvement_runtime_change_requires_test_update() -> None:
    body = """
## Problem Statement
Need runtime change.
## Risk Tier
MED
## Affected Components
supervisor/
## Determinism Impact
No behavior change.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- supervisor/
## Determinism Evidence
artifact://determinism-med.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["supervisor/runtime_refactor.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_runtime_test_update" in result["failed_gates"]


def test_self_improvement_governance_core_requires_high_risk() -> None:
    body = """
## Problem Statement
Touch governance policy.
## Risk Tier
LOW
## Affected Components
governance/
## Determinism Impact
None.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- governance/
- tests/
## Determinism Evidence
artifact://determinism-low.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["governance/policy/example.yaml", "tests/test_example.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_governance_core_restriction" in result["failed_gates"]


def test_self_improvement_runtime_scope_and_tests_pass_boundary_checks() -> None:
    body = """
## Problem Statement
Refactor runtime path.
## Risk Tier
MED
## Affected Components
supervisor/
## Determinism Impact
No behavior change.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- supervisor/
- tests/
## Determinism Evidence
artifact://determinism-med.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["supervisor/refactor_unit.py", "tests/test_refactor_unit.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_allowed_change_boundary" not in result["failed_gates"]
    assert "self_improvement_runtime_test_update" not in result["failed_gates"]


def test_self_improvement_med_requires_determinism_evidence() -> None:
    body = """
## Problem Statement
Refactor runtime path.
## Risk Tier
MED
## Affected Components
supervisor/
## Determinism Impact
No behavior change.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- supervisor/
- tests/
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["supervisor/refactor_unit.py", "tests/test_refactor_unit.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_determinism_evidence_required" in result["failed_gates"]
    assert result["self_improvement_audit"]["decision"] == "deny"


def test_self_improvement_risk_tier_bypass_attempt_is_denied() -> None:
    body = """
## Problem Statement
Attempt to bypass risk tier parsing.
## Risk Tier
CRITICAL
## Affected Components
supervisor/
## Determinism Impact
No behavior change.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- supervisor/
- tests/
## Determinism Evidence
artifact://determinism-med.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["supervisor/refactor_unit.py", "tests/test_refactor_unit.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_risk_tier" in result["failed_gates"]


def test_self_improvement_med_with_determinism_evidence_passes_requirement() -> None:
    body = """
## Problem Statement
Refactor runtime path.
## Risk Tier
MED
## Affected Components
supervisor/
## Determinism Impact
No behavior change.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- supervisor/
- tests/
## Determinism Evidence
artifact://determinism-med.json
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["supervisor/refactor_unit.py", "tests/test_refactor_unit.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_determinism_evidence_required" not in result["failed_gates"]


def test_self_improvement_high_requires_approval_token() -> None:
    body = """
## Problem Statement
High risk governance touch.
## Risk Tier
HIGH
## Affected Components
governance/
## Determinism Impact
Controlled.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- governance/
- tests/
## Determinism Evidence
artifact://determinism-high.json
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["governance/policy/example.yaml", "tests/test_example.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_high_risk_token_required" in result["failed_gates"]
    assert result["self_improvement_audit"]["risk_tier"] == "HIGH"


def test_self_improvement_high_risk_token_bypass_attempt_is_denied() -> None:
    body = """
## Problem Statement
High risk governance touch.
## Risk Tier
HIGH
## Affected Components
governance/
## Determinism Impact
Controlled.
## Test Plan (Mandatory)
pytest -q
## Rollback Strategy
git revert <sha>
## Allowed Mutation Scope
- governance/
- tests/
## Determinism Evidence
artifact://determinism-high.json token://misplaced-token
## Phase Acceptance Evidence
- 0 failed
- skip justifications
- roadmap update
- progress update
- HALT
## HALT Discipline
- HALT entered
- authorization required
- awaiting approval
- no commits beyond proposal
- [x] proposal template
- [x] risk tier
- [x] test plan
"""
    result = evaluate_pr(
        _policy(),
        _pr(labels=[{"name": "self-improvement"}], body=body),
        [],
        ["governance/policy/example.yaml", "tests/test_example.py"],
        [],
        [{"context": "supervisor/status", "state": "success"}],
    )
    assert "self_improvement_high_risk_token_required" in result["failed_gates"]
