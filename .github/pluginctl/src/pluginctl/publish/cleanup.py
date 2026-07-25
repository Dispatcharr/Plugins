"""Remove releases for deleted plugins and prune old versions (port of cleanup.sh).

Runs from the releases-branch checkout directory.
"""

from __future__ import annotations

import glob
import os
import shutil

from ..core import actions, gh
from ..core.version import versioned_tags


def run(repository: str, max_versioned_zips: int = 10) -> int:
    all_tags = gh.release_list_tags(repository)

    # Remove releases for deleted plugins (guarded on zips/ existing, as in Bash).
    if os.path.isdir("zips"):
        for release_dir in sorted(glob.glob("metadata/*/")):
            plugin_name = os.path.basename(release_dir.rstrip("/"))
            if not os.path.isdir(f"plugins/{plugin_name}"):
                actions.log(f"  Removing deleted plugin releases: {plugin_name}")
                for tag in [t for t in all_tags if t.startswith(f"{plugin_name}-")]:
                    actions.log(f"    Deleting release {tag}")
                    gh.release_delete(tag, repository)
                shutil.rmtree(release_dir, ignore_errors=True)

    # Prune old versioned releases per plugin (keep the newest max_versioned_zips).
    for plugin_dir in sorted(glob.glob("plugins/*/")):
        plugin_name = os.path.basename(plugin_dir.rstrip("/"))
        tags = versioned_tags(all_tags, plugin_name)
        if len(tags) <= max_versioned_zips:
            continue
        for old_tag in tags[max_versioned_zips:]:
            actions.log(f"  Removed release {old_tag} (over limit of {max_versioned_zips})")
            gh.release_delete(old_tag, repository)
    return 0
