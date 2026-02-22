import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def _utc_iso8601() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _result(valid: bool, passed: list[str], failed: list[str]) -> dict:
    return {
        "environment_valid": valid,
        "checks_passed": passed,
        "checks_failed": failed,
        "timestamp": _utc_iso8601(),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _api_json_request(method: str, url: str, headers: dict, timeout_seconds: int = 5):
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
        return response.status, json.loads(raw) if raw else None


def validate_environment(
    *,
    api_base: str,
    owner: str,
    repo: str,
    auth_headers: dict,
    governance_path: str = "docs/governance.md",
    environment_path: str = "agents/state/environment.json",
) -> dict:
    checks_passed: list[str] = []
    checks_failed: list[str] = []

    # A) Repository State
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        subprocess.run(
            ["git", "ls-remote", "--exit-code", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        subprocess.run(
            ["git", "status", "--porcelain=v1"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        checks_passed.append("repository_state")
    except Exception:
        checks_failed.append("environment.repository.unavailable")

    # B) Governance Files Presence + Hash Readability
    try:
        gov = Path(governance_path)
        env = Path(environment_path)
        if not gov.is_file():
            raise FileNotFoundError(governance_path)
        if not env.is_file():
            raise FileNotFoundError(environment_path)
        _sha256_file(gov)
        _sha256_file(env)
        checks_passed.append("governance_files")
    except FileNotFoundError:
        checks_failed.append("environment.governance.missing")
    except Exception:
        checks_failed.append("environment.governance.unreadable")

    # C) Python Runtime Integrity
    try:
        subprocess.run(
            ["python3", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        code = (
            "import json,hashlib,subprocess,time,urllib.request;"
            "import supervisor,supervisor.supervisor;"
            "print('ok')"
        )
        subprocess.run(
            ["python3", "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        checks_passed.append("python_runtime")
    except Exception:
        checks_failed.append("environment.runtime.invalid")

    # D) Gitea Connectivity (bounded <=5s)
    try:
        api_headers = {"Accept": "application/json"}
        api_headers.update(auth_headers or {})
        if "Authorization" not in api_headers:
            raise PermissionError("missing auth token")
        _api_json_request("GET", f"{api_base}/user", api_headers, timeout_seconds=5)
        _, issues = _api_json_request(
            "GET",
            f"{api_base}/repos/{owner}/{repo}/issues?state=open",
            api_headers,
            timeout_seconds=5,
        )
        if not isinstance(issues, list):
            raise ValueError("issues endpoint did not return list")
        checks_passed.append("gitea_connectivity")
    except PermissionError:
        checks_failed.append("environment.gitea.auth_failed")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            checks_failed.append("environment.gitea.auth_failed")
        else:
            checks_failed.append("environment.gitea.unreachable")
    except Exception:
        checks_failed.append("environment.gitea.invalid_response")

    # E) Label Availability
    try:
        api_headers = {"Accept": "application/json"}
        api_headers.update(auth_headers or {})
        _, labels = _api_json_request(
            "GET",
            f"{api_base}/repos/{owner}/{repo}/labels",
            api_headers,
            timeout_seconds=5,
        )
        if not isinstance(labels, list):
            raise ValueError("labels endpoint did not return list")
        if not any(lbl.get("name") == "in-progress" for lbl in labels):
            raise ValueError("missing in-progress label")
        checks_passed.append("label_availability")
    except Exception:
        checks_failed.append("environment.labels.missing")

    return _result(valid=(len(checks_failed) == 0), passed=checks_passed, failed=checks_failed)
