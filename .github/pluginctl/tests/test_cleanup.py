import json

from pluginctl.publish import cleanup


def test_stable_publish_removes_retained_prerelease(tmp_path, monkeypatch):
    plugin = tmp_path / "plugins" / "demo"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({"version": "1.1.0"}), encoding="utf-8")
    deleted = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cleanup.gh, "release_list", lambda _repo: [
        {"tag": "demo-1.1.0", "prerelease": False},
        {"tag": "demo-1.0.0-pre.1", "prerelease": True},
    ])
    monkeypatch.setattr(cleanup.gh, "release_delete", lambda tag, _repo: deleted.append(tag) or 0)

    assert cleanup.run("org/repo") == 0
    assert deleted == ["demo-1.0.0-pre.1"]
