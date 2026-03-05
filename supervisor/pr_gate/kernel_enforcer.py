from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


class KernelEnforcementError(Exception):
    pass


def _canonical_json_sha(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


class KernelEnforcer:
    """
    Deterministic PR gate for constitutional kernel checks.

    Input `ctx` keys used by the checks:
    - head_branch: str
    - pr_author: str
    - pr_body: str
    - pr_metadata: dict[str, object]
    - changed_files: list[str]
    - reviews: list[dict]
    - ci_statuses: list[dict]
    - escalation_level: str (L0..L3)
    - owner_approved: bool
    - toolchain: dict[str, str]
    - mirror: dict[str, str] with canonical_main_sha + mirror_main_sha
    - governance_baseline_hash: str (expected)
    """

    def __init__(self, checklist_policy: dict):
        self.policy = checklist_policy

    def _record(self, events: list[dict], failed: list[str], gate: str, ok: bool, reason: str) -> None:
        events.append({"gate": gate, "result": "PASS" if ok else "FAIL", "reason": reason})
        if not ok:
            failed.append(gate)

    def _compute_governance_baseline_hash(self) -> tuple[str | None, list[str]]:
        files = ((self.policy.get("governance_baseline") or {}).get("files") or [])
        missing: list[str] = []
        digests: list[tuple[str, str]] = []
        for rel in files:
            p = Path(rel)
            if not p.exists():
                missing.append(rel)
                continue
            body = p.read_bytes()
            digests.append((rel, hashlib.sha256(body).hexdigest()))
        if missing:
            return None, missing
        return _canonical_json_sha({"files": digests}), []

    def _extract_metadata_from_text(self, text: str) -> dict:
        out: dict[str, str] = {}
        for line in (text or "").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            k = key.strip().lower()
            if not k:
                continue
            out[k] = value.strip()
        return out

    def evaluate(self, ctx: dict) -> dict:
        events: list[dict] = []
        failed: list[str] = []

        order = list(self.policy.get("enforcement_order") or [])
        if not order:
            raise KernelEnforcementError("Checklist enforcement_order missing")

        # 1) Governance Baseline Verification
        baseline_actual, baseline_missing = self._compute_governance_baseline_hash()
        expected_baseline = str(ctx.get("governance_baseline_hash", "")).strip()
        if baseline_missing:
            self._record(
                events,
                failed,
                "governance_baseline_verification",
                False,
                f"SYSTEM_HALT:GOVERNANCE_BASELINE_FILE_MISSING:{','.join(sorted(baseline_missing))}",
            )
        elif not expected_baseline:
            self._record(
                events,
                failed,
                "governance_baseline_verification",
                False,
                "DENY_GOVERNANCE_BASELINE_EXPECTED_HASH_MISSING",
            )
        else:
            ok = baseline_actual == expected_baseline
            reason = "ALLOW_GOVERNANCE_BASELINE_MATCH" if ok else "SYSTEM_HALT:GOVERNANCE_HASH_MISMATCH"
            self._record(events, failed, "governance_baseline_verification", ok, reason)

        # 2) Branch Pattern Validation
        head_branch = str(ctx.get("head_branch", "")).strip()
        allowed_patterns = ((self.policy.get("branch_rules") or {}).get("allowed_patterns") or [])
        branch_ok = any(re.match(pattern, head_branch) for pattern in allowed_patterns)
        self._record(
            events,
            failed,
            "branch_pattern_validation",
            branch_ok,
            "ALLOW_BRANCH_PATTERN_MATCH" if branch_ok else "FAIL_BRANCH_PATTERN",
        )

        # 3) Metadata Completeness Check
        metadata = dict(ctx.get("pr_metadata") or {})
        if not metadata:
            metadata = self._extract_metadata_from_text(str(ctx.get("pr_body", "")))
        required_metadata = list(self.policy.get("required_metadata") or [])
        missing_metadata = [field for field in required_metadata if not str(metadata.get(field, "")).strip()]
        metadata_ok = not missing_metadata
        self._record(
            events,
            failed,
            "metadata_completeness_check",
            metadata_ok,
            "ALLOW_METADATA_COMPLETE" if metadata_ok else f"FAIL_METADATA_INCOMPLETE:{','.join(missing_metadata)}",
        )

        # 4) Distinct Reviewer Verification
        require_distinct = bool(((self.policy.get("review") or {}).get("require_distinct_reviewer")))
        pr_author = str(ctx.get("pr_author", "")).strip()
        reviews = list(ctx.get("reviews") or [])
        approvers = sorted(
            {
                str((review.get("user") or {}).get("login", "")).strip()
                for review in reviews
                if str(review.get("state", "")).upper() == "APPROVED"
                and str((review.get("user") or {}).get("login", "")).strip()
            }
        )
        distinct_approvers = [name for name in approvers if name != pr_author]
        reviewer_ok = (not require_distinct) or bool(distinct_approvers)
        self._record(
            events,
            failed,
            "distinct_reviewer_verification",
            reviewer_ok,
            "ALLOW_DISTINCT_REVIEWER_PRESENT" if reviewer_ok else "FAIL_DISTINCT_REVIEW_REQUIRED",
        )

        # 5) Sensitive Path Detection
        changed_files = sorted(str(path) for path in (ctx.get("changed_files") or []))
        sensitive_prefixes = list(self.policy.get("sensitive_paths") or [])
        sensitive_touched = sorted(
            path for path in changed_files if any(path.startswith(prefix) for prefix in sensitive_prefixes)
        )
        self._record(
            events,
            failed,
            "sensitive_path_detection",
            True,
            "ALLOW_NO_SENSITIVE_PATHS"
            if not sensitive_touched
            else f"SENSITIVE_PATHS_TOUCHED:{','.join(sensitive_touched)}",
        )

        # 6) Escalation Level Validation
        declared_level = str(ctx.get("escalation_level", "")).upper().strip()
        levels_cfg = ((self.policy.get("escalation") or {}).get("levels") or {})
        sensitive_min_level = str(((self.policy.get("escalation") or {}).get("sensitive_path_min_level") or "L3")).upper()
        level_rank = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
        valid_level = declared_level in level_rank and declared_level in levels_cfg
        if not valid_level:
            escalation_ok = False
            escalation_reason = "FAIL_ESCALATION_MISMATCH:invalid_level"
        else:
            required_level = "L0"
            if sensitive_touched:
                required_level = sensitive_min_level
            escalation_ok = level_rank[declared_level] >= level_rank.get(required_level, 99)
            if escalation_ok:
                require_owner = bool((levels_cfg.get(declared_level) or {}).get("require_owner_approval", False))
                owner_approved = bool(ctx.get("owner_approved", False))
                if require_owner and not owner_approved:
                    escalation_ok = False
                    escalation_reason = "FAIL_ESCALATION_REQUIRED:owner_approval_missing"
                else:
                    escalation_reason = "ALLOW_ESCALATION_LEVEL_VALID"
            else:
                escalation_reason = f"FAIL_ESCALATION_MISMATCH:required={required_level}:declared={declared_level}"
        self._record(events, failed, "escalation_level_validation", escalation_ok, escalation_reason)

        # 7) Deterministic Toolchain Verification
        toolchain = dict(ctx.get("toolchain") or {})
        det_cfg = self.policy.get("determinism") or {}
        required_toolchain_fields = list(det_cfg.get("required_toolchain_fields") or [])
        missing_toolchain = [field for field in required_toolchain_fields if not str(toolchain.get(field, "")).strip()]
        require_container_digest = bool(det_cfg.get("require_container_digest", False))
        if require_container_digest and not str(toolchain.get("container_digest", "")).strip():
            missing_toolchain.append("container_digest")
        toolchain_ok = not missing_toolchain
        self._record(
            events,
            failed,
            "deterministic_toolchain_verification",
            toolchain_ok,
            "ALLOW_TOOLCHAIN_DETERMINISTIC"
            if toolchain_ok
            else f"SYSTEM_HALT:TOOLCHAIN_NON_DETERMINISM:{','.join(sorted(set(missing_toolchain)))}",
        )

        # 8) CI Status Verification
        required_checks = list((self.policy.get("ci") or {}).get("required_checks") or [])
        observed_statuses = {
            str(item.get("context", "")).strip(): str(item.get("state", "")).strip().lower()
            for item in list(ctx.get("ci_statuses") or [])
            if str(item.get("context", "")).strip()
        }
        missing_or_failed_checks = [
            name for name in required_checks if observed_statuses.get(name) != "success"
        ]
        ci_ok = not missing_or_failed_checks
        self._record(
            events,
            failed,
            "ci_status_verification",
            ci_ok,
            "ALLOW_CI_VALIDATION" if ci_ok else f"FAIL_CI_VALIDATION:{','.join(missing_or_failed_checks)}",
        )

        # 9) Mirror Integrity Check
        mirror_cfg = self.policy.get("mirror_integrity") or {}
        mirror_enabled = bool(mirror_cfg.get("enabled", True))
        mirror = dict(ctx.get("mirror") or {})
        canonical_sha = str(mirror.get("canonical_main_sha", "")).strip()
        mirror_sha = str(mirror.get("mirror_main_sha", "")).strip()
        if not mirror_enabled:
            mirror_ok = True
            mirror_reason = "ALLOW_MIRROR_CHECK_DISABLED"
        elif not canonical_sha or not mirror_sha:
            mirror_ok = False
            mirror_reason = "FAIL_MIRROR_INTEGRITY_DATA_MISSING"
        else:
            mirror_ok = canonical_sha == mirror_sha
            mirror_reason = (
                "ALLOW_MIRROR_INTEGRITY"
                if mirror_ok
                else "SYSTEM_ALERT:MIRROR_DRIFT_DETECTED"
            )
        self._record(events, failed, "mirror_integrity_check", mirror_ok, mirror_reason)

        # 10) Final Merge Authorization
        hard_halt = any(event["reason"].startswith("SYSTEM_HALT:") for event in events)
        final_ok = not failed and not hard_halt
        self._record(
            events,
            failed,
            "final_merge_authorization",
            final_ok,
            "ALLOW_MERGE_AUTHORIZED" if final_ok else "FAIL_MERGE_INVARIANT",
        )

        # Keep output deterministic in configured check order.
        by_gate = {event["gate"]: event for event in events}
        ordered_events = [by_gate[gate] for gate in order if gate in by_gate]
        for gate, event in by_gate.items():
            if gate not in order:
                ordered_events.append(event)

        failed_unique = sorted(set(failed))
        return {
            "passed": len(failed_unique) == 0,
            "failed_gates": failed_unique,
            "halted": any(event["reason"].startswith("SYSTEM_HALT:") for event in ordered_events),
            "gate_events": ordered_events,
        }
