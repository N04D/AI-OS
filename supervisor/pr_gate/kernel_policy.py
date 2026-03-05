from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


class KernelPolicyError(Exception):
    pass


_REQUIRED_CHECKLIST_KEYS = {
    "version",
    "policy_id",
    "fail_closed",
    "enforcement_order",
    "governance_baseline",
    "branch_rules",
    "required_metadata",
    "review",
    "sensitive_paths",
    "escalation",
    "determinism",
    "ci",
    "mirror_integrity",
}


def _read_yaml(path: str) -> tuple[dict, str]:
    src = Path(path).read_text(encoding="utf-8")
    parsed = yaml.safe_load(src)
    if not isinstance(parsed, dict):
        raise KernelPolicyError(f"YAML root must be a mapping: {path}")
    return parsed, hashlib.sha256(src.encode("utf-8")).hexdigest()


def _ensure_list_of_str(value, path: str, min_len: int = 0) -> list[str]:
    if not isinstance(value, list):
        raise KernelPolicyError(f"Field must be a list: {path}")
    out: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise KernelPolicyError(f"Field must be non-empty string: {path}[{idx}]")
        out.append(item.strip())
    if len(out) < min_len:
        raise KernelPolicyError(f"Field must contain at least {min_len} item(s): {path}")
    return out


def load_kernel_policy_bundle(
    governance_policy_path: str = "governance_policy.yaml",
    checklist_path: str = "governance/policy/kernel-enforcement-checklist.v0.1.yaml",
) -> dict:
    governance_policy, governance_policy_sha = _read_yaml(governance_policy_path)
    checklist, checklist_sha = _read_yaml(checklist_path)

    missing = sorted(_REQUIRED_CHECKLIST_KEYS - set(checklist.keys()))
    if missing:
        raise KernelPolicyError(f"Checklist missing required keys: {', '.join(missing)}")

    if checklist.get("fail_closed") is not True:
        raise KernelPolicyError("Checklist must be fail-closed (fail_closed=true)")

    _ensure_list_of_str(checklist.get("enforcement_order"), "enforcement_order", min_len=1)
    baseline = checklist.get("governance_baseline")
    if not isinstance(baseline, dict):
        raise KernelPolicyError("governance_baseline must be a mapping")
    _ensure_list_of_str(baseline.get("files"), "governance_baseline.files", min_len=1)

    branch_rules = checklist.get("branch_rules")
    if not isinstance(branch_rules, dict):
        raise KernelPolicyError("branch_rules must be a mapping")
    _ensure_list_of_str(branch_rules.get("allowed_patterns"), "branch_rules.allowed_patterns", min_len=1)

    _ensure_list_of_str(checklist.get("required_metadata"), "required_metadata", min_len=1)
    _ensure_list_of_str(checklist.get("sensitive_paths"), "sensitive_paths", min_len=1)

    review = checklist.get("review")
    if not isinstance(review, dict) or not isinstance(review.get("require_distinct_reviewer"), bool):
        raise KernelPolicyError("review.require_distinct_reviewer must be a boolean")

    escalation = checklist.get("escalation")
    if not isinstance(escalation, dict) or not isinstance(escalation.get("levels"), dict):
        raise KernelPolicyError("escalation.levels must be a mapping")

    determinism = checklist.get("determinism")
    if not isinstance(determinism, dict):
        raise KernelPolicyError("determinism must be a mapping")
    _ensure_list_of_str(
        determinism.get("required_toolchain_fields"),
        "determinism.required_toolchain_fields",
        min_len=1,
    )

    ci = checklist.get("ci")
    if not isinstance(ci, dict):
        raise KernelPolicyError("ci must be a mapping")
    _ensure_list_of_str(ci.get("required_checks"), "ci.required_checks", min_len=1)

    mirror = checklist.get("mirror_integrity")
    if not isinstance(mirror, dict):
        raise KernelPolicyError("mirror_integrity must be a mapping")
    if not isinstance(mirror.get("enabled"), bool):
        raise KernelPolicyError("mirror_integrity.enabled must be a boolean")

    return {
        "governance_policy": governance_policy,
        "governance_policy_sha": governance_policy_sha,
        "checklist_policy": checklist,
        "checklist_policy_sha": checklist_sha,
    }
