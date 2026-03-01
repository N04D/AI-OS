from __future__ import annotations

from email.message import EmailMessage
import unittest

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


if __name__ == "__main__":
    unittest.main()
