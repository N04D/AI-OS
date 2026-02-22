from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"feature_to_develop_only": True, "patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 1, "require_distinct_reviewer": True}},
        "issue_link": {"required": True, "patterns": [r"(^|\\s)#([0-9]+)(\\s|$)"]},
        "pr_template": {"required_sections": ["Subsystem"], "reject_placeholders": ["TBD"], "min_section_length": 5},
        "high_risk_paths": ["supervisor/"],
        "locks": {"required_on_high_risk": True, "exclusive": True, "allowed": ["LOCK:supervisor/"]},
        "ci": {"required_checks": ["lint"]},
        "system_evolution": {"detect_paths": ["supervisor/"], "approvals": {"min_approvals": 2, "require_human_approval": True}, "ci": {"required_checks": ["lint", "determinism-check"]}},
        "commit_signing": {"required": False},
    }


def test_failed_reasons_are_textual_strings():
    pr = {
        "number": 1,
        "title": "missing issue ref",
        "body": "### Subsystem\nTBD\n",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }
    result = evaluate_pr(_policy(), pr, [], ["supervisor/supervisor.py"], [], [])
    assert result["failed_reasons"]
    assert all(isinstance(reason, str) for reason in result["failed_reasons"])
    assert any("missing_issue_ref" in reason for reason in result["failed_reasons"])
    assert any("missing LOCK:supervisor/" in reason for reason in result["failed_reasons"])
