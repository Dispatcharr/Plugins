import pytest

from pluginctl.core import version as v


@pytest.mark.parametrize("s,ok", [
    ("1.0.0", True), ("10.20.30", True), ("0.0.1", True),
    ("v1.0.0", False), ("1.0", False), ("1.0.0-1", False), ("1.0.0a", False), ("", False),
])
def test_is_semver(s, ok):
    assert v.is_semver(s) is ok


@pytest.mark.parametrize("s,ok", [
    ("1.0.0", True), ("v1.0.0", True), ("v10.2.3", True),
    ("1.0", False), ("x1.0.0", False), ("", False),
])
def test_is_dispatcharr_version(s, ok):
    assert v.is_dispatcharr_version(s) is ok


@pytest.mark.parametrize("new,old,gt", [
    ("1.0.1", "1.0.0", True),
    ("1.1.0", "1.0.9", True),
    ("2.0.0", "1.9.9", True),
    ("1.0.0", "1.0.0", False),   # equal is not greater
    ("1.0.0", "1.0.1", False),
    ("0.9.9", "1.0.0", False),
])
def test_version_greater_than(new, old, gt):
    assert v.version_greater_than(new, old) is gt


def test_sort_versions_desc():
    assert v.sort_versions_desc(["1.0.0", "1.10.0", "1.2.0", "1.0.0-1"]) == \
        ["1.10.0", "1.2.0", "1.0.0-1", "1.0.0"]
