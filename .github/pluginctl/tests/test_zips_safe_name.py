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


def test_run_skips_external_plugin_when_download_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "external-demo"
    plugin_dir.mkdir(parents=True)
    plugin_dir.joinpath("plugin.json").write_text(json.dumps({
        "name": "External Demo", "version": "1.0.0", "source_type": "external",
        "source_url": "https://downloads.example/external-demo-{version}.zip",
    }), encoding="utf-8")

    warnings = []
    monkeypatch.setattr(gh, "release_exists", lambda *args: False)
    monkeypatch.setattr(zips, "_download", lambda *args: False)
    monkeypatch.setattr(zips.actions, "warning", warnings.append)

    build_meta = tmp_path / "build-meta"
    assert zips.run("main", "org/repo", str(build_meta)) == 0
    assert warnings == [
        "Skipping external-demo v1.0.0: failed to download external ZIP from "
        "https://downloads.example/external-demo-1.0.0.zip after 3 attempts"
    ]
    assert (tmp_path / "changed_plugins.txt").read_text(encoding="utf-8") == ""
    assert not build_meta.exists()


def test_run_skips_existing_prerelease_without_republishing_or_webhook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    plugin_dir.joinpath("plugin.json").write_text(json.dumps({
        "name": "Demo", "version": "1.0.0-dev.1",
    }), encoding="utf-8")

    downloads = []
    monkeypatch.setattr(gh, "release_exists", lambda *args: True)
    monkeypatch.setattr(zips, "_download", lambda *args: downloads.append(args))
    monkeypatch.setattr(zips, "subprocess", None)

    assert zips.run("main", "org/repo", str(tmp_path / "build-meta")) == 0
    assert downloads == []
    assert (tmp_path / "changed_plugins.txt").read_text(encoding="utf-8") == ""
