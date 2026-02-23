from __future__ import annotations

import unittest
from unittest.mock import patch

from supervisor.autonomy_review_intake_gate import AutonomyReviewIntakeGateError
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


if __name__ == "__main__":
    unittest.main()
