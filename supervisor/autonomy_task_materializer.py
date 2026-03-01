from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from supervisor.budgets.autonomy import DEFAULT_HOST_STATE_DIR
from supervisor.budgets.autonomy import check_budget
from supervisor.budgets.autonomy import consume_budget

class AutonomyTaskMaterializerError(RuntimeError):
    pass


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def deterministic_task_id(proposal_hash: str) -> str:
    normalized = proposal_hash.strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", normalized):
        raise AutonomyTaskMaterializerError("invalid_proposal_hash")
    return f"autonomy-task-{normalized[:16]}"


def _normalize_api_base(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise AutonomyTaskMaterializerError("missing_gitea_base_url")
    if base.endswith("/api/v1"):
        return base
    if "/api/v1" in base:
        return base.split("/api/v1", 1)[0] + "/api/v1"
    return f"{base}/api/v1"


def _git_is_clean() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == ""


def _api_json_request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"token {token}",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        parsed: Any = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw": body}
        return exc.code, parsed


def _is_bot_login(login: str) -> bool:
    lowered = login.strip().lower()
    return lowered.endswith("[bot]") or lowered.endswith("-bot") or lowered == "bot"


def _extract_proposal_hash(pr: dict[str, Any]) -> str:
    body = str(pr.get("body") or "")
    match = re.search(r"proposal_hash:\s*([a-fA-F0-9]{64})", body)
    if not match:
        raise AutonomyTaskMaterializerError(
            f"hash_mismatch:missing_hash_in_body:pr#{pr.get('number')}"
        )
    return match.group(1).lower()


def _branch_hash_prefix(branch_name: str) -> str:
    match = re.fullmatch(r"autonomy/proposal-([a-fA-F0-9]{16})", branch_name.strip())
    if not match:
        raise AutonomyTaskMaterializerError(f"hash_mismatch:invalid_branch:{branch_name}")
    return match.group(1).lower()


def _has_non_bot_approval(reviews: list[dict[str, Any]]) -> bool:
    for review in reviews:
        state = str(review.get("state") or "").upper()
        login = str(((review.get("user") or {}).get("login") or "")).strip()
        if state == "APPROVED" and login and not _is_bot_login(login):
            return True
    return False


def _sorted_autonomy_intake_prs(pulls_data: list[dict[str, Any]], label_name: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for pr in pulls_data:
        head_ref = str(((pr.get("head") or {}).get("ref") or "")).strip()
        labels = [str((lbl.get("name") or "")).strip() for lbl in (pr.get("labels") or [])]
        if head_ref.startswith("autonomy/proposal-") and label_name in labels:
            selected.append(pr)
    return sorted(
        selected,
        key=lambda pr: (
            int(pr.get("number", 0)),
            str(((pr.get("head") or {}).get("ref") or "")),
        ),
    )


def materialize_autonomy_tasks(
    *,
    repo_owner: str = "N04D",
    repo_name: str = "AI-OS",
    base_branch: str = "dev",
    intake_label: str = "intake-processed",
    host_state_dir: str = DEFAULT_HOST_STATE_DIR,
    gitea_base_url: str | None = None,
    gitea_token: str | None = None,
) -> list[dict[str, Any]]:
    token = (gitea_token or os.environ.get("GITEA_TOKEN", "")).strip()
    if not token:
        raise AutonomyTaskMaterializerError("missing_gitea_token")
    if not _git_is_clean():
        raise AutonomyTaskMaterializerError("dirty_worktree")
    budget_check = check_budget("materialize", context_id="gate:materialize", host_state_dir=host_state_dir)
    if not budget_check.get("allowed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_check.get("reason", "budget_rejected"),
                "budget": budget_check.get("state", {}),
            }
        ]
    budget_consume = consume_budget("materialize", context_id="gate:materialize", host_state_dir=host_state_dir)
    if not budget_consume.get("consumed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_consume.get("reason", "budget_consume_failed"),
                "budget": budget_consume.get("state", {}),
            }
        ]

    api_base = _normalize_api_base(
        (gitea_base_url or os.environ.get("GITEA_BASE_URL", "")).strip()
    )
    pulls_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls?state=open&base={base_branch}&limit=300"
    status, pulls_data = _api_json_request("GET", pulls_url, token)
    if status != 200 or not isinstance(pulls_data, list):
        raise AutonomyTaskMaterializerError(f"pulls_list_failed:{status}")

    intake_prs = _sorted_autonomy_intake_prs(pulls_data, intake_label)

    state_root = Path(host_state_dir)
    inbox_dir = state_root / "autonomy" / "inbox" / "tasks"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    intake_log_path = state_root / "autonomy" / "intake-log.jsonl"
    intake_log_path.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    log_lines: list[str] = []

    for pr in intake_prs:
        pr_number = int(pr.get("number", 0))
        head_ref = str(((pr.get("head") or {}).get("ref") or "")).strip()
        proposal_hash = _extract_proposal_hash(pr)
        branch_prefix = _branch_hash_prefix(head_ref)
        if proposal_hash[:16] != branch_prefix:
            raise AutonomyTaskMaterializerError(f"hash_mismatch:pr#{pr_number}")

        reviews_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews"
        reviews_status, reviews_data = _api_json_request("GET", reviews_url, token)
        if reviews_status != 200 or not isinstance(reviews_data, list):
            raise AutonomyTaskMaterializerError(
                f"reviews_list_failed:{pr_number}:{reviews_status}"
            )
        if not _has_non_bot_approval(reviews_data):
            raise AutonomyTaskMaterializerError(f"approval_required:pr#{pr_number}")

        task_id = deterministic_task_id(proposal_hash)
        task_path = inbox_dir / f"{task_id}.json"
        task_payload: dict[str, Any] = {
            "version": "autonomy-task-materializer.v0.1",
            "task_id": task_id,
            "proposal_hash": proposal_hash,
            "source": {
                "pr_number": pr_number,
                "pr_url": str(pr.get("html_url") or ""),
                "pr_title": str(pr.get("title") or ""),
                "head": head_ref,
                "base": str(((pr.get("base") or {}).get("ref") or base_branch)),
                "label": intake_label,
            },
        }

        if task_path.is_file():
            try:
                current = json.loads(task_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise AutonomyTaskMaterializerError(f"task_read_failed:{task_path}") from exc
            if _canonical_json(current) != _canonical_json(task_payload):
                raise AutonomyTaskMaterializerError(f"task_exists_mismatch:{task_id}")
            results.append(
                {
                    "task_id": task_id,
                    "proposal_hash": proposal_hash,
                    "task_path": str(task_path),
                    "status": "noop",
                    "pr_number": pr_number,
                }
            )
            continue

        task_path.write_text(
            json.dumps(task_payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        log_entry = {
            "event": "materialized",
            "task_id": task_id,
            "proposal_hash": proposal_hash,
            "pr_number": pr_number,
            "task_path": str(task_path),
        }
        log_lines.append(json.dumps(log_entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        results.append(
            {
                "task_id": task_id,
                "proposal_hash": proposal_hash,
                "task_path": str(task_path),
                "status": "materialized",
                "pr_number": pr_number,
            }
        )

    if log_lines:
        with intake_log_path.open("a", encoding="utf-8") as fh:
            for line in log_lines:
                fh.write(line + "\n")

    return sorted(results, key=lambda item: _canonical_json(item))
