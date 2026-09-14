"""JSON API handlers (/api/*) and static file serving for the dashboard SPA."""

import json
import logging
import mimetypes
import os
import re

logger = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_PLUGIN_KEY = "embyfin_stream_cleanup"

_CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS"),
    ("Access-Control-Allow-Headers", "Authorization, Content-Type"),
]


def _json_ok(start_response, data, status="200 OK"):
    body = json.dumps(data).encode()
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ] + _CORS_HEADERS)
    return [body]


def _json_error(start_response, status, message):
    body = json.dumps({"error": message}).encode()
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ] + _CORS_HEADERS)
    return [body]


def cors_preflight(start_response):
    start_response("204 No Content", _CORS_HEADERS)
    return [b""]


def _read_body(environ) -> bytes:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        return environ["wsgi.input"].read(length) if length > 0 else b""
    except Exception:
        return b""


def _verify_token(environ) -> bool:
    auth = environ.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth[7:]
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        AccessToken(token)
        return True
    except Exception:
        return False


def _get_settings() -> dict:
    try:
        from apps.plugins.models import PluginConfig
        return PluginConfig.objects.get(key=_PLUGIN_KEY).settings
    except Exception:
        return {}


def _save_settings(updates: dict):
    from apps.plugins.models import PluginConfig
    cfg = PluginConfig.objects.get(key=_PLUGIN_KEY)
    for k, v in updates.items():
        if v is None:
            cfg.settings.pop(k, None)
        else:
            cfg.settings[k] = v
    cfg.save()


def _get_config_mod():
    """Return the already-loaded config module (embyfin's config.py has no
    relative imports of its own, so the fast path always hits in practice —
    the fallback loader is kept for parity with force-fallback/multiview's
    identical helper, and as a safety net if that ever changes).
    """
    import importlib.util
    import sys

    for mod in sys.modules.values():
        if hasattr(mod, 'build_plugin_fields') and hasattr(mod, 'PLUGIN_DB_KEY'):
            return mod

    parent_pkg = None
    for name, mod in sys.modules.items():
        if getattr(mod, 'PLUGIN_DB_KEY', None) == _PLUGIN_KEY and hasattr(mod, 'Plugin'):
            parent_pkg = name
            break

    config_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.py")
    )
    mod_name = f"{parent_pkg}.config" if parent_pkg else f"esc_config_{_PLUGIN_KEY}"

    if mod_name in sys.modules:
        return sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(mod_name, config_path)
    mod = importlib.util.module_from_spec(spec)
    if parent_pkg:
        mod.__package__ = parent_pkg
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _find_plugin_module():
    """Return the loaded plugin package module (src/__init__.py) — it owns
    the shared module-level ``_monitor`` instance."""
    import sys
    for mod in sys.modules.values():
        if getattr(mod, "PLUGIN_DB_KEY", None) == _PLUGIN_KEY and hasattr(mod, "_monitor"):
            return mod
    return None


# ------------------------------------------------------------------
# Masking helpers (ported from the old dashboard.py debug page)
# ------------------------------------------------------------------

_IP_RE = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


def _mask_ip(ip):
    """Mask an IP address, keeping the first octet: 192.168.1.50 → 192.*.*.*"""
    parts = (ip or "").split(".")
    if len(parts) == 4:
        return f"{parts[0]}.*.*.*"
    return "***"


def _mask_url(url):
    """Mask the host portion of a URL: http://192.168.1.50:8096 → http://192.*.*.*:8096"""
    if not url or url == "?":
        return url
    m = re.match(r'(https?://)(.+?)(:\d+)?(/.*)?\s*$', url, re.IGNORECASE)
    if m:
        scheme, host, port, path = m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""
        host = _mask_ip(host) if _IP_RE.fullmatch(host) else "***"
        return f"{scheme}{host}{port}{path}"
    return "***"


def _mask_username(username):
    """Mask a username: alice → a***e, ab → a*"""
    if not username:
        return username
    if len(username) <= 2:
        return username[0] + "*"
    return username[0] + "***" + username[-1]


