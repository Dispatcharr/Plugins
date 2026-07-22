"""``pluginctl validate``: port of validate/validate.sh.

Validates one plugin and writes a markdown report fragment identical to the Bash
output: same ``### Plugin:`` header, description/repo subtext, the
``| Check | Status | Details |`` table (rows hidden when they pass, in the same
order), the optional release/compare links, and the trailing ``<!--META_ROW:...-->``
tab-separated marker consumed by ``report``. Emits ``result``/``is_new``/
``has_permission`` outputs and exits non-zero on failure.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Optional

from ..core import actions, gh, git
from ..core.version import is_semver, is_dispatcharr_version, version_greater_than

METADATA_ONLY_FIELDS = [
    "description", "repo_url", "discord_thread", "min_dispatcharr_version",
    "max_dispatcharr_version", "deprecated", "unlisted", "maintainers",
]

_GH_DOWNLOAD_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/")
_GH_DOWNLOAD_TAG_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+/releases/download/([^/]+)/")

SPDX_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"


# ---- jq-parity scalar helpers ------------------------------------------------
def jq_r(value, default: Optional[str] = None) -> str:
    """Mimic ``jq -r``. Without a default, null/missing renders as ``"null"``.

    With ``default`` (the ``// "x"`` idiom), null/missing renders as ``default``.
    """
    if value is None:
        return "null" if default is None else default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def field_present(raw: dict, key: str) -> bool:
    """Reproduce ``jq -e '.\"key\"'``: present unless null or false."""
    val = raw.get(key, None)
    return not (val is None or val is False)


def tsv(fields: list[str]) -> str:
    """Reproduce ``@tsv`` escaping for a single row."""
    def esc(s: str) -> str:
        return (s.replace("\\", "\\\\").replace("\t", "\\t")
                 .replace("\n", "\\n").replace("\r", "\\r"))
    return "\t".join(esc(f) for f in fields)


# ---- network (injectable for tests) -----------------------------------------
def http_status(url: str) -> str:
    """Follow redirects, return the numeric HTTP status as a string ("000" on error)."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return str(getattr(resp, "status", None) or resp.getcode())
    except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
        return str(exc.code)
    except Exception:
        return "000"


def fetch_spdx() -> Optional[dict]:
    try:
        with urllib.request.urlopen(SPDX_URL, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


# ---- helper: source file count (non-external) -------------------------------
def count_source_files(plugin_dir: str) -> int:
    ignore = {"plugin.json", "README.md", "logo.png"}
    count = 0
    for root, _dirs, files in os.walk(plugin_dir):
        for fn in files:
            if fn not in ignore:
                count += 1
    return count


def run(plugin_name: str, pr_author: str, base_ref: str, output_file: str,
        repo: str = "") -> int:
    owner, _, name = repo.partition("/")
    plugin_dir = f"plugins/{plugin_name}"
    plugin_json_path = f"{plugin_dir}/plugin.json"

    failed = False
    is_new = False
    has_permission = False
    rows: list[str] = []
    pre_lines: list[str] = []      # header + desc/repo subtext
    post_lines: list[str] = []     # release/compare link
    meta_row: Optional[str] = None

    pre_lines.append(f"### Plugin: `{plugin_name}`")
    pre_lines.append("")

    raw: Optional[dict] = None
    if os.path.isfile(plugin_json_path):
        try:
            with open(plugin_json_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            raw = None
        if raw is not None:
            desc = jq_r(raw.get("description"), "")
            repo_url = jq_r(raw.get("repo_url"), "")
            if desc:
                pre_lines.append(f"_{desc}_")
                pre_lines.append("")
            if repo_url:
                pre_lines.append(f"[Source Repository]({repo_url})")
                pre_lines.append("")

    def emit_fragment() -> None:
        lines = list(pre_lines)
        lines.append("| Check | Status | Details |")
        lines.append("|-------|:------:|---------|")
        lines.extend(rows)
        lines.append("")
        lines.extend(post_lines)
        if meta_row is not None:
            lines.append(meta_row)
        text = "\n".join(lines) + "\n"
        _write(output_file, text)

    # Folder name format
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", plugin_name):
        rows.append(f"| Folder name | ❌ | Must be lowercase-kebab-case - got "
                    f"`{plugin_name}`, e.g. `my-plugin-name` |")
        failed = True

    # plugin.json existence (early exit)
    if not os.path.isfile(plugin_json_path):
        rows.append("| `plugin.json` | ❌ | File missing |")
        emit_fragment()
        actions.set_outputs(result="fail", is_new="false", has_permission="false")
        return 0

    # JSON syntax (early exit)
    if raw is None:
        rows.append("| JSON syntax | ❌ | Invalid JSON in plugin.json |")
        emit_fragment()
        actions.set_outputs(result="fail", is_new="false", has_permission="false")
        return 0

    # Required fields
    missing = [f"`{key}`" for key in ("name", "version", "description")
               if not field_present(raw, key)]
    if missing:
        failed = True
        rows.append(f"| Required fields | ❌ | Missing: {', '.join(missing)} |")
    else:
        rows.append("| Required fields | ✅ | All required fields present |")

    author = jq_r(raw.get("author"), "")
    maintainers = [str(m) for m in (raw.get("maintainers") or []) if m is not None]
    maintainers_sp = " ".join(maintainers)
    version = jq_r(raw.get("version"))

    # Base branch plugin.json (for version bump + compare link)
    base_json_text = git.show(f"origin/{base_ref}:{plugin_json_path}")
    base_raw = None
    old_version = ""
    old_source_url_tmpl = ""
    if base_json_text is not None:
        try:
            base_raw = json.loads(base_json_text)
            old_version = jq_r(base_raw.get("version"), "")
            old_source_url_tmpl = jq_r(base_raw.get("source_url"), "")
        except json.JSONDecodeError:
            base_raw = None

    # External source checks
    source_type = jq_r(raw.get("source_type"), "local")
    release_link = ""
    compare_link = ""
    gh_tag = ""
    old_gh_tag = ""
    if source_type != "external":
        if count_source_files(plugin_dir) == 0:
            rows.append(f"| Plugin files | ❌ | No source files found in "
                        f"`plugins/{plugin_name}/`. Add your plugin source (e.g. `main.py`) "
                        f"or set `\"source_type\": \"external\"` in `plugin.json` if your plugin "
                        f"is hosted elsewhere |")
            failed = True
    else:
        ext_source_url = jq_r(raw.get("source_url"), "")
        ext_repo_url = jq_r(raw.get("repo_url"), "")
        if not ext_source_url:
            rows.append("| `source_url` | ❌ | Required when `source_type` is `external` |")
            failed = True
        elif not ext_source_url.startswith("https://"):
            rows.append("| `source_url` | ❌ | Must be an HTTPS URL |")
            failed = True
        elif "{version}" not in ext_source_url:
            rows.append("| `source_url` | ❌ | Must contain a `{version}` placeholder "
                        "(e.g. `.../v{version}/plugin.zip`) |")
            failed = True
        else:
            if is_semver(version):
                resolved_url = ext_source_url.replace("{version}", version)
                code = http_status(resolved_url)
                if code == "200":
                    rows.append("| Release artifact | ✅ | Artifact reachable at resolved URL |")
                    m = _GH_DOWNLOAD_RE.match(resolved_url)
                    if m:
                        gh_owner, gh_repo, gh_tag = m.group(1), m.group(2), m.group(3)
                        release_link = f"https://github.com/{gh_owner}/{gh_repo}/releases/tag/{gh_tag}"
                        if old_version and old_source_url_tmpl:
                            old_resolved = old_source_url_tmpl.replace("{version}", old_version)
                            om = _GH_DOWNLOAD_TAG_RE.match(old_resolved)
                            if om:
                                old_gh_tag = om.group(1)
                                compare_link = (f"https://github.com/{gh_owner}/{gh_repo}"
                                                f"/compare/{old_gh_tag}...{gh_tag}")
                else:
                    rows.append(f"| Release artifact | ❌ | Could not reach `{resolved_url}` "
                                f"(HTTP `{code}`) — ensure the release exists |")
                    failed = True
        if not ext_repo_url:
            rows.append("| `repo_url` | ❌ | Required for external plugins — set to the upstream "
                        "source repository URL |")
            failed = True

    # Maintainers
    if not author and not maintainers_sp:
        rows.append("| Maintainers | ❌ | At least one of `author` or `maintainers` must "
                    "include your GitHub username |")
        failed = True
    else:
        parts = []
        if author:
            parts.append(f"`{author}`")
        for m in maintainers_sp.split():
            parts.append(f"`{m}`")
        rows.append(f"| Maintainers | ✅ | {', '.join(parts)} |")

    # License
    license_id = jq_r(raw.get("license"), "")
    if not license_id:
        rows.append("| License | ❌ | `license` is required - provide an "
                    "[OSI-approved SPDX identifier](https://spdx.org/licenses/) "
                    "(e.g. `MIT`, `Apache-2.0`) |")
        failed = True
    else:
        spdx = fetch_spdx()
        if spdx is None:
            rows.append("| License | ⚠️ | Could not fetch SPDX license list - skipping validation |")
        else:
            osi = {l["licenseId"]: l.get("name", "")
                   for l in spdx.get("licenses", []) if l.get("isOsiApproved") is True}
            if license_id in osi:
                rows.append(f"| License | ✅ | `{license_id}` - {osi[license_id]} |")
            else:
                rows.append(f"| License | ❌ | `{license_id}` is not an "
                            "[OSI-approved SPDX identifier](https://spdx.org/licenses/) |")
                failed = True

    # Permission
    is_repo_maintainer = bool(owner) and gh.has_write_access(owner, name, pr_author)
    if is_repo_maintainer:
        rows.append("| Permission | ✅ | You have permission to modify this plugin |")
        has_permission = True
    elif base_raw is not None:
        base_author = jq_r(base_raw.get("author"), "")
        base_maintainers = [str(m) for m in (base_raw.get("maintainers") or []) if m is not None]
        if pr_author == base_author or pr_author in base_maintainers:
            rows.append("| Permission | ✅ | You have permission to modify this plugin |")
            has_permission = True
        else:
            rows.append(f"| Permission | ❌ | `{pr_author}` is not listed in `author` or `maintainers` |")
            failed = True
    else:
        if pr_author == author or pr_author in maintainers:
            rows.append(f"| Permission | ✅ | New plugin - `{pr_author}` listed in `author`/`maintainers` |")
            has_permission = True
        else:
            rows.append(f"| Permission | ❌ | Add `\"author\": \"{pr_author}\"` to plugin.json |")
            failed = True

    # Version format
    if is_semver(version):
        rows.append(f"| Version | ✅ | `{version}` |")
    else:
        rows.append(f"| Version | ❌ | `{version}` is not valid semver - expected `X.Y.Z` |")
        failed = True

    # Version bump
    if base_raw is not None:
        if version_greater_than(version, old_version):
            rows.append(f"| Version bump | ✅ | `{old_version}` → `{version}` |")
        else:
            changed_fields = _changed_fields(base_raw, raw)
            metadata_only = all(f in METADATA_ONLY_FIELDS for f in changed_fields)
            if metadata_only and changed_fields:
                rows.append(f"| Version bump | ✅ | `{old_version}` (unchanged - metadata-only update) |")
            else:
                other_changed = ""
                if not changed_fields:
                    others = git.diff_name_only_range(f"origin/{base_ref}...HEAD", [plugin_dir])
                    others = [f for f in others if f != plugin_json_path]
                    other_changed = others[0] if others else ""
                if not changed_fields and not other_changed:
                    rows.append("| Version bump | ❌ | No changes detected - nothing to publish |")
                else:
                    rows.append(f"| Version bump | ❌ | `{version}` must be greater than current `{old_version}` |")
                failed = True
    else:
        rows.append("| Version bump | ✅ | New plugin |")
        is_new = True

    # Dispatcharr version constraints
    min_da = jq_r(raw.get("min_dispatcharr_version"), "")
    max_da = jq_r(raw.get("max_dispatcharr_version"), "")
    if min_da and not is_dispatcharr_version(min_da):
        rows.append(f"| `min_dispatcharr_version` | ❌ | `{min_da}` is not valid semver - "
                    "expected `X.Y.Z` or `vX.Y.Z` |")
        failed = True
    if max_da and not is_dispatcharr_version(max_da):
        rows.append(f"| `max_dispatcharr_version` | ❌ | `{max_da}` is not valid semver - "
                    "expected `X.Y.Z` or `vX.Y.Z` |")
        failed = True
    if min_da and max_da and is_dispatcharr_version(max_da) and is_dispatcharr_version(min_da):
        _max = max_da[1:] if max_da.startswith("v") else max_da
        _min = min_da[1:] if min_da.startswith("v") else min_da
        if not version_greater_than(_max, _min) and _max != _min:
            rows.append(f"| Version range | ❌ | `max_dispatcharr_version` (`{max_da}`) must be ≥ "
                        f"`min_dispatcharr_version` (`{min_da}`) |")
            failed = True

    # Optional link fields
    repo_url = jq_r(raw.get("repo_url"), "")
    discord_thread = jq_r(raw.get("discord_thread"), "")
    if repo_url and not re.match(r"^https?://", repo_url):
        rows.append("| `repo_url` | ❌ | Must start with `http://` or `https://` |")
        failed = True
    if discord_thread and not re.match(r"^https?://", discord_thread):
        rows.append("| `discord_thread` | ❌ | Must start with `http://` or `https://` |")
        failed = True

    # Release / compare links (after the table)
    if release_link:
        link_line = f"[View release {gh_tag} on GitHub]({release_link})"
        if compare_link:
            link_line += f" · [Compare {old_gh_tag}...{gh_tag}]({compare_link})"
        post_lines.append(link_line)
        post_lines.append("")

    # Meta row
    meta_fields = [
        jq_r(raw.get("name"), ""),
        jq_r(raw.get("version"), ""),
        jq_r(raw.get("description"), ""),
        jq_r(raw.get("author"), ""),
        ", ".join(maintainers),
        jq_r(raw.get("repo_url"), ""),
        jq_r(raw.get("discord_thread"), ""),
    ]
    meta_row = f"<!--META_ROW:{tsv(meta_fields)}-->"

    emit_fragment()
    actions.set_outputs(
        result="pass" if not failed else "fail",
        is_new="true" if is_new else "false",
        has_permission="true" if has_permission else "false",
    )
    return 1 if failed else 0


def _changed_fields(old: dict, new: dict) -> list[str]:
    """Keys of NEW whose value differs from OLD (missing old -> null), sorted like jq keys."""
    changed = [k for k in new.keys() if old.get(k) != new[k]]
    return sorted(changed)


def _write(path: str, text: str) -> None:
    if path in ("/dev/stdout", "-"):
        print(text, end="")
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
