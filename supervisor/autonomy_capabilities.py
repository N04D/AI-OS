from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supervisor.capability_lifecycle import DENY_CAPABILITY_APPROVAL_INVALID
from supervisor.capability_lifecycle import DENY_CAPABILITY_NETWORK_REQUIRED
from supervisor.capability_lifecycle import DENY_CAPABILITY_SECRETS_MISSING
from supervisor.capability_lifecycle import DENY_CAPABILITY_TRANSITION_INVALID
from supervisor.capability_lifecycle import STATE_ACTIVE
from supervisor.capability_lifecycle import STATE_IMPLEMENTED_NOT_ACTIVE
from supervisor.capability_lifecycle import collect_activation_prerequisites

DEFAULT_CAPABILITY_LEDGER_PATH = Path("state/supervisor_capabilities.json")
DEFAULT_CAPABILITY_DENYLIST_PATH = Path("state/supervisor_capability_denies.json")
DEFAULT_POLICY_SHA_PATH = Path("docs/governance-policy-sha.txt")
DEFAULT_CAPABILITY_ACTIVATION_AUDIT_PATH = Path("logs/control/capability_activation.jsonl")
REQUEST_REVOKE_DIR = Path("requests/capabilities/revoke")
APPROVAL_REVOKE_DIR = Path("approvals/capabilities/revoke")


class CapabilityRevokeError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        message = reason_code if not detail else f"{reason_code}: {detail}"
        super().__init__(message)


class CapabilityActivationError(RuntimeError):
    def __init__(self, reason_code: str, detail: str | None = None) -> None:
        self.reason_code = reason_code
        self.detail = detail
        message = reason_code if not detail else f"{reason_code}: {detail}"
        super().__init__(message)


def _run_git(repo_root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git command failed").strip())
    return proc.stdout.strip()


def _commit(repo_root: Path, message: str) -> None:
    proc = subprocess.run(
        [
            "git",
            "-c",
            "user.name=aiosctl",
            "-c",
            "user.email=aiosctl@local",
            "commit",
            "-m",
            message,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git commit failed").strip())


def _utc_now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slugify_reason(text: str) -> str:
    lowered = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug or "reason"


def _read_policy_sha(repo_root: Path) -> str:
    policy_path = repo_root / DEFAULT_POLICY_SHA_PATH
    if policy_path.exists():
        value = policy_path.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "unknown"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def create_revoke_request(repo_root: Path, capability: str, justification: str) -> dict[str, Any]:
    cap = capability.strip()
    why = justification.strip()
    if not cap:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "capability is required")
    if len(why) < 20:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "justification must be at least 20 chars")

    revoke_id = str(uuid.uuid4())
    ts = _utc_now_iso8601()
    baseline_commit = _run_git(repo_root, ["rev-parse", "HEAD"])
    request_payload = {
        "baseline_commit": baseline_commit,
        "capability": cap,
        "justification": why,
        "policy_sha": _read_policy_sha(repo_root),
        "revoked_at": ts,
        "revoke_id": revoke_id,
        "status": "requested",
        "supervisor_id": "core",
    }

    filename_ts = ts.replace(":", "").replace("-", "")
    request_path = repo_root / REQUEST_REVOKE_DIR / f"{filename_ts}__{cap}__{_slugify_reason(why)}.json"
    _write_json(request_path, request_payload)

    _run_git(repo_root, ["add", str(request_path.relative_to(repo_root))])
    _commit(repo_root, f"chore(capabilities): request revoke {cap}")

    return {
        "status": "ok",
        "request_path": str(request_path),
        "revoke": request_payload,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", f"invalid json: {path}") from exc


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", f"invalid field: {key}")
    return value


def _validate_revoke_request(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "request must be object")

    out: dict[str, Any] = {
        "revoke_id": _require_str(payload, "revoke_id"),
        "supervisor_id": _require_str(payload, "supervisor_id"),
        "capability": _require_str(payload, "capability"),
        "revoked_at": _require_str(payload, "revoked_at"),
        "justification": _require_str(payload, "justification"),
        "baseline_commit": _require_str(payload, "baseline_commit"),
        "policy_sha": _require_str(payload, "policy_sha"),
        "status": _require_str(payload, "status"),
    }

    if out["supervisor_id"] != "core":
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "supervisor_id must be core")
    if out["status"] != "requested":
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "status must be requested")
    if len(out["justification"].strip()) < 20:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "justification must be at least 20 chars")
    try:
        uuid.UUID(out["revoke_id"])
    except ValueError as exc:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "revoke_id must be uuid4") from exc

    return out


