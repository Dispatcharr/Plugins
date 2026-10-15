from pluginctl.validate import clamav


def test_parse_infected_lines():
    output = ("/w/plugins/a/x.py: OK\n"
              "/w/plugins/a/evil.sh: Eicar-Test-Signature FOUND\n"
              "Scanned 2 files\n")
    lines = clamav.parse_infected_lines(output)
    assert lines == ["/w/plugins/a/evil.sh: Eicar-Test-Signature FOUND"]


def test_build_findings_table_with_hash():
    lines = ["/w/plugins/a/evil.sh: Eicar-Test-Signature FOUND"]
    table = clamav.build_findings_table(lines, "/w", sha256_fn=lambda p: "abc123")
    assert "| File | Signature |" in table
    assert "| `plugins/a/evil.sh` | [`Eicar-Test-Signature`](https://www.virustotal.com/gui/file/abc123) |" in table


def test_build_findings_table_without_hash():
    lines = ["/w/plugins/a/evil.sh: Win.Test FOUND"]
    table = clamav.build_findings_table(lines, "/w", sha256_fn=lambda p: "")
    assert "| `plugins/a/evil.sh` | `Win.Test` |" in table


def test_build_findings_table_strips_workspace_prefix():
    lines = ["/home/runner/work/x/plugins/p/f: Sig FOUND"]
    table = clamav.build_findings_table(lines, "/home/runner/work/x", sha256_fn=lambda p: "h")
    assert "`plugins/p/f`" in table
