from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from supervisor.autonomy_budget import check_budget
from supervisor.autonomy_budget import consume_budget


class AutonomyBudgetTests(unittest.TestCase):
    def test_cooldown_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            first = consume_budget(
                "promotion",
                context_id="ctx-a",
                now_epoch_s=1704067200,
                host_state_dir=tmp_dir,
            )
            self.assertTrue(first["consumed"])

            check = check_budget(
                "promotion",
                now_epoch_s=1704067205,
                host_state_dir=tmp_dir,
            )
            self.assertFalse(check["allowed"])
            self.assertEqual(check["reason"], "cooldown_active")

    def test_daily_limit_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ts = 1704067200
            for i in range(5):
                res = consume_budget(
                    "commit",
                    context_id=f"ctx-{i}",
                    now_epoch_s=ts + i,
                    host_state_dir=tmp_dir,
                )
                self.assertTrue(res["consumed"])
            blocked = check_budget("commit", now_epoch_s=1704067300, host_state_dir=tmp_dir)
            self.assertFalse(blocked["allowed"])
            self.assertEqual(blocked["reason"], "budget_exceeded")

    def test_immediate_duplicate_consume_same_second_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            first = consume_budget(
                "intake",
                context_id="run-123",
                now_epoch_s=1704067200,
                host_state_dir=tmp_dir,
            )
            second = consume_budget(
                "intake",
                context_id="run-123",
                now_epoch_s=1704067200,
                host_state_dir=tmp_dir,
            )
            self.assertTrue(first["consumed"])
            self.assertFalse(second["consumed"])
            self.assertEqual(second["reason"], "duplicate_context")

    def test_append_only_log_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            consume_budget("materialize", context_id="x1", now_epoch_s=1704067200, host_state_dir=tmp_dir)
            consume_budget("materialize", context_id="x2", now_epoch_s=1704067300, host_state_dir=tmp_dir)
            log_path = Path(tmp_dir) / "autonomy" / "budget-log.jsonl"
            self.assertTrue(log_path.is_file())
            lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2)  # 2 consume events


if __name__ == "__main__":
    unittest.main()
