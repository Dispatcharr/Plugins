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
