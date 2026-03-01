from __future__ import annotations

import hashlib
import json
import os
import re
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from supervisor.channels.policy import DENY_POLICY_INVALID
from supervisor.channels.policy import DENY_POLICY_MISSING
from supervisor.channels.policy import PolicyError
from supervisor.channels.policy import load_email_config
from supervisor.channels.policy import load_email_policy
from supervisor.channels.transports import IMAPTransportAdapter
from supervisor.channels.transports import SMTPTransportAdapter


DENY_AGENT_NOT_REGISTERED = "DENY_AGENT_NOT_REGISTERED"
DENY_AGENT_CHANNEL_DISABLED = "DENY_AGENT_CHANNEL_DISABLED"
DENY_CAPABILITY_MISSING = "DENY_CAPABILITY_MISSING"
DENY_ADDRESS_NOT_ALLOWED = "DENY_ADDRESS_NOT_ALLOWED"
DENY_DOMAIN_NOT_ALLOWED = "DENY_DOMAIN_NOT_ALLOWED"
DENY_BODY_TOO_LARGE = "DENY_BODY_TOO_LARGE"
DENY_REPLY_NOT_ALLOWED = "DENY_REPLY_NOT_ALLOWED"

DEFAULT_EMAIL_CONFIG_PATH = Path("config/channels/email_gateway.json")
DEFAULT_EMAIL_POLICY_PATH = Path("governance/policy/email_gateway.v0.1.json")
DEFAULT_CAPABILITY_LEDGER_PATH = Path("state/supervisor_capabilities.json")
DEFAULT_CAPABILITY_DENYLIST_PATH = Path("state/supervisor_capability_denies.json")
DEFAULT_OUTBOX_ROOT = Path("runtime/channels/email_gateway/outbox")
DEFAULT_INBOX_ROOT = Path("runtime/channels/email_gateway/inbox")
DEFAULT_AUDIT_PATH = Path("logs/control/email_gateway_audit.jsonl")


