"""Canonical JSON helpers that reproduce the exact byte output of the V1 jq programs.

The V1 publish pipeline builds manifests with `jq` and emits them with `jq -c`.
To keep the published `releases`-branch output byte-identical, every manifest
object here is built as an insertion-ordered ``dict`` in the same key order as the
corresponding jq program, nulls are dropped the same way jq's
``with_entries(select(.value != null))`` does, and the compact form is produced
with the same separators jq uses.
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


def drop_none(obj: dict) -> dict:
    """Reproduce ``with_entries(select(.value != null))`` for a single object.

    Only top-level ``None`` values are removed, insertion order preserved,
    matching the jq idiom used throughout ``generate-manifest.sh``.
    """
    return {k: v for k, v in obj.items() if v is not None}


def compact(obj: Any) -> str:
    """Alias for :func:`dumps` for call-site readability."""
    return dumps(obj)
