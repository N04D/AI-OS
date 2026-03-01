from __future__ import annotations

from supervisor.skills.ping import ping


def test_ping_returns_pong() -> None:
    assert ping() == "pong"
