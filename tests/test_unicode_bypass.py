from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": True, "patterns": [r"(^|\\s)#([0-9]+)(\\s|$)"]},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "approvals": {}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr(title, body=""):
    return {
        "number": 1,
        "title": title,
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def test_issue_ref_with_zero_width_space_does_not_match():
    title = "fix #\u200b123"
    result = evaluate_pr(_policy(), _pr(title), [], [], [], [])
    assert "issue_reference_required" in result["failed_gates"]


def test_issue_ref_with_fullwidth_hash_does_not_match():
    title = "fix ＃123"
    result = evaluate_pr(_policy(), _pr(title), [], [], [], [])
    assert "issue_reference_required" in result["failed_gates"]


def test_ascii_issue_ref_matches():
    title = "fix #123"
    result = evaluate_pr(_policy(), _pr(title), [], [], [], [])
    assert "issue_reference_required" not in result["failed_gates"]
