from pluginctl.integrations import automerge, external_readme
from pluginctl.publish import cleanup


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


def test_automerge_requires_mergeable():
    d = automerge.evaluate_labels(["Plugin Update"], "CONFLICTING")
    assert not d.ok and "mergeable" in d.reason


def test_automerge_ok():
    assert automerge.evaluate_labels(["Plugin Update"], "MERGEABLE").ok


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


# ---- cleanup tag selection ----
def test_versioned_tags_sorted_desc_excludes_latest():
    tags = ["demo-1.0.0", "demo-1.10.0", "demo-1.2.0", "demo-latest", "other-1.0.0"]
    assert cleanup._versioned_tags(tags, "demo") == ["demo-1.10.0", "demo-1.2.0", "demo-1.0.0"]
