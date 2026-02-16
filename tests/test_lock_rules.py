from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {"patterns": {"feature": {"regex": r"^feature/.+$"}}},
        "approvals": {"disallow_self_approval": False, "develop": {"min_approvals": 0}},
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": ["supervisor/"],
        "locks": {
            "required_on_high_risk": True,
            "exclusive": True,
            "allowed": ["LOCK:supervisor/"],
        },
        "ci": {"required_checks": []},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": False},
    }


def test_lock_required_for_high_risk_path():
    pr = {"number": 1, "title": "feature", "body": "", "base": {"ref": "develop"}, "head": {"ref": "feature/ok"}, "user": {"login": "a"}, "_open_prs": []}
    result = evaluate_pr(_policy(), pr, [], ["supervisor/supervisor.py"], [], [])
    assert "lock_required" in result["failed_gates"]


def test_lock_conflict_detected():
    pr = {
        "number": 1,
        "title": "feature",
        "body": "LOCK:supervisor/",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/ok"},
        "user": {"login": "a"},
        "_open_prs": [{"number": 2, "title": "x", "body": "LOCK:supervisor/"}],
    }
    result = evaluate_pr(_policy(), pr, [], ["supervisor/supervisor.py"], [], [])
    assert "lock_exclusive" in result["failed_gates"]
