import json

from pluginctl.publish import readmes as r


def test_fmt_date():
    assert r.fmt_date("2024-01-05T09:30:00Z") == "Jan 05 2024, 09:30 UTC"
    assert r.fmt_date("2024-01-05T12:30:00-05:00") == "Jan 05 2024, 17:30 UTC"
    assert r.fmt_date("not a date") == "not a date"
    assert r.fmt_date("") == ""


def test_shields_encode_order():
    # underscores doubled first, then hyphens, then spaces -> underscore
    assert r.shields_encode("Apache-2.0") == "Apache--2.0"
    assert r.shields_encode("a b") == "a_b"
    assert r.shields_encode("a_b-c d") == "a__b--c_d"


def test_anchor_for():
    assert r.anchor_for("My Plugin!") == "my-plugin-"
    assert r.anchor_for("Foo  Bar--Baz") == "foo-bar-baz"


def test_table_row_active_and_deprecated():
    raw = {"name": "Demo", "version": "1.0.0", "author": "alice",
           "description": "d", "license": "MIT"}
    assert r.table_row(raw, False) == "| [`Demo`](#demo) | `1.0.0` | alice | MIT | d |"
    assert r.table_row(raw, True).startswith("| [`Demo`](#demo) (deprecated) |")


def test_table_row_license_default_dash():
    raw = {"name": "N", "version": "1.0.0", "author": "a", "description": "d"}
    assert "| - |" in r.table_row(raw, False)


def test_version_count_fix(tmp_path):
    mf = tmp_path / "manifest.json"
    mf.write_text(json.dumps({"manifest": {"versions": [{"version": "1.0.0"},
                                                         {"version": "1.1.0"}]}}),
                  encoding="utf-8")
    # The deprecated section now counts from the manifest (was always 0 via ls zips/)
    assert r.version_count_from_manifest(str(mf)) == 2
    assert r.version_count_from_manifest(str(tmp_path / "missing.json")) == 0


def test_render_plugin_block_uses_version_count():
    raw = {"name": "Old", "version": "2.0.0", "author": "bob", "description": "legacy"}
    block = r.render_plugin_block(
        is_deprecated=True, plugin_name="old", plugin_raw=raw, manifest=None,
        last_updated="2024-01-01T00:00:00Z", commit_sha="abc", commit_sha_short="abc",
        version_count=3, repository="org/repo", source_branch="main",
        releases_branch="releases", download_base_url="https://dl", has_source_readme=False)
    assert "### [Old](https://github.com/org/repo/blob/releases/metadata/old/README.md) (deprecated)" in block
    assert "- [All Versions (3 available)](./metadata/old)" in block


def test_render_plugin_readme_uses_download_base_url():
    content = r.render_plugin_readme(
        "demo", {"name": "Demo", "version": "1.0.0", "description": "d"},
        {"manifest": {"latest": {"latest_url": "demo-1.0.0/demo.zip"},
                      "versions": [{"version": "1.0.0", "url": "demo-1.0.0/demo.zip"}]}},
        "https://downloads.example", "org/repo", "main", "", False)
    assert content.count("https://downloads.example/demo-1.0.0/demo.zip") == 2
