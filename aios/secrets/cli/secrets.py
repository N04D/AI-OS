from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import sys
from typing import Any

from ..context import ContextFactory
from ..manager import SecretsManager
from ..redaction import redact
from ..types import SecretKey
from ..types import SecretValue
from ..types import SecretsError


def _manager_from_args(args: argparse.Namespace) -> SecretsManager:
    data_dir = Path(args.secrets_data_dir) if getattr(args, "secrets_data_dir", "") else None
    return SecretsManager(data_dir=data_dir)


def _ensure_fallback_passphrase(manager: SecretsManager) -> None:
    status = manager.status()
    if status.get("backend") == "encrypted_store":
        manager.set_fallback_passphrase(getpass("Fallback passphrase: "))


def _read_secret_value(args: argparse.Namespace) -> str:
    if args.from_stdin:
        return sys.stdin.read().rstrip("\n")
    first = getpass("Secret value: ")
    second = getpass("Repeat value: ")
    if first != second:
        raise SecretsError("Secret confirmation mismatch")
    if not first:
        raise SecretsError("Secret value must not be empty")
    return first


def _cmd_status(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    return 0, {"status": "ok", **mgr.status()}, "secrets"


def _cmd_init_fallback(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    p1 = getpass("New fallback passphrase: ")
    p2 = getpass("Repeat fallback passphrase: ")
    if p1 != p2:
        raise SecretsError("Passphrases do not match")
    mgr.init_fallback(p1)
    return 0, {"status": "ok", "message": "fallback initialized"}, "secrets"


def _cmd_set(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    _ensure_fallback_passphrase(mgr)
    key = SecretKey.parse(args.key)
    value = _read_secret_value(args)
    mgr.set(key, SecretValue(value), overwrite=bool(args.overwrite))
    payload = {
        "status": "ok",
        "key": key.as_str(),
        "backend": mgr.status().get("backend"),
        "notice": mgr.status().get("last_error"),
    }
    return 0, payload, "secrets"


def _cmd_get(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    _ensure_fallback_passphrase(mgr)
    key = SecretKey.parse(args.key)
    value = mgr.get(key, context=ContextFactory.interactive_cli())
    payload: dict[str, Any] = {
        "status": "ok",
        "key": key.as_str(),
        "stored": value is not None,
        "value_redacted": redact(value.as_str()) if value is not None else None,
    }
    if value is not None and args.show and not bool(getattr(args, "json", False)):
        print(value.as_str())
    return 0, payload, "secrets"


def _cmd_delete(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    _ensure_fallback_passphrase(mgr)
    key = SecretKey.parse(args.key)
    mgr.delete(key)
    return 0, {"status": "ok", "key": key.as_str()}, "secrets"


def _cmd_list(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    _ensure_fallback_passphrase(mgr)
    keys = mgr.list(prefix=args.prefix)
    return 0, {"status": "ok", "keys": [k.as_str() for k in keys]}, "secrets"


def _cmd_rotate_passphrase(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    old = getpass("Current fallback passphrase: ")
    new_1 = getpass("New fallback passphrase: ")
    new_2 = getpass("Repeat new fallback passphrase: ")
    if new_1 != new_2:
        raise SecretsError("Passphrases do not match")
    mgr.rotate_fallback_passphrase(old, new_1)
    return 0, {"status": "ok", "message": "fallback passphrase rotated"}, "secrets"


def _cmd_migrate(args: argparse.Namespace) -> tuple[int, dict[str, Any], str]:
    mgr = _manager_from_args(args)
    if mgr.status().get("fallback_initialized"):
        mgr.set_fallback_passphrase(getpass("Fallback passphrase: "))
    report = mgr.migrate_to_keyring()
    return 0, {"status": "ok", **report}, "secrets"


def add_secrets_subparser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    secrets = subparsers.add_parser("secrets", help="Manage secure secrets storage")
    secrets.add_argument(
        "--secrets-data-dir",
        default="",
        help="Override secrets state directory (default: ~/.local/share/aios/secrets)",
    )
    secrets_sub = secrets.add_subparsers(dest="secrets_command", required=True)

    status = secrets_sub.add_parser("status", help="Show backend and initialization status")
    status.set_defaults(handler=_cmd_status)

    init = secrets_sub.add_parser("init-fallback", help="Initialize encrypted fallback store")
    init.set_defaults(handler=_cmd_init_fallback)

    set_cmd = secrets_sub.add_parser("set", help="Set secret value")
    set_cmd.add_argument("key")
    set_cmd.add_argument("--from-stdin", action="store_true")
    set_cmd.add_argument("--overwrite", action="store_true")
    set_cmd.set_defaults(handler=_cmd_set)

    get_cmd = secrets_sub.add_parser("get", help="Get secret status/value")
    get_cmd.add_argument("key")
    get_cmd.add_argument("--show", action="store_true", help="Print plaintext to terminal")
    get_cmd.set_defaults(handler=_cmd_get)

    delete_cmd = secrets_sub.add_parser("delete", help="Delete a secret")
    delete_cmd.add_argument("key")
    delete_cmd.set_defaults(handler=_cmd_delete)

    list_cmd = secrets_sub.add_parser("list", help="List available secret keys")
    list_cmd.add_argument("--prefix", default=None)
    list_cmd.set_defaults(handler=_cmd_list)

    rotate = secrets_sub.add_parser("rotate-passphrase", help="Rotate encrypted fallback passphrase")
    rotate.set_defaults(handler=_cmd_rotate_passphrase)

    migrate = secrets_sub.add_parser("migrate-to-keyring", help="Migrate fallback secrets into OS keyring")
    migrate.set_defaults(handler=_cmd_migrate)
