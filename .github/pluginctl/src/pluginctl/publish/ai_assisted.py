"""Best-effort detection of AI attribution in plugin Git history."""

from __future__ import annotations

import re

from ..core import actions, git


TRAILER_RE = re.compile(
    r"^(?:co-authored-by|ai-assisted-by|assisted-by|generated-by):\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Match only agent names in authorship fields, never prose in a commit message.
AGENT_NAME_RE = re.compile(
    r"^(?:"
    r"claude (?:code|opus|sonnet|haiku|fable)(?: [0-9.]+)?|"
    r"(?:openai )?codex|chatgpt|"
    r"(?:github )?copilot|gemini(?: cli)?|cursor|aider|cline|roo code|continue|"
    r"windsurf|codeium|devin|amp|(?:amazon )?q|tabnine|jetbrains ai|kiro|"
    r"augment code|qodo|codiumai|sweep ai|replit agent|hermes agent"
    r")(?: \([^)]*\))?$",
    re.IGNORECASE,
)

# Exact known identities are stronger evidence than a display name and cover
# formats already used in this repository.
AGENT_EMAILS = {
    "noreply@anthropic.com",
    "hermes-agent@g1tech.us",
}


def has_attribution(source_branch: str, plugin_name: str) -> bool:
    """Return whether source-branch history attributes a plugin change to an AI agent."""
    proc = git.run(
        "log", f"origin/{source_branch}", "--format=%aN%x1f%aE%x1f%B%x1e",
        "--", f"plugins/{plugin_name}", check=False,
    )
    if proc.returncode != 0:
        actions.warning(f"Could not inspect AI attribution history for {plugin_name}; "
                        "using manual disclosure only.")
        return False

    for record in proc.stdout.split("\x1e"):
        if not record.strip():
            continue
        try:
            author_name, author_email, message = record.split("\x1f", 2)
        except ValueError:
            actions.warning(f"Could not parse AI attribution history for {plugin_name}; "
                            "using manual disclosure only.")
            return False
        if _is_agent_identity(author_name, author_email):
            return True
        for trailer in TRAILER_RE.findall(message):
            name, email = _identity_parts(trailer)
            if _is_agent_identity(name, email):
                return True
    return False


def _identity_parts(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"\s*(.*?)\s*<([^<>]+)>\s*", value)
    if match:
        return match.group(1), match.group(2)
    return value.strip(), ""


def _is_agent_identity(name: str, email: str) -> bool:
    return email.strip().lower() in AGENT_EMAILS or bool(AGENT_NAME_RE.fullmatch(name.strip()))
