#!/usr/bin/env python3
"""Deterministic plugin manifest validator (Milestone 2, Phases 1-2)."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_SCHEMA_PATH = "governance/schema/plugins/plugin-manifest.v0.1.yaml"
DEFAULT_POLICY_PATH = "governance/policy/plugins/plugin-boundary.v0.1.yaml"


def _strip_inline_comment(line: str) -> str:
    if "#" not in line:
        return line
    in_single = False
    in_double = False
    out: list[str] = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(text: str) -> Any:
    value = text.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    return value


def _parse_yaml_minimal(raw: str) -> Any:
    lines: list[tuple[int, str]] = []
    for original in raw.splitlines():
        line = _strip_inline_comment(original)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, line.strip()))

    idx = 0

    def parse_block(current_indent: int) -> Any:
        nonlocal idx
        if idx >= len(lines):
            return {}

        is_list = lines[idx][1].startswith("- ")
        if is_list:
            out_list: list[Any] = []
            while idx < len(lines):
                indent, text = lines[idx]
                if indent < current_indent or not text.startswith("- "):
                    break
                if indent != current_indent:
                    raise ValueError("Invalid list indentation")
                item_text = text[2:].strip()
                idx += 1
                if item_text == "":
                    out_list.append(parse_block(current_indent + 2))
                elif ":" in item_text:
                    key, rest = item_text.split(":", 1)
                    item: dict[str, Any] = {}
                    if rest.strip():
                        item[key.strip()] = _parse_scalar(rest.strip())
                    else:
                        item[key.strip()] = parse_block(current_indent + 2)
                    while idx < len(lines):
                        ni, nt = lines[idx]
                        if ni <= current_indent:
                            break
                        if ni == current_indent + 2 and ":" in nt and not nt.startswith("- "):
                            sk, sr = nt.split(":", 1)
                            idx += 1
                            if sr.strip():
                                item[sk.strip()] = _parse_scalar(sr.strip())
                            else:
                                item[sk.strip()] = parse_block(current_indent + 4)
                        else:
                            break
                    out_list.append(item)
                else:
                    out_list.append(_parse_scalar(item_text))
            return out_list

        out_map: dict[str, Any] = {}
        while idx < len(lines):
            indent, text = lines[idx]
            if indent < current_indent:
                break
            if indent != current_indent:
                raise ValueError("Invalid mapping indentation")
            if ":" not in text:
                raise ValueError(f"Invalid mapping line: {text}")
            key, rest = text.split(":", 1)
            idx += 1
            key = key.strip()
            rest = rest.strip()
            if rest:
                out_map[key] = _parse_scalar(rest)
            else:
                out_map[key] = parse_block(current_indent + 2)
        return out_map

    return parse_block(0)


def _load_yaml(path: str) -> Any:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        return _parse_yaml_minimal(raw)


def _normalize_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    return p


def _extract_fs_paths(fs_spec: Any) -> list[str]:
    if fs_spec is None:
        return []
    if isinstance(fs_spec, str):
        return [_normalize_path(fs_spec)]
    if isinstance(fs_spec, list):
        return [_normalize_path(str(v)) for v in fs_spec if str(v).strip()]
    if isinstance(fs_spec, dict):
        out: list[str] = []
        for key in ("allow", "paths"):
            value = fs_spec.get(key)
            if isinstance(value, str):
                out.append(_normalize_path(value))
            elif isinstance(value, list):
                out.extend(_normalize_path(str(v)) for v in value if str(v).strip())
        return sorted(set(out))
    return []


def _fail(reason_code: str, details: list[str] | None = None) -> dict[str, Any]:
    return {
        "allow": False,
        "details": sorted(details or []),
        "reason_code": reason_code,
    }


def _ok(reason_code: str | None = None) -> dict[str, Any]:
    return {
        "allow": True,
        "reason_code": reason_code,
    }


def _check_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "any":
        return True
    return False


def _validate_object(value: Any, field_schema: dict[str, Any], path: str, details: list[str]) -> None:
    if not isinstance(value, dict):
        details.append(f"{path}: expected object")
        return

    required = field_schema.get("required", [])
    if isinstance(required, list):
        for req in required:
            if req not in value:
                details.append(f"{path}.{req}: missing required field")

    allow_unknown = bool(field_schema.get("allow_unknown", True))
    properties = field_schema.get("properties", {})
    if not isinstance(properties, dict):
        properties = {}

    if not allow_unknown:
        unknown = sorted(set(value.keys()) - set(properties.keys()))
        for key in unknown:
            details.append(f"{path}.{key}: unknown field")

    for key, prop_schema in properties.items():
        if key not in value:
            continue
        _validate_field(value[key], prop_schema, f"{path}.{key}", details)


def _validate_array(value: Any, field_schema: dict[str, Any], path: str, details: list[str]) -> None:
    if not isinstance(value, list):
        details.append(f"{path}: expected array")
        return

    min_items = field_schema.get("min_items")
    if isinstance(min_items, int) and len(value) < min_items:
        details.append(f"{path}: expected at least {min_items} items")

    item_type = field_schema.get("item_type")
    if isinstance(item_type, str):
        for i, item in enumerate(value):
            if not _check_type(item, item_type):
                details.append(f"{path}[{i}]: expected {item_type}")
            elif item_type == "string" and str(item).strip() == "":
                details.append(f"{path}[{i}]: empty string not allowed")


def _validate_field(value: Any, field_schema: dict[str, Any], path: str, details: list[str]) -> None:
    if not isinstance(field_schema, dict):
        details.append(f"{path}: invalid schema definition")
        return

    expected_type = field_schema.get("type")
    if isinstance(expected_type, str) and not _check_type(value, expected_type):
        details.append(f"{path}: expected {expected_type}")
        return

    if isinstance(expected_type, str) and expected_type == "object":
        _validate_object(value, field_schema, path, details)
        return

    if isinstance(expected_type, str) and expected_type == "array":
        _validate_array(value, field_schema, path, details)
        return

    const = field_schema.get("const")
    if const is not None and value != const:
        details.append(f"{path}: expected constant value {const}")

    pattern = field_schema.get("pattern")
    if isinstance(pattern, str) and isinstance(value, str):
        if re.fullmatch(pattern, value) is None:
            details.append(f"{path}: value does not match required pattern")

    minimum = field_schema.get("minimum")
    if isinstance(minimum, int) and isinstance(value, int):
        if value < minimum:
            details.append(f"{path}: must be >= {minimum}")


# -------- bounded schema compatibility --------

def _schema_kind(schema: dict[str, Any]) -> str | None:
    is_current = "required_top_level" in schema or "fields" in schema
    is_legacy = "required" in schema or "types" in schema
    if is_current and is_legacy:
        return None
    if is_current:
        if not isinstance(schema.get("required_top_level"), list):
            return None
        if not isinstance(schema.get("fields"), dict):
            return None
        return "current"
    if is_legacy:
        if not isinstance(schema.get("required"), list):
            return None
        if not isinstance(schema.get("types"), dict):
            return None
        return "legacy"
    return None


def _get_nested(mapping: Any, dotted_path: str) -> tuple[bool, Any]:
    current = mapping
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _legacy_type_ok(value: Any, expected: str) -> bool:
    if expected == "str":
        return isinstance(value, str)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "list":
        return isinstance(value, list)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "dict":
        return isinstance(value, dict)
    return False


def _validate_legacy_schema(manifest: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    details: list[str] = []

    required = schema.get("required", [])
    for field in required:
        if not isinstance(field, str):
            details.append("required contains non-string path")
            continue
        present, _ = _get_nested(manifest, field)
        if not present:
            details.append(f"{field}: missing required field")

    types = schema.get("types", {})
    for field, expected in types.items():
        if not isinstance(field, str) or not isinstance(expected, str):
            details.append("types contains invalid entry")
            continue
        present, value = _get_nested(manifest, field)
        if not present:
            continue
        if not _legacy_type_ok(value, expected):
            details.append(f"{field}: expected {expected}")

    enums = schema.get("enums", {})
    if isinstance(enums, dict):
        for field, allowed in enums.items():
            if not isinstance(field, str) or not isinstance(allowed, list):
                details.append("enums contains invalid entry")
                continue
            present, value = _get_nested(manifest, field)
            if not present:
                continue
            if value not in allowed:
                details.append(f"{field}: value not in enum")

    const = schema.get("const", {})
    if isinstance(const, dict):
        for field, expected in const.items():
            if not isinstance(field, str):
                details.append("const contains invalid entry")
                continue
            present, value = _get_nested(manifest, field)
            if not present:
                continue
            if value != expected:
                details.append(f"{field}: expected constant value {expected}")

    return details


def _legacy_policy_checks(manifest: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any] | None:
    forbidden_caps = policy.get("forbidden_capabilities", [])
    if isinstance(forbidden_caps, list):
        capabilities = manifest.get("capabilities")
        if isinstance(capabilities, list):
            bad = [str(c) for c in capabilities if str(c) in {str(x) for x in forbidden_caps}]
            if bad:
                return _fail("DENY_FORBIDDEN_CAPABILITY", bad)

    fs_allow: list[str] = []
    permissions = manifest.get("permissions")
    if isinstance(permissions, dict):
        filesystem = permissions.get("filesystem")
        if isinstance(filesystem, dict):
            allow = filesystem.get("allow")
            if isinstance(allow, list):
                fs_allow = [_normalize_path(str(v)) for v in allow if str(v).strip()]

    forbidden_paths = policy.get("forbidden_filesystem_paths", [])
    if isinstance(forbidden_paths, list):
        patterns = [_normalize_path(str(v)) for v in forbidden_paths]
        violations: list[str] = []
        for path in fs_allow:
            for pattern in patterns:
                if fnmatch.fnmatch(path, pattern):
                    violations.append(f"{path} matches forbidden pattern {pattern}")
        if violations:
            return _fail("DENY_FORBIDDEN_FILESYSTEM_PATH", violations)

    require_allowlist = policy.get("require_explicit_network_allowlist") is True
    if require_allowlist:
        hosts: list[str] = []
        if isinstance(permissions, dict):
            network = permissions.get("network")
            if isinstance(network, dict):
                allow_hosts = network.get("allow_hosts")
                if isinstance(allow_hosts, list):
                    hosts = [str(v) for v in allow_hosts if str(v).strip()]
        if not hosts:
            return _fail("DENY_NETWORK_ALLOWLIST_REQUIRED", ["permissions.network.allow_hosts must be non-empty"])

    return None


def validate_manifest(manifest_path: str, schema_path: str = DEFAULT_SCHEMA_PATH, policy_path: str = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    try:
        manifest = _load_yaml(manifest_path)
    except FileNotFoundError:
        return _fail("DENY_MANIFEST_MISSING", ["manifest file not found"])
    except Exception as exc:
        return _fail("DENY_MANIFEST_PARSE_ERROR", [str(exc)])

    try:
        schema = _load_yaml(schema_path)
    except FileNotFoundError:
        return _fail("DENY_SCHEMA_MISSING", ["schema file not found"])
    except Exception as exc:
        return _fail("DENY_SCHEMA_PARSE_ERROR", [str(exc)])

    try:
        policy = _load_yaml(policy_path)
    except FileNotFoundError:
        return _fail("DENY_POLICY_MISSING", ["policy file not found"])
    except Exception as exc:
        return _fail("DENY_POLICY_PARSE_ERROR", [str(exc)])

    if not isinstance(manifest, dict):
        return _fail("DENY_MANIFEST_INVALID", ["manifest must be a mapping"])
    if not isinstance(schema, dict):
        return _fail("DENY_SCHEMA_INVALID", ["schema must be a mapping"])
    if not isinstance(policy, dict):
        return _fail("DENY_POLICY_INVALID", ["policy must be a mapping"])

    kind = _schema_kind(schema)
    if kind is None:
        return _fail("DENY_SCHEMA_INVALID", ["unsupported or ambiguous schema contract"])

    if kind == "legacy":
        details = _validate_legacy_schema(manifest, schema)
        if details:
            return _fail("DENY_SCHEMA_VALIDATION", details)
        policy_verdict = _legacy_policy_checks(manifest, policy)
        if policy_verdict is not None:
            return policy_verdict
        return _ok("ALLOW_MANIFEST_VALID")

    # current schema contract
    details: list[str] = []

    required_top = schema.get("required_top_level", [])
    if not isinstance(required_top, list):
        return _fail("DENY_SCHEMA_INVALID", ["required_top_level must be a list"])
    for field in required_top:
        if field not in manifest:
            details.append(f"{field}: missing required top-level field")

    allow_unknown_top = bool(schema.get("allow_unknown_top_level", False))
    known_top = set(required_top)
    optional_top = schema.get("optional_top_level", [])
    if isinstance(optional_top, list):
        known_top.update(optional_top)
    if not allow_unknown_top:
        unknown_top = sorted(set(manifest.keys()) - known_top)
        for field in unknown_top:
            details.append(f"{field}: unknown top-level field")

    fields_schema = schema.get("fields", {})
    if not isinstance(fields_schema, dict):
        return _fail("DENY_SCHEMA_INVALID", ["fields must be a mapping"])

    for field_name in sorted(fields_schema.keys()):
        if field_name not in manifest:
            continue
        _validate_field(manifest[field_name], fields_schema[field_name], field_name, details)

    if details:
        return _fail("DENY_SCHEMA_VALIDATION", details)

    if policy.get("deny_by_default") is not True:
        return _fail("DENY_POLICY_INVALID", ["deny_by_default must be true"])
    if policy.get("require_manifest") is not True:
        return _fail("DENY_POLICY_INVALID", ["require_manifest must be true"])
    if policy.get("require_out_of_process") is not True:
        return _fail("DENY_POLICY_INVALID", ["require_out_of_process must be true"])

    plugin_id = str(manifest.get("plugin_id", ""))
    if re.fullmatch(r"^[a-z0-9-]+$", plugin_id) is None:
        return _fail("DENY_INVALID_PLUGIN_ID", ["plugin_id must match ^[a-z0-9-]+$"])

    protocol = str(((manifest.get("entrypoint") or {}).get("protocol")) or "")
    if protocol != "stdin_stdout_json":
        return _fail("DENY_PROTOCOL_VIOLATION", [f"entrypoint.protocol={protocol}"])

    disallowed_protocols = policy.get("disallowed_protocols", [])
    if isinstance(disallowed_protocols, list) and protocol in {str(v) for v in disallowed_protocols}:
        return _fail("DENY_PROTOCOL_VIOLATION", [f"protocol {protocol} is disallowed"])

    runtime_mode = str(((manifest.get("runtime") or {}).get("mode")) or "")
    allowed_modes = (
        {str(v) for v in policy.get("allowed_runtime_modes", [])}
        if isinstance(policy.get("allowed_runtime_modes"), list)
        else set()
    )
    if runtime_mode != "subprocess" or runtime_mode not in allowed_modes:
        return _fail("DENY_RUNTIME_MODE_VIOLATION", [f"runtime.mode={runtime_mode}"])

    fs_spec = ((manifest.get("permissions") or {}).get("filesystem")) if isinstance(manifest.get("permissions"), dict) else None
    fs_paths = _extract_fs_paths(fs_spec)
    forbidden_paths = policy.get("forbidden_paths", [])
    if not isinstance(forbidden_paths, list):
        return _fail("DENY_POLICY_INVALID", ["forbidden_paths must be a list"])
    normalized_patterns = [_normalize_path(str(p)) for p in forbidden_paths]
    violations: list[str] = []
    for path in fs_paths:
        for pattern in normalized_patterns:
            if fnmatch.fnmatch(path, pattern):
                violations.append(f"{path} matches forbidden pattern {pattern}")
    if violations:
        return _fail("DENY_FORBIDDEN_FILESYSTEM_PATH", violations)

    return _ok(None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a plugin manifest against schema and boundary policy")
    parser.add_argument("manifest", help="Path to plugin manifest YAML")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA_PATH, help="Schema YAML path")
    parser.add_argument("--policy", default=DEFAULT_POLICY_PATH, help="Boundary policy YAML path")
    args = parser.parse_args(argv)

    verdict = validate_manifest(args.manifest, schema_path=args.schema, policy_path=args.policy)
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict.get("allow") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
