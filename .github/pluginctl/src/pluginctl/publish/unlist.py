"""Open a maintainer-authorized PR that removes a plugin from registry discovery."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile

from .. import label_catalog
from ..core import actions, gh
from ..core.git import configure_identity, push_branch_with_lease, run as _git

_SAFE_PLUGIN_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def set_unlisted(plugin_json: str) -> bool:
    """Set ``unlisted`` to true, returning false when it is already true."""
    with open(plugin_json, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("plugin.json must contain a JSON object")
    if data.get("unlisted") is True:
        return False
    data["unlisted"] = True
    with open(plugin_json, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return True


def _open_pr_for_branch(repository: str, branch: str) -> str:
    owner, _, _ = repository.partition("/")
    if not owner:
        return ""
    pulls = gh.loads(gh.api(
        f"repos/{repository}/pulls?state=open&head={owner}:{branch}",
    ))
    if not isinstance(pulls, list) or not pulls:
        return ""
    first = pulls[0] if isinstance(pulls[0], dict) else {}
    return str(first.get("html_url") or "")


def _push_branch(remote: str, branch: str) -> None:
    """Publish the branch, replacing a stale branch left by a closed request PR."""
    push_branch_with_lease(remote, branch)


def run() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    plugin = os.environ["UNLIST_PLUGIN"]
    issue = os.environ["UNLIST_ISSUE"]
    source_branch = os.environ["SOURCE_BRANCH"]
    app_slug = os.environ.get("APP_SLUG", "")
    branch = f"unlist/{plugin}"
    remote = f"https://x-access-token:{token}@github.com/{repository}.git"

    if not _SAFE_PLUGIN_RE.fullmatch(plugin):
        actions.error(f"Invalid plugin slug: {plugin!r}")
        return 1
    if not issue.isdigit():
        actions.error(f"Invalid issue number: {issue!r}")
        return 1
    if not label_catalog.ensure(repository):
        return 1

    actions.log(f"Unlisting {plugin} (issue #{issue})")
    issue_state = gh.api(f"repos/{repository}/issues/{issue}", jq=".state")
    if not issue_state:
        actions.error(f"Issue #{issue} not found in {repository}.")
        return 1
    if issue_state != "open":
        actions.error(f"Issue #{issue} is already {issue_state}. Only open issues can authorize unlisting.")
        return 1

    existing_pr = _open_pr_for_branch(repository, branch)
    if existing_pr:
        actions.error(f"An unlisting PR for {plugin} is already open: {existing_pr}")
        return 1

    workdir = tempfile.mkdtemp()
    start_cwd = os.getcwd()
    try:
        repo_dir = f"{workdir}/repo"
        _git("clone", "--no-checkout", remote, repo_dir)
        os.chdir(repo_dir)
        configure_identity(app_slug)
        _git("fetch", "origin", source_branch)
        _git("checkout", "-b", branch, f"origin/{source_branch}")

        plugin_json = f"plugins/{plugin}/plugin.json"
        if not os.path.isfile(plugin_json):
            actions.error(f"Plugin '{plugin}' does not exist on {source_branch}.")
            return 1
        try:
            changed = set_unlisted(plugin_json)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            actions.error(f"Could not update {plugin_json}: {exc}")
            return 1
        if not changed:
            actions.error(f"Plugin '{plugin}' is already unlisted.")
            return 1

        _git("add", plugin_json)
        _git("commit", "-m", f"Unlist {plugin}\n\nRefs #{issue}")
        _push_branch(remote, branch)

        title = f"[{plugin}]: Unlist plugin"
        body = (f"## Plugin Unlisting\n\n"
                f"Sets `unlisted` to `true` for `{plugin}`, removing it from registry discovery "
                f"and the releases README after this PR is merged and publishing completes. "
                f"Existing releases remain available.\n\n"
                f"**Authorized by:** #{issue}\n\nCloses #{issue}")
        pr_url = gh.pr_create(repository, source_branch, branch, title, body,
                              labels=["Unlisting"])
        if not pr_url:
            actions.error("Unlisting branch was pushed, but the pull request could not be created.")
            return 1
        actions.log(f"Unlisting PR opened: {pr_url}")
        return 0
    finally:
        os.chdir(start_cwd)
        shutil.rmtree(workdir, ignore_errors=True)
