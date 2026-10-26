from pluginctl.publish import run


def test_commit_removes_source_configuration_from_releases_branch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".github" / "pluginctl").mkdir(parents=True)
    (tmp_path / ".github" / "pluginctl" / "registry-messages.json").write_text(
        "{}", encoding="utf-8"
    )
    calls = []

    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(run, "_git", lambda *args, **kwargs: calls.append(args) or Result())
    monkeypatch.setattr(run, "_only_timestamps", lambda: False)
    monkeypatch.setattr(run, "_read", lambda path: "")
    monkeypatch.setattr(run, "_emit_published", lambda *args: None)

    assert run._commit_and_push("org/repo", "main", "remote") == 0
    assert ("rm", "-r", "--cached", "--ignore-unmatch", ".github") in calls
    assert not (tmp_path / ".github").exists()
