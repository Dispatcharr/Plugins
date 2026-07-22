"""``pluginctl label``: port of the inline ``label-pr`` job.

Reconciles the classification labels on a PR. The decision is pure and unit
tested; applying it just calls ``gh pr edit --add-label/--remove-label`` with the
same add-when-true / remove-when-false behavior as the Bash ``apply_label``.
"""

from __future__ import annotations

from ..core import gh

LABELS = ["New Plugin", "Plugin Update", "Repo Update", "Invalid"]


def decide_labels(has_new_plugin: bool, has_updated_plugin: bool,
                  outside_files: str, outside_violation: bool,
                  close_pr: bool) -> dict[str, bool]:
    """Return the desired on/off state for each managed label."""
    is_repo_update = bool(outside_files) and not outside_violation
    is_invalid = outside_violation or close_pr
    return {
        "New Plugin": has_new_plugin,
        "Plugin Update": has_updated_plugin,
        "Repo Update": is_repo_update,
        "Invalid": is_invalid,
    }


def run(pr_number: str, has_new_plugin: bool, has_updated_plugin: bool,
        outside_files: str, outside_violation: bool, close_pr: bool) -> int:
    desired = decide_labels(has_new_plugin, has_updated_plugin,
                            outside_files, outside_violation, close_pr)
    for label in LABELS:
        gh.pr_edit_label(pr_number, label, desired[label])
    return 0
