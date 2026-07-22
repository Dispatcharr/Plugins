from pluginctl.validate.title import check_title


def test_repo_prefix_zero_plugins_ok():
    r = check_title("[repo]: fix workflow", "alice", 0, [])
    assert r.valid and r.feedback == ""


def test_repo_prefix_zero_plugins_wrong():
    r = check_title("[alice]: fix workflow", "alice", 0, [])
    assert not r.valid
    assert "should be `[repo]`" in r.feedback
    assert r.suggestion == "[repo]: Brief description of changes"


def test_single_plugin_prefix_ok():
    r = check_title("[my-plugin]: bump to 1.2.0", "bob", 1, ["my-plugin"])
    assert r.valid


def test_single_plugin_prefix_mismatch():
    r = check_title("[wrong]: bump", "bob", 1, ["my-plugin"])
    assert not r.valid
    assert "`[my-plugin]`" in r.feedback
    assert r.suggestion == "[my-plugin]: Brief description of changes"


def test_multi_plugin_requires_author_prefix():
    r = check_title("[carol]: update several", "carol", 3, ["a", "b", "c"])
    assert r.valid


def test_multi_plugin_wrong_prefix():
    r = check_title("[a]: update several", "carol", 3, ["a", "b", "c"])
    assert not r.valid
    assert "`[carol]`" in r.feedback
    assert r.suggestion == "[carol]: Brief description of changes"


def test_malformed_title():
    r = check_title("no brackets here", "dan", 1, ["p"])
    assert not r.valid
    assert "does not match the required format" in r.feedback


def test_optional_colon_and_whitespace():
    assert check_title("[repo] just a space no colon", "e", 0, []).valid
    assert check_title("[repo]:with-no-space", "e", 0, []).valid is False
