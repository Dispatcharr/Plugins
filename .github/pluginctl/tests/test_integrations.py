import json
from datetime import datetime, timezone

from pluginctl.core import version
from pluginctl.integrations import automerge, external_readme


# ---- automerge label gate ----
def test_automerge_requires_plugin_update():
    d = automerge.evaluate_labels(["Repo Update"], "MERGEABLE")
    assert not d.ok and "Plugin Update" in d.reason


def test_automerge_blocks_on_new_plugin():
    d = automerge.evaluate_labels(["Plugin Update", "New Plugin"], "MERGEABLE")
    assert not d.ok and "New Plugin" in d.reason


def test_automerge_blocks_on_quarantine():
    d = automerge.evaluate_labels(["Plugin Update", "QUARANTINE"], "MERGEABLE")
    assert not d.ok and "QUARANTINE" in d.reason


def test_automerge_blocks_on_manual_review_requirement():
    d = automerge.evaluate_labels(["Plugin Update", "Manual Review Required"], "MERGEABLE")
    assert not d.ok and "Manual Review Required" in d.reason


def test_automerge_requires_mergeable():
    d = automerge.evaluate_labels(["Plugin Update"], "CONFLICTING")
    assert not d.ok and "mergeable" in d.reason


def test_automerge_ok():
    assert automerge.evaluate_labels(["Plugin Update"], "MERGEABLE").ok


def test_manual_review_is_skipped_for_repo_updates_and_existing_review_labels():
    assert not automerge.should_request_manual_review(["Repo Update"])
    assert not automerge.should_request_manual_review(["Manual Review Required"])
    assert automerge.should_request_manual_review(["Plugin Update"])


def test_automerge_blacklist_csv_is_optional_and_case_insensitive():
    assert not automerge.csv_contains("Alice", "")
    assert automerge.csv_contains("Alice", " bob, ALICE ,carol")
    assert not automerge.csv_contains("Alice", "bob,carol")


def test_automerge_rate_limits_defaults_overrides_and_invalid_values():
    limits, error = automerge.rate_limits_from_env({})
    assert not error
    assert limits == automerge.RateLimits(4, 4, 24)

    limits, error = automerge.rate_limits_from_env({
        "AUTO_MERGE_AUTHOR_LIMIT": "2",
        "AUTO_MERGE_PLUGIN_LIMIT": "0",
        "AUTO_MERGE_RATE_WINDOW_HOURS": "12",
    })
    assert not error
    assert limits == automerge.RateLimits(2, 0, 12)

    limits, error = automerge.rate_limits_from_env({"AUTO_MERGE_AUTHOR_LIMIT": "many"})
    assert limits is None
    assert "integers" in error


def test_automerge_rate_limit_checks_author_and_each_plugin():
    limits = automerge.RateLimits(4, 4, 24)
    history = [
        {"number": 1, "author": {"login": "alice"}},
        {"number": 2, "author": {"login": "alice"}},
        {"number": 3, "author": {"login": "alice"}},
        {"number": 4, "author": {"login": "alice"}},
    ]
    files = {str(n): ["plugins/other/plugin.json"] for n in range(1, 5)}
    decision = automerge.rate_limit_decision("alice", ["demo"], history, files, limits)
    assert not decision.ok and "Author" in decision.reason

    plugin_history = [
        {"number": n, "author": {"login": "other"}} for n in range(1, 5)
    ]
    plugin_files = {str(n): ["plugins/demo/plugin.json"] for n in range(1, 5)}
    decision = automerge.rate_limit_decision("alice", ["demo", "other"], plugin_history,
                                             plugin_files, limits)
    assert not decision.ok and "Plugin 'demo'" in decision.reason


def test_automerge_rate_limit_allows_unexhausted_author_and_plugins():
    limits = automerge.RateLimits(4, 4, 24)
    history = [{"number": 1, "author": {"login": "alice"}}]
    decision = automerge.rate_limit_decision("alice", ["demo"], history,
                                             {"1": ["plugins/demo/plugin.json"]}, limits)
    assert decision.ok


def test_rate_limit_reason_includes_kind_and_relative_reset():
    now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
    history = [
        {"number": 1, "author": {"login": "alice"}, "mergedAt": "2026-11-16T20:00:00Z"},
        {"number": 2, "author": {"login": "alice"}, "mergedAt": "2026-11-16T21:00:00Z"},
    ]
    files = {"1": ["plugins/demo/plugin.json"], "2": ["plugins/demo/plugin.json"]}
    author = automerge.rate_limit_decision("alice", ["demo"], history, files,
                                           automerge.RateLimits(2, 2, 24), now)
    assert "author auto-merge limit" in author.reason
    assert "8 hours" in author.reason
    plugin = automerge.rate_limit_decision("bob", ["demo"], history, files,
                                           automerge.RateLimits(2, 2, 24), now)
    assert "plugin auto-merge limit" in plugin.reason
    assert "8 hours" in plugin.reason


