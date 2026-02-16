from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {
            "required_sections": ["Subsystem", "Risk Level"],
            "reject_placeholders": ["TBD", "TODO", "N/A"],
            "min_section_length": 3,
        },
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "approvals": {}, "ci": {"required_checks": []}},
        "commit_signing": {"required": False},
    }


def _pr(body):
    return {
        "number": 1,
        "title": "x",
        "body": body,
        "base": {"ref": "develop"},
        "head": {"ref": "feature/x"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def test_similar_heading_cannot_bypass_required_section():
    body = "#### Subsystem\ncore\n### Risk Level\nhigh\n"
    result = evaluate_pr(_policy(), _pr(body), [], [], [], [])
    assert "pr_template_sections" in result["failed_gates"]


def test_heading_with_extra_spaces_and_tabs_is_accepted():
    body = "###   Subsystem\ncore\n###\tRisk Level\nhigh\n"
    result = evaluate_pr(_policy(), _pr(body), [], [], [], [])
    assert "pr_template_sections" not in result["failed_gates"]


def test_placeholder_detection_mixed_case():
    body = "### Subsystem\ntBd value\n### Risk Level\nhigh\n"
    result = evaluate_pr(_policy(), _pr(body), [], [], [], [])
    assert "pr_template_placeholders" in result["failed_gates"]
