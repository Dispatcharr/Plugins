"""Publish orchestrator (port of run.sh).

Clones the repo, sets up the releases branch, runs the build/cleanup/manifest/readme
phases, then commits and pushes, skipping commits whose only diff is timestamp
noise. Validated end to end in a fork per the rollout plan; the phase logic it
calls is unit-tested individually.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from ..core import actions, git as _git_mod
from . import cleanup, manifest, readmes, zips

RELEASES_BRANCH = "releases"
MAX_VERSIONED_ZIPS = 10
RELEASES_BRANCH_VERSION = "3"


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], check=check, capture_output=True, text=True)


def _configure_identity(repository: str, app_slug: str) -> None:
    if app_slug:
        from ..core import gh
        bot_user_id = gh.api(f"/users/{app_slug}%5Bbot%5D", jq=".id") or ""
        _git("config", "user.name", f"{app_slug}[bot]")
        if bot_user_id:
            _git("config", "user.email",
                 f"{bot_user_id}+{app_slug}[bot]@users.noreply.github.com")
        else:
            _git("config", "user.email", f"{app_slug}[bot]@users.noreply.github.com")
    else:
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email",
             "41898282+github-actions[bot]@users.noreply.github.com")


def run(source_branch: str) -> int:
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    app_slug = os.environ.get("APP_SLUG", "")
    force_rebuild = os.environ.get("FORCE_REBUILD", "false") == "true"
    force_plugin = os.environ.get("FORCE_REBUILD_PLUGIN", "")
    remote = f"https://x-access-token:{token}@github.com/{repository}.git"

    actions.log(f"Publishing plugins from {source_branch} to {RELEASES_BRANCH}")

    workdir = tempfile.mkdtemp()
    build_meta_dir = tempfile.mkdtemp()
    start_cwd = os.getcwd()
    try:
        _git("clone", "--no-checkout", remote, f"{workdir}/repo")
        os.chdir(f"{workdir}/repo")
        _configure_identity(repository, app_slug)
        _setup_releases_branch(repository, source_branch, token, remote,
                               force_rebuild, force_plugin)

        # Clean regenerated top-level artifacts and fetch source plugins.
        for f in ("manifest.json", "README.md"):
            if os.path.exists(f):
                os.remove(f)
        _git("fetch", "origin", source_branch)
        _git("checkout", f"origin/{source_branch}", "--", "plugins")
        os.makedirs("zips", exist_ok=True)

        if not force_rebuild:
            current = _read("REPO_VER")
            if current != RELEASES_BRANCH_VERSION:
                actions.error("Releases branch version mismatch.")
                actions.error(f"  Expected : {RELEASES_BRANCH_VERSION}")
                actions.error(f"  Found    : {current or '(none - migration not run)'}")
                actions.error("Run the 'Migrate Releases to GitHub Releases' workflow first, then re-run.")
                return 1

        actions.log("\n=== Building ZIPs ===")
        rc = zips.run(source_branch, repository, build_meta_dir)
        if rc != 0:
            return rc
        actions.log("\n=== Cleaning up old releases ===")
        cleanup.run(repository, MAX_VERSIONED_ZIPS)
        actions.log("\n=== Generating manifests ===")
        manifest.generate(source_branch, RELEASES_BRANCH, repository, build_meta_dir)
        actions.log("\n=== Generating per-plugin READMEs ===")
        readmes.generate_plugin_readmes(source_branch, repository)
        actions.log("\n=== Generating releases README ===")
        readmes.generate_releases_readme(source_branch, RELEASES_BRANCH, repository)

        return _commit_and_push(repository, source_branch, remote)
    finally:
        os.chdir(start_cwd)
        subprocess.run(["rm", "-rf", workdir, build_meta_dir], check=False)


def _setup_releases_branch(repository, source_branch, token, remote,
                           force_rebuild, force_plugin) -> None:
    from ..core import gh
    branch_exists = _git("ls-remote", "--exit-code", "--heads", "origin",
                         RELEASES_BRANCH, check=False).returncode == 0

    if force_rebuild and force_plugin:
        if branch_exists:
            _git("checkout", RELEASES_BRANCH)
            _git("pull", "origin", RELEASES_BRANCH, check=False)
        else:
            _orphan_init()
        actions.log(f"Targeted force rebuild: deleting GitHub Releases for {force_plugin}")
        for tag in gh.release_list_tags(repository):
            if tag.startswith(f"{force_plugin}-"):
                gh.release_delete(tag, repository)
        mf = f"metadata/{force_plugin}/manifest.json"
        if os.path.exists(mf):
            os.remove(mf)
    elif force_rebuild:
        actions.log(f"Force rebuild requested - deleting all plugin GitHub Releases and resetting {RELEASES_BRANCH}.")
        _git("fetch", "origin", source_branch, check=False)
        _git("checkout", f"origin/{source_branch}", "--", "plugins", check=False)
        if os.path.isdir("plugins"):
            import glob
            for plugin_dir in glob.glob("plugins/*/"):
                pname = os.path.basename(plugin_dir.rstrip("/"))
                for tag in gh.release_list_tags(repository):
                    if tag.startswith(f"{pname}-"):
                        gh.release_delete(tag, repository)
            subprocess.run(["rm", "-rf", "plugins"], check=False)
        _git("checkout", "--orphan", RELEASES_BRANCH)
        _git("rm", "-rf", ".", check=False)
        _git("commit", "--allow-empty", "-m", f"Initialize {RELEASES_BRANCH} branch (force rebuild)")
        _git("push", "--force", remote, RELEASES_BRANCH)
    elif branch_exists:
        _git("checkout", RELEASES_BRANCH)
        _git("pull", "origin", RELEASES_BRANCH, check=False)
    else:
        _orphan_init()


def _orphan_init() -> None:
    _git("checkout", "--orphan", RELEASES_BRANCH)
    _git("rm", "-rf", ".", check=False)
    _git("commit", "--allow-empty", "-m", f"Initialize {RELEASES_BRANCH} branch")


def _commit_and_push(repository, source_branch, remote) -> int:
    actions.log("\n=== Committing ===")
    subprocess.run(["rm", "-rf", "plugins"], check=False)
    _git("rm", "-rf", "--cached", "plugins", check=False)
    with open("REPO_VER", "w", encoding="utf-8") as fh:
        fh.write(RELEASES_BRANCH_VERSION + "\n")
    _git("add", "metadata", "manifest.json", "README.md", "REPO_VER")

    if _git("diff", "--cached", "--quiet", check=False).returncode == 0:
        actions.log("No changes to commit.")
        return 0

    if _only_timestamps():
        actions.log("No meaningful changes (only timestamps updated) - skipping commit.")
        return 0

    source_commit = _git("rev-parse", "--short", f"origin/{source_branch}").stdout.strip()
    plugin_list = ""
    changed = _read("changed_plugins.txt")
    if changed.strip():
        plugin_list = "\n\n" + "\n".join(f"- {line}" for line in changed.splitlines() if line)
    _git("commit", "-m", f"Publish plugin updates from {source_branch}\n\n"
         f"Source commit: {source_commit}{plugin_list}")
    _git("push", remote, RELEASES_BRANCH)
    actions.log(f"Successfully published to {RELEASES_BRANCH}")
    _emit_published(repository, changed)
    return 0


def _emit_published(repository: str, changed: str) -> None:
    """Emit one plugin.published event per changed plugin (best-effort)."""
    from ..integrations import webhooks
    actor = os.environ.get("GITHUB_ACTOR", "")
    for line in changed.splitlines():
        if "@" not in line:
            continue
        plugin_key, _, version = line.partition("@")
        webhooks.emit("plugin.published",
                      webhooks.plugin_published(plugin_key.replace("_", "-"), version, None, actor))


def _only_timestamps() -> bool:
    """True when the staged diff is only README timestamp / manifest generated_at noise."""
    names = _git("diff", "--cached", "--name-only").stdout.splitlines()
    for changed_file in names:
        if changed_file == "README.md":
            if _strip_lines(":README.md", "*Last updated:") != \
               _strip_lines("HEAD:README.md", "*Last updated:"):
                return False
        elif changed_file == "manifest.json":
            if _strip_lines(":manifest.json", '"generated_at"') != \
               _strip_lines("HEAD:manifest.json", '"generated_at"'):
                return False
        else:
            return False
    return True


def _strip_lines(ref: str, needle: str) -> str:
    out = _git("show", ref, check=False).stdout
    return "\n".join(ln for ln in out.splitlines() if needle not in ln)


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""
