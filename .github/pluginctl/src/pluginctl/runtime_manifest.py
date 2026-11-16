"""Runtime manifest discovery shared by validation and publishing."""

from __future__ import annotations

import json
import os
from typing import Any


def load(plugin_dir: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    """Return the release sidecar or a catalog with an explicit schema version.

    An external sidecar without a schema version represents legacy version 0.
    Local plugins use their catalog only when it declares ``manifest_version``.
    """
    if catalog.get("source_type") == "external":
        sidecar = os.path.join(plugin_dir, ".dispatcharr-runtime-manifest.json")
        try:
            with open(sidecar, encoding="utf-8") as fh:
                fetched = json.load(fh)
        except (OSError, json.JSONDecodeError):
            fetched = None
        if isinstance(fetched, dict):
            return fetched

    return catalog if "manifest_version" in catalog else None
