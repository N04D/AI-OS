from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from aios.secrets.context import ContextFactory
from aios.secrets.manager import SecretsManager
from aios.secrets.types import SecretKey
from supervisor.channels.transports import SMTPTransportAdapter


LOGGER = logging.getLogger("mail_worker")
TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, OSError)


@dataclass
class WorkerSummary:
    processed: int = 0
    sent: int = 0
    failed: int = 0
    retried: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "processed": self.processed,
            "sent": self.sent,
            "failed": self.failed,
            "retried": self.retried,
        }


class MailWorker:
    def __init__(
        self,
        *,
        workspace_root: Path,
        transport: SMTPTransportAdapter | None = None,
        max_retries: int = 3,
        secret_provider: Callable[[], str] | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.transport = transport or SMTPTransportAdapter()
        self.max_retries = max(1, int(max_retries))
        self._secret_provider = secret_provider or self._load_smtp_password

    def run_once(self, *, agent: str | None = None) -> WorkerSummary:
        summary = WorkerSummary()
        for outbox_file in self._iter_outbox(agent=agent):
            summary.processed += 1
            try:
                self._process_single(outbox_file, summary)
            except Exception as exc:  # pragma: no cover - defensive catch
                summary.failed += 1
                LOGGER.error(
                    "mail_worker_message_crash id=%s error=%s",
                    outbox_file.stem,
                    exc.__class__.__name__,
                )
        return summary

    def poll_inbox(self, *, agent: str | None = None) -> dict[str, str]:
        del agent
        if not (os.environ.get("IMAP_HOST", "").strip() and os.environ.get("IMAP_USER", "").strip()):
            return {"status": "noop", "reason": "imap_not_configured"}
        return {"status": "noop", "reason": "imap_scaffold_only"}

    def _iter_outbox(self, *, agent: str | None) -> list[Path]:
        if agent:
            self._ensure_mail_dirs(agent)
            return sorted((self.workspace_root / agent / "mail" / "outbox").glob("*.json"))

        out: list[Path] = []
        if not self.workspace_root.exists():
            return out
        for agent_root in sorted(self.workspace_root.iterdir()):
            if not agent_root.is_dir():
                continue
            self._ensure_mail_dirs(agent_root.name)
            out.extend(sorted((agent_root / "mail" / "outbox").glob("*.json")))
        return out

    def _ensure_mail_dirs(self, agent: str) -> None:
        mail_root = self.workspace_root / agent / "mail"
        for sub in ("inbox", "outbox", "sent", "failed"):
            path = mail_root / sub
            path.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass

    def _load_smtp_password(self) -> str:
        secret_key = SecretKey.parse((os.environ.get("SMTP_PASS_SECRET_KEY", "smtp.pass") or "smtp.pass").strip())
        data_dir_raw = (os.environ.get("AIOS_SECRETS_DATA_DIR", "") or "").strip()
        fallback_passphrase = (os.environ.get("AIOS_SECRETS_FALLBACK_PASSPHRASE", "") or "").strip() or None
        manager = SecretsManager(data_dir=Path(data_dir_raw) if data_dir_raw else None, fallback_passphrase=fallback_passphrase)
        context = ContextFactory.supervisor_mail_worker_transport(
            agent_id="mail_worker",
            epoch_id=datetime.now(UTC).strftime("%Y-%m-%d"),
        )
        value = manager.get(secret_key, context=context)
        if value is None:
            raise RuntimeError("smtp_pass_secret_missing")
        return value.as_str()

    def _process_single(self, outbox_path: Path, summary: WorkerSummary) -> None:
        payload = self._read_json(outbox_path)
        attempts = int(payload.get("attempts", 0))
        message_id = str(payload.get("id", outbox_path.stem))

        try:
            smtp_password = self._secret_provider()
        except Exception as exc:
            self._mark_failed(
                outbox_path,
                payload,
                attempts=attempts + 1,
                error_code="secrets_unavailable",
            )
            summary.failed += 1
            LOGGER.error("mail_worker_secrets_error id=%s error=%s", message_id, exc.__class__.__name__)
            return

        host = (os.environ.get("SMTP_HOST", "") or "").strip()
        port = int((os.environ.get("SMTP_PORT", "587") or "587").strip())
        username = (os.environ.get("SMTP_USER", "") or "").strip()
        from_addr = (os.environ.get("SMTP_FROM", "") or username).strip()

        if not host or not username or not from_addr:
            self._mark_failed(
                outbox_path,
                payload,
                attempts=attempts + 1,
                error_code="smtp_config_missing",
            )
            summary.failed += 1
            LOGGER.error("mail_worker_config_error id=%s error=smtp_config_missing", message_id)
            return

        to_addr = str(payload.get("to", ""))
        subject = str(payload.get("subject", ""))
        body = str(payload.get("body", ""))

        try:
            self.transport.send_mail(
                host=host,
                port=port,
                username=username,
                password=smtp_password,
                from_addr=from_addr,
                to_addr=to_addr,
                subject=subject,
                body=body,
            )
            sent_payload = dict(payload)
            sent_payload["status"] = "sent"
            sent_payload["attempts"] = attempts + 1
            sent_payload["sent_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            self._move_to_bucket(outbox_path, "sent", sent_payload)
            summary.sent += 1
            LOGGER.info("mail_worker_sent id=%s attempts=%s", message_id, attempts + 1)
            return
        except TRANSIENT_EXCEPTIONS as exc:
            next_attempt = attempts + 1
            if next_attempt < self.max_retries:
                pending = dict(payload)
                pending["status"] = "pending"
                pending["attempts"] = next_attempt
                pending["last_error"] = exc.__class__.__name__
                self._write_json(outbox_path, pending)
                summary.retried += 1
                LOGGER.warning("mail_worker_retry id=%s attempts=%s error=%s", message_id, next_attempt, exc.__class__.__name__)
                return
            self._mark_failed(
                outbox_path,
                payload,
                attempts=next_attempt,
                error_code=exc.__class__.__name__,
            )
            summary.failed += 1
            LOGGER.error("mail_worker_failed id=%s attempts=%s error=%s", message_id, next_attempt, exc.__class__.__name__)
            return
        except Exception as exc:
            self._mark_failed(
                outbox_path,
                payload,
                attempts=attempts + 1,
                error_code=exc.__class__.__name__,
            )
            summary.failed += 1
            LOGGER.error("mail_worker_failed id=%s attempts=%s error=%s", message_id, attempts + 1, exc.__class__.__name__)

    def _mark_failed(self, outbox_path: Path, payload: dict[str, Any], *, attempts: int, error_code: str) -> None:
        failed = dict(payload)
        failed["status"] = "failed"
        failed["attempts"] = attempts
        failed["error"] = error_code
        self._move_to_bucket(outbox_path, "failed", failed)

    def _move_to_bucket(self, source: Path, bucket: str, payload: dict[str, Any]) -> None:
        target_dir = source.parent.parent / bucket
        target = target_dir / source.name
        self._write_json(target, payload)
        try:
            source.unlink(missing_ok=True)
        except TypeError:
            if source.exists():
                source.unlink()

    def _read_json(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("outbox_payload_not_object")
        return data

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=path.stem + ".", suffix=".tmp", delete=False) as fh:
            fh.write(serialized)
            fh.flush()
            os.fsync(fh.fileno())
            temp_name = fh.name
        os.replace(temp_name, path)
        os.chmod(path, 0o600)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mail_worker", description="Process workspace mail outbox and deliver via SMTP")
    parser.add_argument("--workspace-root", default="workspace")
    parser.add_argument("--agent", default="")
    parser.add_argument("--max-retries", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = _build_parser().parse_args(argv)
    worker = MailWorker(workspace_root=Path(args.workspace_root), max_retries=args.max_retries)
    summary = worker.run_once(agent=args.agent.strip() or None)
    print(json.dumps({"status": "ok", **summary.to_dict()}, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
