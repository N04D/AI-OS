"""Canonical hash and replay input builders for secure execution layer.

Pure deterministic helpers:
- canonical JSON bytes
- domain-separated hashing
- typed canonical input builders
"""

from __future__ import annotations

import json
import math
from hashlib import sha256
from typing import Any, Mapping


def canon_json_bytes_v1(obj: Mapping[str, Any], *, allow_floats: bool = False) -> bytes:
    _ensure_mapping(obj)
    _validate_json_value(obj, allow_floats=allow_floats)
    rendered = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return rendered.encode("utf-8")


def domain_hash(domain: str, obj: Mapping[str, Any]) -> str:
    if not domain:
        raise ValueError("secure_layer.hash.invalid domain")
    digest_input = domain.encode("utf-8") + b"\n" + canon_json_bytes_v1(obj)
    return sha256(digest_input).hexdigest()


def build_policy_hash_input(
    *,
    policy_id: str,
    policy_version: str,
    conflict_resolution_mode: str,
    tie_breaker: str,
    stable_order_mode: str,
    rules_hash: str,
) -> Mapping[str, Any]:
    return {
        "policy_id": _require_non_empty(policy_id, "policy_id"),
        "policy_version": _require_non_empty(policy_version, "policy_version"),
        "conflict_resolution_mode": _require_non_empty(
            conflict_resolution_mode, "conflict_resolution_mode"
        ),
        "tie_breaker": _require_non_empty(tie_breaker, "tie_breaker"),
        "stable_order_mode": _require_non_empty(stable_order_mode, "stable_order_mode"),
        "rules_hash": _require_non_empty(rules_hash, "rules_hash"),
    }


def build_request_fingerprint_input(
    *,
    actor_id: str,
    capability: str,
    operation: str,
    target: str,
    context_hash: str,
) -> Mapping[str, Any]:
    return {
        "actor_id": _require_non_empty(actor_id, "actor_id"),
        "capability": _require_non_empty(capability, "capability"),
        "operation": _require_non_empty(operation, "operation"),
        "target": _require_non_empty(target, "target"),
        "context_hash": _require_non_empty(context_hash, "context_hash"),
    }


def build_audit_event_identity_input(
    *,
    event_id: str,
    event_type: str,
    policy_hash: str,
    request_fingerprint: str,
    sequence: int,
    stream_id: str,
    prev_event_hash: str | None,
) -> Mapping[str, Any]:
    if sequence < 0:
        raise ValueError("secure_layer.hash.invalid sequence")
    return {
        "event_id": _require_non_empty(event_id, "event_id"),
        "event_type": _require_non_empty(event_type, "event_type"),
        "policy_hash": _require_non_empty(policy_hash, "policy_hash"),
        "request_fingerprint": _require_non_empty(request_fingerprint, "request_fingerprint"),
        "sequence": sequence,
        "stream_id": _require_non_empty(stream_id, "stream_id"),
        "prev_event_hash": prev_event_hash or "",
    }


def build_audit_event_body_input(
    *,
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    _ensure_mapping(payload)
    _validate_json_value(payload, allow_floats=False)
    return {"payload": payload}


def build_review_id_input(
    *,
    policy_hash: str,
    request_fingerprint: str,
) -> Mapping[str, Any]:
    return {
        "policy_hash": _require_non_empty(policy_hash, "policy_hash"),
        "request_fingerprint": _require_non_empty(request_fingerprint, "request_fingerprint"),
    }


def build_review_decision_input(
    *,
    review_id: str,
    policy_hash: str,
    request_fingerprint: str,
    decision: str,
    decided_by: str,
    signature_ref: str,
) -> Mapping[str, Any]:
    if decision not in ("allow", "block"):
        raise ValueError("secure_layer.hash.invalid decision")
    return {
        "review_id": _require_non_empty(review_id, "review_id"),
        "policy_hash": _require_non_empty(policy_hash, "policy_hash"),
        "request_fingerprint": _require_non_empty(request_fingerprint, "request_fingerprint"),
        "decision": decision,
        "decided_by": _require_non_empty(decided_by, "decided_by"),
        "signature_ref": _require_non_empty(signature_ref, "signature_ref"),
    }


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"secure_layer.hash.invalid {field_name}")
    return value


def _ensure_mapping(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("secure_layer.hash.invalid mapping_required")


def _validate_json_value(value: Any, *, allow_floats: bool) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not allow_floats:
            raise ValueError("secure_layer.hash.invalid float_forbidden")
        if not math.isfinite(value):
            raise ValueError("secure_layer.hash.invalid non_finite_float")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item, allow_floats=allow_floats)
        return
    if isinstance(value, Mapping):
        for key in value.keys():
            if not isinstance(key, str):
                raise ValueError("secure_layer.hash.invalid key_type")
        for item in value.values():
            _validate_json_value(item, allow_floats=allow_floats)
        return
    raise ValueError("secure_layer.hash.invalid value_type")
