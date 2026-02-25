from supervisor.pr_gate.evaluator import evaluate_pr


def _policy():
    return {
        "targets": {"allowed_base_branches": ["develop"]},
        "branch_rules": {
            "feature_to_develop_only": False,
            "patterns": {"feature": {"regex": r"^feature/.+$"}},
        },
        "approvals": {
            "disallow_self_approval": False,
            "develop": {
                "min_approvals": 0,
                "require_distinct_reviewer": False,
                "require_human_approval": False,
                "require_supervisor_status": False,
            },
        },
        "issue_link": {"required": False, "patterns": []},
        "pr_template": {"required_sections": [], "reject_placeholders": [], "min_section_length": 0},
        "high_risk_paths": [],
        "locks": {"required_on_high_risk": False, "exclusive": True, "allowed": []},
        "ci": {"required": True, "required_checks": ["lint"]},
        "system_evolution": {"detect_paths": [], "ci": {"required_checks": []}, "approvals": {}},
        "commit_signing": {"required": True, "mode": "all_commits", "accepted_types": ["gpg"]},
    }


def _pr(base="develop"):
    return {
        "number": 1,
        "title": "x",
        "body": "",
        "base": {"ref": base},
        "head": {"ref": "feature/a"},
        "user": {"login": "author"},
        "_open_prs": [],
    }


def _signed_commit(sha="abc", sig_type="gpg"):
    return {
        "sha": sha,
        "signature_verifiable": True,
        "signature_verified": True,
        "signature_type": sig_type,
    }


def _reason(result, gate):
    for event in result["gate_events"]:
        if event["gate"] == gate:
            return event["reason"]
    raise AssertionError(f"gate not found: {gate}")


def test_allowed_base_branches_allow_and_deny_reason_codes():
    policy = _policy()
    allow = evaluate_pr(policy, _pr(base="develop"), [_signed_commit()], [], [], [{"context": "lint", "state": "success"}])
    assert "base_branch_allowed" not in allow["failed_gates"]
    assert _reason(allow, "base_branch_allowed") == "ALLOW_BASE_BRANCH_ALLOWED"

    deny = evaluate_pr(policy, _pr(base="release"), [_signed_commit()], [], [], [{"context": "lint", "state": "success"}])
    assert "base_branch_allowed" in deny["failed_gates"]
    assert _reason(deny, "base_branch_allowed") == "DENY_BASE_BRANCH_NOT_ALLOWED"


def test_ci_required_allow_and_deny_reason_codes():
    policy = _policy()
    policy["ci"]["required"] = False
    allow = evaluate_pr(policy, _pr(), [_signed_commit()], [], [], [])
    assert "required_status_checks" not in allow["failed_gates"]
    assert _reason(allow, "required_status_checks") == "ALLOW_CI_NOT_REQUIRED"

    policy = _policy()
    deny = evaluate_pr(policy, _pr(), [_signed_commit()], [], [], [])
    assert "required_status_checks" in deny["failed_gates"]
    assert _reason(deny, "required_status_checks") == "DENY_REQUIRED_STATUS_CHECKS"


def test_commit_signing_mode_allow_and_deny_reason_codes():
    policy = _policy()
    policy["commit_signing"]["mode"] = "merge_commit_only"
    allow_commits = [
        {"sha": "old", "signature_verifiable": False, "signature_verified": False, "signature_type": "gpg"},
        _signed_commit(sha="tip", sig_type="gpg"),
    ]
    allow = evaluate_pr(policy, _pr(), allow_commits, [], [], [{"context": "lint", "state": "success"}])
    assert "commit_signing_mode" not in allow["failed_gates"]
    assert _reason(allow, "commit_signing_mode") == "ALLOW_COMMIT_SIGNING_MODE_MERGE_COMMIT_ONLY"
    assert "commit_signing_required" not in allow["failed_gates"]
    assert allow["primary_failed_gate"] is None

    policy = _policy()
    deny = evaluate_pr(policy, _pr(), allow_commits, [], [], [{"context": "lint", "state": "success"}])
    assert "commit_signing_required" in deny["failed_gates"]
    assert deny["primary_failed_gate"] == "commit_signing_required"
    assert _reason(deny, "commit_signing_required") == "DENY_COMMIT_UNVERIFIABLE"


def test_commit_signing_accepted_types_allow_and_deny_reason_codes():
    policy = _policy()
    allow = evaluate_pr(policy, _pr(), [_signed_commit(sig_type="gpg")], [], [], [{"context": "lint", "state": "success"}])
    assert "commit_signing_accepted_types" not in allow["failed_gates"]
    assert _reason(allow, "commit_signing_accepted_types") == "ALLOW_COMMIT_SIGNING_TYPE_ACCEPTED"

    deny = evaluate_pr(policy, _pr(), [_signed_commit(sig_type="ssh")], [], [], [{"context": "lint", "state": "success"}])
    assert "commit_signing_accepted_types" in deny["failed_gates"]
    assert _reason(deny, "commit_signing_accepted_types") == "DENY_COMMIT_SIGNING_TYPE_UNACCEPTED"


def test_require_supervisor_status_allow_and_deny_reason_codes():
    policy = _policy()
    policy["approvals"]["develop"]["require_supervisor_status"] = True

    allow_statuses = [
        {"context": "lint", "state": "success"},
        {"context": "supervisor/status", "state": "success"},
    ]
    allow = evaluate_pr(policy, _pr(), [_signed_commit()], [], [], allow_statuses)
    assert "supervisor_status_required" not in allow["failed_gates"]
    assert _reason(allow, "supervisor_status_required") == "ALLOW_SUPERVISOR_STATUS_PRESENT"

    deny = evaluate_pr(policy, _pr(), [_signed_commit()], [], [], [{"context": "lint", "state": "success"}])
    assert "supervisor_status_required" in deny["failed_gates"]
    assert _reason(deny, "supervisor_status_required") == "DENY_SUPERVISOR_STATUS_REQUIRED"
