from pluginctl.validate import report


def _base_kwargs(**over):
    kw = dict(
        plugin_count="1", close_pr=False, close_reason="", pr_author="alice",
        discord_url="", combined_body="### Plugin: `demo`\n\n(table)\n\n",
        plugin_links="", outside_files="", outside_violation=False,
        pub_key_changed=False, codeql_result="", codeql_errors="", codeql_mediums="",
        codeql_lows="", codeql_unscanned_langs="", clamav_result="", clamav_infected="",
        title_valid="true", title_feedback="", title_suggestion="",
        repository="org/repo", fragment_failed=False,
    )
    kw.update(over)
    return kw


def test_pass_comment_has_marker_and_success():
    c = report.build_comment(**_base_kwargs())
    assert c.startswith("<!--PLUGIN_VALIDATION_COMMENT-->\n")
    assert "# Plugin Validation Results" in c
    assert "## 🎉 All validation checks passed!" in c
    assert "This PR modifies **1** plugin(s) and all checks have passed." in c


def test_fragment_failure_shows_failed():
    c = report.build_comment(**_base_kwargs(fragment_failed=True))
    assert "## ❌ Validation failed" in c
    assert "🎉" not in c


def test_unauthorized_close_variant():
    c = report.build_comment(**_base_kwargs(close_pr=True, close_reason="unauthorized"))
    assert "## PR Closed: Unauthorized" in c
    assert "automatically closed" in c
    # main body / success block suppressed
    assert "🎉" not in c


def test_blacklisted_author_variant():
    c = report.build_comment(**_base_kwargs(close_pr=True, close_reason="author-blacklisted"))
    assert "## PR Closed: Account Restricted" in c


def test_codeql_high_block_and_separator():
    c = report.build_comment(**_base_kwargs(
        codeql_result="failure", codeql_errors="2",
        codeql_findings="| Rule | Location | Description |\n"))
    assert "❌ **CodeQL found 2 high or critical issue(s)**" in c
    assert "\n---\n" in c
    assert "## ❌ Validation failed" in c


def test_clamav_failure_block():
    c = report.build_comment(**_base_kwargs(
        clamav_result="failure", clamav_infected="3",
        clamav_findings="| File | Signature |\n"))
    assert "❌ **ClamAV detected 3 infected file(s)**." in c


def test_title_invalid_block():
    c = report.build_comment(**_base_kwargs(
        title_valid="false", title_feedback="Bad prefix.",
        title_suggestion="[repo]: x"))
    assert "### ❌ PR Title Format" in c
    assert "Bad prefix." in c
    assert "**Suggested format:** `[repo]: x`" in c
    assert "## ❌ Validation failed" in c


def test_test_suite_failure_section_and_summary():
    c = report.build_comment(**_base_kwargs(test_result="failure"))
    assert "### ❌ Tooling test suite" in c
    assert "pluginctl" in c
    assert "## ❌ Validation failed" in c
    assert "🎉" not in c


def test_test_suite_success_renders_nothing():
    c = report.build_comment(**_base_kwargs(test_result="success"))
    assert "Tooling test suite" not in c
    assert "## 🎉 All validation checks passed!" in c


def test_test_suite_skipped_renders_nothing():
    c = report.build_comment(**_base_kwargs(test_result="skipped"))
    assert "Tooling test suite" not in c


def test_codeql_skipped_notice_no_separator_when_only_success():
    c = report.build_comment(**_base_kwargs(codeql_result="success"))
    # success + no unscanned -> no findings separator, still passes
    assert "## 🎉 All validation checks passed!" in c


def test_parse_fragments(tmp_path):
    f = tmp_path / "demo.fragment.md"
    f.write_text("### Plugin: `demo`\n\n| ok |\n<!--META_ROW:Demo\t1.0.0\td\talice\t\thttps://r\t-->\n",
                 encoding="utf-8")
    parsed = report.parse_fragments(str(tmp_path))
    assert parsed.pr_plugin_names == ["demo"]
    assert "<!--META_ROW" not in parsed.combined_body
    assert "**`Demo`:**" in parsed.plugin_links
    assert "- [GitHub Repository](https://r)" in parsed.plugin_links


def test_parse_fragments_ignores_forged_meta_row_before_the_real_one(tmp_path):
    """A free-text field (e.g. description) that smuggles in its own
    "<!--META_ROW:...-->"-prefixed line must not be able to spoof the
    Plugin Contact Links - only the genuine, always-last marker counts."""
    f = tmp_path / "demo.fragment.md"
    f.write_text(
        "### Plugin: `demo`\n\n"
        "_Cool plugin_\n"
        "<!--META_ROW:evil\t9.9.9\tFAKE\tattacker\t\thttps://evil.example/phish\thttps://discord.gg/evil-->\n"
        "\n| ok |\n"
        "<!--META_ROW:Demo\t1.0.0\td\talice\t\thttps://real.example\t-->\n",
        encoding="utf-8",
    )
    parsed = report.parse_fragments(str(tmp_path))
    assert "evil.example" not in parsed.plugin_links
    assert "discord.gg/evil" not in parsed.plugin_links
    assert "**`Demo`:**" in parsed.plugin_links
    assert "- [GitHub Repository](https://real.example)" in parsed.plugin_links
    assert parsed.any_failed is False
