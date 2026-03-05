import hashlib
import json
from pathlib import Path

from supervisor.pr_gate.kernel_enforcer import KernelEnforcer
from supervisor.pr_gate.kernel_policy import load_kernel_policy_bundle


def _baseline_hash(checklist_policy: dict) -> str:
    pairs = []
    for rel in checklist_policy["governance_baseline"]["files"]:
        body = Path(rel).read_bytes()
        pairs.append((rel, hashlib.sha256(body).hexdigest()))
    raw = json.dumps({"files": pairs}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _base_ctx(policy: dict) -> dict:
    return {
        "head_branch": "feat/kernel-enforcement",
        "pr_author": "codex",
        "pr_body": "",
        "pr_metadata": {
            "intent_id": "I-100",
            "issue_reference": "#65",
            "risk_level": "L3",
            "touched_paths": "supervisor/pr_gate/kernel_enforcer.py",
            "rollback_strategy": "revert commit",
            "determinism_proof": "pytest -q",
        },
        "changed_files": ["supervisor/pr_gate/kernel_enforcer.py"],
        "reviews": [{"state": "APPROVED", "user": {"login": "reviewer"}}],
        "ci_statuses": [
            {"context": "lint", "state": "success"},
            {"context": "unit-tests", "state": "success"},
            {"context": "smoke-test", "state": "success"},
        ],
        "escalation_level": "L3",
        "owner_approved": True,
        "toolchain": {
            "python_version": "3.11.9",
            "dependency_lock_sha": "abc123",
            "ci_runtime_fingerprint": "runner:v1",
        },
        "mirror": {
            "canonical_main_sha": "abc",
            "mirror_main_sha": "abc",
        },
        "governance_baseline_hash": _baseline_hash(policy),
    }


def _result_reason(result: dict, gate: str) -> str:
    for event in result["gate_events"]:
        if event["gate"] == gate:
            return str(event["reason"])
    raise AssertionError(f"Missing gate in result: {gate}")


def test_kernel_enforcer_allows_valid_context():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    result = enforcer.evaluate(_base_ctx(policy))
    assert result["passed"] is True
    assert result["failed_gates"] == []
    assert _result_reason(result, "final_merge_authorization") == "ALLOW_MERGE_AUTHORIZED"


def test_kernel_enforcer_fails_branch_pattern():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["head_branch"] = "invalid/branch"
    result = enforcer.evaluate(ctx)
    assert "branch_pattern_validation" in result["failed_gates"]
    assert _result_reason(result, "branch_pattern_validation") == "FAIL_BRANCH_PATTERN"


def test_kernel_enforcer_fails_metadata_completeness():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["pr_metadata"].pop("rollback_strategy")
    result = enforcer.evaluate(ctx)
    assert "metadata_completeness_check" in result["failed_gates"]
    assert _result_reason(result, "metadata_completeness_check").startswith("FAIL_METADATA_INCOMPLETE")


def test_kernel_enforcer_fails_distinct_reviewer():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["reviews"] = [{"state": "APPROVED", "user": {"login": "codex"}}]
    result = enforcer.evaluate(ctx)
    assert "distinct_reviewer_verification" in result["failed_gates"]
    assert _result_reason(result, "distinct_reviewer_verification") == "FAIL_DISTINCT_REVIEW_REQUIRED"


def test_kernel_enforcer_fails_escalation_for_sensitive_paths():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["escalation_level"] = "L1"
    result = enforcer.evaluate(ctx)
    assert "escalation_level_validation" in result["failed_gates"]
    assert _result_reason(result, "escalation_level_validation").startswith("FAIL_ESCALATION_MISMATCH")


def test_kernel_enforcer_halts_on_toolchain_missing():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["toolchain"] = {"python_version": "3.11"}
    result = enforcer.evaluate(ctx)
    assert result["halted"] is True
    assert "deterministic_toolchain_verification" in result["failed_gates"]
    assert _result_reason(result, "deterministic_toolchain_verification").startswith("SYSTEM_HALT:TOOLCHAIN_NON_DETERMINISM")


def test_kernel_enforcer_fails_ci_status_checks():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["ci_statuses"] = [{"context": "lint", "state": "success"}]
    result = enforcer.evaluate(ctx)
    assert "ci_status_verification" in result["failed_gates"]
    assert _result_reason(result, "ci_status_verification").startswith("FAIL_CI_VALIDATION")


def test_kernel_enforcer_fails_mirror_drift():
    bundle = load_kernel_policy_bundle()
    policy = bundle["checklist_policy"]
    enforcer = KernelEnforcer(policy)
    ctx = _base_ctx(policy)
    ctx["mirror"] = {"canonical_main_sha": "abc", "mirror_main_sha": "def"}
    result = enforcer.evaluate(ctx)
    assert "mirror_integrity_check" in result["failed_gates"]
    assert _result_reason(result, "mirror_integrity_check") == "SYSTEM_ALERT:MIRROR_DRIFT_DETECTED"
