from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from supervisor import cli


class CliTests(unittest.TestCase):
    @staticmethod
    def _approval_token(scopes: list[str], exp: int, jti: str = "budget-jti-001") -> str:
        return json.dumps({"v": 1, "scope": scopes, "exp": exp, "jti": jti}, sort_keys=True)

    def test_human_output_when_json_flag_not_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["autonomy", "budget", "status", "--host-state-dir", tmp_dir])
            out = buf.getvalue()
            self.assertEqual(code, 0)
            self.assertIn("Budget Status", out)
            self.assertIn("window_utc_day:", out)
            self.assertFalse(out.strip().startswith("{"))

    def test_json_output_unchanged_with_json_flag(self) -> None:
        mocked = [{"status": "existing", "pr_number": 7}]
        with patch("supervisor.cli.create_draft_proposals_prs", return_value=mocked):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "autonomy", "promote"])
            out = buf.getvalue().strip()
            self.assertEqual(code, 0)
            self.assertEqual(out, json.dumps({"promotion": mocked}, sort_keys=True))

    def test_rejected_budget_returns_exit_2(self) -> None:
        mocked = [{"status": "rejected", "reason": "budget_exceeded", "budget": {"counts": {"promotion": 10}}}]
        with patch("supervisor.cli.create_draft_proposals_prs", return_value=mocked):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "autonomy", "promote"])
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason"], "budget_exceeded")

    def test_fatal_error_returns_exit_1(self) -> None:
        with patch("supervisor.cli.create_draft_proposals_prs", side_effect=RuntimeError("boom")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "autonomy", "promote"])
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 1)
            self.assertEqual(out["status"], "error")
            self.assertIn("boom", out["reason"])

    def test_capability_activate_returns_structured_rejection(self) -> None:
        error = cli.CapabilityActivationError("DENY_CAPABILITY_SECRETS_MISSING", "SMTP_PASS")
        with patch("supervisor.cli.activate_capability", side_effect=error):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "autonomy", "capability-activate", "email.send"])
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_CAPABILITY_SECRETS_MISSING")

    def test_budget_reset_requires_approval_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"SUPERVISOR_BUDGET_OVERRIDE_TOKEN": ""}, clear=False):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = cli.main(
                        [
                            "--json",
                            "autonomy",
                            "budget",
                            "reset",
                            "--force",
                            "--host-state-dir",
                            tmp_dir,
                        ]
                    )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_TOKEN_MISSING")

    def test_budget_reset_accepts_valid_approval_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            now = datetime.now(UTC)
            token = self._approval_token(
                ["budget_override"],
                int((now + timedelta(minutes=5)).timestamp()),
            )
            with patch.dict(os.environ, {"SUPERVISOR_BUDGET_OVERRIDE_TOKEN": token}, clear=False):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = cli.main(
                        [
                            "--json",
                            "autonomy",
                            "budget",
                            "reset",
                            "--force",
                            "--host-state-dir",
                            tmp_dir,
                        ]
                    )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 0)
            self.assertEqual(out["status"], "ok")

    def test_phase_acceptance_verify_rejects_failed_pytest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "phase_acceptance.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "version": "v0.1",
                        "pytest": {
                            "passed": 10,
                            "failed": 1,
                            "skipped": 0,
                            "skip_justifications": [],
                        },
                        "roadmap_updated": True,
                        "progress_updated": True,
                        "halt_entered": True,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "phase-acceptance",
                        "verify",
                        "--evidence-path",
                        str(evidence_path),
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_PHASE_ACCEPTANCE_PYTEST_FAILED")

    def test_phase_acceptance_verify_accepts_valid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "phase_acceptance.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "version": "v0.1",
                        "pytest": {
                            "passed": 100,
                            "failed": 0,
                            "skipped": 1,
                            "skip_justifications": ["external env dependency unavailable"],
                        },
                        "roadmap_updated": True,
                        "progress_updated": True,
                        "halt_entered": True,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "phase-acceptance",
                        "verify",
                        "--evidence-path",
                        str(evidence_path),
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 0)
            self.assertEqual(out["status"], "ok")

    def test_determinism_evidence_verify_rejects_invalid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "determinism_evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "version": "v0.1",
                        "risk_tier": "MED",
                        "input_fingerprint": "bad",
                        "output_fingerprint": "b" * 64,
                        "rerun_consistent": True,
                        "timestamps_controlled": True,
                        "artifacts": ["artifacts/determinism_evidence.json"],
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "determinism-evidence",
                        "verify",
                        "--path",
                        str(evidence_path),
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_DETERMINISM_EVIDENCE_SCHEMA_INVALID")

    def test_determinism_evidence_verify_accepts_valid_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            evidence_path = Path(tmp_dir) / "determinism_evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "version": "v0.1",
                        "risk_tier": "HIGH",
                        "input_fingerprint": "a" * 64,
                        "output_fingerprint": "b" * 64,
                        "rerun_consistent": True,
                        "timestamps_controlled": True,
                        "artifacts": ["artifacts/determinism_evidence.json"],
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "determinism-evidence",
                        "verify",
                        "--path",
                        str(evidence_path),
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 0)
            self.assertEqual(out["status"], "ok")

    def test_improvement_budget_consume_accepts_valid_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "improvement-budget",
                        "consume",
                        "--pr-id",
                        "321",
                        "--tier",
                        "MED",
                        "--host-state-dir",
                        tmp_dir,
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 0)
            self.assertEqual(out["status"], "ok")
            self.assertEqual(out["pr_id"], "321")
            self.assertEqual(out["tier"], "MED")

    def test_improvement_budget_consume_rejects_invalid_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "improvement-budget",
                        "consume",
                        "--pr-id",
                        "321",
                        "--tier",
                        "CRITICAL",
                        "--host-state-dir",
                        tmp_dir,
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason"], "invalid_tier")

    def test_improvement_budget_runtime_enforces_exhaustion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i in range(8):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    code = cli.main(
                        [
                            "--json",
                            "autonomy",
                            "improvement-budget",
                            "consume",
                            "--pr-id",
                            str(500 + i),
                            "--tier",
                            "LOW",
                            "--host-state-dir",
                            tmp_dir,
                        ]
                    )
                out = json.loads(buf.getvalue().strip())
                self.assertEqual(code, 0)
                self.assertEqual(out["status"], "ok")

            blocked_buf = io.StringIO()
            with redirect_stdout(blocked_buf):
                blocked_code = cli.main(
                    [
                        "--json",
                        "autonomy",
                        "improvement-budget",
                        "consume",
                        "--pr-id",
                        "9999",
                        "--tier",
                        "LOW",
                        "--host-state-dir",
                        tmp_dir,
                    ]
                )
            blocked_out = json.loads(blocked_buf.getvalue().strip())
            self.assertEqual(blocked_code, 2)
            self.assertEqual(blocked_out["status"], "rejected")
            self.assertEqual(blocked_out["reason"], "budget_exceeded")

    def test_email_send_returns_structured_rejection(self) -> None:
        error = cli.EmailGatewayError("DENY_AGENT_CHANNEL_DISABLED", "module disabled")
        with patch("supervisor.cli.send_email_direct", side_effect=error):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "email",
                        "send",
                        "--agent",
                        "codex",
                        "--to",
                        "ops@example.com",
                        "--subject",
                        "s",
                        "--body",
                        "b",
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_AGENT_CHANNEL_DISABLED")

    def test_email_poll_returns_structured_rejection(self) -> None:
        error = cli.EmailGatewayError("DENY_CAPABILITY_MISSING", "email.poll")
        with patch("supervisor.cli.poll_email_direct", side_effect=error):
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(["--json", "email", "poll", "--agent", "codex", "--max", "5"])
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 2)
            self.assertEqual(out["status"], "rejected")
            self.assertEqual(out["reason_code"], "DENY_CAPABILITY_MISSING")

    def test_email_poll_accepts_deterministic_filters(self) -> None:
        with patch(
            "supervisor.cli.poll_email_direct",
            return_value={"status": "ok", "agent": "codex", "messages": 0, "artifacts": [], "audit_path": "logs/control/email_gateway_audit.jsonl"},
        ) as poll_mock:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli.main(
                    [
                        "--json",
                        "email",
                        "poll",
                        "--agent",
                        "codex",
                        "--max",
                        "5",
                        "--from-contains",
                        "don@",
                        "--subject-contains",
                        "hello",
                    ]
                )
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(code, 0)
            self.assertEqual(out["status"], "ok")
            called = poll_mock.call_args.kwargs
            self.assertEqual(called["from_contains"], "don@")
            self.assertEqual(called["subject_contains"], "hello")


if __name__ == "__main__":
    unittest.main()
