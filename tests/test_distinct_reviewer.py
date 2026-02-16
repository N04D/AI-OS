from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0, "require_distinct_reviewer": True}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": ["supervisor/"], "approvals": {"min_approvals": 0, "require_human_approval": False}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr():
    return {
        "number": 1,
        "title": "feature #1",
        "body": "",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def test_distinct_reviewer_pass_when_non_author_approves():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "reviewer", "type": "User"}}]
    result = evaluate_pr(_policy(), _pr(), [], [], reviews, [])
    assert "distinct_reviewer_required" not in result["failed_gates"]


def test_distinct_reviewer_fail_when_only_author_approves():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "author", "type": "User"}}]
    result = evaluate_pr(_policy(), _pr(), [], [], reviews, [])
    assert "distinct_reviewer_required" in result["failed_gates"]
    assert any("approvers=" in reason for reason in result["failed_reasons"])
