from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {
            "disallow_self_approval": False,
            "develop": {"min_approvals": 1, "require_human_approval": False, "require_distinct_reviewer": False},
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": ["supervisor/"],
        "locks": {"required_on_high_risk": True, "exclusive": True, "allowed": ["LOCK:supervisor/"]},
        "ci": {"required_checks": ["lint"]},
        "system_evolution": {
            "detect_paths": ["supervisor/"],
            "approvals": {"min_approvals": 2, "require_human_approval": True},
            "ci": {"required_checks": ["lint", "determinism-check"]},
        },
        "commit_signing": {"required": False},
    }


def _pr(body=""):
    return {
        "number": 1,
        "title": "x",
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def test_system_evolution_missing_determinism_check_fails_closed():
    reviews = [
        {"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "r1", "type": "User"}},
        {"state": "APPROVED", "submitted_at": "2026-01-01T01:00:00Z", "user": {"login": "r2", "type": "User"}},
    ]
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), _pr("LOCK:supervisor/"), [], ["supervisor/supervisor.py"], reviews, statuses)
    assert "required_status_checks" in result["failed_gates"]
    assert "system_evolution_escalation" in result["failed_gates"]


def test_system_evolution_approvals_below_min_fails_closed():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "r1", "type": "User"}}]
    statuses = [
        {"context": "lint", "state": "success"},
        {"context": "determinism-check", "state": "success"},
    ]
    result = evaluate_pr(_policy(), _pr("LOCK:supervisor/"), [], ["supervisor/supervisor.py"], reviews, statuses)
    assert "min_approvals_met" in result["failed_gates"]
    assert "system_evolution_escalation" in result["failed_gates"]


def test_high_risk_without_lock_fails_lock_only_not_high_risk_gate():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "r1", "type": "User"}}]
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), _pr(""), [], ["supervisor/supervisor.py"], reviews, statuses)
    assert "lock_required" in result["failed_gates"]
    assert "high_risk_path_detection" not in result["failed_gates"]
