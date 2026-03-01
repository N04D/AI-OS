"""Skill mediation layer v0.1 (deny-by-default)."""

from __future__ import annotations

import json
import re
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Callable

from kernel.dispatch import dispatch

_POLICY_TOP_LEVEL_KEYS = {"version", "default_decision", "skills", "channels"}
_SKILL_KEYS = {"description", "target", "input_schema", "safe_defaults", "rate_limit", "allowed_recipients"}
_TARGET_KEYS = {"plugin_id", "method"}
_SCHEMA_KEYS = {"type", "required", "properties"}
_RATE_LIMIT_KEYS = {"cooldown_seconds"}
_CHANNEL_KEYS = {"allowed_users", "allowed_skills", "quotas"}
_QUOTA_KEYS = {"per_user_per_hour"}

_SKILL_ID_RE = re.compile(r"^[a-z0-9-]+$")
_CHANNEL_ID_RE = re.compile(r"^[a-z0-9-]+$")

# In-memory hardening state (v0.2)
_LAST_SUCCESS_BY_USER_SKILL: dict[tuple[str, str], float] = {}
_EXECUTIONS_BY_USER: dict[str, list[float]] = {}


def _deny(skill_id: str, code: str, details: list[str]) -> dict[str, Any]:
    return {
        "ok": False,
        "skill_id": skill_id,
        "error": {
            "code": code,
            "details": details,
        },
    }


def _load_yaml(path: str | Path) -> Any:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        from scripts.validate_plugin_manifest import _load_yaml as _fallback  # type: ignore

        return _fallback(str(path))


def _validate_unknown_keys(obj: dict[str, Any], allowed_keys: set[str], ctx: str) -> None:
    unknown = sorted(set(obj.keys()) - allowed_keys)
    if unknown:
        raise ValueError(f"{ctx}: unknown fields: {', '.join(unknown)}")


def _validate_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    return False


def _now_epoch_seconds() -> float:
    return time.time()


def _reset_runtime_state() -> None:
    """Test-only helper to reset in-memory hardening state."""
    _LAST_SUCCESS_BY_USER_SKILL.clear()
    _EXECUTIONS_BY_USER.clear()


