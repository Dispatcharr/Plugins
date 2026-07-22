"""Version parsing / comparison helpers ported from the Bash validate + publish scripts.

These reproduce the exact acceptance rules of the shell functions:
  validate_semver            -> ^[0-9]+\\.[0-9]+\\.[0-9]+$
  validate_dispatcharr_version -> ^v?[0-9]+\\.[0-9]+\\.[0-9]+$
  version_greater_than       -> field-wise major/minor/patch comparison
and the `sort -V -r` ordering used to pick newest release tags.
"""

from __future__ import annotations

import re
from functools import cmp_to_key

_SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_DA_VERSION_RE = re.compile(r"^v?[0-9]+\.[0-9]+\.[0-9]+$")


def is_semver(version: str) -> bool:
    """True for strict ``X.Y.Z`` (matches validate_semver == 1)."""
    return bool(_SEMVER_RE.match(version or ""))


def is_dispatcharr_version(version: str) -> bool:
    """True for ``X.Y.Z`` or ``vX.Y.Z`` (matches validate_dispatcharr_version == 1)."""
    return bool(_DA_VERSION_RE.match(version or ""))


def version_greater_than(new_version: str, old_version: str) -> bool:
    """Return True when new > old, comparing major/minor/patch as integers.

    Mirrors the Bash ``version_greater_than`` exactly: it reads three
    dot-separated fields and compares them numerically; equal versions are not
    "greater".
    """
    def _parts(v: str) -> tuple[int, int, int]:
        fields = (v or "").split(".")
        # Bash `IFS='.' read -r A B C` leaves missing fields empty -> treated as 0
        nums = []
        for i in range(3):
            try:
                nums.append(int(fields[i]))
            except (IndexError, ValueError):
                nums.append(0)
        return nums[0], nums[1], nums[2]

    nmaj, nmin, npat = _parts(new_version)
    omaj, omin, opat = _parts(old_version)
    if nmaj > omaj:
        return True
    if nmaj < omaj:
        return False
    if nmin > omin:
        return True
    if nmin < omin:
        return False
    if npat > opat:
        return True
    return False


def _version_sort_key(s: str):
    """A key that orders like GNU ``sort -V`` for the version strings we handle.

    Release tags are stripped to bare versions such as ``1.2.3`` or ``1.2.3-1``
    (a migration retry suffix). ``sort -V`` treats each maximal run of digits as a
    number and each run of non-digits lexically, so we tokenize accordingly.
    """
    tokens: list = []
    for part in re.findall(r"\d+|\D+", s or ""):
        if part.isdigit():
            tokens.append((1, int(part), ""))
        else:
            tokens.append((0, 0, part))
    return tokens


def _version_cmp(a: str, b: str) -> int:
    ka, kb = _version_sort_key(a), _version_sort_key(b)
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0


def sort_versions_desc(versions: list[str]) -> list[str]:
    """Sort bare version strings newest-first, like ``sort -V -r``."""
    return sorted(versions, key=cmp_to_key(_version_cmp), reverse=True)
