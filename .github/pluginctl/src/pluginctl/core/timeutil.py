"""Shared timestamp formatting (one definition of the manifest/build ISO format)."""

from __future__ import annotations

import datetime


def now_iso() -> str:
    """Current UTC time as ``YYYY-MM-DDTHH:MM:SSZ`` (the format every artifact uses)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
