"""Per-plugin and root READMEs for the releases branch.

Ports plugin-readmes.sh and releases-readme.sh. Output is kept identical to the
Bash except for one intentional correction, called out in the plan: the
deprecated-plugin "All Versions" count now comes from the per-plugin manifest's
``versions[]`` (same source the active section uses) instead of the removed
``zips/<plugin>/*.zip`` path, which always rendered 0.
"""

from __future__ import annotations

import datetime
import glob
import json
import os
import re
from typing import Optional

from ..core import git
from ..core.timeutil import now_iso


def fmt_date(value: str) -> str:
    """ISO8601 -> "Mon DD YYYY, HH:MM UTC"; returns the input unchanged on failure."""
    if not value:
        return value
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.strftime("%b %d %Y, %H:%M UTC")
    except ValueError:
        return value


def shields_encode(s: str) -> str:
    """shields.io path escaping: _ -> __, - -> --, space -> _ (order matters)."""
    s = s.replace("_", "__")
    s = s.replace("-", "--")
    s = s.replace(" ", "_")
    return s


def _load_json(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _g(data: Optional[dict], key: str, default: str = "") -> str:
    if not data:
        return default
    val = data.get(key)
    return default if val is None else str(val)


# --------------------------------------------------------------------------- #
# Per-plugin README (metadata/<plugin>/README.md)
# --------------------------------------------------------------------------- #
def render_plugin_readme(plugin_name: str, plugin_raw: dict, manifest: dict,
                         root_url: str, repository: str, source_branch: str,
                         last_updated: str, has_readme: bool,
                         source_readme: str = "") -> str:
    name = _g(plugin_raw, "name")
    description = _g(plugin_raw, "description")
    author = _g(plugin_raw, "author")
    maintainers = ", ".join(str(m) for m in (plugin_raw.get("maintainers") or []))
    repo_url = _g(plugin_raw, "repo_url")
    discord_thread = _g(plugin_raw, "discord_thread")
    license_id = _g(plugin_raw, "license")
    min_da = _g(plugin_raw, "min_dispatcharr_version")
    max_da = _g(plugin_raw, "max_dispatcharr_version")
    version = _g(plugin_raw, "version")

    manifest_body = manifest.get("manifest", {}) if manifest else {}
    latest = manifest_body.get("latest") or {}
    latest_url_path = latest.get("latest_url") or ""
    latest_full_url = f"{root_url}/{latest_url_path}" if root_url and latest_url_path else ""

    L: list[str] = []
    L.append("[Back to All Plugins](../../README.md)")
    L.append("")
    L.append(f"# {name}")
    L.append("")
    L.append(f"**Version:** `{version}` | **Author:** {author} | **Last Updated:** {fmt_date(last_updated)}")
    L.append("")
    L.append(description)
    L.append("")

    badges = _badges(license_id, discord_thread, repo_url)
    if badges:
        L.append(badges)
        L.append("")
    compat = _compat_badges(min_da, max_da)
    if compat:
        L.append(compat)
        L.append("")

    L.append("## Downloads")
    L.append("")
    L.append("### Latest Release")
    L.append("")
    if latest_full_url:
        L.append(f"- **Download:** [`{plugin_name}-latest.zip`]({latest_full_url})")
        build_ts = latest.get("build_timestamp") or ""
        commit_sha = latest.get("commit_sha") or ""
        commit_short = latest.get("commit_sha_short") or ""
        md5 = latest.get("checksum_md5") or ""
        sha256 = latest.get("checksum_sha256") or ""
        if build_ts:
            L.append(f"- **Built:** {fmt_date(build_ts)}")
        if commit_sha:
            L.append(f"- **Source Commit:** [`{commit_short}`](https://github.com/{repository}/commit/{commit_sha})")
        if md5 or sha256:
            L.append("")
            L.append("**Checksums:**")
            L.append("```")
            if md5:
                L.append(f"MD5:    {md5}")
            if sha256:
                L.append(f"SHA256: {sha256}")
            L.append("```")

    L.append("")
    L.append("### All Versions")
    L.append("")
    L.append("| Version | Download | Built | Commit | MD5 | SHA256 |")
    L.append("|---------|----------|-------|--------|-----|--------|")
    for ver in (manifest_body.get("versions") or []):
        v = ver.get("version") or ""
        if not v:
            continue
        url_path = ver.get("url") or ""
        full_url = f"{root_url}/{url_path}" if root_url and url_path else ""
        commit_sha = ver.get("commit_sha") or ""
        commit_short = ver.get("commit_sha_short") or ""
        build_ts = ver.get("build_timestamp") or ""
        md5 = ver.get("checksum_md5") or ""
        sha256 = ver.get("checksum_sha256") or ""
        build_date = fmt_date(build_ts)
        commit_cell = f"[`{commit_short}`](https://github.com/{repository}/commit/{commit_sha})" if commit_sha else "-"
        download_cell = f"[Download]({full_url})" if full_url else "-"
        L.append(f"| `{v}` | {download_cell} | {build_date or '-'} | {commit_cell} | {md5 or '-'} | {sha256 or '-'} |")

    L.append("")
    L.append("---")
    L.append("")
    footer = ""
    if maintainers:
        footer = f"**Maintainers:** {maintainers} | "
    footer += (f"**Source:** [Browse Plugin]"
               f"(https://github.com/{repository}/tree/{source_branch}/plugins/{plugin_name})")
    L.append(footer)
    L.append("")
    L.append("**Metadata:** [View full manifest](./manifest.json)")

    if has_readme:
        L.append("")
        L.append("---")
        L.append("")
        L.append("## Plugin README")
        L.append("")
        L.append(source_readme.rstrip("\n"))

    return "\n".join(L) + "\n"


def _badges(license_id: str, discord_thread: str, repo_url: str) -> str:
    badges: list[str] = []
    if license_id:
        badges.append(f"[![License: {license_id}]"
                      f"(https://img.shields.io/badge/License-{shields_encode(license_id)}-blue?style=flat-square)]"
                      f"(https://spdx.org/licenses/{license_id}.html)")
    if discord_thread:
        badges.append("[![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)]"
                      f"({discord_thread})")
    if repo_url:
        badges.append("[![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)]"
                      f"({repo_url})")
    return " ".join(badges)


def _compat_badges(min_da: str, max_da: str) -> str:
    if not (min_da or max_da):
        return ""
    out = ""
    if min_da:
        out = f"![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-{shields_encode(min_da)}-brightgreen?style=flat-square)"
    if max_da:
        if out:
            out += " "
        out += f"![Dispatcharr max](https://img.shields.io/badge/Dispatcharr_max-{shields_encode(max_da)}-orange?style=flat-square)"
    return out


def version_count_from_manifest(manifest_file: str) -> int:
    """Deprecated-plugin fix: derive count from the manifest's versions[] (was ls zips/)."""
    data = _load_json(manifest_file)
    if not data:
        return 0
    versions = (data.get("manifest") or {}).get("versions")
    return len(versions) if isinstance(versions, list) else 0


# --------------------------------------------------------------------------- #
# Root releases README (README.md on the releases branch)
# --------------------------------------------------------------------------- #
def anchor_for(name: str) -> str:
    """GitHub-style heading anchor: lowercase, non [a-z0-9-] -> -, collapse runs."""
    a = name.lower()
    a = re.sub(r"[^a-z0-9-]", "-", a)
    a = re.sub(r"-+", "-", a)
    return a


def table_row(plugin_raw: dict, deprecated_pass: bool) -> str:
    name = _g(plugin_raw, "name")
    version = _g(plugin_raw, "version")
    author = _g(plugin_raw, "author")
    description = _g(plugin_raw, "description")
    license_cell = _g(plugin_raw, "license", "-") or "-"
    suffix = " (deprecated)" if deprecated_pass else ""
    return f"| [`{name}`](#{anchor_for(name)}){suffix} | `{version}` | {author} | {license_cell} | {description} |"


def render_plugin_block(*, is_deprecated: bool, plugin_name: str, plugin_raw: dict,
                        manifest: Optional[dict], last_updated: str, commit_sha: str,
                        commit_sha_short: str, version_count, repository: str,
                        source_branch: str, releases_branch: str, root_url: str,
                        has_source_readme: bool) -> str:
    name = _g(plugin_raw, "name")
    version = _g(plugin_raw, "version")
    author = _g(plugin_raw, "author")
    description = _g(plugin_raw, "description")
    maintainers = ", ".join(str(m) for m in (plugin_raw.get("maintainers") or []))
    license_id = _g(plugin_raw, "license")
    min_da = _g(plugin_raw, "min_dispatcharr_version")
    max_da = _g(plugin_raw, "max_dispatcharr_version")
    repo_url = _g(plugin_raw, "repo_url")
    discord_thread = _g(plugin_raw, "discord_thread")

    latest_url_path = ""
    if manifest:
        latest_url_path = ((manifest.get("manifest") or {}).get("latest") or {}).get("latest_url") or ""
    zip_url = f"{root_url}/{latest_url_path}" if root_url and latest_url_path else ""

    source_url = f"https://github.com/{repository}/tree/{source_branch}/plugins/{plugin_name}"
    readme_url = f"https://github.com/{repository}/blob/{source_branch}/plugins/{plugin_name}/README.md"
    releases_readme_url = f"https://github.com/{repository}/blob/{releases_branch}/metadata/{plugin_name}/README.md"
    commit_url = f"https://github.com/{repository}/commit/{commit_sha}"
    releases_dir = f"./metadata/{plugin_name}"

    suffix = " (deprecated)" if is_deprecated else ""

    L: list[str] = []
    L.append(f"### [{name}]({releases_readme_url}){suffix}")
    L.append("")
    L.append(f"**Version:** `{version}` | **Author:** {author} | **Last Updated:** {fmt_date(last_updated)}")
    L.append("")
    L.append(description)
    L.append("")
    badges = _badges(license_id, discord_thread, repo_url)
    if badges:
        L.append(badges)
        L.append("")
    compat = _compat_badges(min_da, max_da)
    if compat:
        L.append(compat)
        L.append("")
    L.append("**Downloads:**")
    if zip_url:
        L.append(f"- [Latest Release (`{version}`)]({zip_url})")
    L.append(f"- [All Versions ({version_count} available)]({releases_dir})")
    L.append("")
    footer = ""
    if maintainers:
        footer = f"**Maintainers:** {maintainers} | "
    footer += f"**Source:** [Browse]({source_url})"
    if has_source_readme:
        footer += f" | [README]({readme_url})"
    footer += f" | **Last Change:** [`{commit_sha_short}`]({commit_url})"
    L.append(footer)
    L.append("")
    L.append("---")
    L.append("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# Orchestrators (IO): called from the releases-branch checkout directory
# --------------------------------------------------------------------------- #
def _plugin_commit(source_branch: str, plugin_dir: str) -> tuple[str, str, str]:
    """(last_updated, commit_sha, commit_sha_short) of the plugin's last commit.

    One ``git log`` call for all three fields; empty strings when there is none.
    """
    out = git.log_format("%cI%n%H%n%h", f"origin/{source_branch}", plugin_dir)
    if not out:
        return "", "", ""
    fields = out.splitlines()
    fields += [""] * (3 - len(fields))
    return fields[0], fields[1], fields[2]


def _plugin_last_updated(source_branch: str, plugin_dir: str) -> str:
    return _plugin_commit(source_branch, plugin_dir)[0] or now_iso()


def generate_plugin_readmes(source_branch: str, repository: str) -> None:
    """Write metadata/<plugin>/README.md for every plugin (plugin-readmes.sh)."""
    root = _load_json("manifest.json") or {}
    root_url = (root.get("manifest") or {}).get("root_url") or ""
    for plugin_dir in sorted(glob.glob("plugins/*/")):
        plugin_name = os.path.basename(plugin_dir.rstrip("/"))
        plugin_file = os.path.join(plugin_dir, "plugin.json")
        plugin_raw = _load_json(plugin_file)
        if plugin_raw is None:
            continue
        manifest_file = f"metadata/{plugin_name}/manifest.json"
        manifest = _load_json(manifest_file)
        if manifest is None:
            continue
        last_updated = _plugin_last_updated(source_branch, plugin_dir)
        source_readme_path = os.path.join(plugin_dir, "README.md")
        has_readme = os.path.isfile(source_readme_path)
        source_readme = _read(source_readme_path) if has_readme else ""
        content = render_plugin_readme(
            plugin_name, plugin_raw, manifest, root_url, repository, source_branch,
            last_updated, has_readme, source_readme)
        with open(f"metadata/{plugin_name}/README.md", "w", encoding="utf-8") as fh:
            fh.write(content)


def generate_releases_readme(source_branch: str, releases_branch: str, repository: str) -> None:
    """Write the root README.md (releases-readme.sh)."""
    root = _load_json("manifest.json") or {}
    root_url = (root.get("manifest") or {}).get("root_url") or ""

    raws: dict[str, dict] = {}
    has_deprecated = False
    for pd in sorted(glob.glob("plugins/*/")):
        pname = os.path.basename(pd.rstrip("/"))
        raw = _load_json(os.path.join(pd, "plugin.json"))
        if raw is None:
            continue
        raws[pname] = raw
        if raw.get("deprecated") is True:
            has_deprecated = True

    L: list[str] = []
    L.append("# Plugin Releases")
    L.append("")
    L.append("This branch contains all published plugin releases.")
    L.append("")
    L.append("## Quick Access")
    L.append("")
    L.append("- [manifest.json](./manifest.json) - Complete plugin registry with metadata")
    L.append("- [metadata/](./metadata/) - Per-plugin manifests and READMEs")
    L.append("")
    L.append("## Available Plugins")
    L.append("")
    L.append("| Plugin | Version | Author | License | Description |")
    L.append("|--------|---------|-------|---------|-------------|")

    for deprecated_pass in (False, True):
        for raw in raws.values():
            if raw.get("unlisted") is True:
                continue
            if (raw.get("deprecated") is True) is not deprecated_pass:
                continue
            L.append(table_row(raw, deprecated_pass))

    L.append("")
    L.append("---")
    L.append("")

    def emit_block(pname: str, raw: dict, is_deprecated: bool) -> None:
        pd = f"plugins/{pname}/"
        manifest = _load_json(f"metadata/{pname}/manifest.json")
        last_updated, commit_sha, commit_short = _plugin_commit(source_branch, pd)
        last_updated = last_updated or now_iso()
        commit_sha = commit_sha or "unknown"
        commit_short = commit_short or "unknown"
        version_count = version_count_from_manifest(f"metadata/{pname}/manifest.json")
        has_source_readme = os.path.isfile(f"plugins/{pname}/README.md")
        L.append(render_plugin_block(
            is_deprecated=is_deprecated, plugin_name=pname, plugin_raw=raw,
            manifest=manifest, last_updated=last_updated, commit_sha=commit_sha,
            commit_sha_short=commit_short, version_count=version_count,
            repository=repository, source_branch=source_branch,
            releases_branch=releases_branch, root_url=root_url,
            has_source_readme=has_source_readme))

    # Active detailed sections
    for pname, raw in raws.items():
        if raw.get("deprecated") is True or raw.get("unlisted") is True:
            continue
        emit_block(pname, raw, False)

    if has_deprecated:
        L.append("")
        L.append("## Deprecated Plugins")
        L.append("")
        L.append("These plugins are deprecated and may be removed in the future.")
        L.append("")
        for pname, raw in raws.items():
            if raw.get("deprecated") is not True or raw.get("unlisted") is True:
                continue
            emit_block(pname, raw, True)

    L.append("## Using the Manifest")
    L.append("")
    L.append("Fetch `manifest.json` to programmatically access plugin metadata and download URLs:")
    L.append("")
    L.append("```bash")
    L.append(f"curl https://raw.githubusercontent.com/{repository}/{releases_branch}/manifest.json")
    L.append("```")
    L.append("")
    L.append("---")
    L.append("")
    L.append(f"*Last updated: {datetime.datetime.now(datetime.timezone.utc).strftime('%b %d %Y, %H:%M UTC')}*")

    with open("README.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""
