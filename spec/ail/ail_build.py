#!/usr/bin/env python3
"""
AIL message builder
"""

import base64
import hashlib
import time
import uuid
from typing import Optional


def build(intent: str, payload_text: str, auth: str = "none", pow_bits: Optional[int] = None) -> str:
    payload_b64 = base64.b64encode(payload_text.encode()).decode()
    auth_value = auth
    if pow_bits is not None:
        nonce = _find_pow_nonce(pow_bits)
        auth_value = f"pow{pow_bits}:{nonce}"

    lines = [
        "@ail:0.1",
        f"@id:{uuid.uuid4()}",
        f"@ts:{int(time.time()*1000)}",
        "@from:agent.main",
        "@to:executor.local",
        f"@intent:{intent}",
        f"@auth:{auth_value}",
        f"@payload:{payload_b64}",
    ]

    h = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    lines.append(f"@hash:{h}")

    return "\n".join(lines)


def _find_pow_nonce(bits: int) -> str:
    nonce = 0
    while True:
        candidate = f"{nonce}"
        digest = hashlib.sha256(candidate.encode()).digest()
        if _leading_zero_bits(digest) >= bits:
            return candidate
        nonce += 1


def _leading_zero_bits(data: bytes) -> int:
    count = 0
    for b in data:
        if b == 0:
            count += 8
            continue
        for i in range(7, -1, -1):
            if b & (1 << i):
                return count
            count += 1
    return count


if __name__ == "__main__":
    print(build("fs.read", "@path:example.txt"))