def load_skills_policy(path: str | Path) -> dict[str, Any]:
    policy = _load_yaml(path)
    if not isinstance(policy, dict):
        raise ValueError("policy must be a mapping")

    _validate_unknown_keys(policy, _POLICY_TOP_LEVEL_KEYS, "policy")

    if policy.get("version") != "0.1":
        raise ValueError("version must be 0.1")
    if policy.get("default_decision") != "deny":
        raise ValueError("default_decision must be deny")

    skills = policy.get("skills")
    channels = policy.get("channels")
    if not isinstance(skills, dict):
        raise ValueError("skills must be a mapping")
    if not isinstance(channels, dict):
        raise ValueError("channels must be a mapping")

    normalized_skills: dict[str, Any] = {}
    for skill_id, skill_def in sorted(skills.items()):
        if not isinstance(skill_id, str) or _SKILL_ID_RE.fullmatch(skill_id) is None:
            raise ValueError("invalid skill_id")
        if not isinstance(skill_def, dict):
            raise ValueError(f"skill {skill_id} must be a mapping")
        _validate_unknown_keys(skill_def, _SKILL_KEYS, f"skill {skill_id}")

        description = skill_def.get("description")
        target = skill_def.get("target")
        input_schema = skill_def.get("input_schema")
        safe_defaults = skill_def.get("safe_defaults", {})
        rate_limit = skill_def.get("rate_limit", {})
        allowed_recipients = skill_def.get("allowed_recipients", [])

        if not isinstance(description, str) or not description:
            raise ValueError(f"skill {skill_id} description must be non-empty string")
        if not isinstance(target, dict):
            raise ValueError(f"skill {skill_id} target must be object")
        _validate_unknown_keys(target, _TARGET_KEYS, f"skill {skill_id} target")
        plugin_id = target.get("plugin_id")
        method = target.get("method")
        if not isinstance(plugin_id, str) or not plugin_id:
            raise ValueError(f"skill {skill_id} target.plugin_id must be non-empty string")
        if not isinstance(method, str) or not method:
            raise ValueError(f"skill {skill_id} target.method must be non-empty string")

        if not isinstance(input_schema, dict):
            raise ValueError(f"skill {skill_id} input_schema must be object")
        _validate_unknown_keys(input_schema, _SCHEMA_KEYS, f"skill {skill_id} input_schema")
        if input_schema.get("type") != "object":
            raise ValueError(f"skill {skill_id} input_schema.type must be object")
        required = input_schema.get("required", [])
        properties = input_schema.get("properties", {})
        if not isinstance(required, list) or not all(isinstance(v, str) and v for v in required):
            raise ValueError(f"skill {skill_id} input_schema.required must be string array")
        if not isinstance(properties, dict):
            raise ValueError(f"skill {skill_id} input_schema.properties must be object")
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_name, str) or not prop_name:
                raise ValueError(f"skill {skill_id} invalid property name")
            if not isinstance(prop_schema, dict):
                raise ValueError(f"skill {skill_id} property {prop_name} schema must be object")
            if set(prop_schema.keys()) != {"type"}:
                raise ValueError(f"skill {skill_id} property {prop_name} has invalid schema keys")
            if not isinstance(prop_schema.get("type"), str):
                raise ValueError(f"skill {skill_id} property {prop_name} type must be string")

        if not isinstance(safe_defaults, dict):
            raise ValueError(f"skill {skill_id} safe_defaults must be object")

        normalized_rate_limit: dict[str, Any] = {}
        if rate_limit not in ({}, None):
            if not isinstance(rate_limit, dict):
                raise ValueError(f"skill {skill_id} rate_limit must be object")
            _validate_unknown_keys(rate_limit, _RATE_LIMIT_KEYS, f"skill {skill_id} rate_limit")
            cooldown_seconds = rate_limit.get("cooldown_seconds")
            if not isinstance(cooldown_seconds, int) or isinstance(cooldown_seconds, bool) or cooldown_seconds <= 0:
                raise ValueError(f"skill {skill_id} rate_limit.cooldown_seconds must be positive int")
            normalized_rate_limit["cooldown_seconds"] = cooldown_seconds

        if not isinstance(allowed_recipients, list) or not all(isinstance(v, str) for v in allowed_recipients):
            raise ValueError(f"skill {skill_id} allowed_recipients must be string array")

        normalized_skills[skill_id] = {
            "description": description,
            "target": {
                "plugin_id": plugin_id,
                "method": method,
            },
            "input_schema": {
                "type": "object",
                "required": sorted(required),
                "properties": properties,
            },
            "safe_defaults": safe_defaults,
            "rate_limit": normalized_rate_limit,
            "allowed_recipients": sorted(allowed_recipients),
        }

    normalized_channels: dict[str, Any] = {}
    for channel_id, channel_def in sorted(channels.items()):
        if not isinstance(channel_id, str) or _CHANNEL_ID_RE.fullmatch(channel_id) is None:
            raise ValueError("invalid channel_id")
        if not isinstance(channel_def, dict):
            raise ValueError(f"channel {channel_id} must be object")
        _validate_unknown_keys(channel_def, _CHANNEL_KEYS, f"channel {channel_id}")

        allowed_users = channel_def.get("allowed_users")
        allowed_skills = channel_def.get("allowed_skills")
        quotas = channel_def.get("quotas", {})
        if not isinstance(allowed_users, list) or not all(isinstance(v, str) for v in allowed_users):
            raise ValueError(f"channel {channel_id} allowed_users must be string array")
        if not isinstance(allowed_skills, list) or not all(isinstance(v, str) for v in allowed_skills):
            raise ValueError(f"channel {channel_id} allowed_skills must be string array")

        for allowed_skill in allowed_skills:
            if allowed_skill not in normalized_skills:
                raise ValueError(f"channel {channel_id} references unknown skill {allowed_skill}")

        normalized_quotas: dict[str, Any] = {}
        if quotas not in ({}, None):
            if not isinstance(quotas, dict):
                raise ValueError(f"channel {channel_id} quotas must be object")
            _validate_unknown_keys(quotas, _QUOTA_KEYS, f"channel {channel_id} quotas")
            per_user_per_hour = quotas.get("per_user_per_hour")
            if not isinstance(per_user_per_hour, int) or isinstance(per_user_per_hour, bool) or per_user_per_hour <= 0:
                raise ValueError(f"channel {channel_id} quotas.per_user_per_hour must be positive int")
            normalized_quotas["per_user_per_hour"] = per_user_per_hour

        normalized_channels[channel_id] = {
            "allowed_users": sorted(allowed_users),
            "allowed_skills": sorted(allowed_skills),
            "quotas": normalized_quotas,
        }

    return {
        "version": "0.1",
        "default_decision": "deny",
        "skills": normalized_skills,
        "channels": normalized_channels,
    }


