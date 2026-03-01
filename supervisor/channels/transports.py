from __future__ import annotations

import imaplib
import smtplib
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from typing import Any


class SMTPTransportAdapter:
    def send_mail(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
    ) -> dict[str, Any]:
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(host=host, port=port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(msg)
        return {"status": "sent"}


class IMAPTransportAdapter:
    def poll_unseen(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        max_messages: int,
    ) -> list[dict[str, Any]]:
        with imaplib.IMAP4_SSL(host, port=port) as imap:
            imap.login(username, password)
            imap.select("INBOX")
            status, data = imap.search(None, "UNSEEN")
            if status != "OK" or not data:
                return []
            raw_ids = data[0].decode("utf-8").split()
            selected = sorted(raw_ids, key=lambda v: int(v))[:max_messages]
            out: list[dict[str, Any]] = []
            for uid in selected:
                fetch_status, msg_data = imap.fetch(uid, "(RFC822)")
                if fetch_status != "OK" or not msg_data:
                    continue
                raw_bytes = b""
                for part in msg_data:
                    if isinstance(part, tuple) and len(part) == 2 and isinstance(part[1], bytes):
                        raw_bytes = part[1]
                        break
                if not raw_bytes:
                    continue
                parsed = BytesParser(policy=default).parsebytes(raw_bytes)
                out.append(
                    {
                        "uid": uid,
                        "from": str(parsed.get("From", "")),
                        "to": str(parsed.get("To", "")),
                        "subject": str(parsed.get("Subject", "")),
                        "body": str(parsed.get_body(preferencelist=("plain",)).get_content() if parsed.get_body() else parsed.get_payload()),
                    }
                )
            return out

    def mark_seen(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        uids: list[str],
    ) -> None:
        if not uids:
            return
        with imaplib.IMAP4_SSL(host, port=port) as imap:
            imap.login(username, password)
            imap.select("INBOX")
            for uid in sorted(uids, key=lambda v: int(v)):
                imap.store(uid, "+FLAGS", "\\Seen")
