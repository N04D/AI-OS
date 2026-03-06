from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


_ALLOWED_FRONTMATTER_KEYS = {"name", "description", "metadata"}
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class LintIssue:
    code: str
    message: str


@dataclass(frozen=True)
class SkillLintResult:
    path: Path
    issues: tuple[LintIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


def _load_yaml(raw: str) -> object:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(raw)
    except ModuleNotFoundError:
        raise RuntimeError("PyYAML is required for skill linting")


def _parse_frontmatter(text: str) -> tuple[dict[str, object] | None, str, list[LintIssue]]:
    lines = text.splitlines()
    issues: list[LintIssue] = []
    if not lines or lines[0].strip() != "---":
        return None, text, [LintIssue("frontmatter_missing", "frontmatter must start with ---")]
    try:
        closing_idx = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text, [LintIssue("frontmatter_unclosed", "frontmatter block must end with ---")]

    raw_frontmatter = "\n".join(lines[1:closing_idx])
    body = "\n".join(lines[closing_idx + 1 :]).lstrip("\n")
    try:
        parsed = _load_yaml(raw_frontmatter)
    except Exception as exc:  # pragma: no cover - defensive, validated by tests
        return None, body, [LintIssue("frontmatter_invalid_yaml", str(exc))]
    if not isinstance(parsed, dict):
        issues.append(LintIssue("frontmatter_not_mapping", "frontmatter must be a YAML mapping"))
        return None, body, issues
    return parsed, body, issues


def _strip_fenced_code(markdown: str) -> str:
    lines: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines)


def _is_external_link(target: str) -> bool:
    normalized = target.strip().lower()
    return normalized.startswith(("http://", "https://", "mailto:", "#"))


def lint_skill_file(path: Path) -> SkillLintResult:
    issues: list[LintIssue] = []
    text = path.read_text(encoding="utf-8")
    frontmatter, body, parse_issues = _parse_frontmatter(text)
    issues.extend(parse_issues)
    if frontmatter is None:
        return SkillLintResult(path=path, issues=tuple(issues))

    unknown_keys = sorted(set(frontmatter.keys()) - _ALLOWED_FRONTMATTER_KEYS)
    if unknown_keys:
        issues.append(
            LintIssue(
                "frontmatter_unknown_keys",
                f"unknown frontmatter keys: {', '.join(unknown_keys)}",
            )
        )

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    metadata = frontmatter.get("metadata")

    if not isinstance(name, str) or not name.strip():
        issues.append(LintIssue("name_missing", "frontmatter 'name' must be a non-empty string"))
    if not isinstance(description, str) or not description.strip():
        issues.append(LintIssue("description_missing", "frontmatter 'description' must be a non-empty string"))
    if metadata is not None and not isinstance(metadata, dict):
        issues.append(LintIssue("metadata_invalid", "frontmatter 'metadata' must be a mapping when present"))

    expected_name = path.parent.name
    if isinstance(name, str) and name.strip() and name.strip() != expected_name:
        issues.append(
            LintIssue(
                "name_folder_mismatch",
                f"name '{name.strip()}' does not match folder '{expected_name}'",
            )
        )

    if not body.strip():
        issues.append(LintIssue("body_missing", "skill body must contain markdown instructions"))

    body_no_code = _strip_fenced_code(body)
    for target in _MARKDOWN_LINK_RE.findall(body_no_code):
        raw_target = target.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
        if not raw_target or _is_external_link(raw_target):
            continue
        if raw_target.startswith("/"):
            issues.append(LintIssue("link_absolute_path", f"absolute link path is not allowed: {target.strip()}"))
            continue
        resolved = (path.parent / raw_target).resolve()
        if not resolved.exists():
            issues.append(LintIssue("link_missing", f"referenced path does not exist: {raw_target}"))

    return SkillLintResult(path=path, issues=tuple(issues))


def discover_skill_files(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for skill_file in root.rglob("SKILL.md"):
            if skill_file.is_file():
                found.add(skill_file.resolve())
    return sorted(found)


def lint_skill_roots(roots: list[Path]) -> list[SkillLintResult]:
    return [lint_skill_file(path) for path in discover_skill_files(roots)]


def _default_roots() -> list[Path]:
    return [Path.home() / ".codex" / "skills"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint SKILL.md files")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root directory to scan for SKILL.md files (repeatable)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    roots = [Path(p).expanduser() for p in args.root] if args.root else _default_roots()
    results = lint_skill_roots(roots)
    if not results:
        print("No SKILL.md files found.")
        return 1

    issue_count = 0
    for result in results:
        if result.ok:
            print(f"OK {result.path}")
            continue
        print(f"FAIL {result.path}")
        for issue in result.issues:
            issue_count += 1
            print(f"  - {issue.code}: {issue.message}")

    print(f"Summary: skills={len(results)} issues={issue_count}")
    return 0 if issue_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
