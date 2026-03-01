from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from supervisor.budgets.autonomy import DEFAULT_HOST_STATE_DIR
from supervisor.budgets.autonomy import check_budget
from supervisor.budgets.autonomy import consume_budget


class AutonomyPromotionGateError(RuntimeError):
    pass


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposal_content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def deterministic_branch_name(content: str) -> str:
    digest = proposal_content_sha256(content)
    return f"autonomy/proposal-{digest[:16]}"


def _normalize_api_base(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise AutonomyPromotionGateError("missing_gitea_base_url")
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


def _load_proposal_files(proposals_dir: str) -> list[dict[str, str]]:
    root = Path(proposals_dir)
    if not root.is_dir():
        return []

    proposals: list[dict[str, str]] = []
    for path in sorted(root.glob("proposal.*.md")):
        content = path.read_text(encoding="utf-8")
        content_hash = proposal_content_sha256(content)
        parts = path.name.split(".")
        if len(parts) < 4:
            raise AutonomyPromotionGateError(f"proposal_hash_mismatch:{path}")
        expected_prefix = parts[-2]
        if expected_prefix != content_hash[:12]:
            raise AutonomyPromotionGateError(f"proposal_hash_mismatch:{path}")
        proposals.append(
            {
                "path": str(path),
                "content": content,
                "content_hash": content_hash,
                "branch": deterministic_branch_name(content),
                "type": parts[1],
            }
        )
    return proposals


def create_draft_proposals_prs(
    proposals_dir: str | None = None,
    *,
    proposals: list[dict[str, Any]] | None = None,
    repo_owner: str = "N04D",
    repo_name: str = "AI-OS",
    base_branch: str = "dev",
    gitea_base_url: str | None = None,
    gitea_token: str | None = None,
) -> list[dict[str, Any]]:
    token = (gitea_token or os.environ.get("GITEA_TOKEN", "")).strip()
    if not token:
        raise AutonomyPromotionGateError("missing_gitea_token")
    if not _git_is_clean():
        raise AutonomyPromotionGateError("dirty_worktree")
    host_state_dir = os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR
    budget_check = check_budget("promotion", context_id="gate:promotion", host_state_dir=host_state_dir)
    if not budget_check.get("allowed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_check.get("reason", "budget_rejected"),
                "budget": budget_check.get("state", {}),
            }
        ]
    budget_consume = consume_budget("promotion", context_id="gate:promotion", host_state_dir=host_state_dir)
    if not budget_consume.get("consumed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_consume.get("reason", "budget_consume_failed"),
                "budget": budget_consume.get("state", {}),
            }
        ]

    resolved_proposals: list[dict[str, str]]
    if proposals is not None:
        resolved_proposals = []
        for item in proposals:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "")
            content_hash = str(item.get("hash") or "")
            filename = str(item.get("filename") or "")
            branch = str(item.get("branch_name") or "")
            if not content or not content_hash or not filename or not branch:
                continue
            actual_hash = proposal_content_sha256(content)
            if actual_hash != content_hash:
                raise AutonomyPromotionGateError(f"proposal_hash_mismatch:inline:{filename}")
            if branch != deterministic_branch_name(content):
                raise AutonomyPromotionGateError(f"proposal_branch_mismatch:inline:{filename}")
            resolved_proposals.append(
                {
                    "path": str(item.get("path") or f"docs/autonomy/proposals/{filename}"),
                    "content": content,
                    "content_hash": content_hash,
                    "branch": branch,
                    "type": str(item.get("type") or "unknown"),
                }
            )
    else:
        if not proposals_dir:
            raise AutonomyPromotionGateError("missing_proposals_input")
        resolved_proposals = _load_proposal_files(proposals_dir)

    if not resolved_proposals:
        return []

    api_base = _normalize_api_base(
        (gitea_base_url or os.environ.get("GITEA_BASE_URL", "")).strip()
    )
    pulls_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls?state=open&base={base_branch}&limit=300"
    status, pulls_data = _api_json_request("GET", pulls_url, token)
    if status != 200 or not isinstance(pulls_data, list):
        raise AutonomyPromotionGateError(f"pulls_list_failed:{status}")

    existing_by_head: dict[str, dict[str, Any]] = {}
    for pr in pulls_data:
        head_ref = ((pr.get("head") or {}).get("ref") or "").strip()
        if head_ref:
            existing_by_head[head_ref] = pr

    created: list[dict[str, Any]] = []
    for proposal in resolved_proposals:
        branch = proposal["branch"]
        if branch in existing_by_head:
            existing = existing_by_head[branch]
            created.append(
                {
                    "status": "existing",
                    "branch": branch,
                    "proposal_path": proposal["path"],
                    "proposal_hash": proposal["content_hash"],
                    "pr_number": existing.get("number"),
                    "pr_url": existing.get("html_url"),
                }
            )
            continue

        title = f"[autonomy-proposal] {proposal['type']} {proposal['content_hash'][:12]}"
        body = (
            "Deterministic autonomy proposal draft PR.\n\n"
            f"- proposal_path: {proposal['path']}\n"
            f"- proposal_hash: {proposal['content_hash']}\n"
            "- execution: none (proposal only)\n"
        )
        payload = {
            "title": title,
            "head": branch,
            "base": base_branch,
            "body": body,
            "draft": True,
        }
        create_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls"
        create_status, created_data = _api_json_request("POST", create_url, token, payload=payload)
        if create_status not in (200, 201) or not isinstance(created_data, dict):
            raise AutonomyPromotionGateError(f"pull_create_failed:{create_status}")
        created.append(
            {
                "status": "created",
                "branch": branch,
                "proposal_path": proposal["path"],
                "proposal_hash": proposal["content_hash"],
                "pr_number": created_data.get("number"),
                "pr_url": created_data.get("html_url"),
            }
        )

    return sorted(created, key=lambda item: _canonical_json(item))
