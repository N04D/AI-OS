from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from supervisor.autonomy_planner import generate_proposals


class AutonomyPlannerTests(unittest.TestCase):
    def _sample_opportunities(self) -> list[dict]:
        return [
            {
                "type": "repeated_failure",
                "reason": "timeout",
                "count": 4,
                "confidence": 0.8,
            },
            {
                "type": "duration_outlier",
                "task_id": "task-9",
                "task_avg_duration_ms": 1200,
                "global_avg_duration_ms": 500,
                "confidence": 0.7,
            },
        ]

    def test_same_input_produces_identical_filenames_and_content(self) -> None:
        opportunities = self._sample_opportunities()
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            meta_a = generate_proposals(opportunities, tmp_a)
            meta_b = generate_proposals(opportunities, tmp_b)

            names_a = [m["filename"] for m in meta_a]
            names_b = [m["filename"] for m in meta_b]
            self.assertEqual(names_a, names_b)

            for m_a, m_b in zip(meta_a, meta_b):
                content_a = Path(m_a["path"]).read_text(encoding="utf-8")
                content_b = Path(m_b["path"]).read_text(encoding="utf-8")
                self.assertEqual(content_a, content_b)

    def test_different_input_order_produces_identical_output_order(self) -> None:
        opportunities = self._sample_opportunities()
        reversed_ops = list(reversed(opportunities))
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            meta_a = generate_proposals(opportunities, tmp_a)
            meta_b = generate_proposals(reversed_ops, tmp_b)
            self.assertEqual([m["filename"] for m in meta_a], [m["filename"] for m in meta_b])


if __name__ == "__main__":
    unittest.main()