def _validate_approval(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "approval must be object")

    out = {
        "revoke_id": _require_str(payload, "revoke_id"),
        "approved_by": _require_str(payload, "approved_by"),
        "approved_at": _require_str(payload, "approved_at"),
        "decision": _require_str(payload, "decision"),
        "signature_type": _require_str(payload, "signature_type"),
    }
    if out["decision"] != "approve":
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "decision must be approve")
    if out["signature_type"] not in {"human", "supervisor_status"}:
        raise CapabilityRevokeError(
            "DENY_CAPABILITY_REVOKE_INVALID",
            "signature_type must be human or supervisor_status",
        )
    return out


def _normalize_ledger_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, bool):
        return {"granted": entry}
    if not isinstance(entry, dict):
        return {"granted": False}

    normalized: dict[str, Any] = dict(entry)
    normalized["granted"] = bool(normalized.get("granted", False))
    return normalized


def load_capability_ledger(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "ledger must be object")

    ledger: dict[str, dict[str, Any]] = {}
    for capability in sorted(payload.keys()):
        ledger[str(capability)] = _normalize_ledger_entry(payload.get(capability))
    return ledger


def _load_denylist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "deny-list must be object")
    deny = payload.get("deny")
    if not isinstance(deny, list):
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "deny-list deny must be list")
    out: set[str] = set()
    for item in deny:
        if not isinstance(item, str) or not item.strip():
            raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_INVALID", "deny-list entry must be string")
        out.add(item)
    return out


def evaluate_capability_access(
    capability: str,
    *,
    ledger_path: Path = DEFAULT_CAPABILITY_LEDGER_PATH,
    denylist_path: Path = DEFAULT_CAPABILITY_DENYLIST_PATH,
) -> dict[str, Any]:
    denylist = _load_denylist(denylist_path)
    if capability in denylist:
        return {"allow": False, "reason_code": "DENY_CAPABILITY_EMERGENCY"}

    ledger = load_capability_ledger(ledger_path)
    entry = ledger.get(capability, {"granted": False})
    if bool(entry.get("granted", False)):
        return {"allow": True, "reason_code": None}
    return {"allow": False, "reason_code": "DENY_CAPABILITY_NOT_GRANTED"}


def apply_revoke_request(repo_root: Path, request_path: Path, approval_path: Path) -> dict[str, Any]:
    request_payload = _validate_revoke_request(_load_json(request_path))
    approval_payload = _validate_approval(_load_json(approval_path))

    if request_payload["revoke_id"] != approval_payload["revoke_id"]:
        raise CapabilityRevokeError("DENY_CAPABILITY_REVOKE_MISMATCH", "revoke_id mismatch")

    head_sha = _run_git(repo_root, ["rev-parse", "HEAD"])
    if request_payload["baseline_commit"] != head_sha:
        raise CapabilityRevokeError(
            "DENY_CAPABILITY_REVOKE_BASELINE_MISMATCH",
            f"expected {request_payload['baseline_commit']} got {head_sha}",
        )

    ledger_path = repo_root / DEFAULT_CAPABILITY_LEDGER_PATH
    ledger = load_capability_ledger(ledger_path)
    capability = request_payload["capability"]
    entry = ledger.get(capability, {"granted": False})

    entry["granted"] = False
    entry["revoked_at"] = request_payload["revoked_at"]
    entry["revoked_by"] = approval_payload["approved_by"]
    entry["source_revoke_id"] = request_payload["revoke_id"]

    ledger[capability] = entry
    _write_json(ledger_path, {k: ledger[k] for k in sorted(ledger.keys())})

    _run_git(repo_root, ["add", str(ledger_path.relative_to(repo_root)), str(approval_path.relative_to(repo_root))])
    _commit(repo_root, f"chore(capabilities): revoke {capability} via {request_payload['revoke_id']}")

    return {
        "status": "ok",
        "capability": capability,
        "revoke_id": request_payload["revoke_id"],
        "ledger_path": str(ledger_path),
    }


