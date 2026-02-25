import re

from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": True, "patterns": [r"(^|\s)#([0-9]+)(\s|$)"]},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_issue_ref_required():
    pr = {"number": 1, "title": "feature work", "body": "body without ref", "base": {"ref": "develop"}, "head": {"ref": "feature/ok"}, "user": {"login": "a"}, "_open_prs": []}
    result = evaluate_pr(_policy(), pr, [], [], [], [])
    assert "issue_reference_required" in result["failed_gates"]
    assert result["primary_failed_gate"] == "issue_reference_required"


def test_issue_ref_regex_fixture_matches_ascii_issue():
    pattern = _policy()["issue_link"]["patterns"][0]
    assert re.search(pattern, "fix #123")
