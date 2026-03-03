import pytest
import yaml

from supervisor.pr_gate.kernel_policy import KernelPolicyError, load_kernel_policy_bundle


def test_load_kernel_policy_bundle_success():
    bundle = load_kernel_policy_bundle()
    assert "governance_policy" in bundle
    assert "checklist_policy" in bundle
    assert isinstance(bundle["governance_policy_sha"], str)
    assert isinstance(bundle["checklist_policy_sha"], str)


def test_load_kernel_policy_bundle_requires_fail_closed(tmp_path):
    checklist = {
        "version": "v0.1",
        "policy_id": "x",
        "fail_closed": False,
        "enforcement_order": ["governance_baseline_verification"],
        "governance_baseline": {"files": ["a.txt"]},
        "branch_rules": {"allowed_patterns": ["^feat/.+$"]},
        "required_metadata": ["intent_id"],
        "review": {"require_distinct_reviewer": True},
        "sensitive_paths": ["governance/"],
        "escalation": {"levels": {"L0": {"max_scope": ["docs/"]}}},
        "determinism": {"required_toolchain_fields": ["python_version"]},
        "ci": {"required_checks": ["lint"]},
        "mirror_integrity": {"enabled": True},
    }
    governance = {"schema_version": "autonomy-budget.v1"}
    checklist_path = tmp_path / "checklist.yaml"
    governance_path = tmp_path / "governance.yaml"
    checklist_path.write_text(yaml.safe_dump(checklist), encoding="utf-8")
    governance_path.write_text(yaml.safe_dump(governance), encoding="utf-8")

    with pytest.raises(KernelPolicyError):
        load_kernel_policy_bundle(
            governance_policy_path=str(governance_path),
            checklist_path=str(checklist_path),
        )


def test_load_kernel_policy_bundle_missing_required_key(tmp_path):
    checklist = {"version": "v0.1"}
    governance = {"schema_version": "autonomy-budget.v1"}
    checklist_path = tmp_path / "checklist.yaml"
    governance_path = tmp_path / "governance.yaml"
    checklist_path.write_text(yaml.safe_dump(checklist), encoding="utf-8")
    governance_path.write_text(yaml.safe_dump(governance), encoding="utf-8")

    with pytest.raises(KernelPolicyError):
        load_kernel_policy_bundle(
            governance_policy_path=str(governance_path),
            checklist_path=str(checklist_path),
        )