def _validate_payload(input_schema: dict[str, Any], payload: Any) -> tuple[bool, list[str]]:
    if not isinstance(payload, dict):
        return False, ["payload_must_be_object"]

    details: list[str] = []
    required = input_schema.get("required", [])
    properties = input_schema.get("properties", {})

    for field in required:
        if field not in payload:
            details.append(f"missing_required:{field}")

    if isinstance(properties, dict):
        for key, value in payload.items():
            prop_schema = properties.get(key)
            if not isinstance(prop_schema, dict):
                continue
            expected_type = prop_schema.get("type")
            if isinstance(expected_type, str) and not _validate_type(value, expected_type):
                details.append(f"invalid_type:{key}:{expected_type}")

    return len(details) == 0, sorted(details)


def evaluate_skill_request(
    policy: dict[str, Any], channel_id: str, user_id: str, skill_id: str, payload: Any
) -> dict[str, Any]:
    channels = policy.get("channels", {})
    skills = policy.get("skills", {})

    channel = channels.get(channel_id) if isinstance(channels, dict) else None
    if not isinstance(channel, dict):
        return {"allow": False, "code": "SKILL_DENIED", "details": ["channel_not_allowed"]}

    allowed_users = channel.get("allowed_users", [])
    if user_id not in allowed_users:
        return {"allow": False, "code": "SKILL_DENIED", "details": ["user_not_allowed"]}

    allowed_skills = channel.get("allowed_skills", [])
    if skill_id not in allowed_skills:
        return {"allow": False, "code": "SKILL_DENIED", "details": ["skill_not_allowed"]}

    skill = skills.get(skill_id) if isinstance(skills, dict) else None
    if not isinstance(skill, dict):
        return {"allow": False, "code": "SKILL_DENIED", "details": ["unknown_skill"]}

    schema = skill.get("input_schema")
    if not isinstance(schema, dict):
        return {"allow": False, "code": "SKILL_POLICY_INVALID", "details": ["invalid_input_schema"]}

    ok_payload, payload_details = _validate_payload(schema, payload)
    if not ok_payload:
        return {"allow": False, "code": "SKILL_INVALID_ARGS", "details": payload_details}

    safe_defaults = skill.get("safe_defaults", {})
    if not isinstance(safe_defaults, dict):
        return {"allow": False, "code": "SKILL_POLICY_INVALID", "details": ["invalid_safe_defaults"]}

    merged_payload = dict(safe_defaults)
    merged_payload.update(payload)

    target = skill.get("target", {})
    return {
        "allow": True,
        "code": "OK",
        "details": [],
        "target": {
            "plugin_id": target.get("plugin_id"),
            "method": target.get("method"),
        },
        "payload": merged_payload,
        "skill": skill,
        "channel": channel,
    }


