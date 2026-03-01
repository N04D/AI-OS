from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from supervisor.budgets.autonomy import check_budget
from supervisor.budgets.autonomy import consume_budget
from supervisor.budgets.autonomy import consume_improvement_budget


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

    def test_invalid_state_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "autonomy" / "budget.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text("{invalid-json", encoding="utf-8")

            check = check_budget("promotion", host_state_dir=tmp_dir)
            consume = consume_budget("promotion", host_state_dir=tmp_dir)

            self.assertFalse(check["allowed"])
            self.assertEqual(check["reason"], "budget_internal_error")
            self.assertFalse(consume["consumed"])
            self.assertEqual(consume["reason"], "budget_internal_error")

    def test_improvement_budget_records_pr_and_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = consume_improvement_budget(
                pr_id="123",
                tier="MED",
                now_epoch_s=1704067200,
                host_state_dir=tmp_dir,
            )
            self.assertTrue(result["consumed"])
            self.assertEqual(result["pr_id"], "123")
            self.assertEqual(result["tier"], "MED")

            log_path = Path(tmp_dir) / "autonomy" / "budget-log.jsonl"
            lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(any('"event":"improvement_budget_consume"' in ln for ln in lines))
            self.assertTrue(any('"pr_id":"123"' in ln and '"tier":"MED"' in ln for ln in lines))

    def test_improvement_budget_invalid_tier_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = consume_improvement_budget(
                pr_id="999",
                tier="CRITICAL",
                now_epoch_s=1704067200,
                host_state_dir=tmp_dir,
            )
            self.assertFalse(result["consumed"])
            self.assertEqual(result["reason"], "invalid_tier")

    def test_improvement_budget_exhaustion_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            ts = 1704067200
            for i in range(8):
                result = consume_improvement_budget(
                    pr_id=str(100 + i),
                    tier="LOW",
                    now_epoch_s=ts + i,
                    host_state_dir=tmp_dir,
                )
                self.assertTrue(result["consumed"])
            blocked = consume_improvement_budget(
                pr_id="999",
                tier="LOW",
                now_epoch_s=ts + 20,
                host_state_dir=tmp_dir,
            )
            self.assertFalse(blocked["consumed"])
            self.assertEqual(blocked["reason"], "budget_exceeded")


if __name__ == "__main__":
    unittest.main()
