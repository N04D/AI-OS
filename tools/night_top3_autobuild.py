#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _resolve_codex_bin() -> str | None:
    candidate = os.environ.get("CODEX_BIN", "").strip()
    if candidate and Path(candidate).exists():
        return candidate
    for path in (
        "/home/n04d/.npm-global/bin/codex",
        str(Path.home() / ".npm-global" / "bin" / "codex"),
        str(Path.home() / ".local" / "bin" / "codex"),
    ):
        if Path(path).exists():
            return path
    which = subprocess.run(["bash", "-lc", "command -v codex"], capture_output=True, text=True)
    resolved = which.stdout.strip()
    return resolved or None


def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git_failed:{' '.join(args)}:{proc.stderr.strip()}")
    return proc.stdout.strip()


def _ensure_workspace_branch(repo_root: Path) -> str:
    branch = _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch in {"dev", "main", "master"}:
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        new_branch = f"workspace/email-autobuild-{ts}"
        _git(repo_root, "checkout", "-b", new_branch)
        return new_branch
    return branch


@contextlib.contextmanager
def _disable_remote_push(repo_root: Path):
    remotes_raw = _git(repo_root, "remote")
    remotes = [r.strip() for r in remotes_raw.splitlines() if r.strip()]
    backup: dict[str, str] = {}
    for remote in remotes:
        pushurl = subprocess.run(
            ["git", "remote", "get-url", "--push", remote],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if pushurl.returncode == 0:
            backup[remote] = pushurl.stdout.strip()
        else:
            url = _git(repo_root, "remote", "get-url", remote)
            backup[remote] = url
        subprocess.run(["git", "remote", "set-url", "--push", remote, "disabled://local-only"], cwd=repo_root, check=False)
    try:
        yield
    finally:
        for remote, url in backup.items():
            subprocess.run(["git", "remote", "set-url", "--push", remote, url], cwd=repo_root, check=False)


def _extract_top3(report_text: str) -> list[dict[str, Any]]:
    lines = report_text.splitlines()
    idx = -1
    for i, line in enumerate(lines):
        low = line.lower()
        if "aanbevolen volgorde" in low or "top 3 voorstel (op score)" in low:
            idx = i
            break
    if idx < 0:
        return []
    top: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*\d+\.\s+\*\*(\d+)\.\s+\[([^\]]+)\]\s+(.+?)\*\*")
    for line in lines[idx + 1 :]:
        if not line.strip():
            if top:
                break
            continue
        m = pattern.match(line.strip())
        if not m:
            if top:
                break
            continue
        top.append(
            {
                "idea_id": int(m.group(1)),
                "category": m.group(2).strip(),
                "title": m.group(3).strip(),
            }
        )
        if len(top) == 3:
            break
    return top


def _latest_report(repo_root: Path) -> Path:
    report_dir = repo_root / "workspace" / "codex" / "night" / "reports"
    reports = sorted(report_dir.glob("*.md"))
    if not reports:
        raise RuntimeError("no_night_reports_found")
    return reports[-1]


def _append_history(repo_root: Path, record: dict[str, Any]) -> Path:
    history_path = repo_root / "workspace" / "codex" / "night" / "autobuild" / "history.jsonl"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return history_path


def run_autobuild(repo_root: Path, artifact_path: str) -> dict[str, Any]:
    report_path = _latest_report(repo_root)
    report_text = report_path.read_text(encoding="utf-8")
    top3 = _extract_top3(report_text)
    if len(top3) < 3:
        raise RuntimeError("top3_not_found_in_report")
    selected = [top3[1], top3[2]]

    codex_bin = _resolve_codex_bin()
    if not codex_bin:
        raise RuntimeError("codex_bin_not_found")

    branch = _ensure_workspace_branch(repo_root)

    prompt = f"""Operator-command triggered via email artifact:
{artifact_path}

Autonomous build task:
Implement now the OTHER 2 ideas from the latest report top-3:
1) #{selected[0]['idea_id']} [{selected[0]['category']}] {selected[0]['title']}
2) #{selected[1]['idea_id']} [{selected[1]['category']}] {selected[1]['title']}

Hard requirements:
- Make concrete code changes in this repository (not only plan text).
- Run relevant tests for changed components.
- Keep changes local-first and deterministic.
- Work only on local workspace branch: {branch}
- Do NOT push/fetch/pull any remote.
- Do NOT commit to dev/main/master.
- Output a short build summary with files changed and tests run.
"""
    prompt_file = repo_root / "runtime" / "tmp" / "autobuild_prompt.txt"
    out_file = repo_root / "runtime" / "tmp" / "autobuild_out.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")

    with _disable_remote_push(repo_root):
        proc = subprocess.run(
            [codex_bin, "exec", "--cd", str(repo_root), "--full-auto", "--output-last-message", str(out_file), "-"],
            input=prompt,
            text=True,
            capture_output=True,
        )

    out_text = out_file.read_text(encoding="utf-8").strip() if out_file.exists() else ""
    status = "ok" if proc.returncode == 0 else "error"
    record = {
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "type": "night_top3_autobuild",
        "status": status,
        "artifact_path": artifact_path,
        "report_path": str(report_path),
        "selected": selected,
        "branch": branch,
        "codex_rc": proc.returncode,
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
        "summary_tail": out_text[-2000:],
    }
    history_path = _append_history(repo_root, record)
    return {
        "status": status,
        "report_path": str(report_path),
        "selected": selected,
        "branch": branch,
        "history_path": str(history_path),
        "summary_tail": out_text[-1200:],
        "codex_rc": proc.returncode,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autobuild other two ideas from top-3")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--artifact-path", default="")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    artifact_path = args.artifact_path.strip()
    try:
        result = run_autobuild(repo_root=repo_root, artifact_path=artifact_path)
    except Exception as exc:
        result = {
            "status": "error",
            "error": str(exc),
            "artifact_path": artifact_path,
        }
        print(json.dumps(result, sort_keys=True, ensure_ascii=True))
        return 1

    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
