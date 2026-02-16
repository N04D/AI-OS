from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 1, "require_human_approval": False}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": ["lint"]},
        "system_evolution": {
            "detect_paths": ["supervisor/"],
            "approvals": {"min_approvals": 1, "require_human_approval": True},
            "ci": {"required_checks": ["lint"]},
        },
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


def test_system_evolution_bot_only_fails_human_approval():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "bot1", "type": "Bot"}}]
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), _pr(), [], ["supervisor/supervisor.py"], reviews, statuses)
    assert "human_approval_required" in result["failed_gates"]
    assert any("required=True" in reason for reason in result["failed_reasons"])


def test_normal_scenario_user_reviewer_passes_human_approval():
    reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "reviewer", "type": "User"}}]
    statuses = [{"context": "lint", "state": "success"}]
    result = evaluate_pr(_policy(), _pr(), [], [], reviews, statuses)
    assert "human_approval_required" not in result["failed_gates"]
