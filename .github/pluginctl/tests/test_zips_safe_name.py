import json

from pluginctl.core import gh
from pluginctl.publish import zips


def test_run_skips_unsafe_named_plugin_directory(tmp_path, monkeypatch):
    """publish/zips.run() must never build/upload a plugin folder whose name
    failed the validate-time safe-name allowlist, even if it somehow reached
    `main` (defense in depth alongside the detect.py gate)."""
    monkeypatch.chdir(tmp_path)

    safe_dir = tmp_path / "plugins" / "good-plugin"
    safe_dir.mkdir(parents=True)
    (safe_dir / "plugin.json").write_text(json.dumps({
        "name": "Good Plugin", "version": "1.0.0",
    }), encoding="utf-8")

    # Unsafe-named folder with no plugin.json - if run() ever tried to process
    # it (instead of skipping via the safe-name check), this would raise
    # FileNotFoundError and fail the test.
    unsafe_dir = tmp_path / "plugins" / "Bad_Plugin"
    unsafe_dir.mkdir(parents=True)

    monkeypatch.setattr(gh, "release_exists", lambda *a, **k: True)

    rc = zips.run("main", "org/repo", str(tmp_path / "build_meta"))

    assert rc == 0
    changed = (tmp_path / "changed_plugins.txt").read_text(encoding="utf-8")
    assert "Bad_Plugin" not in changed


def test_run_writes_the_effective_manifest_minimum_to_build_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "name": "Demo", "version": "1.0.0", "manifest_version": 2,
        "min_dispatcharr_version": "v0.20.0",
    }), encoding="utf-8")
    monkeypatch.setattr(gh, "release_exists", lambda *args: False)
    monkeypatch.setattr(gh, "commit_pull_number", lambda *args: (None, None))
    monkeypatch.setattr(gh, "release_create", lambda *args, **kwargs: 0)
    monkeypatch.setattr(zips, "_commit_info", lambda *args: ("", "", ""))
    monkeypatch.setattr(zips, "file_digests", lambda *args: ("md5", "sha256"))
    monkeypatch.setattr(zips.os.path, "getsize", lambda path: 1024)
    monkeypatch.setattr(zips.subprocess, "run", lambda *args, **kwargs: None)

    build_meta = tmp_path / "build-meta"
    assert zips.run("main", "org/repo", str(build_meta)) == 0

    metadata = json.loads((build_meta / "demo" / "demo-1.0.0.json").read_text(encoding="utf-8"))
    assert metadata["min_dispatcharr_version"] == "v0.34.0"
