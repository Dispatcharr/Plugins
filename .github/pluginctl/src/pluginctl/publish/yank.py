"""Yank a plugin version from the releases branch (port of yank-version.sh).

Removes a specific version's GitHub Release, regenerates manifests/READMEs, and,
when the yanked version was the latest (or only) one, opens a rollback PR against
the source branch so it is not republished. Authorized by an open issue whose
number is cited and (for non-latest yanks) closed. Env-driven, validated by fork
e2e per the rollout plan.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile

from ..core import actions, gh
from ..core.git import configure_identity, run as _git
from ..core.version import sort_versions_desc
from . import manifest, readmes

RELEASES_BRANCH = "releases"


def run() -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    plugin = os.environ["YANK_PLUGIN"]
    version = os.environ["YANK_VERSION"]
    source_branch = os.environ["SOURCE_BRANCH"]
    issue = os.environ["YANK_ISSUE"]
    app_slug = os.environ.get("APP_SLUG", "")
    remote = f"https://x-access-token:{token}@github.com/{repository}.git"

    actions.log(f"Yanking {plugin} v{version} from {RELEASES_BRANCH} (issue #{issue})")

    issue_state = gh.api(f"repos/{repository}/issues/{issue}", jq=".state")
    if not issue_state:
        actions.error(f"Issue #{issue} not found in {repository}.")
        return 1
    if issue_state != "open":
        actions.error(f"Issue #{issue} is already {issue_state}. Only open issues can authorize a yank.")
        return 1
    actions.log(f"  Issue #{issue} is open - proceeding.")

    workdir = tempfile.mkdtemp()
    build_meta_dir = tempfile.mkdtemp()
    os.environ["BUILD_META_DIR"] = build_meta_dir  # kept for parity; generate() is passed it directly
    start_cwd = os.getcwd()
    try:
        _git("clone", "--no-checkout", remote, f"{workdir}/repo")
        os.chdir(f"{workdir}/repo")
        configure_identity(app_slug)

        if _git("ls-remote", "--exit-code", "--heads", "origin", RELEASES_BRANCH,
                check=False).returncode != 0:
            actions.error("Releases branch does not exist.")
            return 1
        _git("checkout", RELEASES_BRANCH)
        _git("pull", "origin", RELEASES_BRANCH, check=False)

        release_tag = f"{plugin}-{version}"
        plugin_manifest = f"metadata/{plugin}/manifest.json"

        if not gh.release_exists(release_tag, repository):
            actions.error(f"GitHub Release {release_tag} not found. Nothing to yank.")
            return 1

        prefix = f"{plugin}-"
        remaining = [t for t in gh.release_list_tags(repository)
                     if t.startswith(prefix) and t != f"{plugin}-latest" and t != release_tag]
        is_last_version = len(remaining) == 0

        current_latest = ""
        if os.path.isfile(plugin_manifest):
            try:
                with open(plugin_manifest, encoding="utf-8") as fh:
                    data = json.load(fh)
                current_latest = ((data.get("manifest") or {}).get("latest") or {}).get("version") or ""
            except ValueError:
                current_latest = ""
        is_latest = version == current_latest

        actions.log(f"  Current latest   : {current_latest or 'unknown'}")
        actions.log(f"  Is latest        : {str(is_latest).lower()}")
        actions.log(f"  Remaining releases: {len(remaining)}")
        actions.log(f"  Is last version  : {str(is_last_version).lower()}")

        _git("fetch", "origin", source_branch)
        _git("checkout", f"origin/{source_branch}", "--", "plugins")
        source_type = "local"
        pj = f"plugins/{plugin}/plugin.json"
        if os.path.isfile(pj):
            try:
                with open(pj, encoding="utf-8") as fh:
                    source_type = (json.load(fh).get("source_type") or "local")
            except ValueError:
                source_type = "local"

        new_latest_version = ""
        if is_last_version:
            actions.log(f"Last version - deleting all GitHub Releases for {plugin}.")
            gh.release_delete(release_tag, repository)
            subprocess.run(["rm", "-rf", f"metadata/{plugin}"], check=False)
        else:
            actions.log(f"Deleting GitHub Release {release_tag}")
            gh.release_delete(release_tag, repository)
            if is_latest:
                bare = [t[len(prefix):] for t in remaining]
                ordered = sort_versions_desc(bare)
                new_latest_version = ordered[0] if ordered else ""
                if not new_latest_version:
                    actions.error("Could not find a replacement version to promote to latest.")
                    return 1
                actions.log(f"Promoting {new_latest_version} to latest (manifest will be updated by generate-manifest).")

        for f in ("manifest.json", "README.md"):
            if os.path.exists(f):
                os.remove(f)
        actions.log("\n=== Regenerating manifests ===")
        manifest.generate(source_branch, RELEASES_BRANCH, repository, build_meta_dir)
        actions.log("\n=== Regenerating per-plugin READMEs ===")
        readmes.generate_plugin_readmes(source_branch, repository)
        actions.log("\n=== Regenerating releases README ===")
        readmes.generate_releases_readme(source_branch, RELEASES_BRANCH, repository)

        releases_commit = _commit_releases(remote, plugin, version, issue)
        rollback_pr_url = ""
        if is_latest:
            rollback_pr_url = _open_rollback_pr(
                repository, source_branch, remote, plugin, version,
                new_latest_version, is_last_version, source_type, issue)

        _finalize_issue(repository, plugin, version, issue, releases_commit,
                        is_latest, rollback_pr_url)
        from ..integrations import webhooks
        webhooks.emit("plugin.yanked",
                      webhooks.plugin_yanked(plugin, version, issue, rollback_pr_url or None))
        return 0
    finally:
        os.chdir(start_cwd)
        subprocess.run(["rm", "-rf", workdir, build_meta_dir], check=False)


def _commit_releases(remote, plugin, version, issue) -> str:
    actions.log("\n=== Committing ===")
    subprocess.run(["rm", "-rf", "plugins"], check=False)
    _git("rm", "-rf", "--cached", "plugins", check=False)
    _git("add", "metadata", "manifest.json", "README.md")
    if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
        actions.log("No changes to commit - was this version already absent?")
        return ""
    _git("commit", "-m", f"Yank {plugin} v{version}\n\nRefs #{issue}")
    releases_commit = _git("rev-parse", "--short", "HEAD").stdout.strip()
    _git("push", remote, RELEASES_BRANCH)
    actions.log(f"Successfully yanked {plugin} v{version} from {RELEASES_BRANCH}")
    return releases_commit


def _open_rollback_pr(repository, source_branch, remote, plugin, version,
                      new_latest_version, is_last_version, source_type, issue) -> str:
    actions.log("\n=== Opening rollback PR ===")
    rollback_branch = f"yank/{plugin}-{version}"
    _git("fetch", "origin", source_branch)
    _git("checkout", "-b", rollback_branch, f"origin/{source_branch}")

    if is_last_version:
        _git("rm", "-rf", f"plugins/{plugin}")
        pr_title = f"[{plugin}]: Remove plugin (all versions yanked)"
        pr_body = (f"## Plugin Removed\n\nAll published versions of `{plugin}` have been yanked "
                   f"from the releases branch.\n\nThis PR removes the plugin from the source branch "
                   f"to prevent it from being republished on the next run.\n\n"
                   f"**Yanked version:** `{version}`\n**Authorized by:** #{issue}\n\nCloses #{issue}")
    else:
        source_note = _rollback_source(plugin, new_latest_version, source_type)
        _git("add", f"plugins/{plugin}/")
        pr_title = f"[{plugin}]: Roll back to v{new_latest_version} (yank of v{version})"
        pr_body = (f"## Version Rollback\n\n`{plugin}` `{version}` has been yanked from the releases "
                   f"branch. This PR rolls the source back to `{new_latest_version}` so the yanked "
                   f"version is not republished on the next run.\n\n"
                   f"**Yanked version:** `{version}`\n**New latest:** `{new_latest_version}`\n"
                   f"**Authorized by:** #{issue}\n\n{source_note}\n\nCloses #{issue}")

    _git("commit", "-m", pr_title)
    _git("push", remote, rollback_branch)
    gh.label_create("Rollback", "E11D48", "Version rollback opened by the yank workflow", repository)
    url = gh.pr_create(repository, source_branch, rollback_branch, pr_title, pr_body,
                       labels=["Rollback"]) or ""
    actions.log(f"Rollback PR opened: {rollback_branch} -> {source_branch} ({url})")
    return url


def _rollback_source(plugin, new_latest_version, source_type) -> str:
    pj = f"plugins/{plugin}/plugin.json"
    if source_type == "local":
        restore_commit = ""
        shas = _git("log", "--all", "--format=%H", "--", pj).stdout.split()
        for sha in shas:
            show = _git("show", f"{sha}:{pj}", check=False)
            if show.returncode != 0:
                continue
            try:
                if json.loads(show.stdout).get("version") == new_latest_version:
                    restore_commit = sha
                    break
            except ValueError:
                continue
        if restore_commit:
            actions.log(f"Restoring plugins/{plugin}/ from commit {restore_commit}")
            _git("checkout", restore_commit, "--", f"plugins/{plugin}/")
            return (f"Plugin source files restored from commit `{restore_commit[:7]}` "
                    f"(the last commit where `{plugin}` was at `{new_latest_version}`).")
        actions.warning(f"Could not find a commit for {plugin} v{new_latest_version} - "
                        "falling back to version field update only.")
        _bump_version(pj, new_latest_version)
        return ("⚠️ **Could not restore source files** - no commit found for "
                f"`{new_latest_version}` (history may have been squashed). Only the `version` "
                "field was updated. Please review the source files manually before merging.")
    _bump_version(pj, new_latest_version)
    return (f"Version field in `plugin.json` updated to `{new_latest_version}`. The ZIP will be "
            "re-fetched from the external source URL on the next publish run.")


def _bump_version(pj: str, new_version: str) -> None:
    with open(pj, encoding="utf-8") as fh:
        data = json.load(fh)
    data["version"] = new_version
    # jq '.version = $v' rewrites pretty-printed with 2-space indent + trailing newline.
    with open(pj, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _finalize_issue(repository, plugin, version, issue, releases_commit,
                    is_latest, rollback_pr_url) -> None:
    commit_label = releases_commit or "unknown"
    if is_latest:
        gh.issue_comment(issue, repository,
                         f"`{plugin}` v`{version}` has been removed from the releases branch "
                         f"(commit `{commit_label}`).\n\nA rollback PR has been opened to update the "
                         f"source branch: {rollback_pr_url or '(see workflow run for link)'}\n\n"
                         "This issue will close automatically when that PR is merged.")
    else:
        gh.issue_comment(issue, repository,
                         f"`{plugin}` v`{version}` has been removed from the releases branch "
                         f"(commit `{commit_label}`).\n\nThis was not the latest version so no source "
                         "branch changes are needed.")
        gh.issue_close(issue, repository, reason="completed")
