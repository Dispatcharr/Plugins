import json

from pluginctl import label_catalog
from pluginctl.core import gh
from pluginctl.publish import unlist


def test_set_unlisted_updates_only_the_flag(tmp_path):
    plugin_json = tmp_path / "plugin.json"
    plugin_json.write_text(json.dumps({"name": "Demo", "version": "1.0.0"}), encoding="utf-8")

    assert unlist.set_unlisted(str(plugin_json))
    assert json.loads(plugin_json.read_text(encoding="utf-8")) == {
        "name": "Demo", "version": "1.0.0", "unlisted": True,
    }
    assert not unlist.set_unlisted(str(plugin_json))


def test_set_unlisted_rejects_non_object_json(tmp_path):
    plugin_json = tmp_path / "plugin.json"
    plugin_json.write_text("[]", encoding="utf-8")

    try:
        unlist.set_unlisted(str(plugin_json))
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("Expected a ValueError")


def test_open_pr_for_branch_returns_matching_pr(monkeypatch):
    monkeypatch.setattr(gh, "api", lambda *args, **kwargs: json.dumps([
        {"html_url": "https://github.com/org/repo/pull/42"},
    ]))

    assert unlist._open_pr_for_branch("org/repo", "unlist/demo") == "https://github.com/org/repo/pull/42"


def test_run_rejects_closed_authorizing_issue(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("UNLIST_PLUGIN", "demo")
    monkeypatch.setenv("UNLIST_ISSUE", "42")
    monkeypatch.setenv("SOURCE_BRANCH", "main")
    monkeypatch.setattr(label_catalog, "ensure", lambda repository: True)
    monkeypatch.setattr(gh, "api", lambda *args, **kwargs: "closed")

    assert unlist.run() == 1


def test_run_rejects_invalid_plugin_slug_before_api_calls(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("UNLIST_PLUGIN", "../plugin")
    monkeypatch.setenv("UNLIST_ISSUE", "42")
    monkeypatch.setenv("SOURCE_BRANCH", "main")
    monkeypatch.setattr(label_catalog, "ensure", lambda repository: (_ for _ in ()).throw(AssertionError()))

    assert unlist.run() == 1


def test_run_rejects_existing_unlisting_pr(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("UNLIST_PLUGIN", "demo")
    monkeypatch.setenv("UNLIST_ISSUE", "42")
    monkeypatch.setenv("SOURCE_BRANCH", "main")
    monkeypatch.setattr(label_catalog, "ensure", lambda repository: True)
    monkeypatch.setattr(gh, "api", lambda *args, **kwargs: "open")
    monkeypatch.setattr(unlist, "_open_pr_for_branch", lambda *args: "https://example.test/pr/42")

    assert unlist.run() == 1
