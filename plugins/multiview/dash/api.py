"""REST API handlers for /api/* and static file serving under the dashboard's
runtime-configurable mount path (dash_path setting, default /dash)."""

import base64
import json
import logging
import mimetypes
import os
import re

logger = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKGROUNDS_DIR = os.path.join(_PLUGIN_DIR, "style_backgrounds")
_MAX_BACKGROUND_BYTES = 5 * 1024 * 1024
_PLUGIN_KEY = "multiview"

_CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS"),
    ("Access-Control-Allow-Headers", "Authorization, Content-Type"),
]


def _json_ok(start_response, data):
    body = json.dumps(data).encode()
    start_response("200 OK", [
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
    config_mod = _get_config_mod()
    try:
        from apps.plugins.models import PluginConfig
        cfg = PluginConfig.objects.get(key=_PLUGIN_KEY)
    except Exception:
        settings, _ = config_mod.ensure_layout_order({})
        settings, _ = config_mod.reconcile_layout_count(settings)
        settings, _ = config_mod.ensure_custom_layout_order(settings)
        return settings

    settings, changed1 = config_mod.ensure_layout_order(cfg.settings)
    settings, changed2 = config_mod.reconcile_layout_count(settings)
    settings, changed3 = config_mod.ensure_custom_layout_order(settings)
    if changed1 or changed2 or changed3:
        cfg.settings = settings
        cfg.save()
    return settings


def _save_settings(updates: dict):
    from apps.plugins.models import PluginConfig
    cfg = PluginConfig.objects.get(key=_PLUGIN_KEY)
    for k, v in updates.items():
        if v is None:
            cfg.settings.pop(k, None)
        else:
            cfg.settings[k] = v
    # Keep the legacy multiview_count field (still authoritative for
    # reconcile_layout_count, which detects native-settings-page edits) in
    # sync whenever the dashboard itself changes multiview_order -- otherwise
    # reconcile_layout_count treats the dashboard's own change as drift and
    # deletes it back out on the very next settings read.
    if updates.get("multiview_order") is not None:
        cfg.settings["multiview_count"] = len(cfg.settings.get("multiview_order") or [])
    cfg.save()


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


def _plugin_version() -> str:
    try:
        with open(os.path.join(_PLUGIN_DIR, "plugin.json")) as f:
            return json.load(f).get("version", "")
    except Exception:
        return ""


def _dispatcharr_version() -> str:
    # Dispatcharr's version lives in a plain top-level `version.py` module
    # (not under the `dispatcharr` package) -- not a stable public API, so
    # this is defensive: a future Dispatcharr release could move/remove it.
    try:
        import version as _dv
        return getattr(_dv, "__version__", "")
    except Exception:
        return ""


def handle_config(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")

    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET":
        settings = _get_settings()
        layout_count = len(settings.get("multiview_order", []))
        return _json_ok(start_response, {
            "settings": settings,
            "layout_count": layout_count,
            "plugin_version": _plugin_version(),
            "dispatcharr_version": _dispatcharr_version(),
        })

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


def handle_channels(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    try:
        from apps.channels.models import Channel
        from apps.m3u.models import M3UAccount

        excluded = set()
        try:
            acct = M3UAccount.objects.filter(name="Dispatcharr Multiview").first()
            if acct:
                for field_name in ("m3u_account", "account", "m3u_account_id", "source"):
                    try:
                        excluded = set(
                            Channel.objects.filter(**{field_name: acct}).values_list("id", flat=True)
                        )
                        break
                    except Exception:
                        continue
        except Exception:
            pass

        channels = []
        for ch in Channel.objects.order_by("channel_number").values("id", "name", "channel_number").distinct():
            if ch["id"] in excluded:
                continue
            num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
            channels.append({
                "id": str(ch["id"]),
                "name": ch["name"],
                "channel_number": ch["channel_number"],
                "label": f"{num} - {ch['name']}",
            })
        return _json_ok(start_response, channels)

    except Exception as e:
        logger.error(f"Channel list failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def handle_refresh(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_error(start_response, "405 Method Not Allowed", "POST only")

    try:
        import sys
        plugin_mod = None
        for mod in sys.modules.values():
            if getattr(mod, "PLUGIN_DB_KEY", None) == _PLUGIN_KEY and hasattr(mod, "Plugin"):
                plugin_mod = mod
                break
        if plugin_mod is None:
            return _json_error(start_response, "503 Service Unavailable", "Plugin module not found")
        result = plugin_mod.Plugin.__new__(plugin_mod.Plugin)._generate_m3u()
        return _json_ok(start_response, result)
    except Exception as e:
        logger.error(f"Refresh failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def handle_streams_list(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    server = globals().get("_server")
    active = server.get_active_streams() if server else []
    return _json_ok(start_response, {"active": active})


def handle_streams_restart(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_error(start_response, "405 Method Not Allowed", "POST only")

    try:
        # _server is injected by MultiviewServer._handle_api on every request
        server = globals().get("_server")
        if server is None:
            return _json_error(start_response, "503 Service Unavailable", "Server not found")
        data = {}
        body = _read_body(environ)
        if body:
            try:
                data = json.loads(body)
            except Exception:
                pass
        n = data.get("n")
        channel_idx = data.get("channel_idx")
        if n is not None and channel_idx is not None:
            # Reconnect a specific channel within a layout (non-destructive)
            ok = server.reconnect_channel(n, int(channel_idx))
            return _json_ok(start_response, {"status": "ok", "reconnected": ok})
        killed = server.kill_stream(n) if n is not None else server.kill_active_streams()
        return _json_ok(start_response, {"status": "ok", "killed": killed})
    except Exception as e:
        logger.error(f"Streams restart failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def _get_config_mod():
    """Return the already-loaded config module, or load it with the correct package context.

    config.py uses relative imports (from . import deps), so it must be loaded
    under the plugin's parent package name -- not a standalone name -- otherwise
    Python raises 'attempted relative import with no known parent package'.
    """
    import importlib.util
    import sys

    # Fast path: already loaded under any name
    for mod in sys.modules.values():
        if hasattr(mod, 'build_plugin_fields') and hasattr(mod, 'ENCODER_PRESETS'):
            return mod

    # Find the plugin's own package name so relative imports resolve correctly
    parent_pkg = None
    for name, mod in sys.modules.items():
        if getattr(mod, 'PLUGIN_DB_KEY', None) == _PLUGIN_KEY and hasattr(mod, 'Plugin'):
            parent_pkg = name
            break

    config_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.py")
    )
    mod_name = f"{parent_pkg}.config" if parent_pkg else f"mv_config_{_PLUGIN_KEY}"

    if mod_name in sys.modules:
        return sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(mod_name, config_path)
    mod = importlib.util.module_from_spec(spec)
    if parent_pkg:
        mod.__package__ = parent_pkg
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _get_layouts_mod():
    """Return the already-loaded layouts module, or load it standalone.

    dash/api.py isn't always imported under the plugin's own package (see
    _get_config_mod's docstring for why that dance is needed there), so a
    plain top-level `from . import layouts` here can fail the same way even
    though layouts.py itself has no relative imports of its own.
    """
    import importlib.util
    import sys

    for mod in sys.modules.values():
        if hasattr(mod, 'tile_rects') and hasattr(mod, '_even'):
            return mod

    layouts_path = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "layouts.py")
    )
    mod_name = f"mv_layouts_{_PLUGIN_KEY}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(mod_name, layouts_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def handle_styles_preview(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    try:
        from urllib.parse import parse_qs
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        layout = (qs.get("layout") or ["auto"])[0]
        channel_count = int((qs.get("channel_count") or ["4"])[0])
    except Exception:
        return _json_error(start_response, "400 Bad Request", "Invalid layout/channel_count")

    try:
        layouts_mod = _get_layouts_mod()
        # Fixed dummy canvas -- only the fractions matter, geometry is
        # resolution-independent by construction (tile_rects rounds to even
        # pixels, so a larger canvas keeps more precision).
        out_w, out_h = 1920, 1080
        rects = layouts_mod.tile_rects(layout, channel_count, out_w, out_h)
        tiles = [
            [x / out_w, y / out_h, w / out_w, h / out_h, valign, halign]
            for (x, y, w, h, valign, halign) in rects
        ]
        return _json_ok(start_response, {"tiles": tiles})
    except Exception as e:
        logger.error(f"Style preview failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def _sanitize_filename(name: str) -> str:
    base = os.path.basename(name or "background")
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base or "background"


def handle_style_background(environ, start_response):
    """GET serves a style's saved background image; POST uploads/replaces one.

    Uploads are base64-in-JSON, not multipart -- this raw WSGI app has no
    form-parsing anywhere, matching every other endpoint's json-in/json-out
    convention. Image validity is only checked lightly (size cap) rather than
    decoded here: PyAV must never be imported into this gevent-patched
    process (compositor_worker.py runs it in a separate plain-CPython
    subprocess specifically to avoid that conflict) -- a bad file just fails
    gracefully later when the worker tries to decode it, same as the
    existing per-channel logo fallback already handles decode failures.
    """
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")

    method = environ.get("REQUEST_METHOD", "GET")

    if method == "GET":
        from urllib.parse import parse_qs
        qs = parse_qs(environ.get("QUERY_STRING", ""))
        style_id = (qs.get("style_id") or [""])[0]
        if not style_id:
            return _json_error(start_response, "400 Bad Request", "style_id required")
        settings = _get_settings()
        style = settings.get("multiview_custom_layouts", {}).get(style_id)
        filename = style.get("background_image") if style else None
        if not filename:
            return _json_error(start_response, "404 Not Found", "No background image set")
        path = os.path.join(_BACKGROUNDS_DIR, filename)
        if not os.path.isfile(path):
            return _json_error(start_response, "404 Not Found", "Background image file missing")
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            return _json_error(start_response, "500 Internal Server Error", str(e))
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        start_response("200 OK", [
            ("Content-Type", content_type),
            ("Content-Length", str(len(data))),
        ] + _CORS_HEADERS)
        return [data]

    if method == "POST":
        try:
            body = json.loads(_read_body(environ))
        except Exception:
            return _json_error(start_response, "400 Bad Request", "Invalid JSON")
        style_id = body.get("style_id")
        filename = body.get("filename")
        data_b64 = body.get("data_base64")
        if not style_id or not filename or not data_b64:
            return _json_error(start_response, "400 Bad Request", "style_id, filename, data_base64 required")

        try:
            raw = base64.b64decode(data_b64)
        except Exception:
            return _json_error(start_response, "400 Bad Request", "Invalid base64 data")
        if len(raw) > _MAX_BACKGROUND_BYTES:
            return _json_error(start_response, "400 Bad Request", f"Image too large (max {_MAX_BACKGROUND_BYTES // (1024*1024)}MB)")

        stored_name = f"{style_id}_{_sanitize_filename(filename)}"
        try:
            os.makedirs(_BACKGROUNDS_DIR, exist_ok=True)
            with open(os.path.join(_BACKGROUNDS_DIR, stored_name), "wb") as f:
                f.write(raw)
        except OSError as e:
            return _json_error(start_response, "500 Internal Server Error", f"Failed to save image: {e}")

        try:
            settings = _get_settings()
            custom_layouts = dict(settings.get("multiview_custom_layouts", {}))
            style = dict(custom_layouts.get(style_id, {}))
            style["background_image"] = stored_name
            custom_layouts[style_id] = style
            _save_settings({"multiview_custom_layouts": custom_layouts})
        except Exception as e:
            logger.error(f"Failed to save background_image reference: {e}", exc_info=True)
            return _json_error(start_response, "500 Internal Server Error", str(e))

        return _json_ok(start_response, {"status": "ok", "filename": stored_name})

    return _json_error(start_response, "405 Method Not Allowed", "GET or POST only")


def handle_fields(environ, start_response):
    if environ.get("REQUEST_METHOD") == "OPTIONS":
        return cors_preflight(start_response)
    if not _verify_token(environ):
        return _json_error(start_response, "401 Unauthorized", "Authentication required")
    if environ.get("REQUEST_METHOD") != "GET":
        return _json_error(start_response, "405 Method Not Allowed", "GET only")

    try:
        import re
        settings = _get_settings()
        config_mod = _get_config_mod()
        all_fields = config_mod.build_plugin_fields(settings)
        order = settings.get("multiview_order", [])

        layout_re = re.compile(r"^multiview_([0-9a-f]{8})_")
        global_fields = []
        warnings = []
        layout_fields = {}

        for f in all_fields:
            fid = f.get("id", "")
            if fid.startswith("_warn") and fid != "_warnings_header":
                warnings.append(f)
            elif fid.startswith("_") or fid == "multiview_count":
                continue  # skip section headers and the native-page-only count field
            else:
                m = layout_re.match(fid)
                if m:
                    layout_fields.setdefault(m.group(1), []).append(f)
                else:
                    global_fields.append(f)

        return _json_ok(start_response, {
            "warnings": warnings,
            "global": global_fields,
            "layouts": [
                {"n": layout_id, "position": idx + 1, "fields": layout_fields.get(layout_id, [])}
                for idx, layout_id in enumerate(order)
            ],
            "layout_count": len(order),
        })

    except Exception as e:
        logger.error(f"Fields load failed: {e}", exc_info=True)
        return _json_error(start_response, "500 Internal Server Error", str(e))


def serve_static(mount_path: str, sub_path: str, start_response):
    """Serve files from dash/static/, under a runtime-configurable mount path.

    mount_path: normalized prefix the server routed on, e.g. "/dash".
    sub_path: request path relative to mount_path, e.g. "/", "/assets/index-x.js".
    """
    rel = sub_path.lstrip("/") or "index.html"

    # Block path traversal
    safe = os.path.normpath(rel)
    if safe.startswith("..") or os.path.isabs(safe):
        start_response("403 Forbidden", [("Content-Type", "text/plain")])
        return [b"Forbidden\n"]

    file_path = os.path.join(_STATIC_DIR, safe)
    if not os.path.isfile(file_path):
        # SPA fallback: always serve index.html for unknown paths
        file_path = os.path.join(_STATIC_DIR, "index.html")
        if not os.path.isfile(file_path):
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found\n"]

    mime, _ = mimetypes.guess_type(file_path)
    mime = mime or "application/octet-stream"

    with open(file_path, "rb") as f:
        data = f.read()

    if mime == "text/html":
        # The SPA build uses relative asset paths (base: './'), so it doesn't
        # know its own mount path at build time. Inject it at request time so
        # the frontend can build correct API/asset URLs.
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
