import json
import subprocess

import pytest

from pluginctl.core import jsonio


def _jq_compact(obj) -> str:
    """Ground truth: pipe through real jq -c, matching the V1 pipeline."""
    return subprocess.run(
        ["jq", "-cn", "--argjson", "x", json.dumps(obj), "$x"],
        capture_output=True, text=True, check=True,
    ).stdout.rstrip("\n")


def _have_jq() -> bool:
    try:
        subprocess.run(["jq", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@pytest.mark.parametrize("obj", [
    {"b": 1, "a": 2},                         # key order preserved
    {"name": "café", "emoji": "🎉"},          # non-ASCII stays raw (no \uXXXX)
    {"url": "https://example.com/a/b"},        # slashes not escaped
    {"nested": {"x": [1, 2, 3], "y": None}},
    [1, "two", {"three": 3}],
    {"quote": 'he said "hi"', "tab": "a\tb"},
])
def test_dumps_matches_jq(obj):
    if not _have_jq():
        pytest.skip("jq not available")
    assert jsonio.dumps(obj) == _jq_compact(obj)


def test_drop_none_preserves_order_and_removes_none():
    obj = {"a": 1, "b": None, "c": 3, "d": None, "e": 5}
    assert jsonio.drop_none(obj) == {"a": 1, "c": 3, "e": 5}
    assert list(jsonio.drop_none(obj).keys()) == ["a", "c", "e"]


def test_dumps_compact_separators():
    assert jsonio.dumps({"a": 1, "b": 2}) == '{"a":1,"b":2}'
