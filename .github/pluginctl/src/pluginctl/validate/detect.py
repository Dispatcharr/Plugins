"""``pluginctl detect``: port of validate/detect-changes.sh + inline blacklist.

Determines the changed-plugin matrix, whether the PR must be auto-closed, whether
it touches files outside ``plugins/`` without authorization, new/updated flags,
and the signing-key-changed warning. Emits the same ``$GITHUB_OUTPUT`` keys the
Bash script did so the downstream jobs are unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from ..core import actions, gh, git

SAFE_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PUB_KEY_PATH = ".github/scripts/keys/dispatcharr-plugins.pub"


def is_safe_name(name: str) -> bool:
    return bool(SAFE_NAME_RE.match(name))


def author_in_plugin_json(pr_author: str, data: dict) -> bool:
    """True when pr_author is the plugin's ``author`` or one of its ``maintainers``."""
    author = data.get("author") or ""
    maintainers = [str(m) for m in (data.get("maintainers") or []) if m is not None]
    return pr_author == author or pr_author in maintainers


def author_has_plugin_permission(pr_author: str, base_json_text: Optional[str]) -> bool:
    """True when pr_author is the base-branch author or in base maintainers.

    Reads from the base branch only, so a PR cannot self-grant permission.
    """
    if not base_json_text:
        return False
    try:
        data = json.loads(base_json_text)
    except json.JSONDecodeError:
        return False
    return author_in_plugin_json(pr_author, data)


@dataclass
class BlacklistResult:
    matched: bool = False
    reason: str = ""


def check_blacklists(pr_author: str, plugins: list[str],
                     author_blacklist: str, plugin_blacklist: str) -> BlacklistResult:
    """Case-insensitive author/plugin blacklist check (whitespace-trimmed entries)."""
    author_bl = (author_blacklist or "").strip()
    plugin_bl = (plugin_blacklist or "").strip()

    if author_bl and _csv_contains(pr_author, author_bl):
        actions.warning(f"PR author '{pr_author}' is on the author blacklist.")
        return BlacklistResult(True, "author-blacklisted")

    if plugin_bl:
        for plugin in plugins:
            if plugin and _csv_contains(plugin, plugin_bl):
                actions.warning(f"Plugin '{plugin}' is on the plugin blacklist.")
                return BlacklistResult(True, "plugin-blacklisted")
    return BlacklistResult()


def _csv_contains(value: str, csv: str) -> bool:
    """Case-insensitive membership in a comma-separated list (spaces stripped)."""
    return any(value.lower() == entry.replace(" ", "").lower() for entry in csv.split(","))


