from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_ALLOWED_FRONTMATTER_KEYS = {"name", "description", "metadata"}
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class LintIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class SkillLintResult:
    path: Path
    issues: tuple[LintIssue, ...]

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")


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


def _normalized_internal_targets(markdown: str) -> Iterable[str]:
    body_no_code = _strip_fenced_code(markdown)
    for target in _MARKDOWN_LINK_RE.findall(body_no_code):
        raw_target = target.strip().strip("<>").split("#", 1)[0].split("?", 1)[0]
        if not raw_target or _is_external_link(raw_target):
            continue
        yield raw_target


def _check_links_for_file(
    *,
    root_doc: Path,
    skill_root: Path,
    current_doc: Path,
    current_text: str,
    current_depth: int,
    max_depth: int,
    strict_links: bool,
    issues: list[LintIssue],
    seen: set[tuple[Path, int]],
) -> None:
    state = (current_doc.resolve(), current_depth)
    if state in seen:
        return
    seen.add(state)

    for raw_target in _normalized_internal_targets(current_text):
        if raw_target.startswith("/"):
            issues.append(LintIssue("link_absolute_path", f"absolute link path is not allowed: {raw_target}"))
            continue
        resolved = (current_doc.parent / raw_target).resolve()
        try:
            resolved.relative_to(skill_root)
        except ValueError:
            issues.append(
                LintIssue(
                    "link_outside_skill",
                    (
                        "referenced path escapes skill directory at depth "
                        f"{current_depth}: {raw_target}"
                    ),
                )
            )
            continue
        if not resolved.exists():
            if current_depth == 1:
                issues.append(LintIssue("link_missing", f"referenced path does not exist: {raw_target}"))
            else:
                nested_severity = "error" if strict_links else "warning"
                try:
                    rel_doc = current_doc.relative_to(root_doc.parent)
                except ValueError:
                    rel_doc = current_doc
                issues.append(
                    LintIssue(
                        "link_missing",
                        (
                            "referenced path does not exist at depth "
                            f"{current_depth}: {raw_target} (from {rel_doc})"
                        ),
                        severity=nested_severity,
                    )
                )
            continue

        # Only recurse into markdown documents.
        if current_depth >= max_depth or not resolved.is_file():
            continue
        if resolved.suffix.lower() not in {".md", ".markdown"}:
            continue
        try:
            nested_text = resolved.read_text(encoding="utf-8")
        except OSError:
            continue
        _check_links_for_file(
            root_doc=root_doc,
            skill_root=skill_root,
            current_doc=resolved,
            current_text=nested_text,
            current_depth=current_depth + 1,
            max_depth=max_depth,
            strict_links=strict_links,
            issues=issues,
            seen=seen,
        )


def lint_skill_file(path: Path, *, link_depth: int = 1, strict_links: bool = False) -> SkillLintResult:
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

    depth = max(1, link_depth)
    _check_links_for_file(
        root_doc=path,
        skill_root=path.parent.resolve(),
        current_doc=path,
        current_text=body,
        current_depth=1,
        max_depth=depth,
        strict_links=strict_links,
        issues=issues,
        seen=set(),
    )

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


def lint_skill_roots(
    roots: list[Path],
    *,
    link_depth: int = 1,
    strict_links: bool = False,
) -> list[SkillLintResult]:
    return [lint_skill_file(path, link_depth=link_depth, strict_links=strict_links) for path in discover_skill_files(roots)]


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
    parser.add_argument(
        "--link-depth",
        type=int,
        default=1,
        help="Depth for recursive markdown link validation (default: 1)",
    )
    parser.add_argument(
        "--strict-links",
        action="store_true",
        help="Treat missing recursive links beyond depth 1 as errors",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    roots = [Path(p).expanduser() for p in args.root] if args.root else _default_roots()
    link_depth = max(1, int(args.link_depth or 1))
    results = lint_skill_roots(roots, link_depth=link_depth, strict_links=bool(args.strict_links))
    if not results:
        print("No SKILL.md files found.")
        return 1

    issue_count = 0
    error_count = 0
    warning_count = 0
    for result in results:
        issue_count += len(result.issues)
        error_count += result.error_count
        warning_count += result.warning_count
        if result.error_count == 0 and result.warning_count == 0:
            print(f"OK {result.path}")
            continue
        if result.error_count > 0:
            print(f"FAIL {result.path}")
        else:
            print(f"WARN {result.path}")
        for issue in result.issues:
            print(f"  - {issue.severity}: {issue.code}: {issue.message}")

    print(
        f"Summary: skills={len(results)} issues={issue_count} "
        f"errors={error_count} warnings={warning_count}"
    )
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
