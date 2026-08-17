import os

from pluginctl.validate import sarif

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


def _load():
    import json
    with open(os.path.join(FIX, "sample.sarif"), encoding="utf-8") as fh:
        return [json.load(fh)]


def test_extension_rules_override_driver():
    objs = _load()
    secmap = sarif.build_secmap(objs[0]["runs"][0])
    # driver had 6.5, extension 6.9 -> extension wins
    assert secmap["py/weak-hash"] == 6.9


def test_classify_buckets():
    counts = sarif.classify(_load())
    assert counts.blocking == 1
    assert counts.medium == 1
    assert counts.low == 2
    assert counts.suppressed == 1
    assert counts.total == 5
    assert counts.warnings == 4


def test_sandbox_bypass_is_dormant_by_default():
    counts = sarif.classify(_load())
    assert counts.sandbox_bypass == 0
    assert counts.sandbox_bypass_detected == 0
    assert counts.total == 5


def test_sandbox_bypass_is_informational_when_enabled(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    counts = sarif.classify(_load())
    assert counts.blocking == 1
    assert counts.medium == 1
    assert counts.low == 3
    assert counts.suppressed == 2
    assert counts.sandbox_bypass == 1
    assert counts.sandbox_bypass_detected == 2
    assert counts.total == 7


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


def test_sandbox_findings_table_when_enabled(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    table = sarif.sandbox_findings_table(_load(), "org/repo", "abc123", [])
    assert "`plugin/sandbox-bypass/ctypes-usage`" in table
    assert "Suppressed sandbox finding" not in table


def test_generic_low_table_excludes_enabled_sandbox_findings(monkeypatch):
    monkeypatch.setattr(sarif.feature_flags, "SANDBOX_BYPASS_DETECTION", True)
    table = sarif.findings_table(_load(), sarif.is_low, "org/repo", "abc123", [],
                                 exclude_sandbox_bypass=True)
    assert "plugin/sandbox-bypass" not in table


def test_compute_status():
    assert sarif.compute_status(1, False, True, False) == "failure"
    assert sarif.compute_status(0, True, True, False) == "failure"
    assert sarif.compute_status(0, False, False, False) == "skipped"
    assert sarif.compute_status(0, False, True, True) == "skipped"
    assert sarif.compute_status(0, False, True, False) == "success"
