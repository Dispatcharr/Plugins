"""Debug HTTP server (optional).

Manages the gevent WSGI server lifecycle for the debug dashboard.
All HTML rendering is handled by the dashboard module.

Routes:
  GET  /        Landing page
  GET  /debug   Live debug dashboard (auto-refreshes)
  GET  /health  Health check
"""

import logging
import socket
import threading
import time

from .config import (
    PLUGIN_CONFIG, REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT,
    REDIS_KEY_STOP, DEFAULT_PORT, DEFAULT_HOST,
    HEARTBEAT_TTL,
)
from .dashboard import render_debug_page, render_landing_page
from .utils import get_redis_client, read_redis_flag, normalize_host

logger = logging.getLogger(__name__)

# Module-level reference to the currently running server instance (per process).
_debug_server = None


def get_current_server():
    """Return the active DebugServer instance for this process, or None."""
    return _debug_server


def set_current_server(server):
    """Set the active DebugServer instance for this process."""
    global _debug_server
    _debug_server = server


class DebugServer:
    """Lightweight gevent WSGI server for the debug dashboard."""

    def __init__(self, monitor, port=None, host=None):
        self.monitor = monitor
        self.port = port if port is not None else DEFAULT_PORT
        self.host = normalize_host(host, DEFAULT_HOST)
        logger.info(f"DebugServer initialised with host='{self.host}', port={self.port}")
        self.server_thread = None
        self.server = None
        self.running = False
        self.settings = {}

    # -- Port verification ----------------------------------------------------

    def _verify_stopped(self, timeout=3):
        """Block until the server port is confirmed free (up to *timeout* seconds)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(0.5)
                sock.bind((self.host, self.port))
                sock.close()
                logger.info(f"Verified port {self.port} is free after server stop")
                return True
            except OSError:
                try:
                    sock.close()
                except Exception:
                    pass
                time.sleep(0.2)

        logger.warning(
            f"Port {self.port} still in use after {timeout}s - server may not have stopped cleanly"
        )
        return False

    # -- WSGI application -----------------------------------------------------

    def wsgi_app(self, environ, start_response):
        """Handle a single HTTP request."""
        path = environ.get('PATH_INFO', '/')

        if path == '/health':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b"OK\n"]

        elif path == '/debug':
            return self._serve_debug_page(start_response)

        elif path == '/':
            return self._serve_landing_page(start_response)

        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found\n"]

    # -- Debug page ------------------------------------------------------------

    def _serve_debug_page(self, start_response):
        try:
            debug_state = self.monitor.get_debug_state()
            html = render_debug_page(debug_state, self.settings)
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [html.encode('utf-8')]
        except Exception as e:
            logger.error(f"Error generating debug page: {e}", exc_info=True)
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b"Error generating debug page\n"]

    # -- Landing page ----------------------------------------------------------

    def _serve_landing_page(self, start_response):
        html = render_landing_page(self.monitor)
        start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
        return [html.encode('utf-8')]

    # -- Lifecycle -------------------------------------------------------------

    def start(self, settings=None) -> bool:
        """Start the debug server in a background thread."""
        if self.running:
            logger.warning("Debug server is already running")
            return False

        # Guard against duplicate servers across workers via Redis
        redis_client = get_redis_client()
        if redis_client and read_redis_flag(redis_client, REDIS_KEY_RUNNING):
            logger.warning("Another debug server instance is already running (detected via Redis)")
            return False

        current = get_current_server()
        if current and current.is_running():
            logger.warning("Another debug server instance is already running in this process")
            return False

        # Validate host / port binding
        logger.info(f"Attempting to bind debug server to host='{self.host}', port={self.port}")
        try:
            try:
                socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
            except socket.gaierror as e:
                logger.error(
                    f"Cannot resolve host '{self.host}': {e}. "
                    f"In Docker, use '0.0.0.0' to bind to all interfaces."
                )
                return False

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.close()
        except OSError as e:
            if e.errno == -2 or 'Name or service not known' in str(e):
                logger.error(
                    f"Cannot resolve host '{self.host}': {e}. "
                    f"In Docker, use '0.0.0.0' to bind to all interfaces."
                )
            else:
                logger.error(f"Cannot bind to {self.host}:{self.port}: {e}")
            return False

        self.settings = settings or {}

        try:
            from gevent import pywsgi

            def run_server():
                try:
                    server_kwargs = {
                        'listener': (self.host, self.port),
                        'application': self.wsgi_app,
                        'log': None,
                    }

                    self.server = pywsgi.WSGIServer(**server_kwargs)
                    self.running = True
                    set_current_server(self)

                    # Announce via Redis (with heartbeat TTL)
                    _rc = get_redis_client()
                    if _rc:
                        try:
                            _rc.set(REDIS_KEY_RUNNING, "1", ex=HEARTBEAT_TTL)
                            _rc.set(REDIS_KEY_HOST, self.host, ex=HEARTBEAT_TTL)
                            _rc.set(REDIS_KEY_PORT, str(self.port), ex=HEARTBEAT_TTL)
                        except Exception as e:
                            logger.warning(f"Could not set Redis running flags: {e}")

                    logger.info(f"Debug server started on http://{self.host}:{self.port}/")

                    from gevent import spawn, sleep
                    spawn(self.server.serve_forever)

                    # Monitor for Redis stop signal
                    monitor_redis = get_redis_client()
                    while self.running:
                        try:
                            if monitor_redis and read_redis_flag(monitor_redis, REDIS_KEY_STOP):
                                logger.info("Debug server stop signal detected via Redis")
                                self.running = False
                                try:
                                    self.server.stop(timeout=5)
                                except Exception as e:
                                    logger.warning(f"Error during server.stop(): {e}")
                                self._verify_stopped(timeout=3)
                                break
                            elif not monitor_redis:
                                monitor_redis = get_redis_client()
                        except Exception as e:
                            logger.warning(f"Error checking stop signal: {e}")
                            monitor_redis = get_redis_client()

                        # Refresh heartbeat so keys don't expire while alive
                        if monitor_redis:
                            try:
                                monitor_redis.set(REDIS_KEY_RUNNING, "1", ex=HEARTBEAT_TTL)
                                monitor_redis.expire(REDIS_KEY_HOST, HEARTBEAT_TTL)
                                monitor_redis.expire(REDIS_KEY_PORT, HEARTBEAT_TTL)
                            except Exception:
                                pass

                        sleep(1)

                    # Cleanup Redis flags
                    _rc = get_redis_client()
                    if _rc:
                        try:
                            _rc.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP)
                        except Exception as e:
                            logger.warning(f"Could not clear Redis flags on shutdown: {e}")

                    set_current_server(None)
                    logger.info("Debug server stopped and cleaned up")

                except Exception as e:
                    logger.error(f"Error running debug server: {e}", exc_info=True)
                    self.running = False

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()

            time.sleep(0.5)
            return self.running

        except ImportError:
            logger.error("gevent is not installed")
            return False

    def stop(self) -> bool:
        """Stop the debug server."""
        if not self.running:
            return False

        logger.info("Stopping debug server...")

        if self.server:
            try:
                self.server.stop(timeout=5)
            except Exception as e:
                logger.warning(f"Error during server.stop(): {e}")
            self._verify_stopped(timeout=3)

        self.running = False
        set_current_server(None)

        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT)
            except Exception as e:
                logger.warning(f"Could not clear Redis flags: {e}")

        return True

    def is_running(self) -> bool:
        return self.running and self.server_thread is not None and self.server_thread.is_alive()
