from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {
            "disallow_self_approval": True,
            "develop": {"min_approvals": 1, "require_distinct_reviewer": True},
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_self_approval_forbidden():
    pr = {"number": 1, "title": "x", "body": "", "base": {"ref": "develop"}, "head": {"ref": "feature/a"}, "user": {"login": "alice"}, "_open_prs": []}
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "alice", "type": "User"}}]
    result = evaluate_pr(_policy(), pr, [], [], reviews, [])
    assert "self_approval_forbidden" in result["failed_gates"]