class EmailGatewayError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _safe_epoch(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return "epoch-unknown"
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", normalized):
        raise EmailGatewayError(DENY_POLICY_INVALID, "epoch contains unsupported characters")
    return normalized


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _append_audit(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(_canonical_json(payload) + "\n")


def _artifact_name(epoch: str, agent: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{epoch}__{agent}__{digest}.json"


def _extract_domain(address: str) -> str:
    _, parsed = parseaddr(address)
    value = parsed.strip().lower()
    if "@" not in value:
        return ""
    return value.rsplit("@", 1)[1]


def _normalize_address(address: str) -> str:
    _, parsed = parseaddr(address)
    return parsed.strip().lower()


def _assert_agent_enabled(config: dict[str, Any], agent: str) -> None:
    if not bool(config.get("enabled", False)):
        raise EmailGatewayError(DENY_AGENT_CHANNEL_DISABLED, "email gateway module disabled")
    agent_cfg = (config.get("agents") or {}).get(agent)
    if not isinstance(agent_cfg, dict):
        raise EmailGatewayError(DENY_AGENT_NOT_REGISTERED, f"unknown agent: {agent}")
    if not bool(agent_cfg.get("enabled", False)):
        raise EmailGatewayError(DENY_AGENT_CHANNEL_DISABLED, f"agent channel disabled: {agent}")


def _assert_capability(repo_root: Path, capability: str) -> None:
    ledger_path = repo_root / DEFAULT_CAPABILITY_LEDGER_PATH
    if not ledger_path.exists():
        raise EmailGatewayError(DENY_CAPABILITY_MISSING, f"capability ledger missing: {ledger_path}")
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EmailGatewayError(DENY_CAPABILITY_MISSING, f"invalid capability ledger: {ledger_path}") from exc
    if not isinstance(ledger, dict):
        raise EmailGatewayError(DENY_CAPABILITY_MISSING, f"invalid capability ledger payload: {ledger_path}")
    entry = ledger.get(capability)
    allowed = False
    if isinstance(entry, dict):
        allowed = bool(entry.get("granted", False))
    elif isinstance(entry, bool):
        allowed = entry
    if not allowed:
        raise EmailGatewayError(DENY_CAPABILITY_MISSING, f"capability not granted: {capability}")


def _assert_policy_allow(policy: dict[str, Any], *, agent: str, direction: str, address: str, body: str) -> None:
    agent_policy = (policy.get("agents") or {}).get(agent)
    if not isinstance(agent_policy, dict):
        raise EmailGatewayError(DENY_ADDRESS_NOT_ALLOWED, f"missing policy for agent: {agent}")

    max_body_bytes = int(agent_policy.get("max_body_bytes", 65536))
    if len(body.encode("utf-8")) > max_body_bytes:
        raise EmailGatewayError(DENY_BODY_TOO_LARGE, f"body exceeds max bytes: {max_body_bytes}")

    normalized = _normalize_address(address)
    domain = _extract_domain(address)
    if direction == "send":
        allowlist = set(str(v).lower() for v in agent_policy.get("send_allowlist", []))
    else:
        allowlist = set(str(v).lower() for v in agent_policy.get("receive_allowlist", []))
    if normalized and normalized in allowlist:
        return

    domain_allowlist = set(str(v).lower() for v in agent_policy.get("domains_allowlist", []))
    if domain_allowlist:
        if domain and domain in domain_allowlist:
            return
        raise EmailGatewayError(DENY_DOMAIN_NOT_ALLOWED, f"domain not allowed: {domain or '<empty>'}")

    raise EmailGatewayError(DENY_ADDRESS_NOT_ALLOWED, f"address not allowed: {normalized or '<empty>'}")


def _is_reply_subject(subject: str) -> bool:
    return subject.strip().lower().startswith("re:")


def _assert_reply_policy_allow(policy: dict[str, Any], *, agent: str, to: str, subject: str) -> None:
    if not _is_reply_subject(subject):
        return
    agent_policy = (policy.get("agents") or {}).get(agent)
    if not isinstance(agent_policy, dict):
        raise EmailGatewayError(DENY_REPLY_NOT_ALLOWED, f"missing policy for agent: {agent}")
    reply_policy = agent_policy.get("reply_policy")
    if not isinstance(reply_policy, dict) or not bool(reply_policy.get("enabled", False)):
        raise EmailGatewayError(DENY_REPLY_NOT_ALLOWED, "reply policy disabled")
    normalized_to = _normalize_address(to)
    allowed = set(str(v).lower() for v in reply_policy.get("allowed_senders", []))
    if normalized_to not in allowed:
        raise EmailGatewayError(DENY_REPLY_NOT_ALLOWED, f"reply recipient not allowed: {normalized_to or '<empty>'}")
    if bool(reply_policy.get("require_subject_match", False)):
        remainder = subject.strip()[3:].strip()
        if not remainder:
            raise EmailGatewayError(DENY_REPLY_NOT_ALLOWED, "reply subject missing thread content")


def _load_config_and_policy(repo_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        config = load_email_config(repo_root / DEFAULT_EMAIL_CONFIG_PATH)
        policy = load_email_policy(repo_root / DEFAULT_EMAIL_POLICY_PATH)
    except PolicyError as exc:
        raise EmailGatewayError(exc.reason_code, exc.detail) from exc
    return config, policy


def _append_deny_audit(
    *,
    repo_root: Path,
    action: str,
    agent: str,
    epoch: str,
    reason_code: str,
    detail: str,
    target: str = "",
) -> None:
    payload = {
        "action": action,
        "agent": agent,
        "epoch": epoch,
        "reason_code": reason_code,
        "status": "rejected",
        "reason": detail,
    }
    if target:
        if action == "send":
            payload["to"] = target
        elif action == "poll":
            payload["from"] = target
    _append_audit(repo_root / DEFAULT_AUDIT_PATH, payload)


def send_email_direct(
    *,
    repo_root: Path,
    agent: str,
    to: str,
    subject: str,
    body: str,
    epoch: str = "",
    transport: SMTPTransportAdapter | None = None,
) -> dict[str, Any]:
    safe_epoch = _safe_epoch(epoch or os.environ.get("AIOS_EPOCH", ""))
    try:
        config, policy = _load_config_and_policy(repo_root)
        _assert_agent_enabled(config, agent)
        _assert_capability(repo_root, "email.send")
        _assert_policy_allow(policy, agent=agent, direction="send", address=to, body=body)
        _assert_reply_policy_allow(policy, agent=agent, to=to, subject=subject)
    except EmailGatewayError as exc:
        _append_deny_audit(
            repo_root=repo_root,
            action="send",
            agent=agent,
            epoch=safe_epoch,
            reason_code=exc.reason_code,
            detail=exc.detail,
            target=_normalize_address(to),
        )
        raise

    smtp_host = (os.environ.get("SMTP_HOST", "") or "").strip()
    smtp_port = int((os.environ.get("SMTP_PORT", "587") or "587").strip())
    smtp_user = (os.environ.get("SMTP_USER", "") or "").strip()
    smtp_pass = (os.environ.get("SMTP_PASS", "") or "").strip()
    smtp_from = (os.environ.get("SMTP_FROM", "") or smtp_user).strip()

    adapter = transport or SMTPTransportAdapter()
    result = adapter.send_mail(
        host=smtp_host,
        port=smtp_port,
        username=smtp_user,
        password=smtp_pass,
        from_addr=smtp_from,
        to_addr=to,
        subject=subject,
        body=body,
    )

    record = {
        "action": "send",
        "agent": agent,
        "to": _normalize_address(to),
        "subject": subject,
        "body": body,
        "epoch": safe_epoch,
        "result": dict(sorted((result or {}).items())),
    }
    artifact_name = _artifact_name(safe_epoch, agent, record)
    artifact_path = repo_root / DEFAULT_OUTBOX_ROOT / agent / artifact_name
    _write_json(artifact_path, record)

    audit = {
        "action": "send",
        "agent": agent,
        "artifact": str(artifact_path.relative_to(repo_root)),
        "epoch": safe_epoch,
        "reason_code": "ALLOW",
        "status": "ok",
        "to": _normalize_address(to),
    }
    _append_audit(repo_root / DEFAULT_AUDIT_PATH, audit)
    return {
        "status": "ok",
        "agent": agent,
        "to": _normalize_address(to),
        "artifact_path": str(artifact_path),
        "audit_path": str((repo_root / DEFAULT_AUDIT_PATH)),
        "result": dict(sorted((result or {}).items())),
    }


def poll_email_direct(
    *,
    repo_root: Path,
    agent: str,
    max_messages: int,
    epoch: str = "",
    from_contains: str = "",
    subject_contains: str = "",
    seen_mode: str = "unseen",
    transport: IMAPTransportAdapter | None = None,
) -> dict[str, Any]:
    safe_epoch = _safe_epoch(epoch or os.environ.get("AIOS_EPOCH", ""))
    try:
        config, policy = _load_config_and_policy(repo_root)
        _assert_agent_enabled(config, agent)
        _assert_capability(repo_root, "email.poll")
        if max_messages < 1:
            raise EmailGatewayError(DENY_POLICY_INVALID, "max_messages must be >= 1")
        if seen_mode not in {"unseen", "seen", "all"}:
            raise EmailGatewayError(DENY_POLICY_INVALID, "seen_mode must be one of: unseen, seen, all")
    except EmailGatewayError as exc:
        _append_deny_audit(
            repo_root=repo_root,
            action="poll",
            agent=agent,
            epoch=safe_epoch,
            reason_code=exc.reason_code,
            detail=exc.detail,
        )
        raise

    imap_host = (os.environ.get("IMAP_HOST", "") or "").strip()
    imap_port = int((os.environ.get("IMAP_PORT", "993") or "993").strip())
    imap_user = (os.environ.get("IMAP_USER", "") or "").strip()
    imap_pass = (os.environ.get("IMAP_PASS", "") or "").strip()

    adapter = transport or IMAPTransportAdapter()
    unseen = adapter.poll_unseen(
        host=imap_host,
        port=imap_port,
        username=imap_user,
        password=imap_pass,
        max_messages=max_messages,
        seen_mode=seen_mode,
    )

    from_filter = from_contains.strip().lower()
    subject_filter = subject_contains.strip().lower()
    if from_filter:
        unseen = [item for item in unseen if from_filter in str(item.get("from", "")).lower()]
    if subject_filter:
        unseen = [item for item in unseen if subject_filter in str(item.get("subject", "")).lower()]

    written: list[str] = []
    seen_uids: list[str] = []
    for item in unseen:
        from_addr = str(item.get("from", ""))
        body = str(item.get("body", ""))
        try:
            _assert_policy_allow(policy, agent=agent, direction="receive", address=from_addr, body=body)
        except EmailGatewayError as exc:
            _append_deny_audit(
                repo_root=repo_root,
                action="poll",
                agent=agent,
                epoch=safe_epoch,
                reason_code=exc.reason_code,
                detail=exc.detail,
                target=_normalize_address(from_addr),
            )
            continue
        record = {
            "action": "poll",
            "agent": agent,
            "from": _normalize_address(from_addr),
            "to": _normalize_address(str(item.get("to", ""))),
            "subject": str(item.get("subject", "")),
            "body": body,
            "epoch": safe_epoch,
            "uid": str(item.get("uid", "")),
        }
        artifact_name = _artifact_name(safe_epoch, agent, record)
        artifact_path = repo_root / DEFAULT_INBOX_ROOT / agent / artifact_name
        _write_json(artifact_path, record)
        written.append(str(artifact_path))
        uid = str(item.get("uid", "")).strip()
        if uid:
            seen_uids.append(uid)

        _append_audit(
            repo_root / DEFAULT_AUDIT_PATH,
            {
                "action": "poll",
                "agent": agent,
                "artifact": str(artifact_path.relative_to(repo_root)),
                "epoch": safe_epoch,
                "reason_code": "ALLOW",
                "status": "ok",
                "from": _normalize_address(from_addr),
                "uid": uid,
            },
        )

    if seen_uids:
        adapter.mark_seen(
            host=imap_host,
            port=imap_port,
            username=imap_user,
            password=imap_pass,
            uids=seen_uids,
        )

    artifacts = sorted(set(written))
    return {
        "status": "ok",
        "agent": agent,
        "messages": len(artifacts),
        "artifacts": artifacts,
        "audit_path": str((repo_root / DEFAULT_AUDIT_PATH)),
    }
