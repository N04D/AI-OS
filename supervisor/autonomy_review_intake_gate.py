from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any

from aios.secrets.context import ContextFactory
from aios.secrets.integration import resolve_gitea_token
from supervisor.gitea_config import resolve_gitea_base_url
from supervisor.budgets.autonomy import DEFAULT_HOST_STATE_DIR
from supervisor.budgets.autonomy import check_budget
from supervisor.budgets.autonomy import consume_budget


class AutonomyReviewIntakeGateError(RuntimeError):
    pass


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _normalize_api_base(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise AutonomyReviewIntakeGateError("missing_gitea_base_url")
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
        raise AutonomyReviewIntakeGateError(f"hash_mismatch:missing_hash_in_body:pr#{pr.get('number')}")
    return match.group(1).lower()


def _branch_hash_prefix(branch_name: str) -> str:
    match = re.fullmatch(r"autonomy/proposal-([a-fA-F0-9]{16})", branch_name.strip())
    if not match:
        raise AutonomyReviewIntakeGateError(f"hash_mismatch:invalid_branch:{branch_name}")
    return match.group(1).lower()


def _has_non_bot_approval(reviews: list[dict[str, Any]]) -> bool:
    for review in reviews:
        state = str(review.get("state") or "").upper()
        login = str(((review.get("user") or {}).get("login") or "")).strip()
        if state == "APPROVED" and login and not _is_bot_login(login):
            return True
    return False


def intake_approved_autonomy_proposals(
    *,
    repo_owner: str = "N04D",
    repo_name: str = "AI-OS",
    base_branch: str = "dev",
    label_name: str = "intake-processed",
    gitea_base_url: str | None = None,
    gitea_token: str | None = None,
) -> list[dict[str, Any]]:
    token = resolve_gitea_token(
        explicit_token=gitea_token,
        context=ContextFactory.supervisor_autonomy_review_intake_gate(),
    )
    if not token:
        raise AutonomyReviewIntakeGateError("missing_gitea_token")
    if not _git_is_clean():
        raise AutonomyReviewIntakeGateError("dirty_worktree")
    host_state_dir = os.environ.get("HOST_STATE_DIR", "").strip() or DEFAULT_HOST_STATE_DIR
    budget_check = check_budget("intake", context_id="gate:intake", host_state_dir=host_state_dir)
    if not budget_check.get("allowed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_check.get("reason", "budget_rejected"),
                "budget": budget_check.get("state", {}),
            }
        ]
    budget_consume = consume_budget("intake", context_id="gate:intake", host_state_dir=host_state_dir)
    if not budget_consume.get("consumed", False):
        return [
            {
                "status": "rejected",
                "reason": budget_consume.get("reason", "budget_consume_failed"),
                "budget": budget_consume.get("state", {}),
            }
        ]

    api_base = _normalize_api_base(resolve_gitea_base_url(explicit_base_url=gitea_base_url))
    pulls_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls?state=open&base={base_branch}&limit=300"
    status, pulls_data = _api_json_request("GET", pulls_url, token)
    if status != 200 or not isinstance(pulls_data, list):
        raise AutonomyReviewIntakeGateError(f"pulls_list_failed:{status}")

    autonomy_prs: list[dict[str, Any]] = []
    for pr in pulls_data:
        head_ref = str(((pr.get("head") or {}).get("ref") or "")).strip()
        if head_ref.startswith("autonomy/proposal-"):
            autonomy_prs.append(pr)

    # Deterministic ordering.
    autonomy_prs = sorted(
        autonomy_prs,
        key=lambda pr: (
            int(pr.get("number", 0)),
            str(((pr.get("head") or {}).get("ref") or "")),
        ),
    )

    results: list[dict[str, Any]] = []
    for pr in autonomy_prs:
        pr_number = int(pr.get("number", 0))
        head_ref = str(((pr.get("head") or {}).get("ref") or "")).strip()
        labels = [str((lbl.get("name") or "")).strip() for lbl in (pr.get("labels") or [])]

        proposal_hash = _extract_proposal_hash(pr)
        branch_prefix = _branch_hash_prefix(head_ref)
        if proposal_hash[:16] != branch_prefix:
            raise AutonomyReviewIntakeGateError(f"hash_mismatch:pr#{pr_number}")

        if label_name in labels:
            results.append(
                {
                    "pr_number": pr_number,
                    "head": head_ref,
                    "status": "already_processed",
                    "approved": None,
                    "label": label_name,
                }
            )
            continue

        reviews_url = f"{api_base}/repos/{repo_owner}/{repo_name}/pulls/{pr_number}/reviews"
        reviews_status, reviews_data = _api_json_request("GET", reviews_url, token)
        if reviews_status != 200 or not isinstance(reviews_data, list):
            raise AutonomyReviewIntakeGateError(f"reviews_list_failed:{pr_number}:{reviews_status}")

        approved = _has_non_bot_approval(reviews_data)
        if not approved:
            results.append(
                {
                    "pr_number": pr_number,
                    "head": head_ref,
                    "status": "pending_review",
                    "approved": False,
                    "label": None,
                }
            )
            continue

        labels_url = f"{api_base}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/labels"
        label_status, label_data = _api_json_request(
            "POST",
            labels_url,
            token,
            payload={"labels": [label_name]},
        )
        if label_status not in (200, 201) or not isinstance(label_data, list):
            raise AutonomyReviewIntakeGateError(f"label_apply_failed:{pr_number}:{label_status}")
        results.append(
            {
                "pr_number": pr_number,
                "head": head_ref,
                "status": "intake_processed",
                "approved": True,
                "label": label_name,
            }
        )

    return sorted(results, key=lambda item: _canonical_json(item))
