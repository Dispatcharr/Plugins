import json

from pluginctl.validate import detect


def test_is_safe_name():
    assert detect.is_safe_name("my-plugin")
    assert detect.is_safe_name("plugin123")
    assert not detect.is_safe_name("My-Plugin")
    assert not detect.is_safe_name("has space")
    assert not detect.is_safe_name("-leading")
    assert not detect.is_safe_name("trailing-")
    assert not detect.is_safe_name("double--hyphen")


def test_author_permission_by_author():
    base = json.dumps({"author": "alice"})
    assert detect.author_has_plugin_permission("alice", base)
    assert not detect.author_has_plugin_permission("bob", base)


def test_author_permission_by_maintainer():
    base = json.dumps({"author": "alice", "maintainers": ["bob", "carol"]})
    assert detect.author_has_plugin_permission("carol", base)
    assert not detect.author_has_plugin_permission("dan", base)


def test_author_permission_no_base():
    assert not detect.author_has_plugin_permission("alice", None)
    assert not detect.author_has_plugin_permission("alice", "")


def test_blacklist_author_case_insensitive():
    r = detect.check_blacklists("BadActor", ["p"], "goodguy, badactor", "")
    assert r.matched and r.reason == "author-blacklisted"


def test_blacklist_plugin():
    r = detect.check_blacklists("someone", ["evil-plugin"], "", "evil-plugin , other")
    assert r.matched and r.reason == "plugin-blacklisted"


def test_blacklist_none_configured():
    assert not detect.check_blacklists("x", ["p"], "", "").matched


def test_blacklist_no_match():
    assert not detect.check_blacklists("clean", ["clean-plugin"], "bad", "evil").matched
