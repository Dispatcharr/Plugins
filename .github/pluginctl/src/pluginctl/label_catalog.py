"""Repository labels required by pluginctl and its workflows."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .core import actions, gh


@dataclass(frozen=True)
class Label:
    name: str
    color: str
    description: str


# Baseline labels mirror Dispatcharr/Plugins. The remaining entries are labels
# created by this repository's automation.
LABELS = (
    Label("CodeQL Suppression Used", "FBCA04", "PR relies on an inline CodeQL suppression comment and requires maintainer review"),
    Label("Invalid", "333333", "The PR is invalid or created in error."),
    Label("New Plugin", "19D64D", "A new plugin being contributed to the repository."),
    Label("Plugin Update", "130518", "A plugin already in the repository is being updated."),
    Label("Repo Update", "86ADC3", "Scripts or other repository infrastructure."),
    Label("Testing", "F1E909", "This PR was created for testing and should not be merged."),
    Label("Manual Review Required", "CFD3D7", "Security findings, suppressions, or new plugins require maintainer review"),
    Label("QUARANTINE", "FFFF00", "ClamAV detected a potential threat in this PR"),
    Label("Rollback", "E11D48", "Version rollback opened by the yank workflow"),
    Label("Plugin Unlisting", "B60205", "Maintainer request to remove a plugin from registry discovery"),
    Label("Auto Merged", "333333", "PR was merged automatically after validation"),
)


def ensure(repo: str = "") -> bool:
    """Create or update every managed label without touching unrelated labels."""
    repository = repo or os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY", "")
    if not repository:
        actions.error("No repository provided while ensuring labels.")
        return False
    failed = [label.name for label in LABELS
              if gh.label_create(label.name, label.color, label.description, repository) != 0]
    if failed:
        actions.error(f"Could not ensure labels: {', '.join(failed)}")
        return False
    return True
