import hashlib
from pathlib import Path

import yaml

from supervisor.pr_gate.logger import log_event


class PolicyLoadError(Exception):
    pass


REQUIRED_KEYS = {
    "version",
    "targets",
    "branch_rules",
    "approvals",
    "high_risk_paths",
    "commit_signing",
    "ci",
}

ALLOWED_COMMIT_SIGNING_MODES = {"all_commits", "merge_commit_only"}
ALLOWED_COMMIT_SIGNING_TYPES = {"gpg", "ssh"}
INFORMATIONAL_ONLY_FIELD_PATHS = (
    "policy_id",
    "mode",
    "fail_closed",
    "risk.allowed",
    "risk.high_risk_minimum",
    "locks.token_prefix",
    "locks.lock_release",
    "ci.allow_manual_evidence",
    "system_evolution.label",
    "targets.protected_branches",
)


def _require_mapping(value, path):
    if not isinstance(value, dict):
        raise PolicyLoadError(f"Policy field '{path}' must be a mapping")
    return value


def _require_bool(value, path):
    if not isinstance(value, bool):
        raise PolicyLoadError(f"Policy field '{path}' must be a boolean")
    return value


def _require_str(value, path):
    if not isinstance(value, str) or not value.strip():
        raise PolicyLoadError(f"Policy field '{path}' must be a non-empty string")
    return value


def _require_list_of_strings(value, path, *, min_items=0):
    if not isinstance(value, list):
        raise PolicyLoadError(f"Policy field '{path}' must be a list")
    if len(value) < min_items:
        raise PolicyLoadError(f"Policy field '{path}' must contain at least {min_items} item(s)")
    parsed = []
    for idx, item in enumerate(value):
        parsed.append(_require_str(item, f"{path}[{idx}]"))
    return parsed


def _require_key(mapping, key, path):
    if key not in mapping:
        raise PolicyLoadError(f"Policy missing required field '{path}.{key}'")
    return mapping[key]


def _validate_enforced_fields(policy):
    targets = _require_mapping(policy.get("targets"), "targets")
    _require_list_of_strings(
        _require_key(targets, "allowed_base_branches", "targets"),
        "targets.allowed_base_branches",
        min_items=1,
    )

    ci = _require_mapping(policy.get("ci"), "ci")
    _require_bool(_require_key(ci, "required", "ci"), "ci.required")
    _require_list_of_strings(
        _require_key(ci, "required_checks", "ci"),
        "ci.required_checks",
    )

    signing = _require_mapping(policy.get("commit_signing"), "commit_signing")
    _require_bool(_require_key(signing, "required", "commit_signing"), "commit_signing.required")
    mode = _require_str(_require_key(signing, "mode", "commit_signing"), "commit_signing.mode")
    if mode not in ALLOWED_COMMIT_SIGNING_MODES:
        raise PolicyLoadError(
            "Policy field 'commit_signing.mode' must be one of: "
            + ", ".join(sorted(ALLOWED_COMMIT_SIGNING_MODES))
        )
    accepted_types = _require_list_of_strings(
        _require_key(signing, "accepted_types", "commit_signing"),
        "commit_signing.accepted_types",
        min_items=1,
    )
    unknown_types = sorted({item for item in accepted_types if item not in ALLOWED_COMMIT_SIGNING_TYPES})
    if unknown_types:
        raise PolicyLoadError(
            "Policy field 'commit_signing.accepted_types' contains unsupported value(s): "
            + ", ".join(unknown_types)
        )

    approvals = _require_mapping(policy.get("approvals"), "approvals")
    for branch, cfg in approvals.items():
        if branch == "disallow_self_approval":
            continue
        branch_cfg = _require_mapping(cfg, f"approvals.{branch}")
        _require_bool(
            _require_key(branch_cfg, "require_supervisor_status", f"approvals.{branch}"),
            f"approvals.{branch}.require_supervisor_status",
        )


def _present_field_paths(policy):
    present = []
    for path in INFORMATIONAL_ONLY_FIELD_PATHS:
        current = policy
        found = True
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found:
            present.append(path)
    return present


def load_policy(policy_path="governance/policy/pr-governance.v0.2.yaml"):
    path = Path(policy_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        log_event("policy_loader", f"load_failed path={path} error={exc}")
        raise PolicyLoadError(f"Failed to read policy: {exc}") from exc

    try:
        policy = yaml.safe_load(raw)
    except Exception as exc:
        log_event("policy_loader", f"parse_failed path={path} error={exc}")
        raise PolicyLoadError(f"Failed to parse policy YAML: {exc}") from exc

    if not isinstance(policy, dict):
        log_event("policy_loader", f"invalid_mapping path={path}")
        raise PolicyLoadError("Policy YAML must be a mapping")

    missing = sorted(REQUIRED_KEYS - set(policy.keys()))
    if missing:
        log_event("policy_loader", f"missing_keys path={path} missing={','.join(missing)}")
        raise PolicyLoadError(f"Policy missing required keys: {', '.join(missing)}")
    _validate_enforced_fields(policy)
    informational = _present_field_paths(policy)
    if informational:
        log_event(
            "policy_loader",
            "informational_only_fields="
            + ",".join(sorted(informational)),
        )

    policy_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    log_event(
        "policy_loader",
        f"loaded path={path} top_keys={','.join(sorted(policy.keys()))} policy_hash={policy_hash}",
    )
    return policy, policy_hash
