from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.types import SecretKey


def _load_secret(secret_key: str) -> str:
    manager = SecretsManager()
    key = SecretKey.parse(secret_key)
    value = manager.get(
        key,
        context=ContextFactory.supervisor_mail_worker_transport(
            agent_id="email_auto_loop",
        ),
    )
    if value is None or not value.as_str().strip():
        raise RuntimeError(f"Missing secret: {secret_key}")
    return value.as_str().strip()


def _run(cmd: list[str], *, env: dict[str, str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email_auto_loop",
        description="Automatic email loop: poll inbox + process outbox continuously.",
    )
    parser.add_argument("--agent", default="codex")
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--max-messages", type=int, default=25)
    parser.add_argument("--seen-mode", default="unseen", choices=["unseen", "seen", "all"])
    parser.add_argument("--from-contains", default="")
    parser.add_argument("--subject-contains", default="")
    parser.add_argument("--workspace-root", default="workspace")
    parser.add_argument("--smtp-host", default="smtp.gmail.com")
    parser.add_argument("--smtp-port", type=int, default=587)
    parser.add_argument("--smtp-user", required=True)
    parser.add_argument("--smtp-from", default="")
    parser.add_argument("--imap-host", default="imap.gmail.com")
    parser.add_argument("--imap-port", type=int, default=993)
    parser.add_argument("--imap-user", default="")
    parser.add_argument("--smtp-pass-secret-key", default="smtp.pass")
    parser.add_argument("--once", action="store_true")
    return parser


def _poll(env: dict[str, str], args: argparse.Namespace) -> tuple[int, str, str]:
    cmd = [
        "./tools/email_safe_run.sh",
        "poll",
        "--json",
        "--agent",
        args.agent,
        "--max",
        str(args.max_messages),
        "--seen-mode",
        args.seen_mode,
    ]
    if args.from_contains.strip():
        cmd.extend(["--from-contains", args.from_contains.strip()])
    if args.subject_contains.strip():
        cmd.extend(["--subject-contains", args.subject_contains.strip()])
    return _run(cmd, env=env)


def _send(env: dict[str, str], args: argparse.Namespace) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "-m",
        "tools.mail_worker",
        "--workspace-root",
        args.workspace_root,
        "--agent",
        args.agent,
    ]
    return _run(cmd, env=env)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    smtp_from = args.smtp_from.strip() or args.smtp_user.strip()
    imap_user = args.imap_user.strip() or args.smtp_user.strip()

    if args.interval_seconds < 5:
        raise SystemExit("interval-seconds must be >= 5")

    while True:
        smtp_pass = _load_secret(args.smtp_pass_secret_key)
        env = dict(os.environ)
        env.update(
            {
                "SMTP_HOST": args.smtp_host,
                "SMTP_PORT": str(args.smtp_port),
                "SMTP_USER": args.smtp_user.strip(),
                "SMTP_FROM": smtp_from,
                "SMTP_PASS": smtp_pass,
                "IMAP_HOST": args.imap_host,
                "IMAP_PORT": str(args.imap_port),
                "IMAP_USER": imap_user,
                "IMAP_PASS": smtp_pass,
            }
        )

        poll_code, poll_out, poll_err = _poll(env, args)
        send_code, send_out, send_err = _send(env, args)

        status = {
            "poll_code": poll_code,
            "poll_out": poll_out,
            "poll_err": poll_err,
            "send_code": send_code,
            "send_out": send_out,
            "send_err": send_err,
            "agent": args.agent,
        }
        print(json.dumps(status, ensure_ascii=True, sort_keys=True), flush=True)

        if args.once:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
