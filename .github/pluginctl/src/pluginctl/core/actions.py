"""GitHub Actions plumbing: GITHUB_OUTPUT, step summary, workflow commands.

Thin, side-effecting helpers that write to the files/streams the runner reads.
Kept tiny so command modules stay testable (they build values; these emit them).
"""

from __future__ import annotations

import os
import sys
import uuid


def set_output(name: str, value: str) -> None:
    """Append ``name=value`` to ``$GITHUB_OUTPUT`` (multiline-safe).

    Values containing a newline use the heredoc form GitHub documents, with a
    random delimiter to avoid collisions with the payload.
    """
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        # Local/dry-run: echo to stdout the same way the shell scripts did.
        print(f"{name}={value}")
        return
    with open(path, "a", encoding="utf-8") as fh:
        if "\n" in value:
            delim = f"ghadelim_{uuid.uuid4().hex}"
            fh.write(f"{name}<<{delim}\n{value}\n{delim}\n")
        else:
            fh.write(f"{name}={value}\n")


def set_outputs(**kwargs: str) -> None:
    for name, value in kwargs.items():
        set_output(name, "" if value is None else str(value))


def step_summary(markdown: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        print(markdown)
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(markdown)
        if not markdown.endswith("\n"):
            fh.write("\n")


def error(message: str) -> None:
    print(f"::error::{message}")


def warning(message: str) -> None:
    print(f"::warning::{message}")


def notice(message: str) -> None:
    print(f"::notice::{message}")


def log(message: str) -> None:
    print(message)


def eprint(message: str) -> None:
    print(message, file=sys.stderr)
