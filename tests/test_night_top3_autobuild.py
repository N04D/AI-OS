from __future__ import annotations

from tools.night_top3_autobuild import _extract_top3


def test_extract_top3_supports_new_heading() -> None:
    report = """**Top 3 Voorstel (op score)**
1. **13. [Modules] Rapportdiff t.o.v. vorige run** (score `9`)
2. **18. [Test/Infra] Contracttest op mail-body structuur** (score `9`)
3. **19. [Test/Infra] Regression matrix voor lock/preflight paden** (score `9`)
"""
    top3 = _extract_top3(report)
    assert [item["idea_id"] for item in top3] == [13, 18, 19]
