#!/usr/bin/env python3
from __future__ import annotations

import json
import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

SCAN_ROOTS = ("docs", "governance", "schemas")
REF_ROOT_PREFIXES = ("docs/", "governance/", "schemas/", "supervisor/", "scripts/", "state/")
DOC_EXTENSIONS = {".md", ".markdown", ".txt", ".yaml", ".yml", ".json"}
GENERATED_OUTPUTS = {
    "docs/index/spec_inventory.md",
    "docs/index/spec_inventory.json",
    "docs/index/dangling_refs.md",
}
EXCLUDED_PREFIXES = (
    "docs/archive/legacy_specs/",
)

MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
PLAIN_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"((?:docs|governance|schemas|supervisor|scripts|state)/[A-Za-z0-9_./-]+)"
    r"(?![A-Za-z0-9_.-])"
)


@dataclass(frozen=True)
class RefHit:
    raw: str
    normalized: str
    status: str
    line: int
    context: str


def _is_doc_path(path: Path) -> bool:
    rel = path.as_posix()
    if rel in GENERATED_OUTPUTS:
        return False
    if rel.startswith(EXCLUDED_PREFIXES):
        return False
    if path.suffix.lower() not in DOC_EXTENSIONS:
        return False
    parts = path.parts
    if parts and parts[0] == "supervisor":
        return "docs" in parts
    return True


