"""gevent WSGI metrics server.

Binds to a configurable host:port and serves:
  GET /          Landing page with links
  GET /metrics   Prometheus text-format metrics
  GET /health    Simple health check
"""

import logging
import socket
import threading
import time

from .config import PLUGIN_CONFIG, REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP, DEFAULT_PORT, DEFAULT_HOST, HEARTBEAT_TTL
from .utils import get_redis_client, read_redis_flag, normalize_host, get_dispatcharr_version, compare_versions

logger = logging.getLogger(__name__)

# Module-level reference to the currently running server instance (per process).
_metrics_server = None


def get_current_server():
    """Return the active MetricsServer instance for this process, or None."""
    return _metrics_server


def set_current_server(server):
    """Set the active MetricsServer instance for this process."""
    global _metrics_server
    _metrics_server = server


class MetricsServer:
    """Lightweight gevent WSGI server that exposes Prometheus metrics."""

    def __init__(self, collector, port=None, host=None):
        self.collector = collector
        self.port = port if port is not None else DEFAULT_PORT
        self.host = normalize_host(host, DEFAULT_HOST)
        logger.info(
            f"MetricsServer initialised with host='{self.host}', port={self.port}"
        )
        self.server_thread = None
        self.server = None
        self.running = False
        self.settings = {}

    # ── Version helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _get_dispatcharr_version():
        """Deprecated shim kept for callers that used the old static method."""
        return get_dispatcharr_version()

    @staticmethod
    def _compare_versions(current, minimum):
        """Deprecated shim kept for callers that used the old static method."""
        return compare_versions(current, minimum)

    # ── Port verification ────────────────────────────────────────────────────

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

    # ── WSGI application ─────────────────────────────────────────────────────

    def wsgi_app(self, environ, start_response):
        """Handle a single HTTP request."""
        path = environ.get('PATH_INFO', '/')

        if path == '/metrics':
            try:
                metrics_text = self.collector.collect_metrics(settings=self.settings)
                start_response('200 OK', [('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')])
                return [metrics_text.encode('utf-8')]
            except Exception as e:
                logger.error(f"Error generating metrics: {e}", exc_info=True)
                start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
                return [f"# Error: {str(e)}\n".encode('utf-8')]

        elif path == '/health':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b"OK\n"]

        elif path == '/':
            plugin_name = PLUGIN_CONFIG.get('name', 'Dispatcharr Exporter')
            plugin_version = PLUGIN_CONFIG.get('version', 'unknown version').lstrip('-')
            plugin_description = PLUGIN_CONFIG.get('description', 'This exporter provides Prometheus metrics for Dispatcharr.')
            repo_url = PLUGIN_CONFIG.get('repo_url', 'https://github.com/sethwv/dispatcharr-exporter')
            releases_url = f"{repo_url}/releases"

            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{plugin_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{ margin-top: 0; color: #333; }}
        .version {{ color: #999; font-size: 14px; margin-top: -10px; margin-bottom: 20px; }}
        p {{ color: #666; line-height: 1.6; }}
        a {{ color: #0066cc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .links {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
        .links a {{ display: inline-block; margin-right: 20px; font-weight: 500; }}
        .external-links {{ margin-top: 20px; font-size: 14px; }}
        .external-links a {{ margin-right: 15px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{plugin_name}</h1>
        <div class="version">{plugin_version}</div>
        <p>{plugin_description.split('. ')[0]}.</p>
        <div class="external-links">
            <a href="{repo_url}" target="_blank">GitHub Repository</a>
            <a href="{releases_url}" target="_blank">Releases</a>
        </div>
        <div class="links">
            <a href="/metrics">View Metrics</a>
            <a href="/health">Health Check</a>
        </div>
    </div>
</body>
</html>"""
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [html.encode('utf-8')]

        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b"Not Found\n"]

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self, settings=None) -> bool:
        """Start the metrics server in a background thread.

        Returns True on success, False if the server could not be started.
        """
        if self.running:
            logger.warning("Metrics server is already running")
            return False

        # Guard against duplicate servers across workers via Redis
        redis_client = get_redis_client()
        if redis_client and read_redis_flag(redis_client, REDIS_KEY_RUNNING):
            logger.warning(
                "Another metrics server instance is already running (detected via Redis)"
            )
            return False

        # Guard against a duplicate in the same process
        current = get_current_server()
        if current and current.is_running():
            logger.warning("Another metrics server instance is already running in this process")
            return False

        # Check Dispatcharr version
        min_version = PLUGIN_CONFIG.get("min_dispatcharr_version", "1.0.0")
        try:
            dispatcharr_version, dispatcharr_timestamp, full_version = get_dispatcharr_version()
            if dispatcharr_version != "unknown":
                if dispatcharr_timestamp:
                    logger.info(f"Dev build detected ({full_version}), skipping version check")
                elif not compare_versions(dispatcharr_version, min_version):
                    logger.error(
                        f"Dispatcharr {dispatcharr_version} does not meet minimum requirement {min_version}"
                    )
                    return False
                else:
                    logger.info(f"Dispatcharr {dispatcharr_version} meets minimum requirement {min_version}")
            else:
                logger.warning("Could not determine Dispatcharr version, skipping check")
        except Exception as e:
            logger.warning(f"Could not verify Dispatcharr version: {e}. Proceeding anyway.")

        # Validate host / port binding
        logger.info(f"Attempting to bind to host='{self.host}', port={self.port}")
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
                    logger.debug(f"Starting gevent WSGI server on {self.host}:{self.port}")

                    suppress_logs = self.settings.get('suppress_access_logs', True)
                    server_kwargs = {
                        'listener': (self.host, self.port),
                        'application': self.wsgi_app,
                    }
                    if suppress_logs:
                        server_kwargs['log'] = None

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

                    logger.info(f"Metrics server started on http://{self.host}:{self.port}/metrics")

                    from gevent import spawn, sleep
                    spawn(self.server.serve_forever)

                    # Monitor for Redis stop signal
                    monitor_redis = get_redis_client()
                    check_count = 0
                    while self.running:
                        try:
                            if monitor_redis and read_redis_flag(monitor_redis, REDIS_KEY_STOP):
                                logger.info("Stop signal detected via Redis, shutting down")
                                self.running = False
                                try:
                                    self.server.stop(timeout=5)
                                except Exception as e:
                                    logger.warning(f"Error during server.stop(): {e}")
                                self._verify_stopped(timeout=3)
                                break
                            elif not monitor_redis:
                                monitor_redis = get_redis_client()

                            check_count += 1
                            if check_count % 60 == 0:
                                logger.debug(
                                    f"Stop signal monitor alive (check #{check_count}), "
                                    f"server running on {self.host}:{self.port}"
                                )
                        except Exception as e:
                            logger.warning(f"Error checking stop signal (check #{check_count}): {e}")
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

                    # Cleanup Redis flags after stopping
                    _rc = get_redis_client()
                    if _rc:
                        try:
                            _rc.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP)
                        except Exception as e:
                            logger.warning(f"Could not clear Redis flags on shutdown: {e}")

                    set_current_server(None)
                    logger.info("Metrics server stopped and cleaned up")

                except Exception as e:
                    logger.error(f"Error running metrics server: {e}", exc_info=True)
                    self.running = False

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()

            # Brief wait for the server to bind and set running=True
            time.sleep(0.5)

            if self.running:
                return True
            else:
                return False

        except ImportError:
            logger.error("gevent is not installed")
            return False

    def stop(self) -> bool:
        """Stop the metrics server."""
        if not self.running:
            return False

        logger.info("Stopping metrics server...")

        if self.server:
            try:
                self.server.stop(timeout=5)
            except Exception as e:
                logger.warning(f"Error during server.stop(): {e}")
            self._verify_stopped(timeout=3)

        self.running = False
        set_current_server(None)

        # Clear Redis flags
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT)
            except Exception as e:
                logger.warning(f"Could not clear Redis flags: {e}")

        return True

    def is_running(self) -> bool:
        """Return True if the server thread is alive and the server is marked running."""
        return self.running and self.server_thread is not None and self.server_thread.is_alive()
