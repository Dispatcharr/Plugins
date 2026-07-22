"""PR-title format check (ports the inline ``validate-title`` job).

Contract preserved exactly:
  - 0 plugins       -> prefix must be ``repo``
  - 1 plugin        -> prefix must equal the plugin slug
  - 2+ plugins      -> prefix must equal the PR author's login
  - malformed title -> generic "does not match" feedback
The suggestion string is context-dependent and matches the Bash wording verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Bash: ^\[([^]]+)\]:?[[:space:]]+.+  ('[' prefix ']' optional ':' whitespace rest)
_TITLE_RE = re.compile(r"^\[([^\]]+)\]:?\s+.+", re.DOTALL)


@dataclass
class TitleResult:
    valid: bool
    feedback: str
    suggestion: str


def check_title(title: str, author: str, plugin_count: int, matrix: list[str]) -> TitleResult:
    count = plugin_count

    if count == 0:
        context_suggestion = "[repo]: Brief description of changes"
    elif count == 1:
        slug = matrix[0] if matrix else "plugin-slug"
        context_suggestion = f"[{slug}]: Brief description of changes"
    else:
        context_suggestion = f"[{author}]: Brief description of changes"

    match = _TITLE_RE.match(title or "")
    if match:
        prefix = match.group(1)
        if count == 0:
            if prefix != "repo":
                return TitleResult(
                    False,
                    "For repo-level or non-plugin changes, the prefix should be `[repo]`.",
                    context_suggestion,
                )
        elif count == 1:
            expected = matrix[0] if matrix else ""
            if expected and prefix != expected:
                return TitleResult(
                    False,
                    f"For a single plugin change, the prefix should match the plugin folder name: `[{expected}]`.",
                    context_suggestion,
                )
        else:
            if prefix != author:
                return TitleResult(
                    False,
                    f"For changes to multiple plugins, the prefix should be your GitHub username: `[{author}]`.",
                    context_suggestion,
                )
        return TitleResult(True, "", "")

    return TitleResult(
        False,
        "PR title does not match the required format. Expected: `[prefix] description`.",
        context_suggestion,
    )