def test_unknown_mergeability_retries_and_includes_changed_plugin(monkeypatch):
    monkeypatch.setenv("GH_REPO", "owner/repo")
    monkeypatch.setattr(automerge.gh, "pr_list", lambda *a, **k: json.dumps([
        {"number": 573, "headRefOid": "sha", "isDraft": False}]))
    info = {"author": {"login": "alice"}, "labels": [{"name": "Plugin Update"}],
            "mergeable": "UNKNOWN"}
    calls = []
    monkeypatch.setattr(automerge.gh, "pr_view_json", lambda *a, **k: calls.append(1) or json.dumps(info))
    monkeypatch.setattr(automerge.time, "sleep", lambda _: None)
    monkeypatch.setattr(automerge.gh, "pr_files", lambda *a: ["plugins/demo/plugin.json"])
    reviews = []
    monkeypatch.setattr(automerge, "_request_manual_review", lambda *a, **k: reviews.append(k))
    assert automerge.run("sha") == 0
    assert len(calls) == 4
    assert reviews[0]["plugins"] == ["demo"]
    assert "UNKNOWN" in reviews[0]["reason"]


def test_merge_command_failure_after_bot_merge_is_recorded(monkeypatch):
    monkeypatch.setenv("GH_REPO", "owner/repo")
    monkeypatch.setenv("BOT_LOGIN", "bot[bot]")
    monkeypatch.setattr(automerge.gh, "pr_list", lambda repo, state, *a, **k: json.dumps(
        [{"number": 570, "headRefOid": "sha"}] if state == "open" else []))
    def view(pr, fields, **kwargs):
        if "mergedBy" in fields:
            return json.dumps({"state": "MERGED", "mergedBy": {"login": "bot[bot]"}, "headRefOid": "sha"})
        return json.dumps({"author": {"login": "alice"}, "labels": [{"name": "Plugin Update"}],
                           "mergeable": "MERGEABLE"})
    monkeypatch.setattr(automerge.gh, "pr_view_json", view)
    monkeypatch.setattr(automerge, "reverify_is_pure_update", lambda _: ["demo"])
    monkeypatch.setattr(automerge.label_catalog, "ensure", lambda _: True)
    monkeypatch.setattr(automerge.gh, "pr_merge_squash", lambda *a, **k: 1)
    labels = []
    monkeypatch.setattr(automerge.gh, "pr_edit_label", lambda pr, label, add: labels.append(label) or 0)
    monkeypatch.setattr(automerge, "_logo_data", lambda *a: {})
    monkeypatch.setattr(automerge, "_plugin_card_data", lambda *a: {})
    from pluginctl.integrations import webhooks
    monkeypatch.setattr(webhooks, "emit", lambda *a, **k: None)
    monkeypatch.setattr(webhooks, "emit_discord", lambda *a, **k: None)
    assert automerge.run("sha") == 0
    assert labels == ["Auto Merged"]

    labels.clear()
    monkeypatch.setenv("BOT_LOGIN", "other[bot]")
    assert automerge.run("sha") == 0
    assert labels == []


# ---- external readme transforms ----
def test_extract_metadata():
    msg = ("Publish plugin updates from main\n\n"
           "Source commit: abc123def\n\n- foo@1.0.0\n- bar@2.1.0\nnot a plugin line")
    sc, plugins = external_readme.extract_metadata(msg)
    assert sc == "abc123def"
    assert plugins == "- foo@1.0.0\n- bar@2.1.0"


def test_strip_preamble():
    readme = ("# Plugin Releases\n\nThis branch contains all published plugin releases.\n\n"
              "## Quick Access\n\n- [manifest.json](./manifest.json)\n\n"
              "## Available Plugins\n\n| Plugin |\n")
    out = external_readme.strip_preamble(readme, "https://c/CONTRIBUTING.md")
    assert out.startswith("# Plugin Releases\n\nWant to get your plugin added")
    assert "Quick Access" not in out
    assert "## Available Plugins" in out
    assert "| Plugin |" in out


def test_rewrite_links():
    text = "See [x](./metadata/foo) and [anchor](#section)"
    out = external_readme.rewrite_links(text, "https://github.com/o/r/tree/releases")
    assert "[x](https://github.com/o/r/tree/releases/metadata/foo)" in out
    assert "[anchor](#section)" in out  # anchors untouched


# ---- release tag selection ----
def test_versioned_tags_sorted_desc_excludes_latest():
    tags = ["demo-1.0.0", "demo-1.10.0", "demo-1.2.0", "demo-latest", "other-1.0.0"]
    assert version.versioned_tags(tags, "demo") == ["demo-1.10.0", "demo-1.2.0", "demo-1.0.0"]
