from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": ["supervisor/"],
        "locks": {"required_on_high_risk": True, "exclusive": True, "allowed": ["LOCK:supervisor/"]},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": ["supervisor/"], "approvals": {"min_approvals": 0, "require_human_approval": False}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr(body="", open_prs=None):
    return {
        "number": 1,
        "title": "feature #1",
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": open_prs or [],
    }


def test_high_risk_without_lock_fails_lock_required():
    result = evaluate_pr(_policy(), _pr(""), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_required" in result["failed_gates"]
    assert any("missing LOCK:supervisor/" in reason for reason in result["failed_reasons"])


def test_high_risk_with_lock_passes_lock_required():
    result = evaluate_pr(_policy(), _pr("LOCK:supervisor/"), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_required" not in result["failed_gates"]


def test_lock_conflict_fails_lock_exclusive():
    open_prs = [{"number": 2, "title": "other", "body": "LOCK:supervisor/"}]
    result = evaluate_pr(
        _policy(),
        _pr("LOCK:supervisor/", open_prs=open_prs),
        [],
        ["supervisor/supervisor.py"],
        [],
        [],
    )
    assert "lock_exclusive" in result["failed_gates"]
    assert any("conflicts=2" in reason for reason in result["failed_reasons"])