def _mask_identifier(value):
    return _mask_ip(value) if _IP_RE.fullmatch(value) else _mask_username(value)


def _mask_match_reason(reason):
    """Mask any IP/username embedded in parens, e.g. 'IP match (192.168.1.50)'."""
    if not reason:
        return reason
    return re.sub(r'\(([^)]+)\)', lambda m: f"({_mask_identifier(m.group(1))})", reason)


def _apply_masking(state: dict) -> dict:
    """Mask usernames/IPs/URLs throughout a status payload in place."""
    for ch in (state.get("scan") or {}).values():
        for c in ch.get("clients", []):
            if c.get("ip"):
                c["ip"] = _mask_ip(c["ip"])
            if c.get("username"):
                c["username"] = _mask_username(c["username"])
            if c.get("match_reason"):
                c["match_reason"] = _mask_match_reason(c["match_reason"])

    for srv in state.get("media_servers") or []:
        if srv.get("url"):
            srv["url"] = _mask_url(srv["url"])
        if srv.get("error"):
            srv["error"] = _mask_url(srv["error"])

    state["server_identifiers"] = {
        n: [_mask_identifier(i) for i in idents]
        for n, idents in (state.get("server_identifiers") or {}).items()
    }
    state["identifiers"] = [_mask_identifier(i) for i in (state.get("identifiers") or [])]
    state["resolved_ips"] = [_mask_ip(i) for i in (state.get("resolved_ips") or [])]

    for entry in state.get("stopped_log") or []:
        if entry.get("ip"):
            entry["ip"] = _mask_ip(entry["ip"])
        if entry.get("username"):
            entry["username"] = _mask_username(entry["username"])

    if state.get("emby_error"):
        state["emby_error"] = _mask_url(state["emby_error"])

    return state


# ------------------------------------------------------------------
# Route handlers
# ------------------------------------------------------------------

