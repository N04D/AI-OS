from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.autonomy_review_intake_gate import AutonomyReviewIntakeGateError
from supervisor.autonomy_review_intake_gate import _git_is_clean
from supervisor.autonomy_review_intake_gate import intake_approved_autonomy_proposals


def _mk_pr(number: int, head: str, proposal_hash: str, labels: list[str] | None = None) -> dict:
    return {
        "number": number,
        "head": {"ref": head},
        "body": f"proposal_hash: {proposal_hash}",
        "labels": [{"name": name} for name in (labels or [])],
    }


class AutonomyReviewIntakeGateTests(unittest.TestCase):
    def test_approval_validation_requires_non_bot_approval(self) -> None:
        pr = _mk_pr(
            11,
            "autonomy/proposal-1234567890abcdef",
            "1234567890abcdef" + ("0" * 48),
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            if method == "GET" and "/reviews" in url:
                return 200, [{"state": "APPROVED", "user": {"login": "alice"}}]
            if method == "POST" and "/issues/11/labels" in url:
                return 200, [{"name": "intake-processed"}]
            raise AssertionError(f"unexpected API call: {method} {url}")

        with (
            patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=True),
            patch("supervisor.autonomy_review_intake_gate._api_json_request", side_effect=fake_api),
            patch(
                "supervisor.autonomy_review_intake_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_review_intake_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
        ):
            results = intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "intake_processed")
        self.assertTrue(results[0]["approved"])

    def test_bot_approval_is_rejected(self) -> None:
        pr = _mk_pr(
            12,
            "autonomy/proposal-abcdefabcdefabcd",
            "abcdefabcdefabcd" + ("1" * 48),
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            if method == "GET" and "/reviews" in url:
                return 200, [{"state": "APPROVED", "user": {"login": "ci-bot"}}]
            raise AssertionError(f"unexpected API call: {method} {url}")

        with (
            patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=True),
            patch("supervisor.autonomy_review_intake_gate._api_json_request", side_effect=fake_api),
            patch(
                "supervisor.autonomy_review_intake_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_review_intake_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
        ):
            results = intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "pending_review")
        self.assertFalse(results[0]["approved"])

    def test_idempotency_skips_already_processed_label(self) -> None:
        pr = _mk_pr(
            13,
            "autonomy/proposal-feedfacefeedface",
            "feedfacefeedface" + ("2" * 48),
            labels=["intake-processed"],
        )
        api_calls: list[tuple[str, str]] = []

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            api_calls.append((method, url))
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            raise AssertionError(f"unexpected API call: {method} {url}")

        with (
            patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=True),
            patch("supervisor.autonomy_review_intake_gate._api_json_request", side_effect=fake_api),
            patch(
                "supervisor.autonomy_review_intake_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_review_intake_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
        ):
            results = intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "already_processed")
        self.assertEqual(len(api_calls), 1)

    def test_dirty_tree_failure(self) -> None:
        with patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=False):
            with self.assertRaises(AutonomyReviewIntakeGateError) as ctx:
                intake_approved_autonomy_proposals(
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("dirty_worktree", str(ctx.exception))

    def test_hash_mismatch_failure(self) -> None:
        pr = _mk_pr(
            14,
            "autonomy/proposal-aaaaaaaaaaaaaaaa",
            "bbbbbbbbbbbbbbbb" + ("c" * 48),
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            raise AssertionError(f"unexpected API call: {method} {url}")

        with (
            patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=True),
            patch("supervisor.autonomy_review_intake_gate._api_json_request", side_effect=fake_api),
            patch(
                "supervisor.autonomy_review_intake_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_review_intake_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
            self.assertRaises(AutonomyReviewIntakeGateError) as ctx,
        ):
            intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertIn("hash_mismatch", str(ctx.exception))

    def test_missing_token_fails(self) -> None:
        with self.assertRaises(AutonomyReviewIntakeGateError) as ctx:
            intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="",
            )
        self.assertIn("missing_gitea_token", str(ctx.exception))

    def test_budget_rejection_skips_network(self) -> None:
        with (
            patch("supervisor.autonomy_review_intake_gate._git_is_clean", return_value=True),
            patch(
                "supervisor.autonomy_review_intake_gate.check_budget",
                return_value={"allowed": False, "reason": "cooldown_active", "state": {"counts": {"intake": 1}}},
            ),
            patch("supervisor.autonomy_review_intake_gate._api_json_request") as api_mock,
        ):
            result = intake_approved_autonomy_proposals(
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )
        self.assertEqual(result[0]["status"], "rejected")
        self.assertEqual(result[0]["reason"], "cooldown_active")
        api_mock.assert_not_called()

    def test_git_is_clean_ignores_runtime_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
            (repo / ".gitignore").write_text(
                "state/budgets.json\n"
                "state/scheduler_jobs.json\n"
                "state/scheduler_state.json\n"
                "state/supervisor/state_integrity.json\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "baseline"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )
            (repo / "state/supervisor").mkdir(parents=True, exist_ok=True)
            (repo / "state").mkdir(parents=True, exist_ok=True)
            (repo / "state/budgets.json").write_text("{\"version\":\"v0.1\"}\n", encoding="utf-8")
            (repo / "state/scheduler_jobs.json").write_text("{\"version\":\"v0.1\",\"timezone\":\"UTC\",\"jobs\":[]}\n", encoding="utf-8")
            (repo / "state/scheduler_state.json").write_text("{\"version\":\"v0.1\",\"last_run_utc\":\"2026-03-01T00:00:00Z\",\"jobs\":{}}\n", encoding="utf-8")
            (repo / "state/supervisor/state_integrity.json").write_text("{\"version\":\"v0.1\",\"files\":{}}\n", encoding="utf-8")
            prev = Path.cwd()
            try:
                os.chdir(repo)
                self.assertTrue(_git_is_clean())
            finally:
                os.chdir(prev)


if __name__ == "__main__":
    unittest.main()
