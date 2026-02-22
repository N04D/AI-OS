from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {
            "disallow_self_approval": True,
            "develop": {"min_approvals": 1, "require_human_approval": False},
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": ["lint"]},
        "system_evolution": {
            "detect_paths": ["supervisor/", "governance/policy/"],
            "approvals": {"min_approvals": 2, "require_human_approval": True},
            "ci": {"required_checks": ["lint", "determinism-check"]},
        },
        "commit_signing": {"required": False},
    }


def test_system_evolution_escalates_requirements():
    pr = {"number": 1, "title": "x", "body": "", "base": {"ref": "develop"}, "head": {"ref": "feature/a"}, "user": {"login": "author"}, "_open_prs": []}
    files = ["supervisor/supervisor.py"]
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "reviewer1", "type": "User"}}]
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), pr, [], files, reviews, statuses)
    assert result["system_evolution"] is True
    assert "insufficient_approvals" in result["failed_gates"]
    assert "required_status_checks" in result["failed_gates"]
