from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from supervisor.autonomy_task_materializer import AutonomyTaskMaterializerError
from supervisor.autonomy_task_materializer import deterministic_task_id
from supervisor.autonomy_task_materializer import materialize_autonomy_tasks


def _mk_pr(number: int, head: str, proposal_hash: str, labels: list[str] | None = None) -> dict:
    return {
        "number": number,
        "html_url": f"http://example.local/pr/{number}",
        "title": f"proposal {number}",
        "head": {"ref": head},
        "base": {"ref": "dev"},
        "body": f"proposal_hash: {proposal_hash}",
        "labels": [{"name": name} for name in (labels or [])],
    }


class AutonomyTaskMaterializerTests(unittest.TestCase):
    def test_deterministic_task_id(self) -> None:
        proposal_hash = "abcd1234" * 8
        self.assertEqual(
            deterministic_task_id(proposal_hash),
            "autonomy-task-abcd1234abcd1234",
        )

    def test_idempotent_materialization(self) -> None:
        proposal_hash = "1234567890abcdef" + ("0" * 48)
        pr = _mk_pr(
            71,
            "autonomy/proposal-1234567890abcdef",
            proposal_hash,
            labels=["intake-processed"],
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            if method == "GET" and "/pulls/71/reviews" in url:
                return 200, [{"state": "APPROVED", "user": {"login": "alice"}}]
            raise AssertionError(f"unexpected call: {method} {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("supervisor.autonomy_task_materializer._git_is_clean", return_value=True),
                patch("supervisor.autonomy_task_materializer._api_json_request", side_effect=fake_api),
                patch(
                    "supervisor.autonomy_task_materializer.check_budget",
                    return_value={"allowed": True, "reason": "allowed", "state": {}},
                ),
                patch(
                    "supervisor.autonomy_task_materializer.consume_budget",
                    return_value={"consumed": True, "reason": "consumed", "state": {}},
                ),
            ):
                first = materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
                second = materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )

            self.assertEqual(first[0]["status"], "materialized")
            self.assertEqual(second[0]["status"], "noop")

            task_id = deterministic_task_id(proposal_hash)
            task_path = Path(tmp_dir) / "autonomy" / "inbox" / "tasks" / f"{task_id}.json"
            self.assertTrue(task_path.is_file())

            log_path = Path(tmp_dir) / "autonomy" / "intake-log.jsonl"
            lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)

    def test_approval_required(self) -> None:
        proposal_hash = "aaaaaaaaaaaaaaaa" + ("1" * 48)
        pr = _mk_pr(
            72,
            "autonomy/proposal-aaaaaaaaaaaaaaaa",
            proposal_hash,
            labels=["intake-processed"],
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            if method == "GET" and "/pulls/72/reviews" in url:
                return 200, [{"state": "COMMENTED", "user": {"login": "alice"}}]
            raise AssertionError(f"unexpected call: {method} {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("supervisor.autonomy_task_materializer._git_is_clean", return_value=True),
                patch("supervisor.autonomy_task_materializer._api_json_request", side_effect=fake_api),
                patch(
                    "supervisor.autonomy_task_materializer.check_budget",
                    return_value={"allowed": True, "reason": "allowed", "state": {}},
                ),
                patch(
                    "supervisor.autonomy_task_materializer.consume_budget",
                    return_value={"consumed": True, "reason": "consumed", "state": {}},
                ),
                self.assertRaises(AutonomyTaskMaterializerError) as ctx,
            ):
                materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("approval_required", str(ctx.exception))

    def test_bot_approval_rejected(self) -> None:
        proposal_hash = "bbbbbbbbbbbbbbbb" + ("2" * 48)
        pr = _mk_pr(
            73,
            "autonomy/proposal-bbbbbbbbbbbbbbbb",
            proposal_hash,
            labels=["intake-processed"],
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            if method == "GET" and "/pulls/73/reviews" in url:
                return 200, [{"state": "APPROVED", "user": {"login": "ci-bot"}}]
            raise AssertionError(f"unexpected call: {method} {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("supervisor.autonomy_task_materializer._git_is_clean", return_value=True),
                patch("supervisor.autonomy_task_materializer._api_json_request", side_effect=fake_api),
                patch(
                    "supervisor.autonomy_task_materializer.check_budget",
                    return_value={"allowed": True, "reason": "allowed", "state": {}},
                ),
                patch(
                    "supervisor.autonomy_task_materializer.consume_budget",
                    return_value={"consumed": True, "reason": "consumed", "state": {}},
                ),
                self.assertRaises(AutonomyTaskMaterializerError) as ctx,
            ):
                materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("approval_required", str(ctx.exception))

    def test_hash_mismatch_fail_closed(self) -> None:
        pr = _mk_pr(
            74,
            "autonomy/proposal-cccccccccccccccc",
            "dddddddddddddddd" + ("e" * 48),
            labels=["intake-processed"],
        )

        def fake_api(method: str, url: str, token: str, payload=None):  # type: ignore[no-untyped-def]
            if method == "GET" and "pulls?state=open" in url:
                return 200, [pr]
            raise AssertionError(f"unexpected call: {method} {url}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("supervisor.autonomy_task_materializer._git_is_clean", return_value=True),
                patch("supervisor.autonomy_task_materializer._api_json_request", side_effect=fake_api),
                self.assertRaises(AutonomyTaskMaterializerError) as ctx,
            ):
                materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertIn("hash_mismatch", str(ctx.exception))

    def test_budget_rejection_skips_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with (
                patch("supervisor.autonomy_task_materializer._git_is_clean", return_value=True),
                patch(
                    "supervisor.autonomy_task_materializer.check_budget",
                    return_value={"allowed": False, "reason": "budget_exceeded", "state": {"counts": {"materialize": 20}}},
                ),
                patch("supervisor.autonomy_task_materializer._api_json_request") as api_mock,
            ):
                result = materialize_autonomy_tasks(
                    host_state_dir=tmp_dir,
                    gitea_base_url="http://gitea.local",
                    gitea_token="token",
                )
            self.assertEqual(result[0]["status"], "rejected")
            self.assertEqual(result[0]["reason"], "budget_exceeded")
            api_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
