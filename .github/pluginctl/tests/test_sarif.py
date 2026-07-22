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
    assert counts.total == 4
    assert counts.warnings == 3


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


def test_process_message_truncation():
    out = sarif.process_message("a" * 200)
    assert len(out) == 151 and out.endswith("…")


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


def test_compute_status():
    assert sarif.compute_status(1, False, True, False) == "failure"
    assert sarif.compute_status(0, True, True, False) == "failure"
    assert sarif.compute_status(0, False, False, False) == "skipped"
    assert sarif.compute_status(0, False, True, True) == "skipped"
    assert sarif.compute_status(0, False, True, False) == "success"
