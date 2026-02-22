from supervisor.pr_gate.evaluator import evaluate_pr


def _base_policy():
    return {
        "branch_rules": {
            "feature_to_develop_only": True,
            "patterns": {
                "feature": {"regex": r"^feature/.+$"},
                "hotfix": {"regex": r"^hotfix/.+$"},
            },
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


def _pr(base="develop", head="feature/x", title="change #1", body=None):
    if body is None:
        body = "### Subsystem\ncore\n### Risk Level\nhigh\n"
    return {
        "number": 1,
        "title": title,
        "body": body,
        "base": {"ref": base},
        "head": {"ref": head},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def _ok_reviews():
    return [
        {"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "reviewer1", "type": "User"}},
        {"state": "APPROVED", "submitted_at": "2026-01-01T01:00:00Z", "user": {"login": "reviewer2", "type": "User"}},
    ]


def _ok_statuses(system=False):
    statuses = [
        {"context": "lint", "state": "success"},
        {"context": "unit-tests", "state": "success"},
    ]
    if system:
        statuses.append({"context": "determinism-check", "state": "success"})
    return statuses


def _ok_commits():
    return [{"sha": "abc", "signature_verifiable": True, "signature_verified": True}]


def test_pass_path_core_gates():
    pr = _pr()
    result = evaluate_pr(_base_policy(), pr, _ok_commits(), [], _ok_reviews(), _ok_statuses(system=False))
    assert "branch_name_regex" not in result["failed_gates"]
    assert "feature_to_develop_only" not in result["failed_gates"]
    assert "issue_reference_required" not in result["failed_gates"]
    assert "pr_template_sections" not in result["failed_gates"]
    assert "pr_template_placeholders" not in result["failed_gates"]
    assert "required_status_checks" not in result["failed_gates"]
    assert "min_approvals_met" not in result["failed_gates"]
    assert "distinct_reviewer_required" not in result["failed_gates"]
    assert "human_approval_required" not in result["failed_gates"]
    assert "commit_signing_required" not in result["failed_gates"]


def test_fail_branch_and_feature_to_develop():
    result = evaluate_pr(
        _base_policy(),
        _pr(base="main", head="badbranch"),
        _ok_commits(),
        [],
        _ok_reviews(),
        _ok_statuses(),
    )
    assert "branch_name_regex" in result["failed_gates"]
    assert "feature_to_develop_only" not in result["failed_gates"]
    assert any("head_branch=badbranch" in r for r in result["failed_reasons"])


def test_fail_template_placeholder_and_issue_ref():
    pr = _pr(title="change", body="### Subsystem\nTBD\n### Risk Level\nok\n")
    result = evaluate_pr(_base_policy(), pr, _ok_commits(), [], _ok_reviews(), _ok_statuses())
    assert "issue_reference_required" in result["failed_gates"]
    assert "pr_template_placeholders" in result["failed_gates"]


def test_high_risk_detection_never_blocks_but_lock_required_blocks():
    pr = _pr(title="change #1")
    result = evaluate_pr(_base_policy(), pr, _ok_commits(), ["supervisor/supervisor.py"], _ok_reviews(), _ok_statuses(system=True))
    assert "high_risk_path_detection" not in result["failed_gates"]
    assert "lock_required" in result["failed_gates"]


def test_lock_exclusive_conflict_blocks():
    pr = _pr(title="change #1", body="### Subsystem\ncore\n### Risk Level\nhigh\nLOCK:supervisor/")
    pr["_open_prs"] = [{"number": 2, "title": "x", "body": "LOCK:supervisor/"}]
    result = evaluate_pr(_base_policy(), pr, _ok_commits(), ["supervisor/supervisor.py"], _ok_reviews(), _ok_statuses(system=True))
    assert "lock_exclusive" in result["failed_gates"]


def test_system_evolution_pass_and_fail_modes():
    policy = _base_policy()
    pr = _pr(title="change #1", body="### Subsystem\ncore\n### Risk Level\nhigh\nLOCK:supervisor/")
    pass_result = evaluate_pr(policy, pr, _ok_commits(), ["supervisor/supervisor.py"], _ok_reviews(), _ok_statuses(system=True))
    assert "system_evolution_escalation" not in pass_result["failed_gates"]

    fail_reviews = [{"state": "APPROVED", "submitted_at": "2026-01-01T00:00:00Z", "user": {"login": "bot1", "type": "Bot"}}]
    fail_statuses = [{"context": "lint", "state": "success"}]
    fail_result = evaluate_pr(policy, pr, _ok_commits(), ["supervisor/supervisor.py"], fail_reviews, fail_statuses)
    assert "system_evolution_escalation" in fail_result["failed_gates"]
    assert any("required_status_checks=False" in r for r in fail_result["failed_reasons"])


def test_commit_signing_required_pass_and_fail():
    pr = _pr()
    pass_result = evaluate_pr(_base_policy(), pr, _ok_commits(), [], _ok_reviews(), _ok_statuses())
    assert "commit_signing_required" not in pass_result["failed_gates"]

    fail_result = evaluate_pr(
        _base_policy(),
        pr,
        [{"sha": "abc", "signature_verifiable": False, "signature_verified": False}],
        [],
        _ok_reviews(),
        _ok_statuses(),
    )
    assert "commit_signing_required" in fail_result["failed_gates"]
