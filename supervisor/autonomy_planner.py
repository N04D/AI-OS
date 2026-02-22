from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _proposal_markdown(opportunity: dict[str, Any]) -> str:
    opportunity_json = json.dumps(opportunity, sort_keys=True, indent=2, ensure_ascii=True)
    op_type = str(opportunity.get("type", "unknown"))

    rationale = {
        "repeated_failure": "Repeated identical failures indicate a systemic blocker.",
        "success_without_commit": "Execution succeeds but value is not persisted through commits.",
        "duration_outlier": "Task runtime is disproportionately high versus baseline.",
    }.get(op_type, "Ledger signal indicates a deterministic improvement opportunity.")

    proposed_action = {
        "repeated_failure": "Create a focused remediation task that addresses the shared failure reason.",
        "success_without_commit": "Investigate commit gating path and produce an explicit commit-eligibility fix.",
        "duration_outlier": "Profile the slow path and propose bounded runtime optimization.",
    }.get(op_type, "Create a governed proposal scoped to the observed opportunity.")

    return (
        "# Autonomy Proposal\n\n"
        "## Source Opportunity\n\n"
        "```json\n"
        f"{opportunity_json}\n"
        "```\n\n"
        "## Rationale\n\n"
        f"{rationale}\n\n"
        "## Proposed Action\n\n"
        f"{proposed_action}\n\n"
        "## Safety Constraints\n\n"
        "- Read-only analysis artifact; no direct execution.\n"
        "- No queue mutation.\n"
        "- No governance policy mutation.\n"
        "- Follow allowed path constraints and deterministic behavior.\n"
    )


def generate_proposals(opportunities: list[dict], output_dir: str) -> list[dict]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    normalized: list[dict[str, Any]] = []
    for item in opportunities:
        if isinstance(item, dict):
            normalized.append(dict(item))

    # Deterministic ordering irrespective of caller input order.
    sorted_ops = sorted(normalized, key=lambda x: _canonical_json(x))

    generated: list[dict[str, Any]] = []
    for opportunity in sorted_ops:
        digest = _stable_hash(opportunity)
        op_type = str(opportunity.get("type", "unknown"))
        filename = f"proposal.{op_type}.{digest[:12]}.md"
        path = target_dir / filename
        content = _proposal_markdown(opportunity)
        path.write_text(content, encoding="utf-8")
        generated.append(
            {
                "type": op_type,
                "hash": digest,
                "filename": filename,
                "path": str(path),
            }
        )

    return generated
