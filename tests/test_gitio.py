import subprocess
from xtools import gitio


def test_commit_and_push_invokes_git(monkeypatch):
    calls = []

    def fake_run(args, cwd=None, check=False):
        calls.append(args)
        class R:
            returncode = 1
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    pushed = gitio.commit_and_push(["a.md", "b.json"], "msg", cwd="/repo")
    assert pushed is True
    assert calls[0][:2] == ["git", "add"]
    assert any(c[:2] == ["git", "commit"] for c in calls)
    assert any(c == ["git", "push"] for c in calls)


def test_commit_and_push_noop_when_nothing_staged(monkeypatch):
    calls = []

    def fake_run(args, cwd=None, check=False):
        calls.append(args)
        class R:
            returncode = 0 if args[:3] == ["git", "diff", "--cached"] else 1
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    pushed = gitio.commit_and_push(["a.md"], "msg", cwd="/repo")
    assert pushed is False
    assert not any(c == ["git", "push"] for c in calls)
