"""Auto-merge pure plugin-update PRs (port of auto-merge-updates.yml inline logic).

Only squash-merges a PR that carries the ``Plugin Update`` label, none of the
blocking labels, is cleanly mergeable, and independently re-verifies from the diff
that it touches only existing plugins under ``plugins/``. Every rejection is a
notice, never a failure. The workflow already gates on the GitHub App token being
configured (a GITHUB_TOKEN merge would not cascade into publish), so this handler
assumes it is invoked only in that case.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..core import actions, gh
from ..core.git import run as _git
from .. import label_catalog

BLOCKING_LABELS = ("New Plugin", "Repo Update", "Invalid", "QUARANTINE", "Manual Review Required")


@dataclass
class LabelDecision:
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class RateLimits:
    author: int
    plugin: int
    window_hours: int


def evaluate_labels(labels: list[str], mergeable: str) -> LabelDecision:
    """Require Plugin Update, forbid the blocking labels, require MERGEABLE."""
    label_set = set(labels)
    if "Plugin Update" not in label_set:
        return LabelDecision(False, "Missing 'Plugin Update' label")
    for blocked in BLOCKING_LABELS:
        if blocked in label_set:
            return LabelDecision(False, f"Has '{blocked}' label")
    if mergeable != "MERGEABLE":
        return LabelDecision(False, f"PR not cleanly mergeable (mergeable={mergeable})")
    return LabelDecision(True)


def reverify_is_pure_update(pr_number: str, base_branch: str = "main") -> list[str] | None:
    """Re-derive from the diff that the PR only updates existing plugins."""
    if _git("fetch", "origin", f"pull/{pr_number}/merge:pr-merge-{pr_number}", check=False).returncode != 0:
        actions.notice(f"Could not fetch merge ref for PR #{pr_number} - skipping.")
        return None
    _git("checkout", "-q", f"pr-merge-{pr_number}", check=False)
    merge_base = _git("merge-base", f"origin/{base_branch}", "HEAD", check=False).stdout.strip()
    changed = _git("diff", "--name-only", merge_base, "HEAD", check=False).stdout.splitlines()

    outside = [f for f in changed if not f.startswith("plugins/")]
    if outside:
        actions.notice(f"Changes outside plugins/ detected - skipping. Files: {' '.join(outside)}")
        return None

    slugs = sorted({f.split("/")[1] for f in changed
                    if f.startswith("plugins/") and len(f.split("/")) > 1})
    if not slugs:
        actions.notice("No plugin changes detected in diff - skipping.")
        return None

    for slug in slugs:
        if _git("show", f"origin/{base_branch}:plugins/{slug}/plugin.json", check=False).returncode != 0:
            actions.notice(f"Plugin '{slug}' does not exist on {base_branch} - this is a new "
                           "plugin, not an update. Skipping.")
            return None
    return slugs


def csv_contains(value: str, csv: str) -> bool:
    return any(value.lower() == entry.strip().lower() for entry in csv.split(",") if entry.strip())


def rate_limits_from_env(env: dict[str, str] | None = None) -> tuple[RateLimits | None, str]:
    values = os.environ if env is None else env
    raw = {
        "author": values.get("AUTO_MERGE_AUTHOR_LIMIT", "4"),
        "plugin": values.get("AUTO_MERGE_PLUGIN_LIMIT", "4"),
        "window_hours": values.get("AUTO_MERGE_RATE_WINDOW_HOURS", "24"),
    }
    try:
        limits = RateLimits(*(int(raw[key] or default) for key, default in
                              (("author", "4"), ("plugin", "4"), ("window_hours", "24"))))
    except ValueError:
        return None, "Auto-merge rate-limit settings must be integers"
    if limits.window_hours <= 0:
        return None, "AUTO_MERGE_RATE_WINDOW_HOURS must be greater than zero"
    return limits, ""


def rate_limit_decision(author: str, plugins: list[str], history: list[dict],
                        files_by_pr: dict[str, list[str]], limits: RateLimits) -> LabelDecision:
    if limits.author > 0:
        author_count = sum(pr.get("author", {}).get("login", "").lower() == author.lower()
                           for pr in history)
        if author_count >= limits.author:
            return LabelDecision(False, f"Author '{author}' reached the {limits.author} auto-merge limit")
    if limits.plugin > 0:
        for plugin in plugins:
            prefix = f"plugins/{plugin}/"
            count = sum(any(path.startswith(prefix) for path in files_by_pr.get(str(pr.get("number")), []))
                        for pr in history)
            if count >= limits.plugin:
                return LabelDecision(False, f"Plugin '{plugin}' reached the {limits.plugin} auto-merge limit")
    return LabelDecision(True)


def run(head_sha: str, disabled_reason: str = "") -> int:
    repo = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY", "")

    matches_json = gh.pr_list(repo, "open", "number,headRefOid,isDraft") or "[]"
    try:
        matches = [pr for pr in json.loads(matches_json) if pr.get("headRefOid") == head_sha]
    except json.JSONDecodeError:
        matches = []
    if len(matches) != 1:
        actions.notice(f"Found {len(matches)} open PR(s) matching head SHA {head_sha} - "
                       "skipping (expected exactly 1).")
        return 0
    pr = matches[0]
    pr_number = str(pr.get("number"))
    if pr.get("isDraft") is True:
        actions.notice(f"PR #{pr_number} is a draft - skipping.")
        return 0

    info = gh.pr_view_json(pr_number, "author,labels,mergeable,mergeStateStatus", repo=repo)
    data = gh.loads(info) or {}
    labels = [l.get("name") for l in (data.get("labels") or [])]
    mergeable = data.get("mergeable") or ""
    actions.log(f"Labels: {','.join(labels)}")
    actions.log(f"Mergeable: {mergeable}")

    decision = evaluate_labels(labels, mergeable)
    if not decision.ok:
        actions.notice(f"{decision.reason} - skipping.")
        _request_manual_review(pr_number, author=(data.get("author") or {}).get("login", ""),
                               plugins=[], labels=labels, reason=decision.reason, repo=repo)
        return 0

    plugins = reverify_is_pure_update(pr_number)
    if not plugins:
        _request_manual_review(pr_number, author=(data.get("author") or {}).get("login", ""),
                               plugins=[], labels=labels, reason="Could not verify this as a pure plugin update.", repo=repo)
        return 0

    author = (data.get("author") or {}).get("login", "")
    if disabled_reason:
        actions.notice(f"{disabled_reason} - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins,
                               labels=labels, reason=disabled_reason, repo=repo)
        return 0
    if csv_contains(author, os.environ.get("AUTO_MERGE_BLACKLIST", "")):
        actions.notice(f"PR author '{author}' is on the auto-merge blacklist - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                               reason="The PR author is excluded from automatic merging.", repo=repo)
        return 0

    limits, error = rate_limits_from_env()
    if not limits:
        actions.notice(f"{error} - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels, reason=error, repo=repo)
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=limits.window_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    history_json = gh.pr_list(repo, "merged", "number,author", search=f'label:"Auto Merged" merged:>={cutoff}',
                              limit=100)
    history = gh.loads(history_json)
    if not isinstance(history, list):
        actions.notice("Could not retrieve auto-merge history - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                               reason="Could not retrieve auto-merge history.", repo=repo)
        return 0
    files_by_pr = {}
    for previous in history:
        number = str(previous.get("number"))
        paths = gh.pr_files(number, repo)
        if paths is None:
            actions.notice(f"Could not retrieve changed files for auto-merged PR #{number} - skipping.")
            _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                                   reason="Could not retrieve auto-merge history files.", repo=repo)
            return 0
        files_by_pr[number] = paths
    decision = rate_limit_decision(author, plugins, history, files_by_pr, limits)
    if not decision.ok:
        actions.notice(f"{decision.reason} - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                               reason=decision.reason, repo=repo)
        return 0

    if not label_catalog.ensure(repo):
        actions.notice("Could not ensure auto-merge labels - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                               reason="Could not ensure automation labels.", repo=repo)
        return 0
    if gh.pr_merge_squash(pr_number, repo, delete_branch=False) != 0:
        actions.notice(f"Could not merge PR #{pr_number} - skipping.")
        _request_manual_review(pr_number, author=author, plugins=plugins, labels=labels,
                               reason="GitHub could not complete the automatic merge.", repo=repo)
        return 0
    if gh.pr_edit_label(pr_number, "Auto Merged", True) != 0:
        actions.error(f"PR #{pr_number} merged but could not receive the Auto Merged label.")
        return 1
    actions.log(f"Auto-merged PR #{pr_number}")
    from . import webhooks
    payload = webhooks.pr_auto_merged(pr_number, plugins)
    payload.update({"author": author, "pr_url": f"https://github.com/{repo}/pull/{pr_number}"})
    payload.update(_logo_data(repo, plugins))
    payload.update(_plugin_card_data(plugins, repo))
    webhooks.emit("pr.auto_merged", payload)
    webhooks.emit_discord("pr.auto_merged", payload, repository=repo)
    return 0


def _request_manual_review(pr_number: str, *, author: str, plugins: list[str], labels: list[str],
                           reason: str, repo: str) -> None:
    """Latch manual review and notify only on the absent -> present transition."""
    if "Manual Review Required" in labels:
        return
    if gh.pr_edit_label(pr_number, "Manual Review Required", True) != 0:
        actions.warning(f"Could not add Manual Review Required to PR #{pr_number}.")
        return
    from . import webhooks
    reason_code = "new_plugin" if "New Plugin" in labels else "auto_merge_skipped"
    payload = {"pr": pr_number, "author": author, "plugins": plugins, "labels": labels + ["Manual Review Required"],
               "reason": reason, "reason_code": reason_code, "pr_url": f"https://github.com/{repo}/pull/{pr_number}"}
    payload.update(_logo_data(repo, plugins))
    payload.update(_plugin_card_data(plugins, repo))
    webhooks.emit("pr.review_required", payload)
    webhooks.emit_discord("pr.review_required", payload, repository=repo)


def _logo_data(repo: str, plugins: list[str]) -> dict[str, str]:
    """Return a pinned source-logo URL for the first available changed plugin."""
    sha = _git("rev-parse", "HEAD", check=False).stdout.strip()
    if not sha:
        return {}
    for plugin in plugins:
        for ext in ("png", "svg", "jpg", "webp"):
            path = f"plugins/{plugin}/logo.{ext}"
            if _git("cat-file", "-e", f"HEAD:{path}", check=False).returncode == 0:
                return {"logo_url": f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"}
    return {}


def _plugin_card_data(plugins: list[str], repository: str) -> dict[str, str]:
    """Read the first plugin's display name and upstream release links from checkout."""
    if not plugins:
        return {}
    try:
        with open(f"plugins/{plugins[0]}/plugin.json", encoding="utf-8") as fh:
            current = json.load(fh)
    except (OSError, ValueError):
        return {}
    result = {"plugin_name": str(current.get("name") or plugins[0]),
              "description": str(current.get("description") or ""),
              "author": str(current.get("author") or "unknown")}
    upstream = str(current.get("repo_url") or "").rstrip("/")
    current_version = str(current.get("version") or "")
    if not current_version:
        return result
    external_upstream = current.get("source_type") == "external" and upstream.startswith("https://github.com/")
    if not external_upstream:
        upstream = f"https://github.com/{repository}"
    current_tag = f"v{current_version}" if external_upstream else f"{plugins[0]}-{current_version}"
    links = [f"[v{current_version}]({upstream}/releases/tag/{current_tag})"]
    previous_text = _git("show", f"origin/main:plugins/{plugins[0]}/plugin.json", check=False).stdout
    try:
        previous_version = str(json.loads(previous_text).get("version") or "")
    except json.JSONDecodeError:
        previous_version = ""
    if previous_version and previous_version != current_version:
        previous_tag = f"v{previous_version}" if external_upstream else f"{plugins[0]}-{previous_version}"
        links.append(f"[v{previous_version}...v{current_version}]({upstream}/compare/{previous_tag}...{current_tag})")
    result["source_links"] = "-# " + " · ".join(links)
    return result
