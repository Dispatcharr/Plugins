import json
import os

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
        "<!--META_ROW:Demo Plugin\t1.0.0\tA demo plugin\talice\t\thttps://github.com/x/demo\t-->\n"
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
