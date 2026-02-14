#!/usr/bin/env python3
"""
AIL v0.1 minimal executor
"""

import base64
import json
import os
import subprocess
from typing import Dict, List

from ail_parser import parse_ail

ALLOW = {"fs.read", "fs.write", "fs.list", "git.read", "proc.exec"}
PROC_ALLOW = {"echo", "ls", "pwd", "whoami", "cat"}


def sandbox_path(root, rel):
    abs_root = os.path.abspath(root)
    abs_path = os.path.abspath(os.path.join(abs_root, rel))
    if not abs_path.startswith(abs_root):
        raise Exception("Sandbox escape detected")
    return abs_path


def _parse_payload(payload_text: str) -> Dict[str, str]:
    if not payload_text.strip():
        return {}
    items: List[str] = payload_text.splitlines()
    if any(not l.strip() for l in items):
        raise Exception("Invalid payload: blank line")
    out: Dict[str, str] = {}
    for ln in items:
        if not ln.startswith("@") or ":" not in ln:
            raise Exception(f"Invalid payload line: {ln}")
        k, v = ln.split(":", 1)
        if k in out and k != "@arg":
            raise Exception(f"Duplicate payload key: {k}")
        if k == "@arg":
            out.setdefault("@arg", [])
            out["@arg"].append(v)
        else:
            out[k] = v
    return out


def _result_ok(data=None):
    return {"result.ok": True, "result.error": None, "data": data}


def _result_error(message, code="error"):
    return {"result.ok": False, "result.error": {"code": code, "message": message}}


def fs_read(root, payload_text):
    payload = _parse_payload(payload_text)
    rel = payload.get("@path")
    if rel is None:
        raise Exception("Missing @path")
    path = sandbox_path(root, rel)

    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="ignore")


def fs_write(root, payload_text):
    payload = _parse_payload(payload_text)
    rel = payload.get("@path")
    data = payload.get("@data")
    if rel is None or data is None:
        raise Exception("Missing @path or @data")
    path = sandbox_path(root, rel)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    return {"bytes": len(data)}


def fs_list(root, payload_text):
    payload = _parse_payload(payload_text)
    rel = payload.get("@path", ".")
    path = sandbox_path(root, rel)
    entries = sorted(os.listdir(path))
    return entries


def git_read(root, payload_text):
    payload = _parse_payload(payload_text)
    cmd = payload.get("@cmd", "status")
    if cmd != "status":
        raise Exception("Unsupported git.read cmd")
    try:
        proc = subprocess.run(
            ["git", "-C", root, "status", "--short"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except FileNotFoundError as exc:
        raise Exception("git not available") from exc
    if proc.returncode != 0:
        raise Exception(proc.stderr.strip() or "git.read failed")
    return proc.stdout.strip()


def proc_exec(root, payload_text):
    payload = _parse_payload(payload_text)
    cmd = payload.get("@cmd")
    if not cmd:
        raise Exception("Missing @cmd")
    if cmd not in PROC_ALLOW:
        raise Exception("Command not allowed")

    args = []
    if "@args" in payload:
        args = [a for a in payload["@args"].split(" ") if a]
    if "@arg" in payload:
        args.extend(payload["@arg"])
    proc = subprocess.run(
        [cmd] + args,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def execute(file_path, sandbox="./sandbox"):
    raw = open(file_path).read()
    msg = parse_ail(raw)

    intent = msg["@intent"]
    payload = base64.b64decode(msg["@payload"]).decode("utf-8", errors="strict")

    if intent not in ALLOW:
        return _result_error("Intent not allowed", code="intent")

    if intent in {"fs.write", "proc.exec"} and msg["@auth"] == "none":
        return _result_error("PoW required for write/exec", code="auth")

    try:
        if intent == "fs.read":
            data = fs_read(sandbox, payload)
            return _result_ok(data)
        if intent == "fs.write":
            data = fs_write(sandbox, payload)
            return _result_ok(data)
        if intent == "fs.list":
            data = fs_list(sandbox, payload)
            return _result_ok(data)
        if intent == "git.read":
            data = git_read(sandbox, payload)
            return _result_ok(data)
        if intent == "proc.exec":
            data = proc_exec(sandbox, payload)
            return _result_ok(data)
    except Exception as exc:
        return _result_error(str(exc))
    return _result_error("Unhandled intent")


if __name__ == "__main__":
    import sys
    result = execute(sys.argv[1])
    print(json.dumps(result, indent=2, sort_keys=True))
