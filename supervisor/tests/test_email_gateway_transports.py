from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import patch
import unittest

from supervisor.channels.transports import IMAPTransportAdapter
from supervisor.channels.transports import _extract_message_body


class EmailGatewayTransportTests(unittest.TestCase):
    def test_extract_message_body_prefers_plain(self) -> None:
        msg = EmailMessage()
        msg["Subject"] = "s"
        msg.set_content("plain-body")
        self.assertEqual(_extract_message_body(msg).strip(), "plain-body")

    def test_extract_message_body_handles_no_get_body_result(self) -> None:
        msg = EmailMessage()
        msg["Subject"] = "s"
        msg.set_payload("raw-body-without-body-part")
        self.assertIn("raw-body-without-body-part", _extract_message_body(msg))

    def test_poll_unseen_prefers_newest_uids_first(self) -> None:
        class _FakeIMAP:
            def __init__(self) -> None:
                self.fetch_calls: list[str] = []
                self.store_calls: list[str] = []

            def __enter__(self):  # type: ignore[no-untyped-def]
                return self

            def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                return False

            def login(self, username: str, password: str) -> None:
                return None

            def select(self, mailbox: str) -> None:
                return None

            def search(self, charset, criteria):  # type: ignore[no-untyped-def]
                return "OK", [b"1 2 10 11"]

            def fetch(self, uid: str, spec: str):  # type: ignore[no-untyped-def]
                self.fetch_calls.append(uid)
                raw = b"From: ops@example.com\\nTo: codex@example.com\\nSubject: s\\n\\nbody\\n"
                return "OK", [(b"RFC822", raw)]

            def store(self, uid: str, op: str, flag: str) -> None:
                self.store_calls.append(uid)

        fake = _FakeIMAP()
        with patch("supervisor.channels.transports.imaplib.IMAP4_SSL", return_value=fake):
            adapter = IMAPTransportAdapter()
            messages = adapter.poll_unseen(
                host="imap.example.com",
                port=993,
                username="u",
                password="p",
                max_messages=2,
                seen_mode="all",
            )
        self.assertEqual([m.get("uid") for m in messages], ["11", "10"])


if __name__ == "__main__":
    unittest.main()
