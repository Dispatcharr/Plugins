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

from ..core import actions, gh
from ..core.git import run as _git

BLOCKING_LABELS = ("New Plugin", "Repo Update", "Invalid", "QUARANTINE", "CodeQL Suppression Used",
                   "Sandbox Bypass Detected")


@dataclass
class LabelDecision:
    ok: bool
    reason: str = ""


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


def reverify_is_pure_update(pr_number: str, base_branch: str = "main") -> bool:
    """Re-derive from the diff that the PR only updates existing plugins."""
    if _git("fetch", "origin", f"pull/{pr_number}/merge:pr-merge-{pr_number}", check=False).returncode != 0:
        actions.notice(f"Could not fetch merge ref for PR #{pr_number} - skipping.")
        return False
    _git("checkout", "-q", f"pr-merge-{pr_number}", check=False)
    merge_base = _git("merge-base", f"origin/{base_branch}", "HEAD", check=False).stdout.strip()
    changed = _git("diff", "--name-only", merge_base, "HEAD", check=False).stdout.splitlines()

    outside = [f for f in changed if not f.startswith("plugins/")]
    if outside:
        actions.notice(f"Changes outside plugins/ detected - skipping. Files: {' '.join(outside)}")
        return False

    slugs = sorted({f.split("/")[1] for f in changed
                    if f.startswith("plugins/") and len(f.split("/")) > 1})
    if not slugs:
        actions.notice("No plugin changes detected in diff - skipping.")
        return False

    for slug in slugs:
        if _git("show", f"origin/{base_branch}:plugins/{slug}/plugin.json", check=False).returncode != 0:
            actions.notice(f"Plugin '{slug}' does not exist on {base_branch} - this is a new "
                           "plugin, not an update. Skipping.")
            return False
    return True


def run(head_sha: str) -> int:
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

    info = gh.pr_view_json(pr_number, "labels,mergeable,mergeStateStatus", repo=repo)
    data = gh.loads(info) or {}
    labels = [l.get("name") for l in (data.get("labels") or [])]
    mergeable = data.get("mergeable") or ""
    actions.log(f"Labels: {','.join(labels)}")
    actions.log(f"Mergeable: {mergeable}")

    decision = evaluate_labels(labels, mergeable)
    if not decision.ok:
        actions.notice(f"{decision.reason} - skipping.")
        return 0

    if not reverify_is_pure_update(pr_number):
        return 0

    gh.pr_merge_squash(pr_number, repo, delete_branch=False)
    actions.log(f"Auto-merged PR #{pr_number}")
    from . import webhooks
    webhooks.emit("pr.auto_merged", webhooks.pr_auto_merged(pr_number, []))
    return 0
