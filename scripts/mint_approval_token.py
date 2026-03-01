#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import uuid


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _payload_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def mint_token_v2(
    *,
    secret: str,
    issuer: str,
    scope: list[str],
    mode: str,
    risk_class: str,
    policy_sha: str,
    requested_by: str,
    base_ref: str,
    payload: object,
    exp: int,
    jti: str,
) -> str:
    payload_obj = {
        "v": 1,
        "issuer": issuer,
        "scope": scope,
        "mode": mode,
        "risk_class": risk_class,
        "policy_sha": policy_sha,
        "requested_by": requested_by,
        "base_ref": base_ref,
        "payload_sha256": _payload_sha256(payload),
        "exp": int(exp),
        "jti": jti,
    }
    payload_b64 = _b64url(_canonical_json(payload_obj))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url(sig)}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mint approval token for job creation")
    parser.add_argument("--issuer", choices=["human", "supervisor"], default="human")
    parser.add_argument("--scope", default="create_job", help="Comma-separated scopes")
    parser.add_argument("--mode", choices=["auto", "human_required"], default="human_required")
    parser.add_argument("--risk-class", choices=["low", "medium", "high"], default="high")
    parser.add_argument(
        "--policy-path",
        default=".gitea/governance/supervisor-capabilities.v1.yaml",
        help="Capability policy file path (JSON-compatible YAML)",
    )
    parser.add_argument("--requested-by", required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--payload-json", required=True, help='JSON string (example: \'{"job":"..." }\')')
    parser.add_argument("--exp", required=True, type=int, help="Unix expiry seconds")
    parser.add_argument("--jti", default=str(uuid.uuid4()))
    parser.add_argument("--secret", default=os.environ.get("APPROVAL_SECRET", ""))
    args = parser.parse_args(argv)

    if not args.secret:
        print("ERROR: missing approval secret (use --secret or APPROVAL_SECRET)", file=sys.stderr)
        return 1

    try:
        payload = json.loads(args.payload_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid --payload-json: {exc}", file=sys.stderr)
        return 1

    try:
        policy_obj = json.loads(Path(args.policy_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: failed to load policy file: {exc}", file=sys.stderr)
        return 1
    policy_sha = _payload_sha256(policy_obj)

    token = mint_token_v2(
        secret=args.secret,
        issuer=args.issuer,
        scope=[s.strip() for s in args.scope.split(",") if s.strip()],
        mode=args.mode,
        risk_class=args.risk_class,
        policy_sha=policy_sha,
        requested_by=args.requested_by,
        base_ref=args.base_ref,
        payload=payload,
        exp=args.exp,
        jti=args.jti,
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
