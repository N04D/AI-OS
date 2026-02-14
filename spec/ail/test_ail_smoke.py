import subprocess

from ail_build import build
from ail_executor import execute
from ail_parser import parse_ail


def test_parse_basic():
    msg = build("fs.read", "@path:foo.txt")
    fields = parse_ail(msg)
    assert fields["@intent"] == "fs.read"


def _write_msg(tmp_path, msg: str):
    path = tmp_path / "msg.ail"
    path.write_text(msg)
    return str(path)


def test_fs_read_basic(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "hello.txt").write_text("hi")

    msg = build("fs.read", "@path:hello.txt")
    result = execute(_write_msg(tmp_path, msg), sandbox=str(sandbox))
    assert result["result.ok"] is True
    assert result["data"] == "hi"


def test_fs_write_then_read(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    msg = build("fs.write", "@path:out.txt\n@data:hello", pow_bits=8)
    result = execute(_write_msg(tmp_path, msg), sandbox=str(sandbox))
    assert result["result.ok"] is True

    msg2 = build("fs.read", "@path:out.txt")
    result2 = execute(_write_msg(tmp_path, msg2), sandbox=str(sandbox))
    assert result2["result.ok"] is True
    assert result2["data"] == "hello"


def test_fs_list(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "a.txt").write_text("a")
    (sandbox / "b.txt").write_text("b")

    msg = build("fs.list", "@path:.")
    result = execute(_write_msg(tmp_path, msg), sandbox=str(sandbox))
    assert result["result.ok"] is True
    assert "a.txt" in result["data"]
    assert "b.txt" in result["data"]


def test_git_read_status(tmp_path):
    sandbox = tmp_path / "repo"
    sandbox.mkdir()
    subprocess.run(["git", "-C", str(sandbox), "init"], check=True, capture_output=True)
    (sandbox / "file.txt").write_text("data")

    msg = build("git.read", "@cmd:status")
    result = execute(_write_msg(tmp_path, msg), sandbox=str(sandbox))
    assert result["result.ok"] is True
    assert "file.txt" in result["data"]


def test_proc_exec_safe(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    msg = build("proc.exec", "@cmd:echo\n@args:hello world", pow_bits=8)
    result = execute(_write_msg(tmp_path, msg), sandbox=str(sandbox))
    assert result["result.ok"] is True
    assert "hello world" in result["data"]["stdout"]
