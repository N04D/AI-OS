import json
import urllib.error
import urllib.request

from supervisor.pr_gate.logger import log_event


class StatusPublishError(Exception):
    pass


VALID_STATES = {"success", "failure", "pending"}


def _normalize_api_base(api_base):
    base = (api_base or "").rstrip("/")
    if not base:
        raise StatusPublishError("Status publish failed: missing api_base")
    if base.endswith("/api/v1"):
        return base
    if "/api/v1" in base:
        return base.split("/api/v1", 1)[0] + "/api/v1"
    return base + "/api/v1"


def publish_governance_status(
    api_base,
    owner,
    repo,
    sha,
    state,
    description,
    headers=None,
    context="supervisor/governance",
):
    if state not in VALID_STATES:
        raise StatusPublishError(f"Invalid state: {state}")

    req_headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if "Authorization" not in req_headers:
        raise StatusPublishError("Status publish failed: missing Authorization token header")

    base = _normalize_api_base(api_base)
    url = f"{base}/repos/{owner}/{repo}/statuses/{sha}"
    payload = {
        "state": state,
        "context": context,
        "description": description[:140],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            log_event(
                "status_publish",
                f"context={context} state={state} sha={sha} http={response.status}",
            )
            if response.status not in (200, 201):
                raise StatusPublishError(f"Status publish failed: HTTP {response.status} url={url}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        log_event(
            "status_publish",
            f"context={context} state={state} sha={sha} http={exc.code}",
        )
        raise StatusPublishError(
            f"Status publish failed: HTTP {exc.code} url={url} body={body}"
        ) from exc
    except Exception as exc:
        log_event(
            "status_publish",
            f"context={context} state={state} sha={sha} http=ERR",
        )
        raise StatusPublishError(f"Status publish failed: url={url} error={exc}") from exc