def _scope_check(skill: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, list[str]]:
    allowed_recipients = skill.get("allowed_recipients", [])
    if not isinstance(allowed_recipients, list) or not allowed_recipients:
        return True, []

    recipient = payload.get("recipient")
    if not isinstance(recipient, str) or recipient not in allowed_recipients:
        return False, ["recipient_not_allowed"]

    return True, []


def _cooldown_check(user_id: str, skill_id: str, skill: dict[str, Any], now_ts: float) -> tuple[bool, list[str]]:
    rate_limit = skill.get("rate_limit", {})
    if not isinstance(rate_limit, dict):
        return False, ["invalid_rate_limit"]

    cooldown_seconds = rate_limit.get("cooldown_seconds")
    if cooldown_seconds is None:
        return True, []

    if not isinstance(cooldown_seconds, int) or isinstance(cooldown_seconds, bool) or cooldown_seconds <= 0:
        return False, ["invalid_cooldown_seconds"]

    last = _LAST_SUCCESS_BY_USER_SKILL.get((user_id, skill_id))
    if last is None:
        return True, []

    if now_ts - last < cooldown_seconds:
        return False, [f"cooldown_seconds={cooldown_seconds}"]

    return True, []


def _quota_check(user_id: str, channel: dict[str, Any], now_ts: float) -> tuple[bool, list[str]]:
    quotas = channel.get("quotas", {})
    if not isinstance(quotas, dict):
        return False, ["invalid_quotas"]

    per_user_per_hour = quotas.get("per_user_per_hour")
    if per_user_per_hour is None:
        return True, []

    if not isinstance(per_user_per_hour, int) or isinstance(per_user_per_hour, bool) or per_user_per_hour <= 0:
        return False, ["invalid_per_user_per_hour"]

    window_start = now_ts - 3600
    existing = _EXECUTIONS_BY_USER.get(user_id, [])
    pruned = [ts for ts in existing if ts >= window_start]
    _EXECUTIONS_BY_USER[user_id] = pruned

    if len(pruned) >= per_user_per_hour:
        return False, [f"per_user_per_hour={per_user_per_hour}"]

    return True, []


def _record_success(user_id: str, skill_id: str, now_ts: float) -> None:
    _LAST_SUCCESS_BY_USER_SKILL[(user_id, skill_id)] = now_ts
    history = _EXECUTIONS_BY_USER.setdefault(user_id, [])
    history.append(now_ts)


