import json

from pluginctl.core import jsonio
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
