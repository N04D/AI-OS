from orchestrator import git as git_mod


def test_push_uses_preferred_remote(monkeypatch):
    calls = []

    monkeypatch.setattr(git_mod, "preferred_remote_name", lambda: "gitea")
    monkeypatch.setattr(git_mod, "run", lambda cmd: calls.append(cmd))

    git_mod.push("feature/test-1")

    assert calls == [["git", "push", "-u", "gitea", "feature/test-1"]]


def test_commit_stages_only_explicit_files(monkeypatch):
    calls = []
    monkeypatch.setattr(git_mod, "run", lambda cmd: calls.append(cmd))

    git_mod.commit("feat: test", ["a.py", "b.py"])

    assert calls == [
        ["git", "add", "--", "a.py", "b.py"],
        ["git", "commit", "-m", "feat: test"],
    ]
