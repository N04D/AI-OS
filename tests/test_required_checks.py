from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": ["lint", "unit-tests"]},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_required_checks_fail_when_missing():
    pr = {"number": 1, "title": "x", "body": "", "base": {"ref": "develop"}, "head": {"ref": "feature/a"}, "user": {"login": "a"}, "_open_prs": []}
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), pr, [], [], [], statuses)
    assert "required_status_checks" in result["failed_gates"]
