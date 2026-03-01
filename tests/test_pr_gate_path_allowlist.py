import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.pr_gate_path_allowlist import evaluate_paths
from scripts.pr_gate_path_allowlist import load_policy
from scripts.pr_gate_path_allowlist import main


POLICY_YAML = """\
version: 1
policy_id: path-allowlist-v0.1
mode: enforce
default_decision: deny
rules:
  - id: allow-logs-only
    allow:
      paths:
        - "logs/**"
"""


class PathAllowlistEvaluatorTests(unittest.TestCase):
    def test_allowed_logs_only(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "policy.yaml"
            p.write_text(POLICY_YAML, encoding="utf-8")
            policy, policy_sha = load_policy(str(p))
            verdict = evaluate_paths(policy, ["logs/123/job.md", "logs/123/agent.jsonl"], policy_sha)
            self.assertTrue(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "ALLOW_ALL_PATHS_MATCH")
            self.assertEqual(verdict["violations"], [])
            self.assertEqual(verdict["matched_rule_ids"], ["allow-logs-only"])

    def test_violation_outside_allowlist(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "policy.yaml"
            p.write_text(POLICY_YAML, encoding="utf-8")
            policy, policy_sha = load_policy(str(p))
            verdict = evaluate_paths(policy, ["logs/123/job.md", "src/app.py"], policy_sha)
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_PATH_VIOLATION")
            self.assertEqual(verdict["violations"], ["src/app.py"])

    def test_missing_policy_denies(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "gate-verdict.json"
            rc = main(
                [
                    "--repo",
                    "o/r",
                    "--pr-number",
                    "1",
                    "--token",
                    "x",
                    "--policy",
                    str(Path(td) / "missing.yaml"),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(rc, 1)
            verdict = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(verdict["allow"])
            self.assertEqual(verdict["reason_code"], "DENY_POLICY_MISSING")

    def test_rename_case_uses_previous_and_new_paths(self):
        with tempfile.TemporaryDirectory() as td:
            policy_path = Path(td) / "policy.yaml"
            policy_path.write_text(POLICY_YAML, encoding="utf-8")
            output = Path(td) / "gate-verdict.json"

            renamed_payload = [
                {
                    "filename": "logs/123/new-name.jsonl",
                    "status": "renamed",
                    "previous_filename": "logs/123/old-name.jsonl",
                }
            ]

            def fake_fetch(_owner_repo, _pr_number, _token, api_base="https://api.github.com"):
                _ = api_base
                files = set()
                for item in renamed_payload:
                    files.add(item["filename"])
                    if item["status"] == "renamed":
                        files.add(item["previous_filename"])
                return sorted(files)

            with patch("scripts.pr_gate_path_allowlist.fetch_pr_files", side_effect=fake_fetch):
                rc = main(
                    [
                        "--repo",
                        "o/r",
                        "--pr-number",
                        "2",
                        "--token",
                        "x",
                        "--policy",
                        str(policy_path),
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(rc, 0)
            verdict = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(verdict["allow"])
            self.assertEqual(verdict["violations"], [])


if __name__ == "__main__":
    unittest.main()
