"""Remove releases for deleted plugins and prune old versions (port of cleanup.sh).

Runs from the releases-branch checkout directory.
"""

from __future__ import annotations

import glob
import json
import os
import shutil

from ..core import actions, gh
from ..core.version import versioned_tags


def run(repository: str, max_versioned_zips: int = 10) -> int:
    releases = gh.release_list(repository)
    all_tags = [str(release["tag"]) for release in releases]

    # Remove releases for deleted plugins (guarded on zips/ existing, as in Bash).
    if os.path.isdir("zips"):
        for release_dir in sorted(glob.glob("metadata/*/")):
            plugin_name = os.path.basename(release_dir.rstrip("/"))
            if not os.path.isdir(f"plugins/{plugin_name}"):
                actions.log(f"  Removing deleted plugin releases: {plugin_name}")
                for tag in [t for t in all_tags if t.startswith(f"{plugin_name}-")]:
                    actions.log(f"    Deleting release {tag}")
                    if gh.release_delete(tag, repository) != 0:
                        actions.error(f"Could not delete release {tag}")
                        return 1
                shutil.rmtree(release_dir, ignore_errors=True)

    # Prune old versioned releases per plugin (keep the newest max_versioned_zips).
    for plugin_dir in sorted(glob.glob("plugins/*/")):
        plugin_name = os.path.basename(plugin_dir.rstrip("/"))
        with open(os.path.join(plugin_dir, "plugin.json"), encoding="utf-8") as fh:
            source = json.load(fh)
        candidate_tag = (
            f"{plugin_name}-{source.get('version')}"
            if source.get("prerelease") is True else ""
        )
        prefix = f"{plugin_name}-"
        stable_tags = []
        for release in releases:
            tag = str(release["tag"])
            if not tag.startswith(prefix):
                continue
            if release.get("prerelease"):
                if tag != candidate_tag:
                    actions.log(f"  Removing stale prerelease {tag}")
                    if gh.release_delete(tag, repository) != 0:
                        actions.error(f"Could not delete stale prerelease {tag}")
                        return 1
            else:
                stable_tags.append(tag)
        tags = versioned_tags(stable_tags, plugin_name)
        if len(tags) <= max_versioned_zips:
            continue
        for old_tag in tags[max_versioned_zips:]:
            actions.log(f"  Removed release {old_tag} (over limit of {max_versioned_zips})")
            if gh.release_delete(old_tag, repository) != 0:
                actions.error(f"Could not delete old release {old_tag}")
                return 1
    return 0
