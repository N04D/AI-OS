from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "branch_rules": {
            "feature_to_develop_only": True,
            "patterns": {"feature": {"regex": r"^feature/.+$"}},
        },
        "approvals": {
            "disallow_self_approval": True,
            "develop": {
                "min_approvals": 1,
                "require_distinct_reviewer": True,
                "require_human_approval": False,
            },
        },
        "issue_link": {"required": True, "patterns": [r"(^|\\s)#([0-9]+)(\\s|$)"]},
        "pr_template": {
            "required_sections": ["Subsystem", "Risk Level"],
            "reject_placeholders": ["TBD", "TODO", "N/A"],
            "min_section_length": 3,
        },
        "high_risk_paths": ["supervisor/"],
        "locks": {
            "required_on_high_risk": True,
            "exclusive": True,
            "allowed": ["LOCK:supervisor/"],
        },
        "ci": {"required_checks": ["lint", "unit-tests"]},
        "system_evolution": {
            "detect_paths": ["supervisor/"],
            "approvals": {"min_approvals": 2, "require_human_approval": True},
            "ci": {"required_checks": ["lint", "unit-tests", "determinism-check"]},
        },
        "commit_signing": {"required": True},
    }


def _inputs():
    pr = {
        "number": 1,
        "title": "change #12",
        "body": "### Subsystem\ncore\n### Risk Level\nhigh\nLOCK:supervisor/",
        "base": {"ref": "develop"},
        "head": {"ref": "feature/deterministic"},
        "user": {"login": "author"},
        "_open_prs": [],
    }
    commits = [{"sha": "abc", "signature_verifiable": True, "signature_verified": True}]
    files = ["supervisor/supervisor.py"]
    reviews = [
        {"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "rev1", "type": "User"}},
        {"state": "APPROVED", "submitted_at": "2026-01-01T01:00:00Z", "user": {"login": "rev2", "type": "User"}},
    ]
    statuses = [
        {"context": "lint", "state": "success"},
        {"context": "unit-tests", "state": "success"},
        {"context": "determinism-check", "state": "success"},
    ]
    return pr, commits, files, reviews, statuses


def test_determinism_invariants():
    policy = _policy()
    pr, commits, files, reviews, statuses = _inputs()

    result1 = evaluate_pr(policy, pr, commits, files, reviews, statuses)
    result2 = evaluate_pr(policy, pr, commits, files, reviews, statuses)

    assert result1 == result2
    assert result1["failed_gates"] == sorted(result1["failed_gates"])
    assert all(isinstance(x, str) for x in result1["failed_reasons"])

    gate_order = [e["gate"] for e in result1["gate_events"]]
    assert gate_order == [e["gate"] for e in result2["gate_events"]]
