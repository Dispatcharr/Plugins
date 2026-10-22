import json
import os

from pluginctl.validate import sarif

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def _load():
    import json
    with open(os.path.join(FIX, "sample.sarif"), encoding="utf-8") as fh:
        return [json.load(fh)]


def _write_runtime_manifest(tmp_path, manifest):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_extension_rules_override_driver():
    objs = _load()
    secmap = sarif.build_secmap(objs[0]["runs"][0])
    # driver had 6.5, extension 6.9 -> extension wins
    assert secmap["py/weak-hash"] == 6.9


def test_detection_feature_flags_are_booleans():
    """Rollout switches may be enabled without invalidating the test suite."""
    assert isinstance(sarif.feature_flags.CAPABILITY_CONTRACT_DETECTION, bool)
    assert isinstance(sarif.feature_flags.SANDBOX_BYPASS_DETECTION, bool)


def test_classify_buckets_with_detection_features_disabled(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "CAPABILITY_CONTRACT_DETECTION", False)
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", False)
    counts = sarif.classify(_load())
    assert counts.blocking == 1
    assert counts.medium == 1
    assert counts.low == 2
    assert counts.suppressed == 1
    assert counts.total == 4
    assert counts.warnings == 3


def test_sandbox_bypass_is_ignored_when_disabled(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", False)
    counts = sarif.classify(_load())
    assert counts.sandbox_bypass == 0
    assert counts.sandbox_bypass_detected == 0
    assert counts.total == 4


def test_sandbox_bypass_is_informational_when_enabled(tmp_path, monkeypatch):
    _write_runtime_manifest(tmp_path, {"manifest_version": 2})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    counts = sarif.classify(_load())
    assert counts.blocking == 1
    assert counts.medium == 1
    assert counts.low == 2
    assert counts.suppressed == 2
    assert counts.sandbox_bypass == 1
    assert counts.sandbox_bypass_detected == 2
    assert counts.total == 4


def test_missing_severity_defaults_to_low():
    counts = sarif.classify(_load())
    # py/unused-import has no security-severity -> 0 -> low bucket
    assert counts.low == 2


def test_process_message_strips_markdown_link_and_brackets():
    out = sarif.process_message("This depends on a [user-provided value](123).")
    assert "user-provided value" in out
    assert "[" not in out and "]" not in out  # escaped to entities or removed


def test_process_message_zero_width_spaces():
    out = sarif.process_message("see https://x/#4 and www.y")
    assert "​://" in out
    assert "www​" in out
    assert "#​4" in out


def test_process_message_not_truncated():
    out = sarif.process_message("a" * 200)
    assert out == "a" * 200


def test_process_message_dedupes_repeated_sentences():
    out = sarif.process_message("This value flows here. This value flows here. Then here.")
    assert out == "This value flows here. Then here."


def test_process_message_no_repeats_untouched():
    out = sarif.process_message("First sentence. Second sentence.")
    assert out == "First sentence. Second sentence."


def test_findings_table_blocking_links_internal():
    table = sarif.findings_table(_load(), sarif.is_blocking, "org/repo", "abc123", [])
    assert "| Rule | Location | Description |" in table
    assert "`py/sql-injection`" in table
    assert "https://github.com/org/repo/blob/abc123/plugins/demo/main.py#L42" in table


def test_findings_table_external_prefix_plain_location():
    table = sarif.findings_table(_load(), sarif.is_blocking, "org/repo", "abc123",
                                 ["plugins/demo/"])
    assert "https://github.com/org/repo/blob" not in table
    assert "plugins/demo/main.py:42" in table


def test_findings_table_excludes_suppressed_results():
    table = sarif.findings_table(_load(), lambda sev: True, "org/repo", "abc123", [])
    assert "Suppressed via inline codeql" not in table


def test_suppressed_findings_table_includes_only_suppressed():
    table = sarif.suppressed_findings_table(_load(), "org/repo", "abc123", [])
    assert "Suppressed via inline codeql" in table
    assert "plugins/demo/other.py:9" in table
    # only the suppressed py/sql-injection result appears, not the blocking one
    assert table.count("`py/sql-injection`") == 1


def test_sandbox_findings_table_when_enabled(tmp_path, monkeypatch):
    _write_runtime_manifest(tmp_path, {"manifest_version": 2})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    table = sarif.sandbox_findings_table(_load(), "org/repo", "abc123", [])
    assert "`plugin/sandbox-bypass/ctypes-usage`" in table
    assert "Suppressed sandbox finding" not in table


def test_generic_low_table_excludes_enabled_sandbox_findings(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    table = sarif.findings_table(_load(), sarif.is_low, "org/repo", "abc123", [],
                                 exclude_sandbox_bypass=True)
    assert "plugin/sandbox-bypass" not in table


def test_capability_contract_requires_an_enforcing_manifest(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "manifest_version": 2,
        "capabilities": [],
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = {
        "ruleId": "plugin/capability-contract/subprocess",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    assert sarif.contract_result_requires_review(result)
    monkeypatch.setattr(sarif.feature_flags, "CAPABILITY_CONTRACT_DETECTION", True)
    assert sarif.classify([{"runs": [{"results": [result]}]}]).capability_contract == 1


def test_sandbox_bypass_requires_an_enforcing_manifest(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = {
        "ruleId": "plugin/sandbox-bypass/filesystem-api",
        "locations": [{"physicalLocation": {"artifactLocation": {
            "uri": "plugins/demo/plugin.py"}, "region": {"startLine": 1}}}],
    }

    for manifest in ({}, {"manifest_version": 0}, {"manifest_version": 1}):
        (plugin_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
        assert not sarif.sandbox_result_requires_review(result)

    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"manifest_version": 0}), encoding="utf-8")
    sarif_objects = [{"runs": [{"results": [result]}]}]
    assert sarif.classify(sarif_objects).sandbox_bypass == 0
    assert "filesystem-api" not in sarif.sandbox_findings_table(
        sarif_objects, "org/repo", "abc123", []
    )

    (plugin_dir / "plugin.json").write_text(
        json.dumps({"manifest_version": 2}), encoding="utf-8"
    )
    assert sarif.sandbox_result_requires_review(result)


def test_sandbox_bypass_rules_respect_schema_ranges(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    v3_rule = "plugin/sandbox-bypass/v3-only"
    retired_rule = "plugin/sandbox-bypass/retired-in-v3"
    monkeypatch.setitem(sarif.capabilities.SANDBOX_BYPASS_RULES, v3_rule, {
        "min_manifest_version": 3,
        "max_manifest_version": None,
    })
    monkeypatch.setitem(sarif.capabilities.SANDBOX_BYPASS_RULES, retired_rule, {
        "min_manifest_version": 2,
        "max_manifest_version": 2,
    })
    result = lambda rule: {
        "ruleId": rule,
        "locations": [{"physicalLocation": {"artifactLocation": {
            "uri": "plugins/demo/plugin.py"}, "region": {"startLine": 1}}}],
    }

    for manifest_version in (0, 1, 2):
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"manifest_version": manifest_version}), encoding="utf-8"
        )
        assert not sarif.sandbox_result_requires_review(result(v3_rule))

    (plugin_dir / "plugin.json").write_text(
        json.dumps({"manifest_version": 3}), encoding="utf-8"
    )
    assert sarif.sandbox_result_requires_review(result(v3_rule))
    assert not sarif.sandbox_result_requires_review(result(retired_rule))


def test_capability_contract_accepts_declared_or_legacy_manifests(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    result = {
        "ruleId": "plugin/capability-contract/subprocess",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    monkeypatch.chdir(tmp_path)
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "manifest_version": 2,
        "capabilities": ["subprocess"],
    }), encoding="utf-8")
    assert not sarif.contract_result_requires_review(result)
    (plugin_dir / "plugin.json").write_text(json.dumps({"manifest_version": 1}), encoding="utf-8")
    assert not sarif.contract_result_requires_review(result)