def handle_auth_token(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_error(start_response, "405 Method Not Allowed", "POST only")

    try:
        data = json.loads(_read_body(environ))
    except Exception:
        return _json_error(start_response, "400 Bad Request", "Invalid JSON")

    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        return _json_error(start_response, "400 Bad Request", "username and password required")

    from django.contrib.auth import authenticate
    user = authenticate(username=username, password=password)
    if user is None:
        return _json_error(start_response, "401 Unauthorized", "Invalid credentials")

    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        return _json_ok(start_response, {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
    except Exception as e:
        logger.error(f"Token generation failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", f"Token error: {e}")


def handle_auth_refresh(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_error(start_response, "405 Method Not Allowed", "POST only")

    try:
        data = json.loads(_read_body(environ))
    except Exception:
        return _json_error(start_response, "400 Bad Request", "Invalid JSON")

    refresh_str = data.get("refresh", "")
    if not refresh_str:
        return _json_error(start_response, "400 Bad Request", "refresh required")

    try:
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError
        token = RefreshToken(refresh_str)
        return _json_ok(start_response, {"access": str(token.access_token)})
    except TokenError:
        return _json_error(start_response, "401 Unauthorized", "Refresh token invalid or expired")


def handle_status(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    try:
        plugin_mod = _find_plugin_module()
        if plugin_mod is None:
            return _json_error(start_response, "503 Service Unavailable", "Plugin module not found")

        state = plugin_mod._monitor.get_debug_state()
        # sets aren't JSON-serializable
        state["recording_channels"] = sorted(state.get("recording_channels") or [])

        if _get_settings().get("mask_sensitive_data") == "enabled":
            state = _apply_masking(state)

        return _json_ok(start_response, state)
    except Exception as e:
        logger.error(f"Status load failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def handle_config(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")

    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET":
        settings = _get_settings()
        ms_count = max(1, int(settings.get("media_server_count", 1)))
        return _json_ok(start_response, {"settings": settings, "media_server_count": ms_count})

    if method in ("PATCH", "POST"):
        try:
            updates = json.loads(_read_body(environ))
        except Exception:
            return _json_error(start_response, "400 Bad Request", "Invalid JSON")
        if not isinstance(updates, dict):
            return _json_error(start_response, "400 Bad Request", "Expected JSON object")
        try:
            _save_settings(updates)
            return _json_ok(start_response, {"status": "ok"})
        except Exception as e:
            logger.error(f"Config save failed: {e}", exc_info=True)
            return _json_error(start_response, "500 Internal Server Error", str(e))

    return _json_error(start_response, "405 Method Not Allowed", "GET or PATCH only")


def handle_fields(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    try:
        settings = _get_settings()
        config_mod = _get_config_mod()
        all_fields = config_mod.build_plugin_fields(settings)

        server_re = re.compile(r"^media_server_(?:url|api_key|identifier)_(\d+)$")
        global_fields = []
        server_fields = {}

        for f in all_fields:
            fid = f.get("id", "")
            if fid.startswith("_") or fid == "media_server_count":
                continue  # skip section headers and the implicit count field
            m = server_re.match(fid)
            if m:
                n = int(m.group(1))
                server_fields.setdefault(n, []).append(f)
            elif fid in ("media_server_url", "media_server_api_key", "media_server_identifier"):
                # server 1 has no numeric suffix
                server_fields.setdefault(1, []).append(f)
            else:
                global_fields.append(f)

        ms_count = max(1, int(settings.get("media_server_count", 1)))
        return _json_ok(start_response, {
            "global": global_fields,
            "media_servers": [{"n": n, "fields": fs} for n, fs in sorted(server_fields.items())],
            "media_server_count": ms_count,
        })

    except Exception as e:
        logger.error(f"Fields load failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def handle_restart(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_error(start_response, "405 Method Not Allowed", "POST only")

    try:
        plugin_mod = _find_plugin_module()
        if plugin_mod is None:
            return _json_error(start_response, "503 Service Unavailable", "Plugin module not found")

        settings = _get_settings()
        # __new__ skips __init__ (which would re-trigger attempt_autostart) —
        # `run()` doesn't touch instance state, it's fine to call unbound.
        result = plugin_mod.Plugin.__new__(plugin_mod.Plugin).run(
            "restart_monitor", {}, {"settings": settings, "logger": logger},
        )
        return _json_ok(start_response, result)
    except Exception as e:
        logger.error(f"Restart failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


# ------------------------------------------------------------------
# Static file serving (configurable mount path)
# ------------------------------------------------------------------

def serve_static(mount_path: str, sub_path: str, start_response):
    """Serve files from dash/static/, under a runtime-configurable mount path.

    mount_path: normalized prefix the server routed on, e.g. "/dash" (or "").
    sub_path: request path relative to mount_path, e.g. "/", "/assets/index-x.js".
    """
    rel = sub_path.lstrip("/") or "index.html"

    safe = os.path.normpath(rel)
    if safe.startswith("..") or os.path.isabs(safe):
        start_response("403 Forbidden", [("Content-Type", "text/plain")])
        return [b"Forbidden\n"]

    file_path = os.path.join(_STATIC_DIR, safe)
    if not os.path.isfile(file_path):
        file_path = os.path.join(_STATIC_DIR, "index.html")
        if not os.path.isfile(file_path):
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found\n"]

    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "application/octet-stream"

    with open(file_path, "rb") as f:
        data = f.read()

    if mime == "text/html":
        base = (mount_path or "") + "/"
        snippet = f'<script>window.__BASE_PATH__={json.dumps(base)};</script>'.encode()
        data = data.replace(b"<head>", b"<head>" + snippet, 1)
        cache_control = "no-cache"
    else:
        cache_control = "public, max-age=3600"

    start_response("200 OK", [
        ("Content-Type", mime),
        ("Content-Length", str(len(data))),
        ("Cache-Control", cache_control),
    ])
    return [data]
