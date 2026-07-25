"""``pluginctl report``: port of validate/report.sh.

Combines per-plugin fragments, renders the single ``<!--PLUGIN_VALIDATION_COMMENT-->``
comment (same markers / sections / separators / emoji as the Bash), minimizes
prior validation comments as outdated, posts the new one, and closes the PR for
the unauthorized/blacklisted variants. The comment builder is pure so its exact
text is unit-testable; ``run`` performs the IO around it.
"""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field
from typing import Optional

from ..core import actions, gh, git

MARKER = "<!--PLUGIN_VALIDATION_COMMENT-->"

# close_reason values for which the PR itself is closed (vs. merely reported on).
CLOSING_REASONS = ("unauthorized", "author-blacklisted", "plugin-blacklisted")


def closes_pr(close_pr: bool, close_reason: str) -> bool:
    return close_pr and close_reason in CLOSING_REASONS


@dataclass
class ParsedFragments:
    combined_body: str = ""
    plugin_links: str = ""
    any_failed: bool = False
    pr_plugin_names: list[str] = field(default_factory=list)


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def parse_fragments(fragments_dir: str) -> ParsedFragments:
    result = ParsedFragments()
    for fragment in sorted(glob.glob(os.path.join(fragments_dir, "*.fragment.md"))):
        content = _read(fragment)
        if "❌" in content:
            result.any_failed = True
        # META_ROW extraction. plugin.py always appends the genuine marker as
        # the fragment's last line, so anchor here rather than taking the
        # first match - a free-text field (e.g. description) earlier in the
        # fragment must never be able to forge this by embedding its own
        # "<!--META_ROW:" line.
        meta_line = None
        for line in reversed(content.splitlines()):
            if line.startswith("<!--META_ROW:"):
                meta_line = line
                break
        if meta_line is not None:
            meta = meta_line[len("<!--META_ROW:"):]
            if meta.endswith("-->"):
                meta = meta[:-3]
            fields = meta.split("\t")
            fields += [""] * (7 - len(fields))
            f_name, f_version, f_desc, f_author, f_maint, f_repo, f_discord = fields[:7]
            if f_repo or f_discord:
                result.plugin_links += f"**`{f_name}`:**\n"
                if f_repo:
                    result.plugin_links += f"- [GitHub Repository]({f_repo})\n"
                if f_discord:
                    result.plugin_links += f"- [Discord Thread]({f_discord})\n"
                result.plugin_links += "\n"
        # visible = fragment minus META_ROW lines, trailing whitespace stripped ($() semantics)
        visible_lines = [ln for ln in content.splitlines() if not ln.startswith("<!--META_ROW:")]
        visible = "\n".join(visible_lines).rstrip("\n")
        result.combined_body += visible + "\n\n"
        base = os.path.basename(fragment)[: -len(".fragment.md")]
        result.pr_plugin_names.append(base)
    return result


