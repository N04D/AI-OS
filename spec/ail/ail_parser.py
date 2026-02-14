#!/usr/bin/env python3
"""
AIL v0.1 parser — validation + integrity
"""

import hashlib
from typing import Dict, List, Tuple

REQUIRED = [
    "@ail","@id","@ts","@from","@to",
    "@intent","@auth","@payload","@hash"
]

class AILParseError(Exception):
    pass


def parse_ail(text: str) -> Dict[str, str]:
    lines = _normalize_lines(text)
    items = _parse_lines(lines)

    keys = [k for k, _ in items]
    if keys != REQUIRED:
        raise AILParseError("Fields must appear in required order with no extras")

    fields: Dict[str, str] = {}
    for k, v in items:
        if k in fields:
            raise AILParseError(f"Duplicate field: {k}")
        fields[k] = v

    verify_hash(lines, fields["@hash"])
    verify_auth(fields["@auth"])
    return fields


def _normalize_lines(text: str) -> List[str]:
    raw = text.splitlines()
    if any(not l.strip() for l in raw):
        raise AILParseError("Blank lines are not allowed")
    return raw


def _parse_lines(lines: List[str]) -> List[Tuple[str, str]]:
    items = []
    for ln in lines:
        if not ln.startswith("@") or ":" not in ln:
            raise AILParseError(f"Invalid line: {ln}")
        k, v = ln.split(":", 1)
        items.append((k, v))
    return items


def verify_hash(lines, expected):
    content = "\n".join(l for l in lines if not l.startswith("@hash:"))
    actual = hashlib.sha256(content.encode()).hexdigest()
    if actual != expected:
        raise AILParseError("Hash mismatch")


def verify_auth(auth: str) -> None:
    if auth == "none":
        return
    if not auth.startswith("pow"):
        raise AILParseError("Unsupported auth scheme")
    try:
        scheme, nonce = auth.split(":", 1)
        bits = int(scheme[3:])
    except Exception as exc:
        raise AILParseError("Invalid PoW format") from exc
    if bits < 0:
        raise AILParseError("Invalid PoW difficulty")
    if not _check_pow(nonce, bits):
        raise AILParseError("PoW verification failed")


def _check_pow(nonce: str, bits: int) -> bool:
    digest = hashlib.sha256(nonce.encode()).digest()
    return _leading_zero_bits(digest) >= bits


def _leading_zero_bits(data: bytes) -> int:
    count = 0
    for b in data:
        if b == 0:
            count += 8
            continue
        # Count leading zeros in byte
        for i in range(7, -1, -1):
            if b & (1 << i):
                return count
            count += 1
    return count
