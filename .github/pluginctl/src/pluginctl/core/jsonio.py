"""Canonical JSON helpers for manifest payloads and on-disk wrappers.

Manifest objects are built as insertion-ordered ``dict`` objects in the same key
order as the corresponding jq program. Nulls are dropped the same way jq's
``with_entries(select(.value != null))`` does, and compact JSON is retained for
stable payload comparisons and GPG signing. Published wrapper files use formatted
JSON so humans can inspect them easily.
"""

from __future__ import annotations

import json
from typing import Any


def dumps(obj: Any) -> str:
    """Compact JSON, byte-equivalent to ``jq -c '.'``.

    jq -c uses ``,``/``:`` separators, emits UTF-8 (no ``\\uXXXX`` escaping of
    non-ASCII), and does not escape ``/``. ``json.dumps`` with these options
    matches on all three counts.
    """
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def dumps_formatted(obj: Any) -> str:
    """Indented JSON for generated files, with a conventional trailing newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def drop_none(obj: dict) -> dict:
    """Reproduce ``with_entries(select(.value != null))`` for a single object.

    Only top-level ``None`` values are removed, insertion order preserved,
    matching the jq idiom used throughout ``generate-manifest.sh``.
    """
    return {k: v for k, v in obj.items() if v is not None}


def compact(obj: Any) -> str:
    """Alias for :func:`dumps` for call-site readability."""
    return dumps(obj)
