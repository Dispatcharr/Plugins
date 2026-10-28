"""Resolve source and comparison links for plugin notifications.

Registry releases are retention artifacts, so they are deliberately not used to
find a predecessor.  The source repository history is the authority instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from . import git


@dataclass(frozen=True)
class Links:
    current_label: str = ""
    current_url: str = ""
    compare_label: str = ""
    compare_url: str = ""


def github_download_source(url: str) -> Optional[tuple[str, str]]:
    """Return ``(owner/repository, tag)`` for a GitHub release-download URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 6 or parts[2:4] != ["releases", "download"]:
        return None
    return f"{parts[0]}/{parts[1]}", parts[4]


def resolved_source(raw: dict) -> Optional[tuple[str, str]]:
    """Resolve an external manifest's source URL to its GitHub repository and tag."""
    if raw.get("source_type") != "external":
        return None
    version = str(raw.get("version") or "")
    template = str(raw.get("source_url") or "")
    if not version or not template or "{version}" not in template:
        return None
    return github_download_source(template.replace("{version}", version))


def external_links(current: dict, previous: Optional[dict] = None) -> Links:
    """Create links using exact tags encoded by external source URLs."""
    current_source = resolved_source(current)
    if current_source is None:
        return Links()
    repository, tag = current_source
    result = Links(tag, f"https://github.com/{repository}/releases/tag/{tag}")
    previous_source = resolved_source(previous or {})
    if (previous_source is None or previous_source[0] != repository or
            previous_source[1] == tag or previous.get("version") == current.get("version")):
        return result
    previous_tag = previous_source[1]
    return Links(tag, result.current_url, f"{previous_tag}...{tag}",
                 f"https://github.com/{repository}/compare/{previous_tag}...{tag}")


def standard_links(repository: str, current_commit: str, previous_commit: str = "") -> Links:
    """Return no links for a standard plugin.

    The pull request is the scoped review surface. GitHub commit and comparison
    links cover the entire registry repository, not just a plugin directory.
    """
    return Links()


def plugin_at(ref: str, plugin: str) -> Optional[dict]:
    """Read a plugin manifest at ``ref`` without depending on the checkout."""
    text = git.run("show", f"{ref}:plugins/{plugin}/plugin.json", check=False).stdout
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def latest_plugin_commit(plugin: str, ref: str) -> str:
    return git.run("log", "-1", "--format=%H", ref, "--", f":(top)plugins/{plugin}",
                   check=False).stdout.strip()


def previous_plugin_commit(plugin: str, current_commit: str) -> str:
    """Find the prior commit that touched this plugin, skipping unrelated commits."""
    if not current_commit:
        return ""
    return git.run("log", "-1", "--format=%H", f"{current_commit}^", "--",
                   f":(top)plugins/{plugin}", check=False).stdout.strip()


def source_links(repository: str, plugin: str, current_commit: str) -> Links:
    """Resolve the correct link strategy for a published source revision."""
    current = plugin_at(current_commit, plugin)
    if current is None:
        return Links()
    if current.get("source_type") == "external":
        previous_commit = previous_plugin_commit(plugin, current_commit)
        previous = plugin_at(previous_commit, plugin) if previous_commit else None
        return external_links(current, previous)
    return standard_links(repository, current_commit)
