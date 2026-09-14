"""Embyfin Stream Cleanup dashboard server.

Embeds a gevent WSGI server (own port) inside the Dispatcharr plugin process,
since Dispatcharr's plugin system has no route/static-serving hook of its own.
Serves:

  GET  /health                       Health check
  *    {dash_path}/api/*             JSON API (see dash/api.py)
  GET  {dash_path}[/*]               Static SPA (see dash/api.py::serve_static)

`dash_path` (default "/dash") is read from plugin settings on every request
rather than baked in at build/start time, so it can be reconfigured live.

Singleton lifecycle is local-process-only (matching force-fallback/multiview,
not this plugin's old Redis-coordinated approach) — see config.py and
CLAUDE.md for the reasoning. `get_current_server()`/`set_current_server()`
track only what's running in *this* worker process.
"""

import logging
import socket
import threading
import time

logger = logging.getLogger(__name__)

_server_instance = None
_dash_api = None


def _load_dash_api():
    """Load src/dash/api.py using the same file-path loader as other submodules."""
    global _dash_api
    if _dash_api is not None:
        return _dash_api
    import importlib.util
    import os
    import sys
    parent = __name__.rsplit(".", 1)[0] if "." in __name__ else __name__
    mod_name = f"{parent}.dash_api"
    if mod_name in sys.modules:
        _dash_api = sys.modules[mod_name]
        return _dash_api
    api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dash", "api.py")
    spec = importlib.util.spec_from_file_location(mod_name, api_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    _dash_api = mod
    return _dash_api


def get_current_server():
    """Return the active DebugServer instance for this process, or None."""
    return _server_instance


def set_current_server(server):
    """Set the active DebugServer instance for this process."""
    global _server_instance
    _server_instance = server


def _settings() -> dict:
    try:
        from apps.plugins.models import PluginConfig
        return PluginConfig.objects.get(key="embyfin_stream_cleanup").settings
    except Exception:
        return {}


def _normalized_dash_path() -> str:
    """Return the configured mount path, normalized to e.g. '/dash' (no trailing slash), or '' for root."""
    raw = (_settings().get("dash_path") or "/dash").strip()
    if not raw.startswith("/"):
        raw = "/" + raw
    raw = raw.rstrip("/")
    return raw  # "" means mounted at server root


class DebugServer:
    """Embedded gevent WSGI server for the dashboard."""

    def __init__(self, monitor, port=None, host=None):
        from .config import DEFAULT_PORT, DEFAULT_HOST
        from .utils import normalize_host
        self.monitor = monitor
        self.port = port if port is not None else DEFAULT_PORT
        self.host = normalize_host(host, DEFAULT_HOST)
        self._server = None
        self._greenlet = None
        self._thread = None
        self.running = False

    # ------------------------------------------------------------------ WSGI

    def wsgi_app(self, environ, start_response):
        path = environ.get("PATH_INFO", "")

        if path == "/health":
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"OK\n"]

        try:
            return self._route(path, environ, start_response)
        finally:
            # Everything below here can touch Django's ORM (settings, auth)
            # outside of Django's own request cycle, which never runs
            # Django's usual request_finished cleanup. Do it ourselves so
            # connections don't accumulate and eventually go stale.
            try:
                from django.db import close_old_connections
                close_old_connections()
            except Exception:
                pass

    def _route(self, path, environ, start_response):
        dash_path = _normalized_dash_path()

        if _settings().get("dash_enabled") != "enabled":
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found\n"]

        # Redirect the bare mount root (no trailing slash) so the browser's
        # location bar ends in "/" -- the SPA build uses relative asset paths,
        # which resolve against the current document's directory.
        if dash_path and path == dash_path:
            start_response("302 Found", [("Location", dash_path + "/")])
            return [b""]

        prefix = dash_path if dash_path else ""
        if path == prefix or path.startswith(prefix + "/"):
            sub = path[len(prefix):] or "/"
            if sub.startswith("/api/"):
                return self._handle_api(sub, environ, start_response)
            return _load_dash_api().serve_static(dash_path, sub, start_response)

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    def _handle_api(self, sub_path, environ, start_response):
        api = _load_dash_api()

        if sub_path == "/api/auth/token":
            return api.handle_auth_token(environ, start_response)
        if sub_path == "/api/auth/refresh":
            return api.handle_auth_refresh(environ, start_response)
        if sub_path == "/api/status":
            return api.handle_status(environ, start_response)
        if sub_path == "/api/config":
            return api.handle_config(environ, start_response)
        if sub_path == "/api/fields":
            return api.handle_fields(environ, start_response)
        if sub_path == "/api/restart":
            return api.handle_restart(environ, start_response)

        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found\n"]

    # ------------------------------------------------------------- lifecycle

    def start(self) -> bool:
        """Start the dashboard server in a dedicated native thread.

        A gevent WSGI server's ``serve_forever`` greenlet only actually runs
        if *something* keeps pumping the hub on whatever OS thread it was
        spawned on. Fire-and-forget ``gevent.spawn()`` from an arbitrary
        caller thread (the old approach here) only happened to work when
        called from a thread that was already continuously pumped by other
        gevent activity (e.g. the request-handling context ``Plugin()``
        construction runs on) -- it silently never binds when called from a
        thread with no other gevent activity, like the monitor's own poll
        loop thread. Matches dispatcharr-exporter's ``MetricsServer.start()``
        pattern: a dedicated thread creates the server, spawns its
        ``serve_forever`` greenlet, then loops on ``gevent.sleep()`` forever
        to keep that thread's hub alive for as long as the server should run.
        ``start()`` blocks briefly to confirm the bind actually happened
        before reporting success/failure, instead of assuming it will.
        """
        if self.running:
            logger.warning("Dashboard server is already running")
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.close()
        except OSError as e:
            logger.warning(f"Embyfin dashboard: port {self.port} already taken, skipping ({e})")
            return False

        try:
            from gevent import pywsgi
        except ImportError:
            logger.error("gevent is not installed; cannot start the dashboard server")
            return False

        def _run():
            try:
                from gevent import spawn, sleep as gsleep

                self._server = pywsgi.WSGIServer(
                    (self.host, self.port), self.wsgi_app, log=None,
                )
                self.running = True
                set_current_server(self)
                self._greenlet = spawn(self._server.serve_forever)

                # Keep this thread's gevent hub alive for as long as the
                # server should run -- nothing else pumps it otherwise.
                while self.running:
                    gsleep(1)
            except OSError as e:
                # EADDRINUSE here means a concurrent worker won the race between
                # our test-bind above and this re-bind -- expected on multi-worker
                # startup, not an error.
                logger.info(f"Embyfin dashboard: port {self.port} taken by concurrent worker ({e})")
            except Exception as e:  # noqa: BLE001
                logger.error(f"Dashboard server crashed: {e}", exc_info=True)
            finally:
                self.running = False
                if get_current_server() is self:
                    set_current_server(None)

        self._thread = threading.Thread(
            target=_run, daemon=True, name="embyfin-dashboard-server",
        )
        self._thread.start()

        # Brief wait for the server thread to actually bind and confirm.
        deadline = time.time() + 2.0
        while time.time() < deadline and not self.running and self._thread.is_alive():
            time.sleep(0.05)

        return self.running

    def stop(self) -> bool:
        if not self.running:
            return False
        if self._server:
            try:
                self._server.stop(timeout=5)
            except Exception as e:
                logger.warning(f"Error during server.stop(): {e}")
        self.running = False
        set_current_server(None)
        logger.info("Dashboard server stopped")
        return True

    def is_running(self) -> bool:
        return self.running and self._thread is not None and self._thread.is_alive()
