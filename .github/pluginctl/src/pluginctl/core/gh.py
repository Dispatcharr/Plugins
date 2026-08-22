"""Thin wrapper over the ``gh`` CLI and the GitHub REST/GraphQL surface we use.

Every call shells out to ``gh`` (already authenticated on the runner via
``GH_TOKEN``), matching how the V1 scripts invoked it. Helpers return parsed
values and swallow errors the same way the ``|| true`` / ``2>/dev/null`` idioms
did in Bash, so callers keep the same permissive behavior.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Optional


def _run(args: list[str], check: bool = False, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        check=check,
        capture_output=True,
        text=True,
        input=input_text,
    )


def api(endpoint: str, jq: Optional[str] = None, method: Optional[str] = None,
        fields: Optional[dict[str, str]] = None) -> Optional[str]:
    """``gh api <endpoint>`` returning stripped stdout, or None on failure."""
    args = ["api", endpoint]
    if method:
        args += ["-X", method]
    if jq:
        args += ["--jq", jq]
    for k, v in (fields or {}).items():
        args += ["-f", f"{k}={v}"]
    proc = _run(args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def collaborator_permission(owner: str, repo: str, user: str) -> str:
    """Return the collaborator permission string, or ``none`` (matches Bash)."""
    perm = api(f"repos/{owner}/{repo}/collaborators/{user}/permission",
               jq=".permission")
    return perm if perm else "none"


def has_write_access(owner: str, repo: str, user: str) -> bool:
    """True when the user has admin/maintain/write, mirroring has_write_access()."""
    return collaborator_permission(owner, repo, user) in ("admin", "maintain", "write")


def graphql(query: str, f_fields: Optional[dict[str, str]] = None,
            F_fields: Optional[dict[str, str]] = None, jq: Optional[str] = None) -> Optional[str]:
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in (f_fields or {}).items():
        args += ["-f", f"{k}={v}"]
    for k, v in (F_fields or {}).items():
        args += ["-F", f"{k}={v}"]
    if jq:
        args += ["--jq", jq]
    proc = _run(args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def pr_comment(pr_number: str, body: str) -> int:
    """``gh pr comment``: returns the exit code (report.sh keys off it)."""
    return _run(["pr", "comment", str(pr_number), "--body", body]).returncode


def pr_close(pr_number: str) -> int:
    return _run(["pr", "close", str(pr_number)]).returncode


def pr_comment_repo(pr_number: str, repo: str, body: str) -> int:
    return _run(["pr", "comment", str(pr_number), "--repo", repo, "--body", body]).returncode


def pr_edit_label(pr_number: str, label: str, add: bool) -> None:
    flag = "--add-label" if add else "--remove-label"
    _run(["pr", "edit", str(pr_number), flag, label])


def label_create(name: str, color: str, description: str, repo: str) -> None:
    _run(["label", "create", name, "--color", color,
          "--description", description, "--repo", repo])


def pr_view_json(pr_number: str, fields: str, jq: Optional[str] = None,
                 repo: Optional[str] = None) -> Optional[str]:
    args = ["pr", "view", str(pr_number), "--json", fields]
    if jq:
        args += ["--jq", jq]
    if repo:
        args += ["--repo", repo]
    proc = _run(args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def loads(text: Optional[str]) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---- GitHub Releases helpers (publish / yank / cleanup) ---------------------
def release_exists(tag: str, repo: str) -> bool:
    return _run(["release", "view", tag, "--repo", repo]).returncode == 0


def release_list_tags(repo: str, limit: int = 500) -> list[str]:
    proc = _run(["release", "list", "--repo", repo, "--json", "tagName", "--limit", str(limit)])
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    return [entry.get("tagName", "") for entry in data if entry.get("tagName")]


def release_create(tag: str, repo: str, title: str, notes: str, asset: str) -> int:
    return _run(["release", "create", tag, "--repo", repo, "--title", title,
                 "--notes", notes, asset]).returncode


def pages_url(repo: str) -> str:
    """GitHub Pages site URL for the repo, or an empty string when unavailable."""
    return api(f"repos/{repo}/pages", jq=".html_url // empty") or ""


def release_delete(tag: str, repo: str, cleanup_tag: bool = True) -> int:
    args = ["release", "delete", tag, "--repo", repo, "--yes"]
    if cleanup_tag:
        args.append("--cleanup-tag")
    return _run(args).returncode


def pr_list(repo: str, state: str, fields: str, jq: Optional[str] = None) -> Optional[str]:
    args = ["pr", "list", "--repo", repo, "--state", state, "--json", fields]
    if jq:
        args += ["--jq", jq]
    proc = _run(args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def pr_merge_squash(pr: str, repo: str, delete_branch: bool = False) -> int:
    return _run(["pr", "merge", str(pr), "--repo", repo, "--squash",
                 f"--delete-branch={str(delete_branch).lower()}"]).returncode


def issue_comment(issue: str, repo: str, body: str) -> int:
    return _run(["issue", "comment", str(issue), "--repo", repo, "--body", body]).returncode


def issue_close(issue: str, repo: str, reason: str = "completed") -> int:
    return _run(["issue", "close", str(issue), "--repo", repo, "--reason", reason]).returncode


def pr_create(repo: str, base: str, head: str, title: str, body: str,
              labels: Optional[list[str]] = None) -> Optional[str]:
    args = ["pr", "create", "--repo", repo, "--base", base, "--head", head,
            "--title", title, "--body", body]
    for label in (labels or []):
        args += ["--label", label]
    proc = _run(args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def commit_pull_number(repo: str, sha: str) -> tuple[Optional[str], Optional[str]]:
    """The first PR associated with a commit, as (number, html_url) or (None, None)."""
    out = api(f"repos/{repo}/commits/{sha}/pulls",
              jq='.[0] | {number: .number, url: .html_url}')
    data = loads(out) or {}
    number = data.get("number")
    return (str(number) if number else None, data.get("url"))
