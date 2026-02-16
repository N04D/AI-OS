from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": ["lint"]},
        "system_evolution": {"detect_paths": [], "approvals": {}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr():
    return {
        "number": 1,
        "title": "x",
        "body": "",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def test_duplicate_context_first_seen_deterministic():
    statuses = [
        {"context": "lint", "state": "failure"},
        {"context": "lint", "state": "success"},
    ]
    result = evaluate_pr(_policy(), _pr(), [], [], [], statuses)
    assert "required_status_checks" in result["failed_gates"]


def test_duplicate_context_with_success_first_passes():
    statuses = [
        {"context": "lint", "state": "success"},
        {"context": "lint", "state": "failure"},
    ]
    result = evaluate_pr(_policy(), _pr(), [], [], [], statuses)
    assert "required_status_checks" not in result["failed_gates"]