def activate_capability(
    repo_root: Path,
    capability: str,
    *,
    expected_approver: str = "Don",
    ledger_path: Path = DEFAULT_CAPABILITY_LEDGER_PATH,
    audit_path: Path = DEFAULT_CAPABILITY_ACTIVATION_AUDIT_PATH,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    cap = capability.strip()
    if not cap:
        raise CapabilityActivationError("DENY_CAPABILITY_ACTIVATION_INVALID", "capability is required")
    approver = expected_approver.strip()
    if not approver:
        raise CapabilityActivationError("DENY_CAPABILITY_ACTIVATION_INVALID", "expected approver is required")

    if _run_git(repo_root, ["status", "--porcelain"]).strip():
        raise CapabilityActivationError("DENY_DIRTY_WORKTREE", "working tree must be clean before activation")

    resolved_ledger_path = repo_root / ledger_path
    ledger = load_capability_ledger(resolved_ledger_path)
    if cap not in ledger:
        raise CapabilityActivationError("DENY_CAPABILITY_NOT_REGISTERED", f"unknown capability: {cap}")
    entry = dict(ledger[cap])
    if str(entry.get("state", "")).strip() != STATE_IMPLEMENTED_NOT_ACTIVE:
        raise CapabilityActivationError(
            DENY_CAPABILITY_TRANSITION_INVALID,
            f"activation requires state {STATE_IMPLEMENTED_NOT_ACTIVE}",
        )
    approved_by = str(entry.get("approved_by", "") or "").strip()
    if approved_by != approver:
        raise CapabilityActivationError(
            DENY_CAPABILITY_APPROVAL_INVALID,
            f"approved_by must be {approver}",
        )

    runtime_env = dict(os.environ) if env is None else dict(env)
    prereq = collect_activation_prerequisites(runtime_env, capability=cap)
    if prereq.missing_secrets:
        raise CapabilityActivationError(
            DENY_CAPABILITY_SECRETS_MISSING,
            ",".join(prereq.missing_secrets),
        )
    if not prereq.network_enabled:
        raise CapabilityActivationError(DENY_CAPABILITY_NETWORK_REQUIRED, "NETWORK_ACCESS_ENABLED must be true")

    updated_ledger = {key: dict(value) for key, value in ledger.items()}
    updated_entry = dict(updated_ledger[cap])
    timestamps = updated_entry.get("timestamps")
    if not isinstance(timestamps, dict):
        timestamps = {}
    timestamps[f"{STATE_IMPLEMENTED_NOT_ACTIVE}->{STATE_ACTIVE}"] = _utc_now_iso8601()
    updated_entry["timestamps"] = dict(sorted((str(key), str(value)) for key, value in timestamps.items()))
    updated_entry["state"] = STATE_ACTIVE
    updated_entry["granted"] = True
    updated_entry["activated_by"] = approver
    updated_ledger[cap] = updated_entry

    _write_json(resolved_ledger_path, {key: updated_ledger[key] for key in sorted(updated_ledger.keys())})
    audit_record = {
        "capability": cap,
        "activated_by": approver,
        "approved_by": approved_by,
        "issue": updated_entry.get("proposal_issue"),
        "state_after": STATE_ACTIVE,
        "ts_utc": _utc_now_iso8601(),
    }
    resolved_audit_path = repo_root / audit_path
    _append_jsonl(resolved_audit_path, audit_record)

    _run_git(
        repo_root,
        [
            "add",
            str(resolved_ledger_path.relative_to(repo_root)),
            str(resolved_audit_path.relative_to(repo_root)),
        ],
    )
    _commit(repo_root, f"chore(capabilities): activate {cap}")

    return {
        "status": "ok",
        "capability": cap,
        "state": STATE_ACTIVE,
        "granted": True,
        "activated_by": approver,
        "ledger_path": str(resolved_ledger_path.relative_to(repo_root)),
        "audit_path": str(resolved_audit_path.relative_to(repo_root)),
    }
