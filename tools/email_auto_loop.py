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
from kernel.channels.email import emit_email_artifact


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


def _parse_poll_artifacts(raw: str) -> list[str]:
    if not raw.strip():
        return []
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return []
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    out: list[str] = []
    for item in artifacts:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _load_seen(path: Path) -> set[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict) or not isinstance(payload.get("seen"), list):
        return set()
    return {str(v).strip() for v in payload["seen"] if isinstance(v, str) and str(v).strip()}


def _save_seen(path: Path, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep bounded state file while preserving determinism.
    selected = sorted(seen)[-5000:]
    path.write_text(json.dumps({"seen": selected}, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _emit_new_artifacts(
    *,
    artifacts: list[str],
    seen_path: Path,
    registry_path: str,
    config_path: str,
    audit_log_path: str,
) -> dict[str, object]:
    seen = _load_seen(seen_path)
    emitted = 0
    skipped_seen = 0
    new_artifacts: list[str] = []
    for artifact in artifacts:
        normalized = str(Path(artifact))
        if normalized in seen:
            skipped_seen += 1
            continue
        emit_email_artifact(
            normalized,
            registry_path=registry_path,
            config_path=config_path,
            audit_log_path=audit_log_path,
        )
        seen.add(normalized)
        new_artifacts.append(normalized)
        emitted += 1
    _save_seen(seen_path, seen)
    return {"emitted": emitted, "skipped_seen": skipped_seen, "new_artifacts": len(new_artifacts), "artifacts": new_artifacts}


def _run_kick_script(*, script_path: str, artifact_path: str, timeout_seconds: int) -> tuple[bool, str]:
    proc = subprocess.run(
        [script_path, artifact_path],
        capture_output=True,
        text=True,
        timeout=max(10, int(timeout_seconds)),
    )
    detail = (proc.stdout.strip() or proc.stderr.strip() or f"exit={proc.returncode}")[:500]
    return (proc.returncode == 0), detail


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
    parser.add_argument("--registry-path", default="state/plugins/registry.json")
    parser.add_argument("--config-path", default="state/plugins/config.json")
    parser.add_argument("--event-audit-log-path", default="logs/control/kernel-events.jsonl")
    parser.add_argument("--seen-state-path", default="runtime/channels/email_gateway/bridge_seen.json")
    parser.add_argument("--kick-script", default="")
    parser.add_argument("--kick-timeout-seconds", type=int, default=900)
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
        artifacts = _parse_poll_artifacts(poll_out) if poll_code == 0 else []
        bridge_stats = _emit_new_artifacts(
            artifacts=artifacts,
            seen_path=Path(args.seen_state_path),
            registry_path=args.registry_path,
            config_path=args.config_path,
            audit_log_path=args.event_audit_log_path,
        )
        kicks_started = 0
        kicks_failed = 0
        kick_details: list[str] = []
        kick_script = args.kick_script.strip()
        if kick_script:
            for artifact_path in bridge_stats.get("artifacts", []):
                kicks_started += 1
                ok, detail = _run_kick_script(
                    script_path=kick_script,
                    artifact_path=str(artifact_path),
                    timeout_seconds=args.kick_timeout_seconds,
                )
                if not ok:
                    kicks_failed += 1
                if detail:
                    kick_details.append(detail)

        status = {
            "poll_code": poll_code,
            "poll_out": poll_out,
            "poll_err": poll_err,
            "send_code": send_code,
            "send_out": send_out,
            "send_err": send_err,
            "mail_artifacts": len(artifacts),
            "events_emitted": bridge_stats["emitted"],
            "events_skipped_seen": bridge_stats["skipped_seen"],
            "kicks_started": kicks_started,
            "kicks_failed": kicks_failed,
            "kick_details": kick_details,
            "agent": args.agent,
        }
        print(json.dumps(status, ensure_ascii=True, sort_keys=True), flush=True)

        if args.once:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
