from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {
            "feature_to_develop_only": True,
            "patterns": {
                "feature": {"regex": r"^feature/.+$"},
                "hotfix": {"regex": r"^hotfix/.+$"},
                "release": {"regex": r"^release/.+$"},
            },
        },
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}, "main": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_invalid_branch_pattern_fails():
    pr = {"number": 1, "title": "t", "body": "", "base": {"ref": "develop"}, "head": {"ref": "badbranch"}, "user": {"login": "a"}, "_open_prs": []}
    result = evaluate_pr(_policy(), pr, [], [], [], [])
    assert "branch_name_regex" in result["failed_gates"]


def test_feature_to_main_fails():
    pr = {"number": 1, "title": "t", "body": "", "base": {"ref": "main"}, "head": {"ref": "feature/ok"}, "user": {"login": "a"}, "_open_prs": []}
    result = evaluate_pr(_policy(), pr, [], [], [], [])
    assert "feature_to_develop_only" in result["failed_gates"]
