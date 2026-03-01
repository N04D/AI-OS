from types import SimpleNamespace

import pytest

from supervisor import git_remote


def test_preferred_remote_name_uses_env(monkeypatch):
    monkeypatch.setenv("AIOS_GIT_REMOTE", "custom")
    assert git_remote.preferred_remote_name() == "custom"


def test_preferred_remote_name_prefers_gitea_when_present(monkeypatch):
    monkeypatch.delenv("AIOS_GIT_REMOTE", raising=False)

    def fake_run(cmd, capture_output, text):
        if cmd[-1] == "remote.gitea.url":
            return SimpleNamespace(returncode=0, stdout="ssh://git@gitea:2222/org/repo.git\n")
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(git_remote.subprocess, "run", fake_run)
    assert git_remote.preferred_remote_name() == "gitea"


def test_required_remote_url_raises_when_selected_remote_missing(monkeypatch):
    monkeypatch.setenv("AIOS_GIT_REMOTE", "missing")

    def fake_run(cmd, capture_output, text):
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(git_remote.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match=r"remote\.missing\.url"):
        git_remote.required_remote_url()
