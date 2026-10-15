"""Thin wrappers over the local ``git`` CLI used by detect / validate / publish."""

from __future__ import annotations

import subprocess
from typing import Optional


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """``git <args>`` with output captured as text."""
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def configure_identity(app_slug: str) -> None:
    """Set the committer identity to the GitHub App bot, else github-actions[bot]."""
    if not app_slug:
        run("config", "user.name", "github-actions[bot]")
        run("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
        return
    from . import gh
    bot_user_id = gh.api(f"/users/{app_slug}%5Bbot%5D", jq=".id") or ""
    run("config", "user.name", f"{app_slug}[bot]")
    email = (f"{bot_user_id}+{app_slug}[bot]@users.noreply.github.com" if bot_user_id
             else f"{app_slug}[bot]@users.noreply.github.com")
    run("config", "user.email", email)


def merge_base(a: str, b: str) -> str:
    return run("merge-base", a, b).stdout.strip()


def diff_name_only(base: str, head: str = "HEAD", paths: Optional[list[str]] = None) -> list[str]:
    args = ["diff", "--name-only", base, head]
    if paths:
        args += ["--", *paths]
    out = run(*args).stdout
    return [line for line in out.splitlines() if line]


def diff_name_only_range(range_spec: str, paths: Optional[list[str]] = None) -> list[str]:
    """``git diff --name-only <range> [-- paths]`` where range is e.g. ``a...HEAD``."""
    args = ["diff", "--name-only", range_spec]
    if paths:
        args += ["--", *paths]
    out = run(*args).stdout
    return [line for line in out.splitlines() if line]


def show(ref_path: str) -> Optional[str]:
    """``git show <ref>:<path>`` returning None when the object does not exist."""
    proc = run("show", ref_path, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def object_exists(ref_path: str) -> bool:
    return run("show", ref_path, check=False).returncode == 0


def log_format(fmt: str, ref: str, path: Optional[str] = None) -> Optional[str]:
    """``git log -1 --format=<fmt> <ref> [-- <path>]`` (None if empty/failure)."""
    args = ["log", "-1", f"--format={fmt}", ref]
    if path is not None:
        args += ["--", path]
    proc = run(*args, check=False)
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def rev_parse(rev: str, short: bool = False) -> str:
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append(rev)
    return run(*args).stdout.strip()


def fetch(*args: str) -> None:
    run("fetch", *args, check=False)


def sparse_checkout_add(path: str) -> bool:
    return run("sparse-checkout", "add", path, check=False).returncode == 0


def checkout(*args: str) -> bool:
    return run("checkout", *args, check=False).returncode == 0
