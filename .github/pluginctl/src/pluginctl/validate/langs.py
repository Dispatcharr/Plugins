"""``pluginctl detect-langs``: which CodeQL languages are present in changed plugins.

Ports the "Detect supported languages" bash step. Emits ``found`` / ``languages``
/ ``unscanned_langs`` the same way, in the same order, so the CodeQL matrix and
the "unscanned file types" notice are unchanged.
"""

from __future__ import annotations

import os

from ..core import actions

# CodeQL-supported languages, in the Bash detection order.
_SUPPORTED = [
    ("python", {".py"}),
    ("javascript", None),  # special-cased (prunes vendored dirs)
    ("go", {".go"}),
    ("ruby", {".rb"}),
    ("java-kotlin", {".java", ".kt", ".kts"}),
    ("c-cpp", {".c", ".cpp", ".cc", ".h", ".hpp"}),
]

# Present-but-unsupported file types, in the Bash order.
_UNSCANNED = [
    ("shell", {".sh", ".bash"}),
    ("php", {".php"}),
    ("lua", {".lua"}),
    ("perl", {".pl", ".pm"}),
    ("rust", {".rs"}),
]

# Directories pruned from the JavaScript search (vendored / build output).
_JS_PRUNE = {"node_modules", "dist", "build", "static"}
_JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}


def _has_ext(root: str, exts: set[str]) -> bool:
    for _dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if os.path.splitext(fn)[1] in exts:
                return True
    return False


def _has_js(root: str) -> bool:
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _JS_PRUNE]
        for fn in files:
            if os.path.splitext(fn)[1] in _JS_EXTS:
                return True
    return False


def detect(root: str = "plugins") -> tuple[bool, str, str]:
    """Return (found, languages_csv, unscanned_csv)."""
    langs: list[str] = []
    for name, exts in _SUPPORTED:
        if name == "javascript":
            if _has_js(root):
                langs.append(name)
        elif _has_ext(root, exts):
            langs.append(name)
    unscanned = [name for name, exts in _UNSCANNED if _has_ext(root, exts)]
    return bool(langs), ",".join(langs), ",".join(unscanned)


def run(root: str = "plugins") -> int:
    found, languages, unscanned = detect(root)
    actions.set_output("unscanned_langs", unscanned)
    actions.set_output("found", "true" if found else "false")
    actions.set_output("languages", languages)
    if found:
        actions.log(f"Detected languages for CodeQL: {languages}")
    else:
        actions.log("No supported language files found in changed plugins, skipping CodeQL.")
    if unscanned:
        actions.log(f"Unscanned file types (no CodeQL support): {unscanned}")
    return 0
