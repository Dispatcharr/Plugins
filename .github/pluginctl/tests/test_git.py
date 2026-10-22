from types import SimpleNamespace

from pluginctl.core import git


def test_push_branch_with_lease_uses_remote_sha(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "ls-remote":
            return SimpleNamespace(returncode=0, stdout="abc123\trefs/heads/unlist/demo\n")
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(git, "run", fake_run)

    git.push_branch_with_lease("https://example.test/repo.git", "unlist/demo")

    assert calls == [
        (("ls-remote", "--heads", "https://example.test/repo.git", "unlist/demo"), {"check": False}),
        (("push", "--force-with-lease=refs/heads/unlist/demo:abc123",
          "https://example.test/repo.git", "HEAD:refs/heads/unlist/demo"), {}),
    ]


def test_push_branch_with_lease_creates_missing_branch(monkeypatch):
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(git, "run", fake_run)

    git.push_branch_with_lease("https://example.test/repo.git", "unlist/demo")

    assert calls == [
        (("ls-remote", "--heads", "https://example.test/repo.git", "unlist/demo"), {"check": False}),
        (("push", "https://example.test/repo.git", "HEAD:refs/heads/unlist/demo"), {}),
    ]
