from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {
            "required_sections": ["Subsystem", "Risk Level"],
            "reject_placeholders": ["TBD", "TODO", "N/A"],
            "min_section_length": 2,
        },
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_missing_template_section_fails():
    pr = {
        "number": 1,
        "title": "feature",
        "body": "### Subsystem\ncore\n",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "alice"},
        "_open_prs": [],
    }
    result = evaluate_pr(_policy(), pr, [], [], [], [])
    assert "pr_template_sections" in result["failed_gates"]
