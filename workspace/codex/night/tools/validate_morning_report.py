#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SECTIONS: tuple[str, ...] = (
    "Night-run Resultaat",
    "Uitgevoerde Taken",
    "10 Ideeën Voor Vandaag",
    "Mijn Favoriet Om Nu Te Bouwen",
    "Aanbevolen Volgorde",
)


def _normalized_heading(line: str) -> str:
    base = line.strip().lower()
    base = re.sub(r"[*_`]+", "", base)
    return re.sub(r"^[#0-9\).\s:-]+", "", base).strip()


def _find_heading_line_index(lines: list[str], heading: str) -> int:
    target = _normalized_heading(heading)
    for idx, line in enumerate(lines):
        if _normalized_heading(line) == target:
            return idx
    return -1


def validate_report(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"report_missing:{path}"]

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for section in REQUIRED_SECTIONS:
        if _find_heading_line_index(lines, section) < 0:
            errors.append(f"missing_section:{section}")

    ideas_start = _find_heading_line_index(lines, "10 Ideeën Voor Vandaag")
    ideas_end = _find_heading_line_index(lines, "Mijn Favoriet Om Nu Te Bouwen")
    if ideas_start >= 0:
        end = ideas_end if ideas_end > ideas_start else len(lines)
        ideas_block = "\n".join(lines[ideas_start:end])
        numbers = sorted({int(n) for n in re.findall(r"(?m)^([0-9]{1,2})\.\s", ideas_block)})
        if numbers != list(range(1, 11)):
            errors.append(f"ideas_numbering_invalid:{numbers}")
    else:
        errors.append("ideas_block_missing")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: validate_morning_report.py <report_path>", file=sys.stderr)
        return 2
    report_path = Path(args[0])
    errors = validate_report(report_path)
    if errors:
        for err in errors:
            print(f"FAIL {err}")
        return 1
    print(f"OK {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
