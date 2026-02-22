from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def analyze_ledger(runs_path: str, evaluations_path: str) -> list[dict]:
    runs = _read_jsonl(runs_path)
    evaluations = _read_jsonl(evaluations_path)

    opportunities: list[dict[str, Any]] = []

    # 1) Repeated identical failure reasons (>=3 occurrences).
    reason_counts: dict[str, int] = {}
    for row in runs:
        status = str(row.get("status", ""))
        if status == "success":
            continue
        reason = str(row.get("reason", "")).strip()
        if not reason:
            reason = str(row.get("stderr", "")).strip() or "unknown_failure"
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    for reason in sorted(reason_counts.keys()):
        count = reason_counts[reason]
        if count >= 3:
            opportunities.append(
                {
                    "type": "repeated_failure",
                    "reason": reason,
                    "count": count,
                    "confidence": 0.8,
                }
            )

    # 2) Tasks that succeed but never commit.
    committed_tasks: set[str] = set()
    for row in evaluations:
        if row.get("commit_performed") is True:
            task_id = str(row.get("task_id", "")).strip()
            if task_id:
                committed_tasks.add(task_id)

    successful_tasks: set[str] = set()
    for row in runs:
        if str(row.get("status", "")) == "success":
            task_id = str(row.get("task_id", "")).strip()
            if task_id:
                successful_tasks.add(task_id)

    for task_id in sorted(successful_tasks - committed_tasks):
        opportunities.append(
            {
                "type": "success_without_commit",
                "task_id": task_id,
                "confidence": 0.75,
            }
        )

    # 3) Tasks exceeding average duration by >2x.
    durations_by_task: dict[str, list[int]] = {}
    all_durations: list[int] = []
    for row in runs:
        task_id = str(row.get("task_id", "")).strip()
        start = row.get("ts_start_ms")
        end = row.get("ts_end_ms")
        if (
            not task_id
            or not isinstance(start, int)
            or not isinstance(end, int)
            or end < start
        ):
            continue
        duration = end - start
        durations_by_task.setdefault(task_id, []).append(duration)
        all_durations.append(duration)

    if all_durations:
        avg = sum(all_durations) / float(len(all_durations))
        for task_id in sorted(durations_by_task.keys()):
            task_avg = sum(durations_by_task[task_id]) / float(len(durations_by_task[task_id]))
            if task_avg > (2.0 * avg):
                opportunities.append(
                    {
                        "type": "duration_outlier",
                        "task_id": task_id,
                        "task_avg_duration_ms": int(task_avg),
                        "global_avg_duration_ms": int(avg),
                        "confidence": 0.7,
                    }
                )

    return opportunities
