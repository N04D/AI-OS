from __future__ import annotations

from pathlib import Path

from supervisor.skill_linter import lint_skill_file
from supervisor.skill_linter import lint_skill_roots


def test_lint_skill_file_ok_with_existing_relative_link(tmp_path: Path) -> None:
    skill_dir = tmp_path / "my-skill"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "scripts" / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        """---
name: my-skill
description: Minimal geldige skill
---

# My Skill

Gebruik [run script](scripts/run.sh) voor uitvoering.
""",
        encoding="utf-8",
    )

    result = lint_skill_file(skill_dir / "SKILL.md")
    assert result.ok


def test_lint_skill_file_reports_missing_required_fields(tmp_path: Path) -> None:
    skill_dir = tmp_path / "broken-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: ""
---

Instructies
""",
        encoding="utf-8",
    )

    result = lint_skill_file(skill_dir / "SKILL.md")
    codes = {issue.code for issue in result.issues}
    assert "name_missing" in codes
    assert "description_missing" in codes


def test_lint_skill_file_reports_missing_relative_link(tmp_path: Path) -> None:
    skill_dir = tmp_path / "link-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: link-skill
description: Test
---

[Ontbrekend bestand](references/does-not-exist.md)
""",
        encoding="utf-8",
    )

    result = lint_skill_file(skill_dir / "SKILL.md")
    codes = {issue.code for issue in result.issues}
    assert "link_missing" in codes


def test_lint_skill_file_checks_second_level_links_with_depth_2(tmp_path: Path) -> None:
    skill_dir = tmp_path / "depth-skill"
    references = skill_dir / "references"
    references.mkdir(parents=True)
    (references / "guide.md").write_text(
        """# Guide

Zie [verdieping](./missing.md).
""",
        encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        """---
name: depth-skill
description: Test
---

Zie [guide](references/guide.md).
""",
        encoding="utf-8",
    )

    result_depth_1 = lint_skill_file(skill_dir / "SKILL.md", link_depth=1)
    assert result_depth_1.ok

    result_depth_2 = lint_skill_file(skill_dir / "SKILL.md", link_depth=2)
    messages = [issue.message for issue in result_depth_2.issues if issue.code == "link_missing"]
    assert any("depth 2" in message for message in messages)


def test_lint_skill_roots_discovers_nested_skills(tmp_path: Path) -> None:
    root = tmp_path / ".codex" / "skills" / ".system"
    skill_a = root / "alpha"
    skill_b = root / "beta"
    skill_a.mkdir(parents=True)
    skill_b.mkdir(parents=True)
    (skill_a / "SKILL.md").write_text(
        """---
name: alpha
description: A
---
A
""",
        encoding="utf-8",
    )
    (skill_b / "SKILL.md").write_text(
        """---
name: beta
description: B
---
B
""",
        encoding="utf-8",
    )

    results = lint_skill_roots([root])
    assert len(results) == 2
    assert all(result.ok for result in results)
