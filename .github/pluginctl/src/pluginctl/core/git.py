"""Thin wrappers over the local ``git`` CLI used by detect / validate / publish."""

from __future__ import annotations

import subprocess
from typing import Optional


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def merge_base(a: str, b: str) -> str:
    return _run(["merge-base", a, b]).stdout.strip()


def diff_name_only(base: str, head: str = "HEAD", paths: Optional[list[str]] = None) -> list[str]:
    args = ["diff", "--name-only", base, head]
    if paths:
        args += ["--", *paths]
    out = _run(args).stdout
    return [line for line in out.splitlines() if line]


def diff_name_only_range(range_spec: str, paths: Optional[list[str]] = None) -> list[str]:
    """``git diff --name-only <range> [-- paths]`` where range is e.g. ``a...HEAD``."""
    args = ["diff", "--name-only", range_spec]
    if paths:
        args += ["--", *paths]
    out = _run(args).stdout
    return [line for line in out.splitlines() if line]


def show(ref_path: str) -> Optional[str]:
    """``git show <ref>:<path>`` returning None when the object does not exist."""
    proc = _run(["show", ref_path], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


def object_exists(ref_path: str) -> bool:
    return _run(["show", ref_path], check=False).returncode == 0


def log_format(fmt: str, ref: str, path: Optional[str] = None) -> Optional[str]:
    """``git log -1 --format=<fmt> <ref> [-- <path>]`` (None if empty/failure)."""
    args = ["log", "-1", f"--format={fmt}", ref]
    if path is not None:
        args += ["--", path]
    proc = _run(args, check=False)
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def rev_parse(rev: str, short: bool = False) -> str:
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append(rev)
    return _run(args).stdout.strip()


def fetch(*args: str) -> None:
    _run(["fetch", *args], check=False)


def sparse_checkout_add(path: str) -> bool:
    return _run(["sparse-checkout", "add", path], check=False).returncode == 0


def checkout(*args: str) -> bool:
    return _run(["checkout", *args], check=False).returncode == 0
