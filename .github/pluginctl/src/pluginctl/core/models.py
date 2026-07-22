"""Typed view over a ``plugin.json`` document.

Wraps the parsed dict and exposes the handful of accessors the validate/publish
logic needs, with the same ``// ""`` / ``// false`` defaulting the jq programs
used. ``raw`` stays available for the manifest builders that must preserve the
original key set and ordering.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Plugin:
    raw: dict = field(default_factory=dict)

    # ---- constructors -------------------------------------------------------
    @classmethod
    def from_json_text(cls, text: str) -> "Plugin":
        return cls(raw=json.loads(text))

    @classmethod
    def from_file(cls, path: str) -> "Plugin":
        with open(path, encoding="utf-8") as fh:
            return cls(raw=json.load(fh))

    # ---- scalar accessors (jq `// ""` semantics) ----------------------------
    def str_field(self, key: str, default: str = "") -> str:
        val = self.raw.get(key)
        return default if val is None else str(val)

    @property
    def name(self) -> str:
        return self.str_field("name")

    @property
    def version(self) -> str:
        return self.str_field("version")

    @property
    def description(self) -> str:
        return self.str_field("description")

    @property
    def author(self) -> str:
        return self.str_field("author")

    @property
    def license(self) -> str:
        return self.str_field("license")

    @property
    def repo_url(self) -> str:
        return self.str_field("repo_url")

    @property
    def discord_thread(self) -> str:
        return self.str_field("discord_thread")

    @property
    def source_type(self) -> str:
        return self.str_field("source_type", "local")

    @property
    def source_url(self) -> str:
        return self.str_field("source_url")

    @property
    def min_dispatcharr_version(self) -> str:
        return self.str_field("min_dispatcharr_version")

    @property
    def max_dispatcharr_version(self) -> str:
        return self.str_field("max_dispatcharr_version")

    @property
    def deprecated(self) -> bool:
        return self.raw.get("deprecated") is True

    @property
    def unlisted(self) -> bool:
        return self.raw.get("unlisted") is True

    @property
    def maintainers(self) -> list[str]:
        """``[.maintainers[]?]``: always a list, dropping non-list values."""
        val = self.raw.get("maintainers")
        return list(val) if isinstance(val, list) else []

    def maintainers_joined(self, sep: str = " ") -> str:
        return sep.join(str(m) for m in self.maintainers)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)
