import io
import json
import zipfile

import pytest

from pluginctl.release_archive import stage_release
from pluginctl.validate import langs, sarif


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for name, value in entries:
            z.writestr(name, value)
    data.seek(0)
    return data


@pytest.mark.parametrize("prefix", ["", "wrapped/"])
def test_stage_selected_source_and_manifest_aware_findings(tmp_path, monkeypatch, prefix):
    plugin = tmp_path / "plugins" / "demo"
    plugin.mkdir(parents=True)
    catalog = {"source_type": "external", "manifest_version": 1, "capabilities": ["subprocess"]}
    (plugin / "plugin.json").write_text(json.dumps(catalog))
    (plugin / "plugin.py").write_text("catalog source")
    (plugin / "stale.py").write_text("catalog only")
    runtime = {"manifest_version": 2, "capabilities": []}
    artifact = archive([(prefix + "plugin.json", json.dumps(runtime)),
                        (prefix + "plugin.py", "release source"),
                        (prefix + "lib/util.py", "release utility")])
    stage_release(artifact, plugin)
    assert json.loads((plugin / "plugin.json").read_text()) == catalog
    assert json.loads((plugin / ".dispatcharr-runtime-manifest.json").read_text()) == runtime
    assert (plugin / "plugin.py").read_text() == "release source"
    assert (plugin / "lib/util.py").exists()
    assert not (plugin / "stale.py").exists()
    assert langs.detect(str(tmp_path / "plugins")) == (True, "python", "")
    monkeypatch.chdir(tmp_path)
    result = {"ruleId": "plugin/capability-contract/subprocess", "locations": [{
        "physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                             "region": {"startLine": 1}}}]}
    assert sarif.contract_result_requires_review(result)
    result["ruleId"] = "plugin/sandbox-bypass/filesystem-api"
    assert sarif.sandbox_result_requires_review(result)


@pytest.mark.parametrize("entries", [
    [],
    [("plugin.json", "{}"), ("other/plugin.json", "{}")],
    [("a/plugin.json", "{}"), ("b/plugin.json", "{}")],
    [("a/b/plugin.json", "{}"), ("a/b/plugin.py", "")],
    [("pkg/plugin.json", "{}"), ("pkg/__init__.py", ""), ("other/plugin.py", "")],
    [("pkg/plugin.json", "{}"), ("pkg/plugin.py", ""), ("plugin.py", "")],
    [("plugin.json", "{}"), ("nested/plugin.py", "")],
    [("plugin.json", "{}"), ("plugin.py", ""), ("../escape.py", "")],
    [("plugin.json", "{}"), ("plugin.py", ""), ("dir\\file.py", "")],
    [("plugin.json", "{}"), ("plugin.py", ""), (".dispatcharr-runtime-manifest.json", "{}")],
])
def test_stage_rejects_invalid_archive_without_changing_catalog(tmp_path, entries):
    plugin = tmp_path / "demo"
    plugin.mkdir()
    (plugin / "plugin.json").write_text('{"source_type":"external"}')
    with pytest.raises(ValueError):
        stage_release(archive(entries), plugin)
    assert (plugin / "plugin.json").read_text() == '{"source_type":"external"}'
