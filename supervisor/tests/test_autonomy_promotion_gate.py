from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.autonomy_promotion_gate import AutonomyPromotionGateError
from supervisor.autonomy_promotion_gate import create_draft_proposals_prs
from supervisor.autonomy_promotion_gate import deterministic_branch_name


class AutonomyPromotionGateTests(unittest.TestCase):
    def test_deterministic_branch_name_uses_sha256_content(self) -> None:
        content = "# proposal\nhello\n"
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.assertEqual(
            deterministic_branch_name(content),
            f"autonomy/proposal-{digest[:16]}",
        )

    def test_idempotent_pr_detection_reuses_existing_open_pr(self) -> None:
        proposal = {
            "path": "docs/autonomy/proposals/proposal.repeated_failure.abcdef123456.md",
            "content": "# proposal\n",
            "content_hash": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "branch": "autonomy/proposal-abcdef1234567890",
            "type": "repeated_failure",
        }
        calls: list[tuple[str, str]] = []

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            calls.append((method, url))
            self.assertEqual(method, "GET")
            return (
                200,
                [
                    {
                        "number": 91,
                        "html_url": "http://example/pr/91",
                        "head": {"ref": "autonomy/proposal-abcdef1234567890"},
                    }
                ],
            )

        with (
            patch("supervisor.autonomy_promotion_gate._git_is_clean", return_value=True),
            patch("supervisor.autonomy_promotion_gate._load_proposal_files", return_value=[proposal]),
            patch("supervisor.autonomy_promotion_gate._api_json_request", side_effect=fake_api),
            patch(
                "supervisor.autonomy_promotion_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_promotion_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
        ):
            result = create_draft_proposals_prs(
                "docs/autonomy/proposals",
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result[0]["status"], "existing")
        self.assertEqual(result[0]["pr_number"], 91)

    def test_missing_token_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(AutonomyPromotionGateError) as ctx:
                create_draft_proposals_prs(
                    tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="",
                )
            self.assertIn("missing_gitea_token", str(ctx.exception))

    def test_dirty_tree_fails_closed(self) -> None:
        with patch("supervisor.autonomy_promotion_gate._git_is_clean", return_value=False):
            with self.assertRaises(AutonomyPromotionGateError) as ctx:
                create_draft_proposals_prs(
                    "docs/autonomy/proposals",
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("dirty_worktree", str(ctx.exception))

    def test_proposal_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            proposals_dir = root / "docs" / "autonomy" / "proposals"
            proposals_dir.mkdir(parents=True, exist_ok=True)
            bad_file = proposals_dir / "proposal.repeated_failure.deadbeefcafe.md"
            bad_file.write_text("# bad\n", encoding="utf-8")

            with (
                patch("supervisor.autonomy_promotion_gate._git_is_clean", return_value=True),
                patch(
                    "supervisor.autonomy_promotion_gate.check_budget",
                    return_value={"allowed": True, "reason": "allowed", "state": {}},
                ),
                patch(
                    "supervisor.autonomy_promotion_gate.consume_budget",
                    return_value={"consumed": True, "reason": "consumed", "state": {}},
                ),
                self.assertRaises(AutonomyPromotionGateError) as ctx,
            ):
                create_draft_proposals_prs(
                    str(proposals_dir),
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("proposal_hash_mismatch", str(ctx.exception))

    def test_inline_proposals_are_supported(self) -> None:
        content = "# Autonomy Proposal\n\ncontent\n"
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        inline = [
            {
                "type": "repeated_failure",
                "hash": digest,
                "filename": f"proposal.repeated_failure.{digest[:12]}.md",
                "path": f"docs/autonomy/proposals/proposal.repeated_failure.{digest[:12]}.md",
                "content": content,
                "branch_name": f"autonomy/proposal-{digest[:16]}",
            }
        ]

        with (
            patch("supervisor.autonomy_promotion_gate._git_is_clean", return_value=True),
            patch(
                "supervisor.autonomy_promotion_gate._api_json_request",
                return_value=(200, [{"number": 99, "html_url": "http://example/pr/99", "head": {"ref": f"autonomy/proposal-{digest[:16]}"}}]),
            ),
            patch(
                "supervisor.autonomy_promotion_gate.check_budget",
                return_value={"allowed": True, "reason": "allowed", "state": {}},
            ),
            patch(
                "supervisor.autonomy_promotion_gate.consume_budget",
                return_value={"consumed": True, "reason": "consumed", "state": {}},
            ),
        ):
            result = create_draft_proposals_prs(
                proposals_dir=None,
                gitea_base_url="http://gitea.local",
                gitea_token="token",
                proposals=inline,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "existing")

    def test_budget_rejection_skips_network(self) -> None:
        with (
            patch("supervisor.autonomy_promotion_gate._git_is_clean", return_value=True),
            patch(
                "supervisor.autonomy_promotion_gate.check_budget",
                return_value={"allowed": False, "reason": "budget_exceeded", "state": {"counts": {"promotion": 10}}},
            ),
            patch("supervisor.autonomy_promotion_gate._api_json_request") as api_mock,
        ):
            result = create_draft_proposals_prs(
                proposals=[],
                proposals_dir=None,
                gitea_base_url="http://gitea.local",
                gitea_token="token",
            )

        self.assertEqual(result[0]["status"], "rejected")
        self.assertEqual(result[0]["reason"], "budget_exceeded")
        api_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
