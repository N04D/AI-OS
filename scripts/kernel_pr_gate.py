#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from supervisor.pr_gate.gitea_client import (
    _normalize_api_base,
    get_commit_statuses,
    get_pull_request_files,
    get_pull_request_reviews,
)
from supervisor.pr_gate.kernel_enforcer import KernelEnforcer
from supervisor.pr_gate.kernel_policy import KernelPolicyError, load_kernel_policy_bundle


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _deny(reason_code: str) -> dict:
    return {
        "allow": False,
        "reason_code": reason_code,
        "failed_gates": [],
        "gate_events": [],
    }


def _extract_metadata(pr_body: str) -> dict:
    metadata: dict[str, str] = {}
    for line in (pr_body or "").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip().lower()
        if key:
            metadata[key] = v.strip()
    return metadata


def _build_context_from_fixtures(pr_path: str, extra_path: str) -> dict:
    pr = _load_json(pr_path)
    extra = _load_json(extra_path)
    return {
        "head_branch": str(((pr.get("head") or {}).get("ref") or "")).strip(),
        "pr_author": str(((pr.get("user") or {}).get("login") or "")).strip(),
        "pr_body": str(pr.get("body") or ""),
        "pr_metadata": _extract_metadata(str(pr.get("body") or "")),
        "changed_files": list(extra.get("files") or []),
        "reviews": list(extra.get("reviews") or []),
        "ci_statuses": list(extra.get("statuses") or []),
        "escalation_level": str(extra.get("escalation_level") or ""),
        "owner_approved": bool(extra.get("owner_approved", False)),
        "toolchain": dict(extra.get("toolchain") or {}),
        "mirror": dict(extra.get("mirror") or {}),
        "governance_baseline_hash": str(extra.get("governance_baseline_hash") or ""),
    }


def _build_context_from_api(
    api_base: str,
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    escalation_level: str,
    owner_approved: bool,
    toolchain: dict,
    mirror: dict,
    governance_baseline_hash: str,
) -> dict:
    import urllib.error
    import urllib.request

    base = _normalize_api_base(api_base)
    headers = {"Authorization": f"token {token}", "Accept": "application/json"}
    pr_url = f"{base}/repos/{owner}/{repo}/pulls/{pr_number}"
    req = urllib.request.Request(pr_url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            pr = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc

    head_sha = str(((pr.get("head") or {}).get("sha") or "")).strip()
    files = get_pull_request_files(base, owner, repo, pr_number, headers=headers)
    reviews = get_pull_request_reviews(base, owner, repo, pr_number, headers=headers)
    statuses = get_commit_statuses(base, owner, repo, head_sha, headers=headers)

    return {
        "head_branch": str(((pr.get("head") or {}).get("ref") or "")).strip(),
        "pr_author": str(((pr.get("user") or {}).get("login") or "")).strip(),
        "pr_body": str(pr.get("body") or ""),
        "pr_metadata": _extract_metadata(str(pr.get("body") or "")),
        "changed_files": files,
        "reviews": reviews,
        "ci_statuses": statuses,
        "escalation_level": escalation_level,
        "owner_approved": owner_approved,
        "toolchain": toolchain,
        "mirror": mirror,
        "governance_baseline_hash": governance_baseline_hash,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kernel PR gate evaluator")
    parser.add_argument("--output", default="kernel-gate-verdict.json")
    parser.add_argument("--governance-policy", default="governance_policy.yaml")
    parser.add_argument(
        "--checklist-policy",
        default="governance/policy/kernel-enforcement-checklist.v0.1.yaml",
    )
    parser.add_argument("--pr-json", help="Fixture PR payload path (offline mode)")
    parser.add_argument("--extra-json", help="Fixture extra payload path (offline mode)")
    parser.add_argument("--api-base", help="Gitea API base")
    parser.add_argument("--repo", help="owner/repo")
    parser.add_argument("--pr-number", type=int, help="PR number")
    parser.add_argument("--token", help="Gitea token")
    parser.add_argument("--escalation-level", default="L0")
    parser.add_argument("--owner-approved", action="store_true")
    parser.add_argument("--toolchain-json", help="JSON object string for toolchain evidence")
    parser.add_argument("--mirror-json", help="JSON object string for mirror evidence")
    parser.add_argument("--governance-baseline-hash", required=True)
    args = parser.parse_args(argv)

    try:
        bundle = load_kernel_policy_bundle(
            governance_policy_path=args.governance_policy,
            checklist_path=args.checklist_policy,
        )
    except (KernelPolicyError, FileNotFoundError):
        _write_json(args.output, _deny("DENY_POLICY_LOAD_FAILED"))
        return 1

    toolchain = json.loads(args.toolchain_json) if args.toolchain_json else {}
    mirror = json.loads(args.mirror_json) if args.mirror_json else {}

    try:
        if args.pr_json and args.extra_json:
            ctx = _build_context_from_fixtures(args.pr_json, args.extra_json)
        else:
            if not (args.api_base and args.repo and args.pr_number and args.token):
                _write_json(args.output, _deny("DENY_MISSING_API_INPUT"))
                return 1
            owner, repo = args.repo.split("/", 1)
            ctx = _build_context_from_api(
                api_base=args.api_base,
                owner=owner,
                repo=repo,
                pr_number=args.pr_number,
                token=args.token,
                escalation_level=args.escalation_level,
                owner_approved=args.owner_approved,
                toolchain=toolchain,
                mirror=mirror,
                governance_baseline_hash=args.governance_baseline_hash,
            )
        if not str(ctx.get("escalation_level", "")).strip():
            ctx["escalation_level"] = args.escalation_level
        if "owner_approved" not in ctx:
            ctx["owner_approved"] = args.owner_approved
        if not isinstance(ctx.get("toolchain"), dict) or not ctx.get("toolchain"):
            ctx["toolchain"] = toolchain
        if not isinstance(ctx.get("mirror"), dict) or not ctx.get("mirror"):
            ctx["mirror"] = mirror
        if not str(ctx.get("governance_baseline_hash", "")).strip():
            ctx["governance_baseline_hash"] = args.governance_baseline_hash

        result = KernelEnforcer(bundle["checklist_policy"]).evaluate(ctx)
        verdict = {
            "allow": bool(result.get("passed", False)),
            "reason_code": "ALLOW_KERNEL_ENFORCEMENT_PASS"
            if result.get("passed", False)
            else "DENY_KERNEL_ENFORCEMENT_FAIL",
            "failed_gates": result.get("failed_gates", []),
            "gate_events": result.get("gate_events", []),
            "checklist_policy_sha": bundle["checklist_policy_sha"],
            "governance_policy_sha": bundle["governance_policy_sha"],
        }
        _write_json(args.output, verdict)
        return 0 if verdict["allow"] else 1
    except Exception:
        _write_json(args.output, _deny("DENY_KERNEL_ENFORCER_ERROR"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
