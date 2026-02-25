#!/usr/bin/env python3
"""Operator CLI for plugin config state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kernel.audit import AuditWriteError
from kernel.audit import append_plugin_event
from kernel.plugins.config import PluginConfigError
from kernel.plugins.config import load_config
from kernel.plugins.config import save_config_atomic
from kernel.plugins.config import set_enabled
from kernel.plugins.registry import PluginRegistryError
from kernel.plugins.registry import get_plugin
from kernel.plugins.registry import list_plugins_sorted
from kernel.plugins.registry import load_registry


def _print_result(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True))


def cmd_list(args: argparse.Namespace) -> int:
    try:
        registry = load_registry(args.registry_path)
        config = load_config(args.config_path)
    except (PluginRegistryError, PluginConfigError) as exc:
        _print_result({"ok": False, "reason_code": str(exc)})
        return 1

    enabled_set = set(config["enabled"])
    unsafe = config.get("unsafe_allow_external", False) is True

    print("plugin_id | version | trust_tier | enabled_effective")
    for entry in list_plugins_sorted(registry):
        plugin_id = str(entry.get("plugin_id"))
        trust = str(entry.get("trust_tier"))
        enabled_effective = plugin_id in enabled_set and (trust != "external" or unsafe)
        row = f"{plugin_id} | {entry.get('version')} | {trust} | {'true' if enabled_effective else 'false'}"
        print(row)
    return 0


def _audit_then_save(
    *,
    action: str,
    result: str,
    reason_code: str,
    details: list[str],
    plugin_id: str | None,
    trust_tier: str | None,
    audit_log_path: str,
    config_path: str,
    config: dict | None,
) -> int:
    try:
        append_plugin_event(
            action=action,
            result=result,
            reason_code=reason_code,
            details=details,
            plugin_id=plugin_id,
            trust_tier=trust_tier,
            audit_log_path=audit_log_path,
        )
    except AuditWriteError:
        _print_result({"ok": False, "reason_code": "AUDIT_LOG_WRITE_FAILED"})
        return 1

    if result == "ok" and config is not None:
        try:
            save_config_atomic(config_path, config)
        except PluginConfigError as exc:
            _print_result({"ok": False, "reason_code": str(exc)})
            return 1
    _print_result({"ok": result == "ok", "reason_code": reason_code})
    return 0 if result == "ok" else 1


def cmd_enable(args: argparse.Namespace) -> int:
    plugin_id = args.plugin_id
    try:
        registry = load_registry(args.registry_path)
        config = load_config(args.config_path)
    except (PluginRegistryError, PluginConfigError) as exc:
        _print_result({"ok": False, "reason_code": str(exc)})
        return 1

    entry = get_plugin(registry, plugin_id)
    if entry is None:
        return _audit_then_save(
            action="enable",
            result="deny",
            reason_code="PLUGIN_NOT_DISCOVERED",
            details=[],
            plugin_id=plugin_id,
            trust_tier=None,
            audit_log_path=args.audit_log_path,
            config_path=args.config_path,
            config=None,
        )

    trust_tier = str(entry.get("trust_tier"))
    unsafe = config.get("unsafe_allow_external", False) is True
    if trust_tier == "external" and not unsafe:
        return _audit_then_save(
            action="enable",
            result="deny",
            reason_code="EXTERNAL_NOT_ALLOWED",
            details=[],
            plugin_id=plugin_id,
            trust_tier=trust_tier,
            audit_log_path=args.audit_log_path,
            config_path=args.config_path,
            config=None,
        )

    new_config = set_enabled(config, plugin_id, True)
    return _audit_then_save(
        action="enable",
        result="ok",
        reason_code="OK",
        details=[],
        plugin_id=plugin_id,
        trust_tier=trust_tier,
        audit_log_path=args.audit_log_path,
        config_path=args.config_path,
        config=new_config,
    )


def cmd_disable(args: argparse.Namespace) -> int:
    plugin_id = args.plugin_id
    try:
        registry = load_registry(args.registry_path)
        config = load_config(args.config_path)
    except (PluginRegistryError, PluginConfigError) as exc:
        _print_result({"ok": False, "reason_code": str(exc)})
        return 1

    entry = get_plugin(registry, plugin_id)
    trust_tier = str(entry.get("trust_tier")) if isinstance(entry, dict) else None
    was_enabled = plugin_id in set(config.get("enabled", []))
    details = [] if was_enabled else ["plugin_was_not_enabled"]
    new_config = set_enabled(config, plugin_id, False)
    return _audit_then_save(
        action="disable",
        result="ok",
        reason_code="OK",
        details=details,
        plugin_id=plugin_id,
        trust_tier=trust_tier,
        audit_log_path=args.audit_log_path,
        config_path=args.config_path,
        config=new_config,
    )


def cmd_set_unsafe_external(args: argparse.Namespace) -> int:
    raw = args.value.lower().strip()
    if raw not in {"true", "false"}:
        _print_result({"ok": False, "reason_code": "INVALID_BOOLEAN"})
        return 1
    try:
        config = load_config(args.config_path)
    except PluginConfigError as exc:
        _print_result({"ok": False, "reason_code": str(exc)})
        return 1

    new_config = dict(config)
    new_config["unsafe_allow_external"] = raw == "true"
    return _audit_then_save(
        action="set_unsafe_external",
        result="ok",
        reason_code="OK",
        details=[],
        plugin_id=None,
        trust_tier=None,
        audit_log_path=args.audit_log_path,
        config_path=args.config_path,
        config=new_config,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-OS plugin operator CLI")
    parser.add_argument("--registry-path", default="state/plugins/registry.json")
    parser.add_argument("--config-path", default="state/plugins/config.json")
    parser.add_argument("--audit-log-path", default="logs/control/plugin-events.jsonl")

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")

    p_enable = sub.add_parser("enable")
    p_enable.add_argument("plugin_id")

    p_disable = sub.add_parser("disable")
    p_disable.add_argument("plugin_id")

    p_unsafe = sub.add_parser("set-unsafe-external")
    p_unsafe.add_argument("value")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "enable":
        return cmd_enable(args)
    if args.cmd == "disable":
        return cmd_disable(args)
    if args.cmd == "set-unsafe-external":
        return cmd_set_unsafe_external(args)
    _print_result({"ok": False, "reason_code": "UNKNOWN_COMMAND"})
    return 1


if __name__ == "__main__":
    sys.exit(main())
