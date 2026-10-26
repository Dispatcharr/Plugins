import datetime as dt
from types import SimpleNamespace

import pytest

from pluginctl import messages


MESSAGE_ID = "123e4567-e89b-42d3-a456-426614174000"


def message(**overrides):
    return {
        "id": MESSAGE_ID,
        "severity": "warning",
        "body": "Maintenance is scheduled.",
        **overrides,
    }


def test_validates_minimal_and_full_messages():
    minimal = messages.validate_message(message(body="First line\nSecond line"))
    full = messages.validate_message(message(
        title="Maintenance", link="https://status.example.test/notice",
        starts_at="2026-11-01T01:00:00Z", expires_at="2026-11-01T03:00:00Z",
        target=">=0.34.0 <0.36.0", dev=True,
    ))

    assert minimal["body"] == "First line\nSecond line"
    assert full["target"] == ">=0.34.0 <0.36.0"
    assert full["dev"] is True
    for severity in messages.SEVERITIES:
        assert messages.validate_message(message(severity=severity))["severity"] == severity


@pytest.mark.parametrize("changes", [
    {"severity": "urgent"},
    {"link": "http://example.test"},
    {"expires_at": "2026-11-01"},
    {"starts_at": "2026-11-01T01:00:00Z"},
    {"starts_at": "2026-11-01T03:00:00Z", "expires_at": "2026-11-01T03:00:00Z"},
    {"target": "~1.0"},
    {"dev": "true"},
    {"extra": True},
])
def test_rejects_invalid_messages(changes):
    with pytest.raises(messages.FeedError):
        messages.validate_message(message(**changes))


def test_feed_rejects_duplicate_ids_and_canonical_check(tmp_path):
    path = tmp_path / "messages.json"
    path.write_text(messages.render([]), encoding="utf-8")
    assert messages.load(str(path), require_canonical=True) == []

    path.write_text(messages.render([message(), message(body="Different")]), encoding="utf-8")
    with pytest.raises(messages.FeedError, match="unique"):
        messages.load(str(path))


def test_active_omits_only_expired_messages():
    now = dt.datetime(2026, 11, 1, 2, tzinfo=dt.timezone.utc)
    active = message()
    expired = message(id="123e4567-e89b-42d3-a456-426614174001", expires_at="2026-11-01T02:00:00Z")

    assert messages.active([active, expired], now) == [active]


def test_flag_values_decode_json_style_escapes():
    assert messages.decode_flag_value(r"First\nSecond\t\u2603", "body") == "First\nSecond\t☃"
    assert messages.decode_flag_value(r"\\n", "body") == r"\n"
    with pytest.raises(messages.FeedError):
        messages.decode_flag_value(r"\x", "body")


def test_add_and_update_are_canonical_and_preserve_id(tmp_path):
    path = tmp_path / "messages.json"
    messages.write(str(path), [])
    add = SimpleNamespace(
        messages_command="add", file=str(path), severity="info", body="Hello", title=None,
        link=None, starts_at=None, expires_at=None, target=None, dev=None,
    )

    assert messages.command(add) == 0
    created = messages.load(str(path))[0]
    update = SimpleNamespace(
        messages_command="update", file=str(path), id=created["id"], severity="success",
        title=None, body=None, link=None, starts_at=None, expires_at=None, target=None, dev=None,
        clear_title=False, clear_link=False, clear_starts_at=False, clear_expires_at=False,
        clear_target=False, clear_dev=False,
    )

    assert messages.command(update) == 0
    updated = messages.load(str(path), require_canonical=True)[0]
    assert updated["id"] == created["id"]
    assert updated["severity"] == "success"


def test_noninteractive_incomplete_add_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(messages, "_interactive", lambda: False)
    args = SimpleNamespace(
        messages_command="add", file=str(tmp_path / "messages.json"), severity="info", body=None,
        title=None, link=None, starts_at=None, expires_at=None, target=None, dev=None,
    )
    assert messages.command(args) == 1
