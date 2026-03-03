from __future__ import annotations

import json
from pathlib import Path

import pytest

from supervisor.channels.agent_io import AgentIOError
from supervisor.channels.agent_io import ArtifactWriter
from supervisor.channels.agent_io import DENY_ARTIFACT_PATH_ESCAPE
from supervisor.channels.agent_io import DENY_SECRET_PERSISTENCE


def test_deterministic_naming_same_payload_same_artifact_path(tmp_path: Path) -> None:
    writer = ArtifactWriter(repo_root=tmp_path)
    payload = {"message": "hello", "meta": {"x": 1, "y": "z"}}
    a = writer.write(channel="inbox", epoch="2026-03-03", agent="codex", payload=payload)
    b = writer.write(channel="inbox", epoch="2026-03-03", agent="codex", payload=payload)

    assert a["artifact_path"] == b["artifact_path"]
    assert a["sha256"] == b["sha256"]
    artifact = tmp_path / a["artifact_path"]
    assert artifact.exists()
    assert artifact.name.startswith("2026-03-03__codex__")
    assert artifact.name.endswith(".json")


def test_deny_path_artifact_escape_for_named_write(tmp_path: Path) -> None:
    writer = ArtifactWriter(repo_root=tmp_path)
    with pytest.raises(AgentIOError) as exc:
        writer.write_named(
            channel="inbox",
            filename="../escape.json",
            payload={"ok": True},
        )
    assert exc.value.reason_code == DENY_ARTIFACT_PATH_ESCAPE


def test_no_secret_persistence_rejects_sensitive_payload(tmp_path: Path) -> None:
    writer = ArtifactWriter(repo_root=tmp_path)
    with pytest.raises(AgentIOError) as exc:
        writer.write(
            channel="audit",
            epoch="2026-03-03",
            agent="codex",
            payload={"summary": "x", "api_token": "super-secret"},
        )
    assert exc.value.reason_code == DENY_SECRET_PERSISTENCE
    assert list((tmp_path / "runtime/agent_io/audit").glob("*.json")) == []


def test_idempotent_writes_preserve_content(tmp_path: Path) -> None:
    writer = ArtifactWriter(repo_root=tmp_path)
    payload = {"event": "ingest", "items": [1, 2, 3]}
    result = writer.write(channel="outbox", epoch="2026-03-03", agent="codex", payload=payload)
    artifact = tmp_path / result["artifact_path"]
    before = artifact.read_text(encoding="utf-8")

    again = writer.write(channel="outbox", epoch="2026-03-03", agent="codex", payload=payload)
    after = artifact.read_text(encoding="utf-8")

    assert again["artifact_path"] == result["artifact_path"]
    assert before == after
    assert json.loads(after) == payload
