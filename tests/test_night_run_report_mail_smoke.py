from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_night_run_report_mail_smoke_creates_report_and_outbox_item(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "epoch": "2026-03-06",
                "tasks_executed": 0,
                "tasks_skipped": 0,
                "tasks_failed": 0,
                "budget_used": 0,
                "violations": [],
                "stopped": False,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report_output = tmp_path / "report.md"
    workspace_root = tmp_path / "workspace"

    env = os.environ.copy()
    env["AIOS_MAIL_QUEUE_NOW"] = "2026-03-06T00:00:00Z"
    proc = subprocess.run(
        [
            "python3",
            "tools/night_run_report_mail_smoke.py",
            "--repo-root",
            str(REPO_ROOT),
            "--summary-path",
            str(summary_path),
            "--report-output",
            str(report_output),
            "--workspace-root",
            str(workspace_root),
            "--agent",
            "codex",
            "--to",
            "don.berghuijs@gmail.com",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    assert payload["status"] == "ok"

    report_path = Path(payload["report_path"])
    outbox_path = Path(payload["outbox_path"])
    assert report_path.exists()
    assert outbox_path.exists()

    report_text = report_path.read_text(encoding="utf-8")
    assert "**Night-run Resultaat**" in report_text
    assert "**10 Ideeën Voor Vandaag**" in report_text
    assert "**Top 3 Voorstel (op score)**" in report_text

    mail_payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert mail_payload["status"] == "pending"
    assert mail_payload["to"] == "don.berghuijs@gmail.com"
    assert "Morning Night-Run Report 2026-03-06" in mail_payload["subject"]


def test_night_run_report_mail_body_contract_structure(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "epoch": "2026-03-06",
                "tasks_executed": 0,
                "tasks_skipped": 0,
                "tasks_failed": 0,
                "budget_used": 0,
                "violations": [],
                "stopped": False,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    report_output = tmp_path / "report.md"
    workspace_root = tmp_path / "workspace"

    env = os.environ.copy()
    env["AIOS_MAIL_QUEUE_NOW"] = "2026-03-06T00:00:00Z"
    proc = subprocess.run(
        [
            "python3",
            "tools/night_run_report_mail_smoke.py",
            "--repo-root",
            str(REPO_ROOT),
            "--summary-path",
            str(summary_path),
            "--report-output",
            str(report_output),
            "--workspace-root",
            str(workspace_root),
            "--agent",
            "codex",
            "--to",
            "don.berghuijs@gmail.com",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip())
    outbox_path = Path(payload["outbox_path"])
    mail_payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    body = str(mail_payload.get("body", "")).strip()
    assert body

    required_headings = [
        "**Night-run Resultaat**",
        "**Uitgevoerde Taken**",
        "**10 Ideeën Voor Vandaag**",
        "**Mijn Favoriet Om Nu Te Bouwen**",
        "**Top 3 Voorstel (op score)**",
    ]
    heading_positions = []
    for heading in required_headings:
        idx = body.find(heading)
        assert idx >= 0, f"missing heading: {heading}"
        heading_positions.append(idx)
    assert heading_positions == sorted(heading_positions), "heading order changed"

    idea_numbers = [int(raw) for raw in re.findall(r"(?m)^([0-9]{1,2})\.\s+\*\*\[", body)]
    assert idea_numbers == list(range(1, 11)), "10 ideas block numbering mismatch"

    top3_numbers = [int(raw) for raw in re.findall(r"(?m)^([1-3])\.\s+\*\*[0-9]{1,2}\.\s+\[", body)]
    assert top3_numbers == [1, 2, 3], "top-3 block numbering mismatch"
