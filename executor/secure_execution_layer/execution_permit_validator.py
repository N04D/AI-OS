"""Pure deterministic execution permit validator utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from executor.secure_execution_layer.canonical_hash import domain_hash

_PERMIT_DOMAIN = "secure_execution_layer.execution_permit.v1"
_ALLOWED_DECISIONS = ("allow", "warn", "block", "review")
_ALLOWED_SCOPE = ("one_shot", "bounded")
_ALLOWED_EXPIRY_KEYS = ("valid_for_sequence_range", "valid_for_commit")


@dataclass(frozen=True)
class ExecutionPermit:
    permit_id: str
    policy_hash: str
    request_fingerprint: str
    capability: Mapping[str, Any]
    decision: Literal["allow", "warn", "block", "review"]
    severity_to_gating: Mapping[str, str]
    issued_by: str
    issued_at_sequence: int
    stream_id: str
    prev_event_hash: str
    permit_scope: Literal["one_shot", "bounded"]
    expiry_condition: Mapping[str, Any]


def validate_execution_permit_structure(permit: ExecutionPermit) -> None:
    _require_non_empty_string(permit.permit_id, "permit_id")
    _require_non_empty_string(permit.policy_hash, "policy_hash")
    _require_non_empty_string(permit.request_fingerprint, "request_fingerprint")
    _require_non_empty_string(permit.issued_by, "issued_by")
    _require_non_empty_string(permit.stream_id, "stream_id")
    _require_non_empty_string(permit.prev_event_hash, "prev_event_hash")

    if not isinstance(permit.issued_at_sequence, int) or isinstance(permit.issued_at_sequence, bool):
        raise ValueError("secure_layer.permit.invalid.issued_at_sequence_type")
    if permit.issued_at_sequence < 0:
        raise ValueError("secure_layer.permit.invalid.issued_at_sequence")

    if permit.decision not in _ALLOWED_DECISIONS:
        raise ValueError("secure_layer.permit.invalid.decision")
    if permit.permit_scope not in _ALLOWED_SCOPE:
        raise ValueError("secure_layer.permit.invalid.permit_scope")

    _validate_non_empty_mapping(permit.capability, "capability")
    _validate_non_empty_mapping(permit.severity_to_gating, "severity_to_gating")
    _validate_severity_to_gating(permit.severity_to_gating)
    _validate_expiry_condition(permit.expiry_condition)

    computed_id = compute_permit_id(permit)
    if permit.permit_id != computed_id:
        raise ValueError("secure_layer.permit.invalid.permit_id_mismatch")


def compute_permit_id_input(permit: ExecutionPermit) -> Mapping[str, Any]:
    return {
        "policy_hash": permit.policy_hash,
        "request_fingerprint": permit.request_fingerprint,
        "capability": _copy_mapping(permit.capability),
        "decision": permit.decision,
        "severity_to_gating": _copy_string_mapping(permit.severity_to_gating),
        "issued_by": permit.issued_by,
        "issued_at_sequence": permit.issued_at_sequence,
        "stream_id": permit.stream_id,
        "prev_event_hash": permit.prev_event_hash,
        "permit_scope": permit.permit_scope,
        "expiry_condition": _copy_mapping(permit.expiry_condition),
    }


def compute_permit_id(permit: ExecutionPermit) -> str:
    return domain_hash(_PERMIT_DOMAIN, compute_permit_id_input(permit))


def verify_execution_permit_against_chain(
    permit: ExecutionPermit,
    current_stream_id: str,
    current_sequence: int,
    current_prev_event_hash: str,
) -> None:
    validate_execution_permit_structure(permit)

    _require_non_empty_string(current_stream_id, "current_stream_id")
    _require_non_empty_string(current_prev_event_hash, "current_prev_event_hash")
    if not isinstance(current_sequence, int) or isinstance(current_sequence, bool):
        raise ValueError("secure_layer.permit.invalid.current_sequence_type")
    if current_sequence < 0:
        raise ValueError("secure_layer.permit.invalid.current_sequence")

    if permit.stream_id != current_stream_id:
        raise ValueError("secure_layer.permit.invalid.stream_id_mismatch")
    if permit.prev_event_hash != current_prev_event_hash:
        raise ValueError("secure_layer.permit.invalid.prev_event_hash_mismatch")
    if permit.issued_at_sequence != current_sequence:
        raise ValueError("secure_layer.permit.invalid.sequence_mismatch")

    sequence_range = permit.expiry_condition.get("valid_for_sequence_range")
    if sequence_range is None:
        raise ValueError("secure_layer.permit.invalid.expiry_sequence_range_missing")
    start, end = _validate_sequence_range(sequence_range)

    if permit.permit_scope == "one_shot":
        if start != permit.issued_at_sequence or end != permit.issued_at_sequence:
            raise ValueError("secure_layer.permit.invalid.one_shot_range_mismatch")
    else:
        if not (start <= current_sequence <= end):
            raise ValueError("secure_layer.permit.invalid.bounded_range_violation")

    if "valid_for_commit" in permit.expiry_condition:
        commit_sha = permit.expiry_condition["valid_for_commit"]
        if not isinstance(commit_sha, str) or not commit_sha:
            raise ValueError("secure_layer.permit.invalid.valid_for_commit")


def _validate_non_empty_mapping(value: Mapping[str, Any], field_name: str) -> None:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"secure_layer.permit.invalid.{field_name}")


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"secure_layer.permit.invalid.{field_name}")


def _validate_severity_to_gating(value: Mapping[str, str]) -> None:
    for key in ("allow", "warn", "block", "review"):
        mapped = value.get(key)
        if not isinstance(mapped, str) or not mapped:
            raise ValueError("secure_layer.permit.invalid.severity_to_gating")

    for key in value.keys():
        if not isinstance(key, str):
            raise ValueError("secure_layer.permit.invalid.severity_to_gating")
        if key not in ("allow", "warn", "block", "review"):
            raise ValueError("secure_layer.permit.invalid.severity_to_gating")


def _validate_expiry_condition(expiry_condition: Mapping[str, Any]) -> None:
    _validate_non_empty_mapping(expiry_condition, "expiry_condition")

    for key in expiry_condition.keys():
        if not isinstance(key, str):
            raise ValueError("secure_layer.permit.invalid.expiry_condition_key")
        if key not in _ALLOWED_EXPIRY_KEYS:
            raise ValueError("secure_layer.permit.invalid.expiry_condition_key")

    has_range = "valid_for_sequence_range" in expiry_condition
    has_commit = "valid_for_commit" in expiry_condition
    if not (has_range or has_commit):
        raise ValueError("secure_layer.permit.invalid.expiry_condition_missing")

    if has_range:
        _validate_sequence_range(expiry_condition["valid_for_sequence_range"])
    if has_commit:
        commit_sha = expiry_condition["valid_for_commit"]
        if not isinstance(commit_sha, str) or not commit_sha:
            raise ValueError("secure_layer.permit.invalid.valid_for_commit")

    _reject_floats_in_value(expiry_condition)


def _validate_sequence_range(value: Any) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("secure_layer.permit.invalid.valid_for_sequence_range")
    start = value[0]
    end = value[1]
    if (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
    ):
        raise ValueError("secure_layer.permit.invalid.valid_for_sequence_range")
    if start < 0 or end < 0 or start > end:
        raise ValueError("secure_layer.permit.invalid.valid_for_sequence_range")
    return (start, end)


def _reject_floats_in_value(value: Any) -> None:
    if isinstance(value, float):
        raise ValueError("secure_layer.permit.invalid.float_in_expiry_condition")
    if isinstance(value, list):
        for item in value:
            _reject_floats_in_value(item)
        return
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_floats_in_value(item)
        return


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("secure_layer.permit.invalid.mapping_key")
        result[key] = _copy_value(item)
    return result


def _copy_string_mapping(value: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError("secure_layer.permit.invalid.severity_to_gating")
        result[key] = item
    return result


def _copy_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise ValueError("secure_layer.permit.invalid.float_in_mapping")
    if isinstance(value, list):
        return [_copy_value(item) for item in value]
    if isinstance(value, Mapping):
        return _copy_mapping(value)
    raise ValueError("secure_layer.permit.invalid.value_type")