def build_comment(*, plugin_count: str, close_pr: bool, close_reason: str,
                  pr_author: str, discord_url: str, combined_body: str,
                  plugin_links: str, outside_files: str, outside_violation: bool,
                  pub_key_changed: bool, codeql_result: str, codeql_errors: str,
                  codeql_mediums: str, codeql_lows: str, codeql_unscanned_langs: str,
                  clamav_result: str, clamav_infected: str, title_valid: str,
                  title_feedback: str, title_suggestion: str, repository: str,
                  fragment_failed: bool, test_result: str = "skipped",
                  codeql_findings: str = "", codeql_medium_findings: str = "",
                  codeql_low_findings: str = "", clamav_findings: str = "",
                  other_plugins_section: str = "") -> str:
    L: list[str] = []
    overall_failed = fragment_failed
    if title_valid and title_valid != "true":
        overall_failed = True
    if test_result in ("failure", "cancelled"):
        overall_failed = True

    L.append(MARKER)
    L.append("")
    L.append("# Plugin Validation Results")
    L.append("")
    L.append(f"**Modified plugins:** {plugin_count}")
    L.append("")

    if close_reason == "no-valid-plugins":
        L.append("")
        L.append("⚠️ Your PR modifies plugin folder(s) whose names do not meet the naming "
                 "requirements. Plugin folder names must be **lowercase letters, numbers, and "
                 "hyphens only** (e.g. `my-plugin`). Spaces and other special characters are "
                 "not allowed.")
        L.append("")
        L.append("Please rename the folder(s) and update your PR.")
        if discord_url:
            L.append("")
            L.append(f"For help: [Dispatcharr Discord]({discord_url})")
    elif close_reason == "author-blacklisted":
        L.append("")
        L.append("## PR Closed: Account Restricted")
        L.append("")
        L.append(f"Your GitHub account (`{pr_author}`) is not permitted to submit plugins to "
                 "this repository. This PR has been automatically closed.")
        if discord_url:
            L.append("")
            L.append(f"If you believe this is an error, please reach out via the "
                     f"[Dispatcharr Discord]({discord_url}).")
    elif close_reason == "plugin-blacklisted":
        L.append("")
        L.append("## PR Closed: Plugin Restricted")
        L.append("")
        L.append("One or more plugins in this PR are on the restricted list and cannot be "
                 "submitted to this repository. This PR has been automatically closed.")
        if discord_url:
            L.append("")
            L.append(f"If you believe this is an error, please reach out via the "
                     f"[Dispatcharr Discord]({discord_url}).")
    elif close_pr:
        L.append("")
        L.append("## PR Closed: Unauthorized")
        L.append("")
        L.append(f"Your GitHub username (`{pr_author}`) does not appear in `author` or "
                 "`maintainers` for any of the plugin(s) in this PR. This PR has been "
                 "automatically closed.")
        L.append("If you would like to contribute to this plugin, please consider reaching out "
                 "to the maintainers of this plugin on Discord, or the plugin's Github repository.")
        L.append("")
        L.append("If you are submitting a new plugin, add your GitHub username to the `author` "
                 "field in your `plugin.json`.")
        if plugin_links:
            L.append("")
            L.append("### Plugin Contact Links")
            L.append("")
            L.append(plugin_links)
        if discord_url:
            L.append("")
            L.append("For general help or plugin discussion:")
            L.append(f"- [Dispatcharr Discord]({discord_url})")
    else:
        L.append(combined_body)

        if outside_files and outside_violation:
            overall_failed = True
            L.append("")
            L.append("⚠️ This PR modifies files outside of `plugins/`, which requires write "
                     "access to the repository. These changes will block merging.")
            L.append("")
            L.append("External contributions to repository tooling and scripts are not accepted "
                     f"via PR. If you think something needs fixing, please [open an issue]"
                     f"(https://github.com/{repository}/issues/new/choose) instead.")
            L.append("")
            L.append("**Modified files:**")
            L.append("```")
            L.append(outside_files)
            L.append("```")
            L.append("")
            L.append("Remove these changes and resubmit with only modifications inside `plugins/`.")
            if discord_url:
                L.append("")
                L.append(f"For help: [Dispatcharr Discord]({discord_url})")
            L.append("")

        if pub_key_changed:
            L.append("")
            L.append("---")
            L.append("")
            L.append("### ⚠️ Signing Key Change Detected")
            L.append("")
            L.append("This PR modifies `.github/scripts/keys/dispatcharr-plugins.pub`. This is "
                     "the public GPG key used by Dispatcharr to verify manifest signatures.")
            L.append("")
            L.append("**Before merging, confirm:**")
            L.append("- The corresponding private key and passphrase secrets (`GPG_PRIVATE_KEY`, "
                     "`GPG_PASSPHRASE`) have been updated in the repository settings.")
            L.append("- The new public key has been bundled into the Dispatcharr application.")
            L.append("- Existing embedded signatures in `manifest.json` files on the `releases` "
                     "branch will be regenerated on next publish.")
            L.append("")

        if _needs_separator(codeql_result, codeql_mediums, codeql_lows,
                            codeql_unscanned_langs, clamav_result):
            L.append("")
            L.append("---")
            L.append("")

        if clamav_result == "failure":
            overall_failed = True
            infected = clamav_infected or "unknown"
            L.append("")
            L.append(f"❌ **ClamAV detected {infected} infected file(s)**.")
            L.append("")
            if clamav_findings:
                L.append(clamav_findings.rstrip("\n"))

        if codeql_result and codeql_result not in ("skipped", "success"):
            L.append("")
            overall_failed = True
            errors = codeql_errors or "unknown"
            L.append(f"❌ **CodeQL found {errors} high or critical issue(s)** - these must be "
                     "fixed before merging.")
            L.append("")
            if codeql_findings:
                L.append(codeql_findings.rstrip("\n"))

        if codeql_mediums and codeql_mediums != "0" and codeql_result != "skipped":
            L.append("")
            L.append(f"**CodeQL found {codeql_mediums} medium severity issue(s)**")
            L.append("These are not blocking, but are included for visibility.")
            L.append("")
            if codeql_medium_findings:
                L.append(codeql_medium_findings.rstrip("\n"))

        if codeql_lows and codeql_lows != "0" and codeql_result != "skipped":
            L.append("")
            L.append("<details>")
            L.append(f"<summary>CodeQL found {codeql_lows} low severity or informational result(s)</summary>")
            L.append("These are not blocking, but are included for visibility.")
            L.append("")
            if codeql_low_findings:
                L.append(codeql_low_findings.rstrip("\n"))
            L.append("")
            L.append("</details>")

        if codeql_result == "skipped" and codeql_unscanned_langs:
            display = codeql_unscanned_langs.replace(",", " ")
            L.append("")
            L.append("**CodeQL analysis was skipped** - no supported source files were found. "
                     f"The following bundled file type(s) are not covered by CodeQL: `{display}`.")
            L.append("")
        elif codeql_unscanned_langs and codeql_result != "skipped" and codeql_result:
            display = codeql_unscanned_langs.replace(",", " ")
            L.append("")
            L.append(f"**Note:** The following bundled file type(s) were not scanned by CodeQL "
                     f"(unsupported language): `{display}`.")
            L.append("")

        if title_valid and title_valid != "true":
            L.append("")
            L.append("---")
            L.append("")
            L.append("### ❌ PR Title Format")
            L.append("")
            L.append(title_feedback)
            if title_suggestion:
                L.append("")
                L.append(f"**Suggested format:** `{title_suggestion}`")
            L.append("")

        if test_result in ("failure", "cancelled"):
            L.append("")
            L.append("---")
            L.append("")
            L.append("### ❌ Tooling test suite")
            L.append("")
            L.append("The automation test suite (`pluginctl`) failed for this change. "
                     "See the **Test Suite** job in this workflow run for details.")
            L.append("")

        L.append("")
        L.append("---")
        L.append("")
        if not overall_failed:
            L.append("## 🎉 All validation checks passed!")
            L.append("")
            L.append(f"This PR modifies **{plugin_count}** plugin(s) and all checks have passed.")
        else:
            L.append("## ❌ Validation failed")
            L.append("")
            L.append("Some checks failed. Please review the errors above and update your PR.")

        if other_plugins_section:
            L.append("")
            L.append("---")
            L.append("")
            L.append(other_plugins_section)

    return "\n".join(L) + "\n"


