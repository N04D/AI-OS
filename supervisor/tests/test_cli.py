from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from supervisor import cli


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
