import json

import pytest

from pluginctl.core import actions, gh, git
from pluginctl.validate import detect


def test_is_safe_name():
    assert detect.is_safe_name("my-plugin")
    assert detect.is_safe_name("plugin123")
    assert not detect.is_safe_name("My-Plugin")
    assert not detect.is_safe_name("has space")
    assert not detect.is_safe_name("-leading")
    assert not detect.is_safe_name("trailing-")
    assert not detect.is_safe_name("double--hyphen")


def test_author_permission_by_author():
    base = json.dumps({"author": "alice"})
    assert detect.author_has_plugin_permission("alice", base)
    assert not detect.author_has_plugin_permission("bob", base)


def test_author_permission_by_maintainer():
    base = json.dumps({"author": "alice", "maintainers": ["bob", "carol"]})
    assert detect.author_has_plugin_permission("carol", base)
    assert not detect.author_has_plugin_permission("dan", base)


def test_author_permission_no_base():
    assert not detect.author_has_plugin_permission("alice", None)
    assert not detect.author_has_plugin_permission("alice", "")


def test_blacklist_author_case_insensitive():
    r = detect.check_blacklists("BadActor", ["p"], "goodguy, badactor", "")
    assert r.matched and r.reason == "author-blacklisted"


def test_blacklist_plugin():
    r = detect.check_blacklists("someone", ["evil-plugin"], "", "evil-plugin , other")
    assert r.matched and r.reason == "plugin-blacklisted"


def test_blacklist_none_configured():
    assert not detect.check_blacklists("x", ["p"], "", "").matched


def test_blacklist_no_match():
    assert not detect.check_blacklists("clean", ["clean-plugin"], "bad", "evil").matched


def _outputs(out_path) -> dict:
    d = {}
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            d[k] = v
    return d


def test_unsafe_named_companion_folder_blocks_pr(tmp_path, monkeypatch):
    """A PR touching one safe-named + one unsafe-named plugin folder must be
    blocked, not silently narrowed to just the safe one - an unscanned folder
    must never be able to ride along with a legitimately-passing change."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "gh_output"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))

    monkeypatch.setattr(git, "merge_base", lambda *a, **k: "base-sha")
    monkeypatch.setattr(git, "diff_name_only", lambda *a, **k: [
        "plugins/good-plugin/plugin.json",
        "plugins/Bad_Plugin/plugin.json",
    ])
    monkeypatch.setattr(gh, "has_write_access", lambda *a, **k: True)

    rc = detect.run("alice", "main", repo="org/repo")

    assert rc == 0
    outputs = _outputs(out)
    assert outputs["close_pr"] == "true"
    assert outputs["close_reason"] == "unsafe-plugin-name"
    assert outputs["matrix"] == "[]"


def test_metadata_only_update_accepts_approved_field_removal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "plugins" / "demo-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
    monkeypatch.setattr(git, "show", lambda *_: json.dumps({
        "version": "1.0.0", "maintainers": ["alice"],
    }))

    assert detect.is_metadata_only_update(
        "demo-plugin", "main", ["plugins/demo-plugin/plugin.json"]
    )


@pytest.mark.parametrize(
    ("changed_files", "current"),
    [
        (["plugins/demo-plugin/main.py", "plugins/demo-plugin/plugin.json"],
         {"version": "1.0.0", "description": "Updated"}),
        (["plugins/demo-plugin/plugin.json"],
         {"version": "1.0.1", "description": "Updated"}),
    ],
)
def test_metadata_only_update_rejects_source_or_unapproved_changes(tmp_path, monkeypatch,
                                                                   changed_files, current):
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "plugins" / "demo-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps(current), encoding="utf-8")
    monkeypatch.setattr(git, "show", lambda *_: json.dumps({
        "version": "1.0.0", "description": "Original",
    }))

    assert not detect.is_metadata_only_update("demo-plugin", "main", changed_files)


def test_detect_marks_only_an_all_metadata_matrix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "gh_output"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    pdir = tmp_path / "plugins" / "demo-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({
        "version": "1.0.0", "description": "Updated", "author": "alice",
    }), encoding="utf-8")

    monkeypatch.setattr(git, "merge_base", lambda *a, **k: "base-sha")
    monkeypatch.setattr(git, "diff_name_only", lambda *a, **k: [
        "plugins/demo-plugin/plugin.json",
    ])
    monkeypatch.setattr(git, "object_exists", lambda *a, **k: True)
    monkeypatch.setattr(git, "show", lambda *a, **k: json.dumps({
        "version": "1.0.0", "description": "Original", "author": "alice",
    }))
    monkeypatch.setattr(gh, "has_write_access", lambda *a, **k: True)

    assert detect.run("alice", "main", repo="org/repo") == 0
    assert _outputs(out)["metadata_only"] == "true"
