import json

from pluginctl.core import jsonio
from pluginctl.core import gh
from pluginctl import feature_flags
from pluginctl.publish import manifest as m


META = {
    "version": "1.2.0",
    "commit_sha": "abcdef0",
    "commit_sha_short": "abcdef0",
    "build_timestamp": "2024-01-01T00:00:00Z",
    "last_updated": "2024-01-01T00:00:00Z",
    "checksum_md5": "deadbeef",
    "checksum_sha256": "cafef00d",
    "source_url": "https://s/1.2.0/x.zip",
    "size_kb": 10,
}

PLUGIN_RAW = {
    "name": "Demo",
    "version": "1.2.0",
    "description": "a plugin",
    "author": "alice",
    "maintainers": ["bob"],
    "license": "MIT",
    "source_type": "external",
    "source_url": "https://s/{version}/x.zip",
    "repo_url": "https://r",
}


def test_version_entry_key_order_and_null_drop():
    entry = m.build_version_entry(META, "demo-1.2.0/demo-1.2.0.zip", 10, "1.2.0")
    # min/max absent in META -> dropped; key order matches the jq object literal
    assert list(entry.keys()) == [
        "version", "commit_sha", "commit_sha_short", "build_timestamp",
        "last_updated", "checksum_md5", "checksum_sha256", "source_url", "url", "size",
    ]


def test_version_entry_empty_metadata():
    entry = m.build_version_entry({}, "u", 5, "1.2.0")
    assert entry == {"version": "1.2.0", "url": "u", "size": 5}


def test_override_current_min_max():
    zips = [{"version": "1.2.0", "url": "u", "size": 5}]
    out = m.override_current_min_max(zips, "1.2.0", "v0.9.0", "")
    assert out[0]["min_dispatcharr_version"] == "v0.9.0"
    assert "max_dispatcharr_version" not in out[0]  # "" -> None -> dropped


def test_plugin_entry_key_order():
    zips = [m.build_version_entry(META, "demo-1.2.0/demo-1.2.0.zip", 10, "1.2.0")]
    entry = m.build_plugin_entry(
        PLUGIN_RAW, "demo", "demo-1.2.0/demo-1.2.0.zip",
        "https://github.com/org/repo", "org/repo", zips, META, 10)
    assert list(entry.keys()) == [
        "slug", "name", "description", "author", "maintainers", "license",
        "source_type", "source_url", "repo_url", "registry_url", "registry_name",
        "last_updated", "latest", "versions",
    ]
    # discord_thread + deprecated absent -> dropped
    assert "discord_thread" not in entry
    assert "deprecated" not in entry
    # latest sub-object key order
    assert list(entry["latest"].keys()) == [
        "version", "commit_sha", "commit_sha_short", "build_timestamp",
        "last_updated", "checksum_md5", "checksum_sha256", "source_url",
        "latest_url", "url", "size",
    ]


def test_root_entry_key_order():
    entry = m.build_root_entry(
        PLUGIN_RAW, "demo", META, 10, "v0.9.0", "",
        "demo-1.2.0/demo-1.2.0.zip", "https://raw/metadata/demo/manifest.json")
    assert list(entry.keys()) == [
        "slug", "name", "description", "manifest_url", "author", "license",
        "last_updated", "latest_version", "latest_md5", "latest_sha256",
        "latest_url", "latest_size", "min_dispatcharr_version",
    ]  # max_dispatcharr_version "" -> dropped


def test_trim_description():
    assert m.trim_description("x" * 200) == "x" * 200
    long = m.trim_description("x" * 250)
    assert len(long) == 200 and long.endswith("...")


def test_root_manifest_compact_matches_jq(tmp_path):
    import shutil
    import subprocess
    entry = m.build_root_entry(PLUGIN_RAW, "demo", META, 10, "", "",
                               "u", "https://raw/m.json")
    root = m.build_root_manifest("https://github.com/org/repo", "org/repo",
                                 "https://dl", [entry])
    compact = jsonio.dumps(root)
    if shutil.which("jq"):
        jq_out = subprocess.run(["jq", "-c", "."], input=compact,
                                capture_output=True, text=True, check=True).stdout.strip()
        assert compact == jq_out  # stable round-trip through real jq
    assert json.loads(compact)["plugins"][0]["slug"] == "demo"


