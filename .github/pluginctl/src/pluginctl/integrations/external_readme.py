"""Open/update the plugin-listing PR in an external repo (port of update-external-readme.yml).

Reads the releases-branch README, strips the releases-only preamble, rewrites its
relative links to absolute releases-branch URLs, then creates or updates a PR in
the configured target repo. The text-transform helpers are pure and unit-tested;
the PR plumbing uses the GitHub Contents/PR APIs. Skips when the only change is the
timestamp line.
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
from typing import Optional

from ..core import actions, gh

BRANCH = "auto/dispatcharr-plugin-readme"
_SOURCE_COMMIT_RE = re.compile(r"Source commit: ([0-9a-f]+)")
_PLUGIN_LINE_RE = re.compile(r"^- [a-z0-9].*@")


def extract_metadata(commit_msg: str) -> tuple[str, str]:
    """Return (source_commit, plugin_list_block) from the releases-branch commit."""
    m = _SOURCE_COMMIT_RE.search(commit_msg)
    source_commit = m.group(1) if m else ""
    plugin_lines = [ln for ln in commit_msg.splitlines() if _PLUGIN_LINE_RE.match(ln)]
    return source_commit, "\n".join(plugin_lines)


def strip_preamble(readme: str, contrib_url: str) -> str:
    """Keep the title + a contribute line, drop the intro/Quick Access, keep from Available Plugins."""
    out: list[str] = []
    found = False
    for line in readme.splitlines():
        if line.startswith("# Plugin Releases"):
            out.append(line)
            out.append("")
            out.append(f"Want to get your plugin added to this list? Check out the "
                       f"[plugin repository]({contrib_url}) to learn how to contribute.")
            continue
        if line.startswith("## Available Plugins"):
            found = True
        if found:
            out.append(line)
    return "\n".join(out) + ("\n" if readme.endswith("\n") else "")


def rewrite_links(text: str, base_url: str) -> str:
    """Rewrite relative ``](./`` links to absolute releases-branch URLs."""
    return text.replace("](./", f"]({base_url}/")


def _strip_timestamp(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.startswith("*Last updated:"))


def run(releases_ref: str = "origin/releases") -> int:
    """Read the releases README from ``releases_ref`` and sync it to the target repo.

    Sourcing from a git ref (rather than a working-tree checkout) lets the caller
    keep the base branch checked out, where the composite actions and this package
    live, while still reading the releases-branch content and its publish commit.
    """
    target_repo = os.environ.get("TARGET_REPO", "")
    target_path = os.environ.get("TARGET_PATH", "")
    source_repo = os.environ.get("SOURCE_REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    reviewer = os.environ.get("PR_REVIEWER", "")

    show = subprocess.run(["git", "show", f"{releases_ref}:README.md"],
                          capture_output=True, text=True)
    if show.returncode != 0:
        actions.error("README.md not found on the releases branch - has the Publish Plugins workflow run yet?")
        return 1
    readme = show.stdout

    commit_msg = subprocess.run(["git", "log", "-1", "--format=%B", releases_ref],
                                capture_output=True, text=True).stdout
    source_commit, plugin_list = extract_metadata(commit_msg)
    releases_commit = subprocess.run(["git", "rev-parse", "--short", releases_ref],
                                     capture_output=True, text=True).stdout.strip()

    contrib_url = f"https://github.com/{source_repo}/blob/main/CONTRIBUTING.md"
    readme = strip_preamble(readme, contrib_url)
    readme = rewrite_links(readme, f"https://github.com/{source_repo}/tree/releases")

    default_branch = gh.api(f"repos/{target_repo}", jq=".default_branch")
    if not default_branch:
        actions.error(f"Could not resolve default branch for {target_repo}.")
        return 1

    if gh.api(f"repos/{target_repo}/branches/{BRANCH}") is None:
        base_sha = gh.api(f"repos/{target_repo}/git/refs/heads/{default_branch}", jq=".object.sha")
        gh.api(f"repos/{target_repo}/git/refs", method="POST",
               fields={"ref": f"refs/heads/{BRANCH}", "sha": base_sha or ""})
        actions.log(f"Created branch {BRANCH}")

    existing = gh.api(f"repos/{target_repo}/contents/{target_path}?ref={BRANCH}")
    file_sha = ""
    if existing:
        data = gh.loads(existing) or {}
        file_sha = data.get("sha") or ""
        try:
            existing_content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except Exception:
            existing_content = ""
        if _strip_timestamp(readme) == _strip_timestamp(existing_content):
            actions.log("README content unchanged (only timestamp differs) - skipping.")
            actions.notice("External README not updated: only the timestamp line changed.")
            return 0

    put_fields = {
        "message": f"chore: update plugin releases listing (source commit {source_commit})",
        "content": base64.b64encode(readme.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if file_sha:
        put_fields["sha"] = file_sha
    gh.api(f"repos/{target_repo}/contents/{target_path}", method="PUT", fields=put_fields)

    summary = _build_summary(source_repo, source_commit, releases_commit, plugin_list)
    existing_pr = gh.pr_list(target_repo, "open", "number", jq=".[0].number // empty")
    if existing_pr:
        gh.pr_comment_repo(existing_pr, target_repo, f"### Plugin README update\n\n{summary}")
        actions.log(f"Added update comment to existing PR #{existing_pr}")
    else:
        body = (f"Automated update of the plugin releases listings generated from "
                f"[`{source_repo}`](https://github.com/{source_repo}).\n\n{summary}")
        labels = None
        reviewers = [r.lstrip("@").replace(" ", "") for r in reviewer.split(",") if r.strip()]
        _pr_create_with_reviewers(target_repo, BRANCH, default_branch,
                                  "chore: update plugin releases listings", body, reviewers)
        actions.log("Created new PR")
    return 0


def _build_summary(source_repo, source_commit, releases_commit, plugin_list) -> str:
    lines = [
        f"**Source commit:** [`{source_commit}`](https://github.com/{source_repo}/commit/{source_commit})",
        f"**Releases commit:** [`{releases_commit}`](https://github.com/{source_repo}/commit/{releases_commit})",
    ]
    if plugin_list:
        lines.append("")
        lines.append("**Plugins updated:**")
        lines.extend(plugin_list.splitlines())
    return "\n".join(lines)


def _pr_create_with_reviewers(repo, head, base, title, body, reviewers) -> None:
    args = ["gh", "pr", "create", "--repo", repo, "--head", head, "--base", base,
            "--title", title, "--body", body]
    for r in reviewers:
        if r:
            args += ["--reviewer", r]
    subprocess.run(args, capture_output=True, text=True)