def run(pr_author: str, base_ref: str, head_ref: str = "",
        author_blacklist: str = "", plugin_blacklist: str = "",
        repo: str = "") -> int:
    """Execute detection; write outputs; return process exit code (0 ok, 1 hard block)."""
    owner, _, name = repo.partition("/")
    cached_write_access: Optional[bool] = None

    def write_access() -> bool:
        """``gh api`` permission lookup, resolved at most once per run."""
        nonlocal cached_write_access
        if cached_write_access is None:
            cached_write_access = gh.has_write_access(owner, name, pr_author)
        return cached_write_access

    # Bot-authored yank rollback PRs bypass plugin validation entirely.
    if pr_author.endswith("[bot]") and head_ref.startswith("yank/"):
        actions.log(f"Bot-authored yank rollback PR detected ({pr_author}, {head_ref}) "
                    "- skipping plugin validation.")
        actions.set_outputs(matrix="[]", plugin_count="0", close_pr="false",
                            close_reason="", skip_validation="true",
                            outside_violation="false", pub_key_changed="false",
                            has_new_plugin="false", has_updated_plugin="false")
        return 0

    merge_base = git.merge_base(f"origin/{base_ref}", "HEAD")
    changed = git.diff_name_only(merge_base, "HEAD")
    outside_changes = [f for f in changed if not f.startswith("plugins/")]
    has_outside_violation = bool(outside_changes) and not write_access()

    plugin_list = sorted({f.split("/")[1] for f in changed if f.startswith("plugins/") and len(f.split("/")) > 1})

    if not plugin_list:
        return _no_plugins(pr_author, outside_changes, has_outside_violation, write_access)

    # Allowlist: only safe kebab-case names enter the matrix. A folder with an
    # unsafe name is never scanned (ClamAV/CodeQL/publish all iterate the safe
    # matrix), so its presence must block the whole PR rather than being
    # silently dropped - otherwise it can ride along with a legitimate,
    # passing plugin change straight to `main` and publish unscanned.
    safe_list: list[str] = []
    unsafe_list: list[str] = []
    for plugin in plugin_list:
        if is_safe_name(plugin):
            safe_list.append(plugin)
        else:
            unsafe_list.append(plugin)
            actions.warning(f"Unsafe plugin folder name: '{plugin}'")
    plugin_list = safe_list

    if unsafe_list:
        actions.error(f"Unsafe plugin folder name(s) detected: {', '.join(unsafe_list)}")
        actions.set_outputs(close_pr="true", close_reason="unsafe-plugin-name",
                            plugin_count="0", matrix="[]",
                            has_new_plugin="false", has_updated_plugin="false")
        return 0

    if not plugin_list:
        actions.error("No valid plugin changes detected in this PR.")
        actions.set_outputs(close_pr="true", close_reason="no-valid-plugins",
                            plugin_count="0", matrix="[]",
                            has_new_plugin="false", has_updated_plugin="false")
        return 0

    plugin_count = len(plugin_list)

    has_new_plugin = False
    has_updated_plugin = False
    for plugin in plugin_list:
        if git.object_exists(f"origin/{base_ref}:plugins/{plugin}/plugin.json"):
            has_updated_plugin = True
        else:
            has_new_plugin = True

    is_maintainer = write_access()
    has_any_permission = is_maintainer
    if not is_maintainer:
        for plugin in plugin_list:
            base_json = git.show(f"origin/{base_ref}:plugins/{plugin}/plugin.json")
            if base_json and author_has_plugin_permission(pr_author, base_json):
                has_any_permission = True
                break

    close_pr = (not has_any_permission) and (not has_new_plugin)

    # Blacklist gate (only meaningful when not already closing).
    close_reason = "unauthorized" if close_pr else ""
    if not close_pr:
        bl = check_blacklists(pr_author, plugin_list, author_blacklist, plugin_blacklist)
        if bl.matched:
            close_pr = True
            close_reason = bl.reason

    actions.set_outputs(matrix=json.dumps(plugin_list, separators=(",", ":")),
                        plugin_count=str(plugin_count),
                        close_pr="true" if close_pr else "false",
                        skip_validation="false",
                        outside_violation="true" if has_outside_violation else "false",
                        close_reason=close_reason)
    if outside_changes:
        actions.set_output("outside_files", "\n".join(outside_changes))

    pub_key_changed = is_maintainer and PUB_KEY_PATH in outside_changes
    actions.set_outputs(pub_key_changed="true" if pub_key_changed else "false",
                        has_new_plugin="true" if has_new_plugin else "false",
                        has_updated_plugin="true" if has_updated_plugin else "false")

    actions.log(f"Detected {plugin_count} plugin(s): {' '.join(plugin_list)}")
    actions.log(f"close_pr={'true' if close_pr else 'false'}")
    return 0


def _no_plugins(pr_author, outside_changes, has_outside_violation, write_access) -> int:
    if has_outside_violation:
        actions.set_outputs(matrix="[]", plugin_count="0", close_pr="false",
                            close_reason="", skip_validation="false",
                            outside_violation="true",
                            has_new_plugin="false", has_updated_plugin="false")
        actions.set_output("outside_files", "\n".join(outside_changes))
        return 0
    if write_access():
        pub_key_changed = PUB_KEY_PATH in outside_changes
        actions.set_outputs(matrix="[]", plugin_count="0", close_pr="false",
                            close_reason="", skip_validation="true",
                            outside_violation="false",
                            pub_key_changed="true" if pub_key_changed else "false",
                            has_new_plugin="false", has_updated_plugin="false")
        if outside_changes:
            actions.set_output("outside_files", "\n".join(outside_changes))
        actions.log("No plugin changes detected - skipping plugin validation (author has write access).")
        return 0
    actions.error("No plugin changes detected in this PR.")
    return 1
