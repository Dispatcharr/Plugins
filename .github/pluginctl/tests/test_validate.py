import io
import json
import os
import zipfile

import pytest

from pluginctl.validate import plugin as validate
from pluginctl.core import gh, git


@pytest.fixture
def plugin_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "plugins" / "demo-plugin"
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({
        "name": "Demo Plugin",
        "version": "1.0.0",
        "description": "A demo plugin",
        "author": "alice",
        "license": "MIT",
        "repo_url": "https://github.com/x/demo",
    }), encoding="utf-8")
    (pdir / "main.py").write_text("print('hi')\n", encoding="utf-8")
    # Capture GITHUB_OUTPUT
    out = tmp_path / "gh_output"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    # Stub network + gh + git
    monkeypatch.setattr(gh, "has_write_access", lambda *a, **k: False)
    monkeypatch.setattr(git, "show", lambda *a, **k: None)
    monkeypatch.setattr(validate, "fetch_spdx", lambda: {
        "licenses": [{"licenseId": "MIT", "name": "MIT License", "isOsiApproved": True}]
    })
    return tmp_path, out


def _outputs(out_path) -> dict:
    d = {}
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            d[k] = v
    return d


def _zip(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        for name, contents in entries:
            archive.writestr(name, contents)
    return result.getvalue()


def _external(plugin_repo, monkeypatch, catalog, artifact, status="200"):
    tmp_path, out = plugin_repo
    path = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(path.read_text())
    data.update({"source_type": "external", "source_url": "https://example.com/{version}.zip"})
    data.update(catalog)
    path.write_text(json.dumps(data))
    calls = []
    def fetch(url):
        calls.append(url)
        if artifact is None:
            return status, None, None
        manifest, error = validate.release_manifest(io.BytesIO(artifact))
        return status, manifest, error
    monkeypatch.setattr(validate, "fetch_release", fetch)
    fragment = tmp_path / "frag.md"
    rc = validate.run("demo-plugin", "alice", "main", str(fragment), repo="org/repo")
    return rc, _outputs(out), fragment.read_text(), calls


@pytest.mark.parametrize("prefix", ["", "demo/"])
@pytest.mark.parametrize("version", ["1.0.0", "1.0.0-beta.1"])
def test_external_matching_manifests(plugin_repo, monkeypatch, version, prefix):
    if "-" in version:
        monkeypatch.setattr(git, "show", lambda *args: json.dumps({"version": "1.0.0", "author": "alice"}))
    manifest = {"version": version, "manifest_version": 2}
    rc, outputs, text, calls = _external(plugin_repo, monkeypatch, manifest,
                                         _zip([(prefix + "plugin.json", json.dumps(manifest)), (prefix + "plugin.py", "")]))
    assert rc == 0 and outputs["result"] == "pass"
    assert "| Release artifact | ✅" in text
    assert "| Release manifest" not in text and "| Release `manifest_version`" not in text
    assert calls == [f"https://example.com/{version}.zip"]


@pytest.mark.parametrize("prefix", ["", "demo/"])
@pytest.mark.parametrize("catalog,release,expected", [
    ({"manifest_version": 2}, {"version": "2.0.0", "manifest_version": 2}, "Release manifest `version`"),
    ({"manifest_version": 2}, {"manifest_version": 2}, "Release manifest `version`"),
    ({"manifest_version": 2}, {"version": 1, "manifest_version": 2}, "Release manifest `version`"),
    ({}, {"version": "1.0.0", "manifest_version": 2}, "same `manifest_version`"),
    ({"manifest_version": 2}, {"version": "1.0.0"}, "same `manifest_version`"),
    ({"manifest_version": True}, {"version": "1.0.0", "manifest_version": 2}, "Catalog `plugin.json`"),
    ({"manifest_version": 2}, {"version": "1.0.0", "manifest_version": False}, "release `plugin.json`"),
    ({"manifest_version": -1}, {"version": "1.0.0", "manifest_version": 2}, "Catalog `plugin.json`"),
    ({"manifest_version": 2}, {"version": "1.0.0", "manifest_version": "2"}, "release `plugin.json`"),
    ({"manifest_version": None}, {"version": "1.0.0", "manifest_version": 0}, "Catalog `plugin.json`"),
    ({"manifest_version": 0}, {"version": "1.0.0", "manifest_version": None}, "release `plugin.json`"),
    ({"manifest_version": 1}, {"version": "1.0.0", "manifest_version": 2}, "same `manifest_version`"),
])
def test_external_manifest_field_failures(plugin_repo, monkeypatch, catalog, release, expected, prefix):
    rc, outputs, text, calls = _external(plugin_repo, monkeypatch, catalog,
                                         _zip([(prefix + "plugin.json", json.dumps(release)), (prefix + "plugin.py", "")]))
    assert rc == 1 and outputs["result"] == "fail"
    assert expected in text and len(calls) == 1


@pytest.mark.parametrize("prefix", ["", "demo/"])
@pytest.mark.parametrize("catalog_version,release_version", [({}, {}), ({"manifest_version": 0}, {}),
                                                               ({}, {"manifest_version": 0})])
def test_external_omitted_manifest_version_defaults_to_zero(plugin_repo, monkeypatch, prefix,
                                                                    catalog_version, release_version):
    release = {"version": "1.0.0", **release_version}
    rc, outputs, _, _ = _external(plugin_repo, monkeypatch, catalog_version,
                                   _zip([(prefix + "plugin.json", json.dumps(release)),
                                         (prefix + "plugin.py", "")]))
    assert rc == 0 and outputs["result"] == "pass"


@pytest.mark.parametrize("artifact", [
    b"not a zip",
    _zip([]),
    _zip([("nested/deeper/plugin.json", "{}")]),
    _zip([("plugin.json", "bad json"), ("plugin.py", "")]),
    _zip([("plugin.json", "[]"), ("plugin.py", "")]),
    _zip([("plugin.json", "{}"), ("nested/plugin.json", "{}")]),
    _zip([("a/plugin.json", "{}"), ("b/plugin.json", "{}")]),
    _zip([("nested/plugin.json", "{}"), ("nested/__init__.py", ""), ("other/plugin.py", "")]),
])
def test_external_invalid_artifacts_fail(plugin_repo, monkeypatch, artifact):
    rc, outputs, text, _ = _external(plugin_repo, monkeypatch, {"manifest_version": 2}, artifact)
    assert rc == 1 and outputs["result"] == "fail"
    assert "| Release manifest | ❌" in text


def test_external_duplicate_manifest_fails(plugin_repo, monkeypatch):
    with pytest.warns(UserWarning, match="Duplicate name"):
        artifact = _zip([("plugin.json", "{}"), ("plugin.json", "{}")])
    rc, outputs, text, _ = _external(plugin_repo, monkeypatch, {"manifest_version": 2}, artifact)
    assert rc == 1 and outputs["result"] == "fail"
    assert "duplicate" in text


def test_external_download_failure(plugin_repo, monkeypatch):
    rc, outputs, text, _ = _external(plugin_repo, monkeypatch, {"manifest_version": 2}, None, "404")
    assert rc == 1 and outputs["result"] == "fail"
    assert "HTTP `404`" in text


def test_fetch_release_streams_and_reads_manifest(monkeypatch):
    manifest = {"version": "1.0.0", "manifest_version": 2}
    data = _zip([("plugin.json", json.dumps(manifest)), ("plugin.py", "")])
    class Response(io.BytesIO):
        status = 200

        def read(self, size=-1):
            assert size == 1024 * 1024
            return super().read(size)

    monkeypatch.setattr(validate.urllib.request, "urlopen", lambda request, timeout: Response(data))
    status, actual, error = validate.fetch_release("https://example.com/plugin.zip")
    assert (status, actual, error) == ("200", manifest, None)


def test_new_local_plugin_passes(plugin_repo):
    tmp_path, out = plugin_repo
    frag = tmp_path / "frag.md"
    rc = validate.run("demo-plugin", "alice", "main", str(frag), repo="org/repo")
    assert rc == 0
    outputs = _outputs(out)
    assert outputs["result"] == "pass"
    assert outputs["is_new"] == "true"
    assert outputs["has_permission"] == "true"

    expected = (
        "### Plugin: `demo-plugin`\n"
        "\n"
        "_A demo plugin_\n"
        "\n"
        "[Source Repository](https://github.com/x/demo)\n"
        "\n"
        "| Check | Status | Details |\n"
        "|-------|:------:|---------|\n"
        "| Required fields | ✅ | All required fields present |\n"
        "| Maintainers | ✅ | `alice` |\n"
        "| License | ✅ | `MIT` - MIT License |\n"
        "| Permission | ✅ | New plugin - `alice` listed in `author`/`maintainers` |\n"
        "| Version | ✅ | `1.0.0` |\n"
        "| Version bump | ✅ | New plugin |\n"
        "\n"
        "<!--META_ROW:Demo Plugin\t1.0.0\tA demo plugin\talice\t\thttps://github.com/x/demo\t\tpass\tfalse-->\n"
    )
    assert frag.read_text(encoding="utf-8") == expected


def test_missing_plugin_json_early_exit(plugin_repo):
    tmp_path, out = plugin_repo
    os.remove(tmp_path / "plugins" / "demo-plugin" / "plugin.json")
    frag = tmp_path / "frag.md"
    rc = validate.run("demo-plugin", "alice", "main", str(frag), repo="org/repo")
    assert rc == 0
    assert _outputs(out)["result"] == "fail"
    text = frag.read_text(encoding="utf-8")
    assert "| `plugin.json` | ❌ | File missing |" in text
    assert "<!--META_ROW" not in text


def test_bad_version_and_unsafe_name_fail(plugin_repo):
    tmp_path, out = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["version"] = "1.0"
    pj.write_text(json.dumps(data), encoding="utf-8")
    frag = tmp_path / "frag.md"
    rc = validate.run("demo-plugin", "alice", "main", str(frag), repo="org/repo")
    assert rc == 1
    assert _outputs(out)["result"] == "fail"
    assert "is not valid semver" in frag.read_text(encoding="utf-8")


def test_unauthorized_author_new_plugin(plugin_repo):
    tmp_path, out = plugin_repo
    frag = tmp_path / "frag.md"
    rc = validate.run("demo-plugin", "mallory", "main", str(frag), repo="org/repo")
    assert rc == 1
    text = frag.read_text(encoding="utf-8")
    assert '| Permission | ❌ | Add `"author": "mallory"` to plugin.json |' in text
    assert _outputs(out)["has_permission"] == "false"


def test_description_newline_cannot_forge_meta_row(plugin_repo):
    """A description embedding its own "<!--META_ROW:...-->"-prefixed line
    must not produce that line in the fragment - only the genuine, always-last
    marker plugin.py itself appends should ever start with that prefix."""
    tmp_path, out = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["description"] = ("Cool plugin\n<!--META_ROW:evil\t9.9.9\tFAKE\tattacker\t\t"
                            "https://evil.example/phish\thttps://discord.gg/evil-->")
    pj.write_text(json.dumps(data), encoding="utf-8")
    frag = tmp_path / "frag.md"
    validate.run("demo-plugin", "alice", "main", str(frag), repo="org/repo")
    lines = frag.read_text(encoding="utf-8").splitlines()
    meta_lines = [ln for ln in lines if ln.startswith("<!--META_ROW:")]
    # Exactly one marker line - the description's embedded newline must not
    # have split it into an earlier, forged "<!--META_ROW:" line.
    assert len(meta_lines) == 1
    fields = meta_lines[0][len("<!--META_ROW:"):-len("-->")].split("\t")
    f_repo, f_discord = fields[5], fields[6]
    assert "evil.example" not in f_repo
    assert "discord.gg/evil" not in f_discord


def test_ai_assisted_true_is_accepted(plugin_repo):
    tmp_path, out = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["ai_assisted"] = True
    pj.write_text(json.dumps(data), encoding="utf-8")

    assert validate.run("demo-plugin", "alice", "main", str(tmp_path / "frag.md"), repo="org/repo") == 0
    assert _outputs(out)["result"] == "pass"


@pytest.mark.parametrize("value", [False, None, "true", 1])
def test_ai_assisted_non_positive_values_are_ignored(plugin_repo, value):
    tmp_path, out = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["ai_assisted"] = value
    pj.write_text(json.dumps(data), encoding="utf-8")

    fragment = tmp_path / "frag.md"
    assert validate.run("demo-plugin", "alice", "main", str(fragment), repo="org/repo") == 0
    assert _outputs(out)["result"] == "pass"
    assert "ai_assisted" not in fragment.read_text(encoding="utf-8")


def test_prerelease_requires_current_stable_base(plugin_repo, monkeypatch):
    tmp_path, out = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["version"] = "1.0.0-beta.1"
    pj.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        git, "show",
        lambda ref: json.dumps({"version": "1.0.0", "author": "alice"}) if ref == "origin/main:plugins/demo-plugin/plugin.json" else None,
    )

    fragment = tmp_path / "frag.md"
    assert validate.run("demo-plugin", "alice", "main", str(fragment), repo="org/repo") == 0
    text = fragment.read_text(encoding="utf-8")
    assert "| Prerelease | ✅ |" in text
    assert "| Prerelease base | ✅ | `1.0.0` |" in text
    assert "\tpass\ttrue-->" in text


def test_source_prerelease_boolean_fails(plugin_repo):
    tmp_path, _ = plugin_repo
    pj = tmp_path / "plugins" / "demo-plugin" / "plugin.json"
    data = json.loads(pj.read_text())
    data["prerelease"] = True
    pj.write_text(json.dumps(data), encoding="utf-8")

    fragment = tmp_path / "frag.md"
    assert validate.run("demo-plugin", "alice", "main", str(fragment), repo="org/repo") == 1
    assert "Do not set this field" in fragment.read_text(encoding="utf-8")
