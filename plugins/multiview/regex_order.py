"""Ordering helpers for dynamically selected regex channels."""

import re


def regex_sort_key(pattern: str, name: str, channel_number, mode: str):
    """Return a stable ordering key for a regex-matched channel."""
    if mode == "channel_number_reverse":
        return (0, channel_number is None, -(channel_number or 0), name.casefold())
    number_key = (channel_number is None, channel_number or 0, name.casefold())
    if mode != "pattern":
        return (0, *number_key)
    alternatives = _top_level_alternatives(pattern)
    try:
        for index, alternative in enumerate(alternatives):
            if re.search(alternative, name, re.IGNORECASE):
                return (index, *number_key)
    except re.error:
        pass
    return (len(alternatives), *number_key)


def _top_level_alternatives(pattern: str) -> list[str]:
    """Split unescaped alternatives outside groups and character classes."""
    alternatives = []
    start = depth = 0
    escaped = in_class = False
    for index, char in enumerate(pattern):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif in_class:
            in_class = char != "]"
        elif char == "[":
            in_class = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "|" and depth == 0:
            alternatives.append(pattern[start:index])
            start = index + 1
    alternatives.append(pattern[start:])
    return alternatives