def _now_rfc3339_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _append_audit(
    *,
    audit_log_path: str,
    channel_id: str,
    user_id: str,
    skill_id: str,
    result: str,
    reason_code: str,
) -> None:
    row = {
        "channel_id": channel_id,
        "reason_code": reason_code,
        "result": result,
        "skill_id": skill_id,
        "ts": _now_rfc3339_utc(),
        "user_id": user_id,
    }
    path = Path(audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _deny_with_audit(
    *,
    audit_log_path: str,
    channel_id: str,
    user_id: str,
    skill_id: str,
    code: str,
    details: list[str],
) -> dict[str, Any]:
    try:
        _append_audit(
            audit_log_path=audit_log_path,
            channel_id=channel_id,
            user_id=user_id,
            skill_id=skill_id,
            result="deny",
            reason_code=code,
        )
    except Exception:
        return _deny(skill_id, "SKILL_DENIED", ["AUDIT_LOG_WRITE_FAILED"])
    return _deny(skill_id, code, [str(v) for v in details])


def run_skill(
    channel_id: str,
    user_id: str,
    skill_id: str,
    payload: Any,
    *,
    policy_path: str,
    registry_path: str,
    config_path: str,
    audit_log_path: str,
    now_fn: Callable[[], float] | None = None,
) -> dict[str, Any]:
    safe_channel = channel_id if isinstance(channel_id, str) else ""
    safe_user = user_id if isinstance(user_id, str) else ""
    safe_skill = skill_id if isinstance(skill_id, str) else ""

    try:
        policy = load_skills_policy(policy_path)
    except Exception as exc:
        return _deny(safe_skill, "SKILL_POLICY_INVALID", [str(exc)])

    verdict = evaluate_skill_request(policy, safe_channel, safe_user, safe_skill, payload)
    if verdict.get("allow") is not True:
        code = str(verdict.get("code") or "SKILL_DENIED")
        details = verdict.get("details")
        if not isinstance(details, list):
            details = ["evaluation_failed"]
        return _deny_with_audit(
            audit_log_path=audit_log_path,
            channel_id=safe_channel,
            user_id=safe_user,
            skill_id=safe_skill,
            code=code,
            details=[str(v) for v in details],
        )

    target = verdict.get("target") if isinstance(verdict.get("target"), dict) else {}
    plugin_id = target.get("plugin_id")
    method = target.get("method")
    mediated_payload = verdict.get("payload")
    skill = verdict.get("skill") if isinstance(verdict.get("skill"), dict) else {}
    channel = verdict.get("channel") if isinstance(verdict.get("channel"), dict) else {}

    if not isinstance(plugin_id, str) or not plugin_id or not isinstance(method, str) or not method:
        return _deny(safe_skill, "SKILL_POLICY_INVALID", ["invalid_target"])
    if not isinstance(mediated_payload, dict):
        return _deny(safe_skill, "SKILL_POLICY_INVALID", ["invalid_mediated_payload"])

    # 4) Capability scope check
    scope_ok, scope_details = _scope_check(skill, mediated_payload)
    if not scope_ok:
        return _deny_with_audit(
            audit_log_path=audit_log_path,
            channel_id=safe_channel,
            user_id=safe_user,
            skill_id=safe_skill,
            code="SKILL_SCOPE_VIOLATION",
            details=scope_details,
        )

    now_ts = now_fn() if now_fn is not None else _now_epoch_seconds()

    # 5) Cooldown check
    cooldown_ok, cooldown_details = _cooldown_check(safe_user, safe_skill, skill, now_ts)
    if not cooldown_ok:
        return _deny_with_audit(
            audit_log_path=audit_log_path,
            channel_id=safe_channel,
            user_id=safe_user,
            skill_id=safe_skill,
            code="SKILL_RATE_LIMITED",
            details=cooldown_details,
        )

    # 6) Quota check
    quota_ok, quota_details = _quota_check(safe_user, channel, now_ts)
    if not quota_ok:
        return _deny_with_audit(
            audit_log_path=audit_log_path,
            channel_id=safe_channel,
            user_id=safe_user,
            skill_id=safe_skill,
            code="SKILL_QUOTA_EXCEEDED",
            details=quota_details,
        )

    try:
        _append_audit(
            audit_log_path=audit_log_path,
            channel_id=safe_channel,
            user_id=safe_user,
            skill_id=safe_skill,
            result="allow",
            reason_code="OK",
        )
    except Exception:
        return _deny(safe_skill, "SKILL_DENIED", ["AUDIT_LOG_WRITE_FAILED"])

    # 7) Dispatch
    try:
        dispatch_result = dispatch(
            plugin_id,
            method,
            mediated_payload,
            registry_path=registry_path,
            config_path=config_path,
            audit_log_path=audit_log_path,
        )
    except Exception as exc:
        return _deny(safe_skill, "SKILL_DENIED", [str(exc)])

    if not isinstance(dispatch_result, dict):
        return _deny(safe_skill, "SKILL_DENIED", ["dispatch_result_invalid"])

    if dispatch_result.get("ok") is True:
        _record_success(safe_user, safe_skill, float(now_ts))

    return {
        "ok": True,
        "skill_id": safe_skill,
        "result": dispatch_result,
    }