def _iter_doc_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for item in sorted(root.rglob("*")):
            if item.is_file() and _is_doc_path(item.relative_to(repo_root)):
                files.append(item)

    supervisor_root = repo_root / "supervisor"
    if supervisor_root.is_dir():
        for item in sorted(supervisor_root.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(repo_root)
            if _is_doc_path(rel):
                files.append(item)

    deduped = sorted(set(files), key=lambda p: str(p.relative_to(repo_root)).replace("\\", "/"))
    return deduped


def _classify_doc(rel_path: str) -> str:
    lowered = rel_path.lower()
    name = lowered.rsplit("/", 1)[-1]
    if "roadmap" in lowered:
        return "roadmap"
    if "progress" in lowered:
        return "progress"
    if "policy" in lowered:
        return "policy"
    if "schema" in lowered or lowered.startswith("schemas/") or "/schema/" in lowered:
        return "schema"
    if "spec" in lowered or "/specs/" in lowered:
        return "spec"
    if "note" in lowered or name.startswith("notes"):
        return "note"
    return "other"


def _normalize_reference(raw: str, doc_rel: PurePosixPath) -> tuple[str, str] | None:
    candidate = raw.strip().strip("<>").strip('"').strip("'")
    if not candidate:
        return None
    if "://" in candidate or candidate.startswith("#") or candidate.startswith("mailto:"):
        return None

    candidate = candidate.split("#", 1)[0].split("?", 1)[0].strip()
    if not candidate:
        return None

    if candidate.startswith("/"):
        candidate = candidate.lstrip("/")

    for trailing in (".", ",", ";", ":", ")", "]"):
        if candidate.endswith(trailing):
            candidate = candidate[: -len(trailing)]

    if not candidate:
        return None

    if candidate.startswith(REF_ROOT_PREFIXES):
        normalized = posixpath.normpath(candidate)
    else:
        joined = posixpath.normpath(str(doc_rel.parent / candidate))
        if joined.startswith("../") or joined == "..":
            return None
        normalized = joined

    if not normalized or normalized == ".":
        return None

    if not normalized.startswith(("docs/", "governance/", "schemas/", "supervisor/", "scripts/", "state/")):
        return None

    return candidate, normalized


def _status_for_path(repo_root: Path, normalized: str, raw_candidate: str) -> str:
    path = repo_root / normalized
    looks_dir = raw_candidate.endswith("/") or Path(raw_candidate).suffix == ""
    if looks_dir:
        return "ambiguous"
    if path.is_file():
        return "exists"
    if path.is_dir():
        return "ambiguous"
    return "missing"


def _extract_refs(repo_root: Path, doc_path: Path) -> list[RefHit]:
    rel = PurePosixPath(doc_path.relative_to(repo_root).as_posix())
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    hits: list[RefHit] = []
    seen: set[tuple[str, str, str, int]] = set()

    for line_no, line in enumerate(text.splitlines(), start=1):
        candidates: list[str] = []
        candidates.extend(MD_LINK_RE.findall(line))
        candidates.extend(INLINE_CODE_RE.findall(line))
        candidates.extend(match.group(1) for match in PLAIN_PATH_RE.finditer(line))

        for raw in candidates:
            normalized_pair = _normalize_reference(raw, rel)
            if normalized_pair is None:
                continue
            raw_candidate, normalized = normalized_pair
            status = _status_for_path(repo_root, normalized, raw_candidate)
            key = (raw.strip(), normalized, status, line_no)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                RefHit(
                    raw=raw.strip(),
                    normalized=normalized,
                    status=status,
                    line=line_no,
                    context=" ".join(line.strip().split()),
                )
            )

    hits.sort(key=lambda h: (h.normalized, h.line, h.raw, h.status))
    return hits


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _render_inventory_md(docs: list[dict], summary: dict) -> str:
    lines: list[str] = []
    lines.append("# Spec & Doc Inventory")
    lines.append("")
    lines.append(f"- total docs scanned: {summary['total_docs_scanned']}")
    lines.append(f"- total refs found: {summary['total_refs_found']}")
    lines.append(f"- missing refs count: {summary['missing_refs_count']}")
    lines.append("")
    lines.append("| Document | Type | Ref count | Missing refs count | Status |")
    lines.append("|---|---|---:|---:|---|")
    for doc in docs:
        lines.append(
            f"| {doc['path']} | {doc['type']} | {len(doc['refs'])} | {len(doc['missing_refs'])} | {doc['status']} |"
        )

    lines.append("")
    lines.append("## Missing References Per Document")
    lines.append("")
    for doc in docs:
        lines.append(f"### {doc['path']}")
        if not doc["missing_refs"]:
            lines.append("- none")
        else:
            for ref in doc["missing_refs"]:
                lines.append(f"- {ref}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_dangling_md(docs: list[dict], missing_hits: dict[str, list[dict]]) -> str:
    lines: list[str] = []
    lines.append("# Dangling References Audit")
    lines.append("")
    lines.append("## Grouped By Missing Path")
    lines.append("")
    if not missing_hits:
        lines.append("- none")
    else:
        for missing_path in sorted(missing_hits.keys()):
            lines.append(f"### {missing_path}")
            refs = sorted(missing_hits[missing_path], key=lambda r: (r["doc"], r["line"], r["raw"]))
            for ref in refs:
                lines.append(f"- {ref['doc']}:{ref['line']} — {ref['context']}")
            lines.append("")

    lines.append("## Grouped By Document")
    lines.append("")
    for doc in docs:
        misses = [r for r in doc["refs"] if r["status"] == "missing"]
        lines.append(f"### {doc['path']}")
        if not misses:
            lines.append("- none")
        else:
            for ref in sorted(misses, key=lambda r: (r["normalized"], r["line"], r["raw"])):
                lines.append(f"- {ref['normalized']} ({doc['path']}:{ref['line']}) — {ref['context']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _json_doc_entry(path: str, doc_type: str, refs: Iterable[RefHit]) -> dict:
    ref_list = []
    missing = []
    for hit in refs:
        ref_list.append({"raw": hit.raw, "normalized": hit.normalized, "status": hit.status, "line": hit.line, "context": hit.context})
        if hit.status == "missing":
            missing.append(hit.normalized)

    missing_sorted = sorted(set(missing))
    return {
        "path": path,
        "type": doc_type,
        "refs": ref_list,
        "missing_refs": missing_sorted,
        "status": "HAS_MISSING_REFS" if missing_sorted else "OK",
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    docs = []
    missing_hits: dict[str, list[dict]] = defaultdict(list)

    for doc_file in _iter_doc_files(repo_root):
        rel = doc_file.relative_to(repo_root).as_posix()
        doc_type = _classify_doc(rel)
        refs = _extract_refs(repo_root, doc_file)
        entry = _json_doc_entry(rel, doc_type, refs)
        docs.append(entry)

        for ref in entry["refs"]:
            if ref["status"] == "missing":
                missing_hits[ref["normalized"]].append(
                    {
                        "doc": rel,
                        "line": int(ref["line"]),
                        "raw": str(ref["raw"]),
                        "context": str(ref["context"]),
                    }
                )

    docs.sort(key=lambda d: d["path"])

    summary = {
        "total_docs_scanned": len(docs),
        "total_refs_found": sum(len(doc["refs"]) for doc in docs),
        "missing_refs_count": sum(1 for doc in docs for ref in doc["refs"] if ref["status"] == "missing"),
    }

    payload = {
        "generated_at": None,
        "repo_root": str(repo_root),
        "docs": docs,
        "summary": summary,
    }

    inventory_json = repo_root / "docs" / "index" / "spec_inventory.json"
    inventory_md = repo_root / "docs" / "index" / "spec_inventory.md"
    dangling_md = repo_root / "docs" / "index" / "dangling_refs.md"

    _write_text(inventory_json, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    _write_text(inventory_md, _render_inventory_md(docs, summary))
    _write_text(dangling_md, _render_dangling_md(docs, missing_hits))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