def test_capability_contract_rules_respect_schema_ranges(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    v3_rule = "plugin/capability-contract/v3-only"
    retired_rule = "plugin/capability-contract/retired-in-v3"
    monkeypatch.setitem(sarif.capabilities.KNOWN_CAPABILITIES, "v3_only", {
        "min_manifest_version": 3,
        "max_manifest_version": None,
        "codeql_rules": [v3_rule],
    })
    monkeypatch.setitem(sarif.capabilities.KNOWN_CAPABILITIES, "retired_in_v3", {
        "min_manifest_version": 1,
        "max_manifest_version": 2,
        "codeql_rules": [retired_rule],
    })

    for manifest_version in (0, 1, 2):
        (plugin_dir / "plugin.json").write_text(
            json.dumps({"manifest_version": manifest_version, "capabilities": []}),
            encoding="utf-8",
        )
        assert not sarif.contract_result_requires_review({
            "ruleId": v3_rule,
            "locations": [{"physicalLocation": {"artifactLocation": {
                "uri": "plugins/demo/plugin.py"}, "region": {"startLine": 1}}}],
        })

    (plugin_dir / "plugin.json").write_text(
        json.dumps({"manifest_version": 3, "capabilities": []}), encoding="utf-8"
    )
    assert sarif.contract_result_requires_review({
        "ruleId": v3_rule,
        "locations": [{"physicalLocation": {"artifactLocation": {
            "uri": "plugins/demo/plugin.py"}, "region": {"startLine": 1}}}],
    })
    assert not sarif.contract_result_requires_review({
        "ruleId": retired_rule,
        "locations": [{"physicalLocation": {"artifactLocation": {
            "uri": "plugins/demo/plugin.py"}, "region": {"startLine": 1}}}],
    })


def test_local_plugin_cannot_override_its_manifest_with_an_external_sidecar(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    result = {
        "ruleId": "plugin/capability-contract/subprocess",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "manifest_version": 2,
        "capabilities": [],
    }), encoding="utf-8")
    (plugin_dir / ".dispatcharr-runtime-manifest.json").write_text(
        json.dumps({"manifest_version": 1}), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert sarif.contract_result_requires_review(result)


def test_external_plugin_uses_the_release_manifest_sidecar(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    result = {
        "ruleId": "plugin/capability-contract/subprocess",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    (plugin_dir / "plugin.json").write_text(json.dumps({"source_type": "external"}), encoding="utf-8")
    (plugin_dir / ".dispatcharr-runtime-manifest.json").write_text(json.dumps({
        "manifest_version": 2,
        "capabilities": [],
    }), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert sarif.contract_result_requires_review(result)


def test_capability_contract_accepts_background_tasks_implied_by_async_action(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "manifest_version": 2,
        "actions": [{"id": "refresh", "async": True}],
    }), encoding="utf-8")
    result = {
        "ruleId": "plugin/capability-contract/background-tasks",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    monkeypatch.chdir(tmp_path)
    assert not sarif.contract_result_requires_review(result)


def test_capability_contract_reviews_explicit_malformed_versions(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.json").write_text(json.dumps({"manifest_version": "two"}), encoding="utf-8")
    result = {
        "ruleId": "plugin/capability-contract/subprocess",
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "plugins/demo/plugin.py"},
                                               "region": {"startLine": 1}}}],
    }
    monkeypatch.chdir(tmp_path)
    assert sarif.contract_result_requires_review(result)


def test_compute_status():
    assert sarif.compute_status(1, False, True, False) == "failure"
    assert sarif.compute_status(0, True, True, False) == "failure"
    assert sarif.compute_status(0, False, False, False) == "skipped"
    assert sarif.compute_status(0, False, True, True) == "skipped"
    assert sarif.compute_status(0, False, True, False) == "success"
