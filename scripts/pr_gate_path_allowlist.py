#!/usr/bin/env python3
"""Minimal PR-Gate v0.1 evaluator (path allowlist only)."""

from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


def _utc_now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_path(path: str) -> str:
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    return p


def _policy_sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _strip_inline_comment(line: str) -> str:
    if "#" not in line:
        return line
    in_single = False
    in_double = False
    out: List[str] = []
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _parse_scalar(text: str):
    value = text.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.isdigit():
        return int(value)
    return value


def _parse_yaml_minimal(raw: str) -> Dict:
    """Parse a narrow YAML subset needed by path-allowlist.v1.yaml."""
    version = None
    default_decision = None
    rules: List[Dict] = []
    current_rule = None
    in_rules = False
    in_allow = False
    in_paths = False

    for original in raw.splitlines():
        line = _strip_inline_comment(original)
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0 and stripped.startswith("version:"):
            version = _parse_scalar(stripped.split(":", 1)[1])
            in_rules = in_allow = in_paths = False
            continue
        if indent == 0 and stripped.startswith("default_decision:"):
            default_decision = str(_parse_scalar(stripped.split(":", 1)[1]))
            in_rules = in_allow = in_paths = False
            continue
        if indent == 0 and stripped == "rules:":
            in_rules = True
            in_allow = False
            in_paths = False
            continue
        if not in_rules:
            continue

        if indent == 2 and stripped.startswith("- id:"):
            rule_id = str(_parse_scalar(stripped.split(":", 1)[1]))
            current_rule = {"id": rule_id, "allow": {"paths": []}}
            rules.append(current_rule)
            in_allow = False
            in_paths = False
            continue

        if current_rule is None:
            continue

        if indent == 4 and stripped == "allow:":
            in_allow = True
            in_paths = False
            continue
        if indent == 6 and stripped == "paths:" and in_allow:
            in_paths = True
            continue
        if indent >= 8 and stripped.startswith("- ") and in_paths:
            path_glob = str(_parse_scalar(stripped[2:]))
            current_rule["allow"]["paths"].append(path_glob)

    if version is None or default_decision is None:
        raise ValueError("Policy missing required keys: version/default_decision")
    return {
        "version": version,
        "default_decision": default_decision,
        "rules": rules,
    }


def load_policy(policy_path: str) -> Tuple[Dict, str]:
    raw = Path(policy_path).read_text(encoding="utf-8")
    digest = _policy_sha(raw)
    try:
        import yaml  # type: ignore

        policy = yaml.safe_load(raw)
    except ModuleNotFoundError:
        policy = _parse_yaml_minimal(raw)

    if not isinstance(policy, dict):
        raise ValueError("Policy root must be a mapping")
    return policy, digest


def _extract_allow_rules(policy: Dict) -> List[Tuple[str, str]]:
    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        return []
    out: List[Tuple[str, str]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("id") or f"rule-{idx}")
        allow = rule.get("allow", {})
        if not isinstance(allow, dict):
            continue
        paths = allow.get("paths", [])
        if not isinstance(paths, list):
            continue
        for p in paths:
            pat = _normalize_path(str(p))
            if pat:
                out.append((rule_id, pat))
    return out


def _match_path(path: str, rule_patterns: Sequence[Tuple[str, str]]) -> Tuple[bool, Set[str]]:
    matched: Set[str] = set()
    for rule_id, pattern in rule_patterns:
        if fnmatch.fnmatch(path, pattern):
            matched.add(rule_id)
    return bool(matched), matched


def evaluate_paths(policy: Dict, changed_files: Iterable[str], policy_sha: str) -> Dict:
    default_decision = str(policy.get("default_decision", "")).strip().lower()
    evaluated_at = _utc_now_iso()
    rule_patterns = _extract_allow_rules(policy)
    files = sorted({_normalize_path(f) for f in changed_files if _normalize_path(f)})

    if default_decision != "deny":
        return {
            "allow": False,
            "reason_code": "DENY_INVALID_POLICY_DEFAULT",
            "violations": files,
            "matched_rule_ids": [],
            "policy_sha": policy_sha,
            "evaluated_at": evaluated_at,
        }

    violations: List[str] = []
    matched_rule_ids: Set[str] = set()
    for f in files:
        matched, rule_ids = _match_path(f, rule_patterns)
        if not matched:
            violations.append(f)
        matched_rule_ids.update(rule_ids)

    allow = len(violations) == 0
    return {
        "allow": allow,
        "reason_code": "ALLOW_ALL_PATHS_MATCH" if allow else "DENY_PATH_VIOLATION",
        "violations": violations,
        "matched_rule_ids": sorted(matched_rule_ids),
        "policy_sha": policy_sha,
        "evaluated_at": evaluated_at,
    }


def _github_get_json(url: str, token: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body), dict(resp.headers.items())


def fetch_pr_files(owner_repo: str, pr_number: int, token: str, api_base: str = "https://api.github.com") -> List[str]:
    files: Set[str] = set()
    page = 1
    while True:
        url = f"{api_base.rstrip('/')}/repos/{owner_repo}/pulls/{pr_number}/files?per_page=100&page={page}"
        payload, _headers = _github_get_json(url, token)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub PR files response is not a list")
        if not payload:
            break
        for item in payload:
            if not isinstance(item, dict):
                continue
            filename = _normalize_path(str(item.get("filename", "")))
            if filename:
                files.add(filename)
            if str(item.get("status", "")).lower() == "renamed":
                prev = _normalize_path(str(item.get("previous_filename", "")))
                if prev:
                    files.add(prev)
        if len(payload) < 100:
            break
        page += 1
    return sorted(files)


def write_verdict(path: str, verdict: Dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(verdict, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _deny_verdict(reason_code: str, policy_sha: str = "", violations: Sequence[str] | None = None) -> Dict:
    return {
        "allow": False,
        "reason_code": reason_code,
        "violations": sorted(set(violations or [])),
        "matched_rule_ids": [],
        "policy_sha": policy_sha,
        "evaluated_at": _utc_now_iso(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Minimal PR-Gate path allowlist evaluator")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr-number", required=True, type=int, help="Pull request number")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument(
        "--policy",
        default=".gitea/governance/path-allowlist.v1.yaml",
        help="Policy YAML path",
    )
    parser.add_argument("--output", default="gate-verdict.json", help="Verdict JSON output path")
    parser.add_argument("--api-base", default="https://api.github.com", help="GitHub API base URL")
    args = parser.parse_args(argv)

    verdict: Dict
    exit_code = 1

    try:
        try:
            policy, policy_sha = load_policy(args.policy)
        except FileNotFoundError:
            verdict = _deny_verdict("DENY_POLICY_MISSING")
            write_verdict(args.output, verdict)
            return 1
        except Exception:
            verdict = _deny_verdict("DENY_POLICY_PARSE_ERROR")
            write_verdict(args.output, verdict)
            return 1

        changed_files = fetch_pr_files(args.repo, args.pr_number, args.token, api_base=args.api_base)
        verdict = evaluate_paths(policy, changed_files, policy_sha)
        write_verdict(args.output, verdict)
        exit_code = 0 if verdict.get("allow") is True else 1
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        verdict = _deny_verdict("DENY_GITHUB_API_ERROR")
        write_verdict(args.output, verdict)
        exit_code = 1
    except Exception:
        verdict = _deny_verdict("DENY_EVALUATOR_ERROR")
        write_verdict(args.output, verdict)
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
