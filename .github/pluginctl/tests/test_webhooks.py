import hashlib
import hmac
import json

from pluginctl.integrations import webhooks


def test_sign_matches_manual_hmac():
    body = b'{"a":1}'
    expected = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert webhooks.sign("secret", body) == expected


def test_envelope_shape():
    env = webhooks.build_envelope("plugin.published", {"plugin": "p"}, "org/repo", "alice")
    assert env["event"] == "plugin.published"
    assert env["repository"] == "org/repo"
    assert env["actor"] == "alice"
    assert env["data"] == {"plugin": "p"}
    assert env["delivered_at"].endswith("Z")


def test_emit_noop_when_unconfigured():
    assert webhooks.emit("x", {}, url="", secret="") is False
    assert webhooks.emit("x", {}, url="https://h", secret="") is False


def test_emit_delivers_with_valid_signature():
    captured = {}

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def getcode(self): return 200

    def fake_opener(request, timeout=15):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = request.data
        return _Resp()

    ok = webhooks.emit("plugin.published", {"plugin": "p", "version": "1.0.0"},
                       repository="org/repo", actor="bot",
                       url="https://hook.example", secret="topsecret",
                       _opener=fake_opener)
    assert ok is True
    sig = captured["headers"]["x-pluginctl-signature"]
    assert sig == webhooks.sign("topsecret", captured["body"])
    assert captured["headers"]["x-pluginctl-event"] == "plugin.published"
    assert "x-pluginctl-delivery" in captured["headers"]
    body = json.loads(captured["body"])
    assert body["data"]["version"] == "1.0.0"


def test_emit_swallows_delivery_error():
    def boom(request, timeout=15):
        raise OSError("connection refused")
    assert webhooks.emit("x", {}, url="https://h", secret="s", _opener=boom) is False


def test_discord_payload_uses_components_v2_and_optional_logo():
    payload = webhooks.discord_payload("plugin.published", {
        "plugin": "demo", "version": "1.0.0", "logo_url": "https://images.example/demo.png",
    }, "owner/repo")
    assert payload["flags"] == 32768
    assert "content" not in payload
    container = payload["components"][0]
    assert container["type"] == 17
    section = container["components"][2]
    assert section["type"] == 9
    assert section["accessory"]["type"] == 11


def test_discord_routes_and_wildcard_delivery():
    captured = []
    class _Resp:
        status = 204
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def getcode(self): return 204
    def opener(request, timeout=15):
        captured.append(request.full_url)
        return _Resp()
    config = json.dumps({
        "published": {"url": "https://discord.example/a", "events": ["plugin.published"]},
        "all": {"url": "https://discord.example/b?wait=true", "events": ["*"]},
    })
    assert webhooks.emit_discord("plugin.published", {"plugin": "demo"}, config=config, _opener=opener)
    assert len(captured) == 2
    assert all("with_components=true" in url for url in captured)
