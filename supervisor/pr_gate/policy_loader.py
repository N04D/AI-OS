import hashlib
from pathlib import Path

import yaml

from supervisor.pr_gate.logger import log_event


class PolicyLoadError(Exception):
    pass


REQUIRED_KEYS = {
    "version",
    "branch_rules",
    "approvals",
    "high_risk_paths",
    "commit_signing",
    "ci",
}


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

    policy_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    log_event(
        "policy_loader",
        f"loaded path={path} top_keys={','.join(sorted(policy.keys()))} policy_hash={policy_hash}",
    )
    return policy, policy_hash