def test_root_manifest_split_base_urls_key_order():
    entry = m.build_root_entry(PLUGIN_RAW, "demo", META, 10, "", "",
                               "u", "metadata/demo/manifest.json")
    root = m.build_root_manifest(
        "https://github.com/org/repo", "org/repo",
        "https://github.com/org/repo/releases/download", [entry],
        "https://org.github.io/repo")
    assert list(root) == [
        "registry_url", "registry_name", "download_base_url",
        "metadata_base_url", "plugins",
    ]
    assert "root_url" not in root
    assert root["plugins"][0]["manifest_url"] == "metadata/demo/manifest.json"


def test_write_manifest_uses_formatted_json_and_ignores_existing_whitespace(tmp_path):
    dest = tmp_path / "manifest.json"
    payload = {"registry_name": "demo", "plugins": []}

    assert m.write_manifest_if_changed(str(dest), payload, "2026-01-01T00:00:00Z")
    rendered = dest.read_text(encoding="utf-8")
    assert rendered.startswith("{\n  \"generated_at\":")
    assert rendered.endswith("\n")
    assert json.loads(rendered)["manifest"] == payload

    dest.write_text(json.dumps({"manifest": payload}), encoding="utf-8")
    assert not m.write_manifest_if_changed(str(dest), payload, "2026-01-02T00:00:00Z")
    assert dest.read_text(encoding="utf-8") == json.dumps({"manifest": payload})


def test_pages_url_returns_empty_string_when_pages_is_unavailable(monkeypatch):
    monkeypatch.setattr(gh, "api", lambda *args, **kwargs: None)
    assert gh.pages_url("org/repo") == ""


def test_sync_icon_prefers_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "logo.png").write_bytes(b"png")
    (plugin_dir / "logo.svg").write_bytes(b"svg")
    (tmp_path / "metadata" / "demo").mkdir(parents=True)

    m._sync_icon(str(plugin_dir), "demo")

    assert (tmp_path / "metadata" / "demo" / "logo.png").read_bytes() == b"png"
    assert not (tmp_path / "metadata" / "demo" / "logo.svg").exists()


def test_generate_uses_legacy_manifest_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "Demo", "version": "1.0.0", "description": "d"}),
        encoding="utf-8")
    monkeypatch.setattr(feature_flags, "SPLIT_MANIFEST_BASE_URLS", False)
    monkeypatch.setattr(gh, "release_list_tags", lambda repo: [])
    monkeypatch.setattr(gh, "pages_url", lambda repo: (_ for _ in ()).throw(AssertionError()))

    assert m.generate("main", "releases", "org/repo", "") == 0

    root = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["manifest"]
    assert root["root_url"] == "https://github.com/org/repo/releases/download"
    assert root["plugins"][0]["manifest_url"].startswith("https://raw.githubusercontent.com/")


def test_generate_uses_split_manifest_and_copies_icon_when_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "Demo", "version": "1.0.0", "description": "d"}),
        encoding="utf-8")
    (plugin_dir / "logo.png").write_bytes(b"png")
    monkeypatch.setattr(feature_flags, "SPLIT_MANIFEST_BASE_URLS", True)
    monkeypatch.setattr(gh, "release_list_tags", lambda repo: [])
    monkeypatch.setattr(gh, "pages_url", lambda repo: "https://org.github.io/repo/")

    assert m.generate("main", "releases", "org/repo", "") == 0

    root = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["manifest"]
    assert root["download_base_url"] == "https://github.com/org/repo/releases/download"
    assert root["metadata_base_url"] == "https://org.github.io/repo"
    assert "root_url" not in root
    assert root["plugins"][0]["manifest_url"] == "metadata/demo/manifest.json"
    assert (tmp_path / "metadata" / "demo" / "logo.png").read_bytes() == b"png"
