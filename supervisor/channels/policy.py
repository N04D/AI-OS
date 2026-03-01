from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DENY_POLICY_MISSING = "DENY_POLICY_MISSING"
DENY_POLICY_INVALID = "DENY_POLICY_INVALID"


class PolicyError(RuntimeError):
    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}")


def _load_json_object(path: Path, *, missing_code: str, invalid_code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(missing_code, f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PolicyError(invalid_code, f"invalid json: {path}") from exc
    if not isinstance(payload, dict):
        raise PolicyError(invalid_code, f"payload must be object: {path}")
    return payload


def load_email_policy(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, missing_code=DENY_POLICY_MISSING, invalid_code=DENY_POLICY_INVALID)
    if str(payload.get("default_action", "")).strip().lower() != "deny":
        raise PolicyError(DENY_POLICY_INVALID, "default_action must be deny")
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        raise PolicyError(DENY_POLICY_INVALID, "agents must be object")
    out_agents: dict[str, dict[str, Any]] = {}
    for agent in sorted(agents.keys()):
        rule = agents.get(agent)
        if not isinstance(rule, dict):
            raise PolicyError(DENY_POLICY_INVALID, f"agent policy must be object: {agent}")
        send_allowlist = rule.get("send_allowlist", [])
        receive_allowlist = rule.get("receive_allowlist", [])
        domains_allowlist = rule.get("domains_allowlist", [])
        max_body_bytes = rule.get("max_body_bytes", 65536)
        if not isinstance(send_allowlist, list) or not all(isinstance(v, str) for v in send_allowlist):
            raise PolicyError(DENY_POLICY_INVALID, f"send_allowlist invalid: {agent}")
        if not isinstance(receive_allowlist, list) or not all(isinstance(v, str) for v in receive_allowlist):
            raise PolicyError(DENY_POLICY_INVALID, f"receive_allowlist invalid: {agent}")
        if not isinstance(domains_allowlist, list) or not all(isinstance(v, str) for v in domains_allowlist):
            raise PolicyError(DENY_POLICY_INVALID, f"domains_allowlist invalid: {agent}")
        if not isinstance(max_body_bytes, int) or max_body_bytes < 1:
            raise PolicyError(DENY_POLICY_INVALID, f"max_body_bytes invalid: {agent}")
        out_agents[agent] = {
            "send_allowlist": sorted(v.strip().lower() for v in send_allowlist if v.strip()),
            "receive_allowlist": sorted(v.strip().lower() for v in receive_allowlist if v.strip()),
            "domains_allowlist": sorted(v.strip().lower() for v in domains_allowlist if v.strip()),
            "max_body_bytes": max_body_bytes,
        }
    return {
        "version": str(payload.get("version", "v0.1")),
        "default_action": "deny",
        "agents": out_agents,
    }


def load_email_config(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, missing_code=DENY_POLICY_MISSING, invalid_code=DENY_POLICY_INVALID)
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise PolicyError(DENY_POLICY_INVALID, "enabled must be bool")
    agents = payload.get("agents")
    if not isinstance(agents, dict):
        raise PolicyError(DENY_POLICY_INVALID, "agents must be object")
    out_agents: dict[str, dict[str, bool]] = {}
    for agent in sorted(agents.keys()):
        cfg = agents.get(agent)
        if not isinstance(cfg, dict) or not isinstance(cfg.get("enabled"), bool):
            raise PolicyError(DENY_POLICY_INVALID, f"agent config invalid: {agent}")
        out_agents[agent] = {"enabled": bool(cfg["enabled"])}
    return {"enabled": enabled, "agents": out_agents}
