import json
import re
import subprocess
import urllib.error
import urllib.request


class GiteaClientError(Exception):
    pass


def _normalize_api_base(api_base):
    base = (api_base or "").rstrip("/")
    if not base:
        raise GiteaClientError("Missing api_base")
    if base.endswith("/api/v1"):
        return base
    if "/api/v1" in base:
        return base.split("/api/v1", 1)[0] + "/api/v1"
    return base + "/api/v1"


def _api_json_request(method, url, payload=None, headers=None):
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode()
            parsed = json.loads(raw) if raw else None
            return response.status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        parsed = None
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
        return e.code, parsed, raw


def _require_list_response(status, data, endpoint_label, raw):
    if status != 200 or not isinstance(data, list):
        raise GiteaClientError(
            f"PR gate API failure endpoint={endpoint_label} status={status} body={raw}"
        )
    return data


def get_open_pull_requests(api_base, owner, repo, headers=None, target_branches=None):
    if target_branches is None:
        target_branches = {"main", "develop"}
    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/pulls?state=open&limit=300"
    status, data, raw = _api_json_request("GET", url, headers=headers)
    pulls = _require_list_response(status, data, "pulls", raw)

    selected = []
    for pr in pulls:
        base_ref = ((pr.get("base") or {}).get("ref") or "").strip()
        if base_ref in target_branches:
            selected.append(pr)
    return sorted(selected, key=lambda pr: pr.get("number", 0))


def get_pull_request_files(api_base, owner, repo, pr_number, headers=None):
    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    status, data, raw = _api_json_request("GET", url, headers=headers)
    file_entries = _require_list_response(status, data, f"pulls/{pr_number}/files", raw)
    return sorted(
        [
            (item.get("filename") or "").strip()
            for item in file_entries
            if (item.get("filename") or "").strip()
        ]
    )


def get_pull_request_reviews(api_base, owner, repo, pr_number, headers=None):
    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
    status, data, raw = _api_json_request("GET", url, headers=headers)
    return _require_list_response(status, data, f"pulls/{pr_number}/reviews", raw)


def get_commit_statuses(api_base, owner, repo, sha, headers=None):
    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/commits/{sha}/statuses"
    status, data, raw = _api_json_request("GET", url, headers=headers)
    return _require_list_response(status, data, f"commits/{sha}/statuses", raw)


def _detect_gitea_signature(commit):
    verification = commit.get("verification") or (commit.get("commit") or {}).get("verification")
    if verification is None:
        return None
    verified = bool(verification.get("verified", False))
    return {
        "signature_verifiable": True,
        "signature_verified": verified,
        "signature_source": "gitea",
    }


def _fetch_pr_ref(pr_number):
    candidates = [
        ["git", "fetch", "--quiet", "origin", f"refs/pull/{pr_number}/head"],
        ["git", "fetch", "--quiet", "origin", f"pull/{pr_number}/head"],
    ]
    for cmd in candidates:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    return False


def _local_signature_probe(sha):
    exists = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if exists.returncode != 0:
        return {
            "signature_verifiable": False,
            "signature_verified": False,
            "signature_source": "local_git",
            "signature_reason": "commit_not_found",
        }

    probe = subprocess.run(
        ["git", "log", "--show-signature", "-n", "1", "--format=%H", sha],
        capture_output=True,
        text=True,
    )
    text = f"{probe.stdout}\n{probe.stderr}"
    if re.search(r"Good .* signature", text):
        sig_type = "ssh" if "Good \"git\" signature" in text else "gpg"
        return {
            "signature_verifiable": True,
            "signature_verified": True,
            "signature_source": "local_git",
            "signature_type": sig_type,
            "signature_reason": "good_signature",
        }
    if "No signature" in text or "BAD signature" in text or "bad signature" in text:
        return {
            "signature_verifiable": True,
            "signature_verified": False,
            "signature_source": "local_git",
            "signature_reason": "missing_or_bad_signature",
        }
    if "Can't check signature" in text or "No public key" in text:
        return {
            "signature_verifiable": False,
            "signature_verified": False,
            "signature_source": "local_git",
            "signature_reason": "unverifiable_key",
        }
    return {
        "signature_verifiable": False,
        "signature_verified": False,
        "signature_source": "local_git",
        "signature_reason": "unknown_signature_output",
    }


def get_pull_request_commits(api_base, owner, repo, pr_number, head_sha, headers=None):
    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    status, data, raw = _api_json_request("GET", url, headers=headers)
    commits = _require_list_response(status, data, f"pulls/{pr_number}/commits", raw)

    _fetch_pr_ref(pr_number)

    enriched = []
    for commit in commits:
        enriched_commit = dict(commit)
        sig = _detect_gitea_signature(enriched_commit)
        if sig is None:
            sha = enriched_commit.get("sha") or ""
            sig = _local_signature_probe(sha)
        enriched_commit.update(sig)
        enriched.append(enriched_commit)

    if not enriched:
        raise GiteaClientError(f"PR gate API failure endpoint=pulls/{pr_number}/commits status=200 body=empty")
    return enriched
