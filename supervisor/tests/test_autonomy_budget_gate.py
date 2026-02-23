from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from supervisor.autonomy_budget_gate import check_and_consume
from supervisor.autonomy_budget_gate import load_or_init_budget_state
from supervisor.autonomy_budget_gate import roll_window_if_needed


class AutonomyBudgetGateTests(unittest.TestCase):
    def test_window_roll_resets_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = str(Path(tmp_dir) / "budget.json")
            state, _ = load_or_init_budget_state(state_path=state_path, now_epoch_s=1704067200)
            state["counts"]["promotion"] = 7
            state["last_action_epoch_s"]["promotion"] = 1704067200
            rolled_state, rolled = roll_window_if_needed(state, now_epoch_s=1704153600)
            self.assertTrue(rolled)
            self.assertEqual(rolled_state["window_utc_day"], "2024-01-02")
            self.assertEqual(rolled_state["counts"]["promotion"], 0)

    def test_cooldown_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = str(Path(tmp_dir) / "budget.json")
            log_path = str(Path(tmp_dir) / "budget-log.jsonl")
            first = check_and_consume(
                "promotion",
                now_epoch_s=1704067200,
                state_path=state_path,
                log_path=log_path,
            )
            second = check_and_consume(
                "promotion",
                now_epoch_s=1704067205,
                state_path=state_path,
                log_path=log_path,
            )
            self.assertTrue(first["allowed"])
            self.assertFalse(second["allowed"])
            self.assertEqual(second["reason"], "cooldown_active")

    def test_budget_exhaustion_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = str(Path(tmp_dir) / "budget.json")
            log_path = str(Path(tmp_dir) / "budget-log.jsonl")
            ts = 1704067200
            for _ in range(5):
                result = check_and_consume(
                    "commit",
                    now_epoch_s=ts,
                    state_path=state_path,
                    log_path=log_path,
                )
                self.assertTrue(result["allowed"])
            blocked = check_and_consume(
                "commit",
                now_epoch_s=ts,
                state_path=state_path,
                log_path=log_path,
            )
            self.assertFalse(blocked["allowed"])
            self.assertEqual(blocked["reason"], "daily_limit_exhausted")

    def test_allowed_increments_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = str(Path(tmp_dir) / "budget.json")
            log_path = str(Path(tmp_dir) / "budget-log.jsonl")
            result = check_and_consume(
                "exec_attempt",
                now_epoch_s=1704067200,
                state_path=state_path,
                log_path=log_path,
                subject_id="issue:1",
            )
            self.assertTrue(result["allowed"])
            self.assertEqual(result["counts"]["exec_attempt"], 1)

            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            event = json.loads(lines[0])
            self.assertEqual(event["action_type"], "exec_attempt")
            self.assertTrue(event["allowed"])

    def test_blocked_logs_no_increment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = str(Path(tmp_dir) / "budget.json")
            log_path = str(Path(tmp_dir) / "budget-log.jsonl")
            check_and_consume(
                "intake",
                now_epoch_s=1704067200,
                state_path=state_path,
                log_path=log_path,
            )
            blocked = check_and_consume(
                "intake",
                now_epoch_s=1704067201,
                state_path=state_path,
                log_path=log_path,
            )
            self.assertFalse(blocked["allowed"])
            self.assertEqual(blocked["reason"], "cooldown_active")

            state = json.loads(Path(state_path).read_text(encoding="utf-8"))
            self.assertEqual(state["counts"]["intake"], 1)
            lines = Path(log_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertFalse(json.loads(lines[-1])["allowed"])


if __name__ == "__main__":
    unittest.main()
