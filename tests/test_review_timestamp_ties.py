from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {
            "disallow_self_approval": False,
            "develop": {"min_approvals": 1, "require_distinct_reviewer": True},
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
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


def test_same_user_same_timestamp_later_review_wins_deterministically():
    reviews = [
        {"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "rev1", "type": "User"}},
        {"state": "CHANGES_REQUESTED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "rev1", "type": "User"}},
    ]
    result = evaluate_pr(_policy(), _pr(), [], [], reviews, [])
    assert "min_approvals_met" in result["failed_gates"]
