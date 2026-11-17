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
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..core import actions, gh, release_links
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


def should_request_manual_review(labels: list[str]) -> bool:
    """Skip manual-review handling for repository-update PRs."""
    return "Manual Review Required" not in labels and "Repo Update" not in labels


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
                        files_by_pr: dict[str, list[str]], limits: RateLimits,
                        now: datetime | None = None) -> LabelDecision:
    def reset_text(matches: list[dict], limit: int) -> str:
        try:
            times = sorted(datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00"))
                           for pr in matches)
            reset = times[len(times) - limit] + timedelta(hours=limits.window_hours)
            minutes = max(1, math.ceil((reset - (now or datetime.now(timezone.utc))).total_seconds() / 60))
            if minutes < 60:
                return f" At the time of this check, it lifts in approximately {minutes} minute{'s' if minutes != 1 else ''}."
            hours = math.ceil(minutes / 60)
            return f" At the time of this check, it lifts in approximately {hours} hour{'s' if hours != 1 else ''}."
        except (KeyError, TypeError, ValueError):
            return " The reset time could not be determined."

    reasons = []
    if limits.author > 0:
        matches = [pr for pr in history if pr.get("author", {}).get("login", "").lower() == author.lower()]
        if len(matches) >= limits.author:
            reasons.append(f"Author '{author}' reached the {limits.author} author auto-merge limit."
                           + reset_text(matches, limits.author))
    if limits.plugin > 0:
        for plugin in plugins:
            prefix = f"plugins/{plugin}/"
            matches = [pr for pr in history if any(path.startswith(prefix)
                       for path in files_by_pr.get(str(pr.get("number")), []))]
            if len(matches) >= limits.plugin:
                reasons.append(f"Plugin '{plugin}' reached the {limits.plugin} plugin auto-merge limit."
                               + reset_text(matches, limits.plugin))
    if reasons:
        return LabelDecision(False, " ".join(reasons))
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
    for _ in range(3):
        if data.get("mergeable") != "UNKNOWN":
            break
        time.sleep(2)
        data = gh.loads(gh.pr_view_json(pr_number, "author,labels,mergeable,mergeStateStatus", repo=repo)) or {}
    labels = [l.get("name") for l in (data.get("labels") or [])]
    mergeable = data.get("mergeable") or ""
    actions.log(f"Labels: {','.join(labels)}")
    actions.log(f"Mergeable: {mergeable}")

    decision = evaluate_labels(labels, mergeable)
    if not decision.ok:
        actions.notice(f"{decision.reason} - skipping.")
        paths = gh.pr_files(pr_number, repo) or []
        plugins = sorted({parts[1] for path in paths if len(parts := path.split("/")) >= 3
                          and parts[0] == "plugins"})
        _request_manual_review(pr_number, author=(data.get("author") or {}).get("login", ""),
                               plugins=plugins, labels=labels, reason=decision.reason, repo=repo)
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
    history_json = gh.pr_list(repo, "merged", "number,author,mergedAt", search=f'label:"Auto Merged" merged:>={cutoff}',
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
        state = gh.loads(gh.pr_view_json(pr_number, "state,mergedBy,headRefOid", repo=repo)) or {}
        if state.get("state") == "MERGED":
            bot = os.environ.get("BOT_LOGIN", "")
            merged_by = (state.get("mergedBy") or {}).get("login", "")
            if not bot or merged_by.lower() != bot.lower() or state.get("headRefOid") != head_sha:
                actions.notice(f"PR #{pr_number} was merged, but not confirmed as this bot's merge - skipping.")
                return 0
            actions.warning(f"Merge command failed, but PR #{pr_number} was merged by the bot.")
        else:
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
    payload["author"] = author
    webhooks.emit("pr.auto_merged", payload)
    webhooks.emit_discord("pr.auto_merged", payload, repository=repo)
    return 0


def _request_manual_review(pr_number: str, *, author: str, plugins: list[str], labels: list[str],
                           reason: str, repo: str) -> None:
    """Latch manual review and notify only on the absent -> present transition."""
    if not should_request_manual_review(labels):
        return
    if gh.pr_edit_label(pr_number, "Manual Review Required", True) != 0:
        actions.warning(f"Could not add Manual Review Required to PR #{pr_number}.")
        return
    from ..validate import report
    if not report.append_auto_merge_reason(pr_number, repo, os.environ.get("BOT_LOGIN", ""), reason):
        actions.warning(f"Could not update the validation report for PR #{pr_number}.")
    from . import webhooks
    reason_code = "new_plugin" if "New Plugin" in labels else "auto_merge_skipped"
    payload = {"pr": pr_number, "author": author, "plugins": plugins, "labels": labels + ["Manual Review Required"],
               "reason": reason, "reason_code": reason_code, "pr_url": f"https://github.com/{repo}/pull/{pr_number}"}
    payload.update(_logo_data(repo, plugins))
    payload.update(_plugin_card_data(plugins, repo))
    payload["author"] = author
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
    current_commit = release_links.latest_plugin_commit(plugins[0], "HEAD")
    links_data = release_links.source_links(repository, plugins[0], current_commit)
    links = []
    if links_data.current_url:
        links.append(f"[{links_data.current_label}]({links_data.current_url})")
    if links_data.compare_url:
        links.append(f"[{links_data.compare_label}]({links_data.compare_url})")
    result["source_links"] = "-# " + " · ".join(links)
    return result
