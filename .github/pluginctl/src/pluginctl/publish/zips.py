"""Build versioned ZIPs + GitHub Releases (port of build-zips.sh).

Runs from the releases-branch checkout directory. For every plugin whose current
version has no GitHub Release yet, it builds (or downloads, for external plugins)
the ZIP, records per-version metadata under ``BUILD_META_DIR`` for
generate-manifest to consume, uploads the release, and appends the plugin to
``changed_plugins.txt``.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from typing import Optional

from ..core import actions, gh, git, jsonio
from ..core.hashing import file_digests
from ..core.jsonio import drop_none
from ..core.timeutil import now_iso
from ..validate.detect import is_safe_name


def _download(url: str, dest: str, attempts: int = 3) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
                shutil.copyfileobj(resp, out)
            return True
        except Exception:
            if os.path.exists(dest):
                os.remove(dest)
            if attempt < attempts:
                actions.log(f"  Download attempt {attempt} failed, retrying in 15s...")
                time.sleep(15)
    return False


def _commit_info(source_branch: str, plugin_dir: str) -> tuple[str, str, str]:
    """(commit_sha, commit_sha_short, commit_date) of the last commit touching the plugin."""
    out = git.log_format("%H%n%h%n%cI", f"origin/{source_branch}", plugin_dir)
    if not out:
        return "", "", ""
    fields = out.splitlines()
    fields += [""] * (3 - len(fields))
    return fields[0], fields[1], fields[2]


def run(source_branch: str, repository: str, build_meta_dir: str) -> int:
    changed: list[str] = []
    open("changed_plugins.txt", "w", encoding="utf-8").close()

    for plugin_dir in sorted(glob.glob("plugins/*/")):
        plugin_name = os.path.basename(plugin_dir.rstrip("/"))
        if not is_safe_name(plugin_name):
            actions.warning(f"Skipping publish for unsafe plugin folder name: '{plugin_name}'")
            continue
        plugin_key = plugin_name.replace("-", "_")
        with open(os.path.join(plugin_dir, "plugin.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        version = str(raw.get("version"))
        os.makedirs(f"metadata/{plugin_name}", exist_ok=True)

        zip_path = f"/tmp/{plugin_name}-{version}.zip"
        release_tag = f"{plugin_name}-{version}"

        if gh.release_exists(release_tag, repository):
            actions.log(f"  {plugin_name} v{version} - skipping (release already exists)")
            continue

        source_type = raw.get("source_type") or "local"
        build_timestamp = now_iso()
        commit_sha, commit_sha_short, commit_date = _commit_info(source_branch, plugin_dir)
        last_updated = commit_date or now_iso()
        source_url_resolved = ""

        if source_type == "external":
            source_url_resolved = str(raw.get("source_url") or "").replace("{version}", version)
            actions.log(f"  {plugin_name} v{version} - fetching external ZIP from {source_url_resolved}")
            changed.append(f"{plugin_key}@{version}")
            if not _download(source_url_resolved, zip_path):
                actions.error(f"Failed to download external ZIP from {source_url_resolved} after 3 attempts")
                return 1
        else:
            actions.log(f"  {plugin_name} v{version} - building")
            changed.append(f"{plugin_key}@{version}")
            with tempfile.TemporaryDirectory() as tmpdir:
                shutil.copytree(f"plugins/{plugin_name}", os.path.join(tmpdir, plugin_key))
                subprocess.run(["zip", "-r", zip_path, plugin_key], cwd=tmpdir,
                               check=True, stdout=subprocess.DEVNULL)

        checksum_md5, checksum_sha256 = file_digests(zip_path, "md5", "sha256")
        min_da = str(raw.get("min_dispatcharr_version") or "")
        max_da = str(raw.get("max_dispatcharr_version") or "")
        zip_size_kb = os.path.getsize(zip_path) // 1024

        meta = drop_none({
            "version": version,
            "commit_sha": commit_sha or None,
            "commit_sha_short": commit_sha_short or None,
            "build_timestamp": build_timestamp,
            "last_updated": last_updated,
            "checksum_md5": checksum_md5,
            "checksum_sha256": checksum_sha256,
            "min_dispatcharr_version": min_da or None,
            "max_dispatcharr_version": max_da or None,
            "source_url": source_url_resolved or None,
            "size_kb": zip_size_kb,
        })
        os.makedirs(os.path.join(build_meta_dir, plugin_key), exist_ok=True)
        with open(os.path.join(build_meta_dir, plugin_key, f"{plugin_key}-{version}.json"),
                  "w", encoding="utf-8") as fh:
            fh.write(jsonio.dumps(meta))

        notes = _release_notes(repository, plugin_name, commit_sha, commit_sha_short)
        actions.log(f"  {plugin_name} v{version} - uploading to GitHub Releases")
        gh.release_create(release_tag, repository, f"{plugin_name} v{version}", notes, zip_path)
        os.remove(zip_path)

    with open("changed_plugins.txt", "w", encoding="utf-8") as fh:
        for line in changed:
            fh.write(line + "\n")
    actions.log(f"Built {len(changed)} new/updated plugin(s).")
    return 0


def _release_notes(repository: str, plugin_name: str, commit_sha: str,
                   commit_sha_short: str) -> str:
    readme_url = f"https://github.com/{repository}/blob/releases/metadata/{plugin_name}/README.md"
    notes = ""
    if commit_sha:
        commit_url = f"https://github.com/{repository}/commit/{commit_sha}"
        notes = f"**Commit:** [`{commit_sha_short}`]({commit_url})"
        pr_number, pr_url = gh.commit_pull_number(repository, commit_sha)
        if pr_number:
            notes += f"\n**PR:** [#{pr_number}]({pr_url})"
        notes += "\n"
    notes += f"**README:** [Plugin README]({readme_url})"
    return notes
