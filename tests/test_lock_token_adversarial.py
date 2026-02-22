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


def _pr(body, open_prs=None):
    return {
        "number": 1,
        "title": "change #1",
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": open_prs or [],
    }


def test_embedded_token_not_accepted_if_no_word_boundary():
    body = "prefixXLOCK:supervisor/"
    result = evaluate_pr(_policy(), _pr(body), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_required" in result["failed_gates"]


def test_token_with_punctuation_is_accepted():
    body = "(LOCK:supervisor/)"
    result = evaluate_pr(_policy(), _pr(body), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_required" not in result["failed_gates"]


def test_multiple_tokens_fail_lock_exclusive():
    body = "LOCK:supervisor/ LOCK:supervisor/"
    result = evaluate_pr(_policy(), _pr(body), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_exclusive" in result["failed_gates"]


def test_conflict_with_adversarial_other_pr_body():
    body = "```\nLOCK:supervisor/\n```"
    other = [{"number": 2, "title": "x", "body": "> LOCK:supervisor/"}]
    result = evaluate_pr(_policy(), _pr(body, open_prs=other), [], ["supervisor/supervisor.py"], [], [])
    assert "lock_exclusive" in result["failed_gates"]
