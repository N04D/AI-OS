from __future__ import annotations

from pathlib import Path

from supervisor.morning_reporter import generate_report


def test_generate_report_contains_required_sections_and_ideas(tmp_path: Path) -> None:
    summary = {
        "epoch": "2026-03-06",
        "tasks_executed": 0,
        "tasks_skipped": 0,
        "tasks_failed": 0,
        "budget_used": 0,
        "violations": [],
        "stopped": False,
    }
    report = generate_report(
        summary=summary,
        summary_path=tmp_path / "night.json",
        night_status="ok",
        linter_root=None,
    )

    assert "**Night-run Resultaat**" in report
    assert "**Uitgevoerde Taken**" in report
    assert "**10 Ideeën Voor Vandaag**" in report
    assert "**Actie-items Voor Ochtendtest**" in report
    assert "**Mijn Favoriet Om Nu Te Bouwen**" in report
    assert "**Aanbevolen Volgorde**" in report

    for i in range(1, 11):
        assert f"{i}. **[" in report

    assert report.count("Taak: Implementeer idee") >= 3
    assert report.count("Doel: ") >= 3
    assert report.count("Check: ") >= 3


def test_generate_report_includes_linter_summary(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: demo-skill
description: Demo
---

Body
""",
        encoding="utf-8",
    )
    summary = {
        "epoch": "2026-03-06",
        "tasks_executed": 1,
        "tasks_skipped": 0,
        "tasks_failed": 0,
        "budget_used": 1,
        "violations": [],
        "stopped": False,
    }
    report = generate_report(
        summary=summary,
        summary_path=tmp_path / "night.json",
        night_status="ok",
        linter_root=tmp_path / "skills",
    )
    assert "Skill-linter:" in report
    assert "skills=1" in report