def _needs_separator(codeql_result, codeql_mediums, codeql_lows,
                     codeql_unscanned_langs, clamav_result) -> bool:
    if codeql_result and codeql_result != "skipped" and codeql_result != "success":
        return True
    if codeql_mediums and codeql_mediums != "0" and codeql_result != "skipped":
        return True
    if codeql_lows and codeql_lows != "0" and codeql_result != "skipped":
        return True
    if codeql_result == "skipped" and codeql_unscanned_langs:
        return True
    if codeql_result != "skipped" and codeql_result and codeql_unscanned_langs:
        return True
    if clamav_result == "failure":
        return True
    return False


def build_other_plugins_section(fragments_dir: str, pr_plugin_names: list[str],
                                pr_author: str, repository: str, base_ref: str) -> str:
    """Scan plugins/ for other plugins owned by the author (best-effort, like the Bash)."""
    import json
    git.sparse_checkout_add("plugins")
    git.checkout()
    entries: list[str] = []
    for pjson in sorted(glob.glob("plugins/*/plugin.json")):
        pname = os.path.basename(os.path.dirname(pjson))
        if pname in pr_plugin_names:
            continue
        try:
            with open(pjson, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        p_author = data.get("author") or ""
        p_maint = [str(m) for m in (data.get("maintainers") or []) if m is not None]
        if pr_author == p_author or pr_author in p_maint:
            p_display = data.get("name") or pname
            p_version = data.get("version") or ""
            p_repo = data.get("repo_url") or ""
            p_link = p_repo or f"https://github.com/{repository}/tree/{base_ref or 'main'}/plugins/{pname}"
            display_link = f"[**{p_display}**]({p_link})"
            slug_link = f"[`{pname}`](https://github.com/{repository}/tree/{base_ref or 'main'}/plugins/{pname})"
            entries.append(f"| {display_link} | {slug_link} | {p_version} |")
    if not entries:
        return ""
    section = "<details>\n"
    section += f"<summary>Other plugins by <code>{pr_author}</code> in this repository ({len(entries)})</summary>\n\n"
    section += "| Plugin | Slug | Version |\n"
    section += "|--------|------|---------|\n"
    for entry in entries:
        section += entry + "\n"
    section += "\n</details>"
    return section


def minimize_previous_comments(pr_number: str, repository: str) -> None:
    owner, _, repo = repository.partition("/")
    query = ('query($owner: String!, $repo: String!, $number: Int!) {'
             ' repository(owner: $owner, name: $repo) {'
             ' pullRequest(number: $number) {'
             ' comments(first: 100) { nodes { id body } } } } }')
    node_ids = gh.graphql(
        query,
        f_fields={"owner": owner, "repo": repo},
        F_fields={"number": str(pr_number)},
        jq=f'.data.repository.pullRequest.comments.nodes[] | select(.body | contains("{MARKER}")) | .id',
    )
    if not node_ids:
        return
    for node_id in node_ids.splitlines():
        if not node_id:
            continue
        gh.graphql(
            'mutation($id: ID!) { minimizeComment(input: {subjectId: $id, classifier: OUTDATED})'
            ' { minimizedComment { isMinimized } } }',
            f_fields={"id": node_id},
        )


def run(pr_number: str, pr_author: str, plugin_count: str, close_pr: bool,
        fragments_dir: str, repo: str = "") -> int:
    parsed = parse_fragments(fragments_dir)

    close_reason = os.environ.get("CLOSE_REASON", "")
    other_section = ""
    if not (close_pr or close_reason in ("no-valid-plugins", "author-blacklisted", "plugin-blacklisted")):
        other_section = build_other_plugins_section(
            fragments_dir, parsed.pr_plugin_names, pr_author, repo,
            os.environ.get("BASE_REF", ""))

    comment = build_comment(
        plugin_count=str(plugin_count),
        close_pr=close_pr,
        close_reason=close_reason,
        pr_author=pr_author,
        discord_url=os.environ.get("DISCORD_URL", ""),
        combined_body=parsed.combined_body,
        plugin_links=parsed.plugin_links,
        outside_files=os.environ.get("OUTSIDE_FILES", ""),
        outside_violation=os.environ.get("OUTSIDE_VIOLATION", "") == "true",
        pub_key_changed=os.environ.get("PUB_KEY_CHANGED", "") == "true",
        codeql_result=os.environ.get("CODEQL_RESULT", ""),
        codeql_errors=os.environ.get("CODEQL_ERRORS", ""),
        codeql_mediums=os.environ.get("CODEQL_MEDIUMS", ""),
        codeql_lows=os.environ.get("CODEQL_LOWS", ""),
        codeql_unscanned_langs=os.environ.get("CODEQL_UNSCANNED_LANGS", ""),
        clamav_result=os.environ.get("CLAMAV_RESULT", ""),
        clamav_infected=os.environ.get("CLAMAV_INFECTED", ""),
        title_valid=os.environ.get("TITLE_VALID", ""),
        title_feedback=os.environ.get("TITLE_FEEDBACK", ""),
        title_suggestion=os.environ.get("TITLE_SUGGESTION", ""),
        repository=repo,
        fragment_failed=parsed.any_failed,
        test_result=os.environ.get("TEST_RESULT", "skipped"),
        codeql_findings=_read("codeql-findings/codeql-findings.md"),
        codeql_medium_findings=_read("codeql-medium-findings/codeql-medium-findings.md"),
        codeql_low_findings=_read("codeql-low-findings/codeql-low-findings.md"),
        clamav_findings=_read("clamav-findings/clamav-findings.md"),
        other_plugins_section=other_section,
    )

    with open("pr_comment.txt", "w", encoding="utf-8") as fh:
        fh.write(comment)

    minimize_previous_comments(pr_number, repo)
    comment_exit = gh.pr_comment(pr_number, comment)

    _emit_webhook(pr_number, pr_author, close_pr, close_reason, parsed)

    if closes_pr(close_pr, close_reason):
        gh.pr_close(pr_number)
        actions.log(f"PR #{pr_number} closed: unauthorized")
    return comment_exit


def _emit_webhook(pr_number, pr_author, close_pr, close_reason, parsed) -> None:
    from ..integrations import webhooks
    if closes_pr(close_pr, close_reason):
        webhooks.emit("pr.closed_unauthorized",
                      webhooks.pr_closed_unauthorized(pr_number, pr_author, close_reason))
        return
    codeql = os.environ.get("CODEQL_RESULT", "")
    clamav = os.environ.get("CLAMAV_RESULT", "")
    title = os.environ.get("TITLE_VALID", "")
    outside = os.environ.get("OUTSIDE_FILES", "") and os.environ.get("OUTSIDE_VIOLATION", "") == "true"
    failed = (parsed.any_failed or (title and title != "true")
              or (codeql and codeql not in ("skipped", "success"))
              or clamav == "failure" or bool(outside))
    webhooks.emit("pr.validated", webhooks.pr_validated(
        pr_number, pr_author, "fail" if failed else "pass",
        parsed.pr_plugin_names, {"codeql": codeql, "clamav": clamav, "title": title}))
