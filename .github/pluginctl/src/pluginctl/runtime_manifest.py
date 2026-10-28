"""Runtime manifest discovery shared by validation and publishing."""

from __future__ import annotations

import json
import os
from typing import Any


def load(plugin_dir: str, catalog: dict[str, Any]) -> dict[str, Any] | None:
    """Return the runtime manifest when it explicitly declares a schema version.

    External plugin scans save the fetched release manifest in a sidecar. Local
    plugins use their catalog file only when it also contains ``manifest_version``.
    """
    manifests: list[dict[str, Any]] = [catalog]
    if catalog.get("source_type") == "external":
        sidecar = os.path.join(plugin_dir, ".dispatcharr-runtime-manifest.json")
        try:
            with open(sidecar, encoding="utf-8") as fh:
                fetched = json.load(fh)
        except (OSError, json.JSONDecodeError):
            fetched = None
        if isinstance(fetched, dict):
            manifests.insert(0, fetched)

    for manifest in manifests:
        if "manifest_version" in manifest:
            return manifest
    return None
