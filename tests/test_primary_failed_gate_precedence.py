from supervisor.pr_gate.evaluator import GATE_SEVERITY
from supervisor.pr_gate.evaluator import _primary_failed_gate
from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "targets": {"allowed_base_branches": ["develop"]},
        "branch_rules": {
            "feature_to_develop_only": False,
            "patterns": {"feature": {"regex": r"^feature/.+$"}},
        },
        "approvals": {
            "disallow_self_approval": False,
            "develop": {
                "min_approvals": 2,
                "require_distinct_reviewer": False,
                "require_human_approval": True,
                "require_supervisor_status": False,
            },
        },
        "issue_link": {"required": True, "patterns": [r"(^|\s)#([0-9]+)(\s|$)"]},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required": True, "required_checks": ["lint"]},
        "system_evolution": {
            "detect_paths": ["supervisor/"],
            "ci": {"required_checks": ["lint", "determinism-check"]},
            "approvals": {"min_approvals": 2, "require_human_approval": True},
        },
        "commit_signing": {"required": False, "mode": "all_commits", "accepted_types": ["gpg"]},
    }


def test_primary_failed_gate_uses_max_severity_contract():
    failed = ["issue_reference_required", "required_status_checks", "commit_signing_required"]
    primary = _primary_failed_gate(failed)
    assert primary == "commit_signing_required"
    assert GATE_SEVERITY[primary] == max(GATE_SEVERITY[g] for g in failed)


def test_lock_precedence_contract_prefers_lock_exclusive_when_both_fail():
    failed = ["lock_required", "lock_exclusive"]
    primary = _primary_failed_gate(failed)
    assert primary == "lock_exclusive"
    assert GATE_SEVERITY["lock_exclusive"] > GATE_SEVERITY["lock_required"]


def test_primary_failed_gate_none_when_no_failures():
    assert _primary_failed_gate([]) is None


def test_evaluate_pr_exposes_primary_failed_gate():
    policy = _policy()
    pr = {
        "number": 1,
        "title": "change",
        "body": "",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }
    files = ["supervisor/supervisor.py"]
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "r1", "type": "User"}}]
    statuses = [{"context": "lint", "state": "success"}]

    result = evaluate_pr(policy, pr, [], files, reviews, statuses)
    assert result["primary_failed_gate"] in result["failed_gates"]
    assert result["primary_failed_gate"] == "system_evolution_escalation"
