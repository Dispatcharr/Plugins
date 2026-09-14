"""Dispatcharr Prometheus Exporter - package root.

Dispatcharr discovers the plugin by importing this package and looking for
the ``Plugin`` class.  All metric collection, server management, and
auto-start logic live in their own modules; this file only contains the
plugin API.
"""

import logging
import os
import time

from .config import (
    PLUGIN_CONFIG, PLUGIN_FIELDS,
    REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP,
    DEFAULT_PORT, DEFAULT_HOST,
)
from .collector import PrometheusMetricsCollector
from .server import MetricsServer, get_current_server
from .autostart import attempt_autostart
from .utils import get_redis_client, read_redis_flag, normalize_host, redis_decode

logger = logging.getLogger(__name__)


class Plugin:
    """Dispatcharr Plugin - Prometheus metrics exporter."""

    name        = PLUGIN_CONFIG["name"]
    description = PLUGIN_CONFIG["description"]
    version     = PLUGIN_CONFIG["version"]
    author      = PLUGIN_CONFIG["author"]

    fields  = PLUGIN_FIELDS

    actions = [
        {
            "id": "restart_server",
            "label": "Start / Restart Metrics Server",
            "description": "Start or restart the HTTP metrics server",
            "button_label": "Start / Restart",
            "button_variant": "filled",
            "button_color": "green",
        },
        {
            "id": "stop_server",
            "label": "Stop Metrics Server",
            "description": "Stop the HTTP metrics server",
            "button_label": "Stop Server",
            "button_variant": "filled",
            "button_color": "red",
        },
        {
            "id": "server_status",
            "label": "Server Status",
            "description": "Check if the metrics server is running and get endpoint URL",
            "button_label": "Check Status",
            "button_variant": "filled",
            "button_color": "blue",
        },
    ]

    # ── Initialisation ───────────────────────────────────────────────────────

    def __init__(self):
        self.collector = PrometheusMetricsCollector()
        self._cleanup_root_pycache()
        # Spawn (at most once per process) a background thread that races via
        # Redis NX to become the leader and start the server if auto_start is on.
        attempt_autostart(self.collector)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _cleanup_root_pycache(self):
        """Warn if root-owned __pycache__ dirs exist (Dispatcharr startup artefact)."""
        try:
            if os.getuid() != 0:
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                root_owned = []
                try:
                    for root_dir, dirs, _files in os.walk(plugin_dir):
                        if "__pycache__" in dirs:
                            pycache_path = os.path.join(root_dir, "__pycache__")
                            try:
                                if os.stat(pycache_path).st_uid == 0:
                                    root_owned.append(pycache_path)
                            except (OSError, PermissionError):
                                pass
                except (OSError, PermissionError):
                    pass

                if root_owned:
                    logger.warning(
                        f"Detected {len(root_owned)} root-owned __pycache__ directories in plugin. "
                        f"This is caused by Dispatcharr running 'manage.py migrate/collectstatic' as root. "
                        f"Plugin updates may fail. SOLUTION: Add 'PYTHONDONTWRITEBYTECODE=1' to your Docker "
                        f"environment, or run: "
                        f"docker exec -u root <container> find {plugin_dir} -name __pycache__ -exec rm -rf {{}} +"
                    )
        except Exception as e:
            logger.debug(f"Could not check for root-owned __pycache__: {e}")

    def _get_redis_server_state(self):
        """Return (redis_client, server_running, server_host, server_port)."""
        redis_client = get_redis_client()
        server_running = False
        server_host = None
        server_port = None

        try:
            if redis_client:
                server_running = read_redis_flag(redis_client, REDIS_KEY_RUNNING)
                if server_running:
                    server_host = redis_decode(redis_client.get(REDIS_KEY_HOST)) or DEFAULT_HOST
                    server_port = redis_decode(redis_client.get(REDIS_KEY_PORT)) or str(DEFAULT_PORT)
        except Exception as e:
            logger.debug(f"Could not read Redis server state: {e}")

        return redis_client, server_running, server_host, server_port

    # ── Action dispatcher ────────────────────────────────────────────────────

    def run(self, action: str, params: dict, context: dict):
        """Execute a plugin action and return a result dict."""
        logger_ctx = context.get("logger", logger)
        settings   = context.get("settings", {})

        redis_client, server_running_redis, server_host, server_port = self._get_redis_server_state()
        current_server = get_current_server()

        # ── restart_server (also serves as start) ────────────────────────────
        if action == "restart_server":
            try:
                # Clear manual-stop flag so this explicit start is honored
                if redis_client:
                    try:
                        from .config import REDIS_KEY_MANUAL_STOP
                        redis_client.delete(REDIS_KEY_MANUAL_STOP)
                    except Exception:
                        pass

                if current_server and current_server.is_running():
                    current_server.stop()

                if redis_client:
                    try:
                        redis_client.set(REDIS_KEY_STOP, "1")
                        stopped = False
                        for _ in range(50):
                            if not read_redis_flag(redis_client, REDIS_KEY_RUNNING):
                                stopped = True
                                break
                            time.sleep(0.1)
                        if not stopped:
                            logger_ctx.warning("Server did not confirm shutdown within 5s during restart, force-cleaning")
                            redis_client.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP)
                    except Exception as e:
                        return {"status": "error", "message": f"Failed to stop server: {str(e)}"}

                time.sleep(0.5)

                if redis_client:
                    try:
                        redis_client.delete(REDIS_KEY_STOP)
                    except Exception:
                        pass

                time.sleep(0.5)

                port = int(settings.get("port", DEFAULT_PORT))
                host = normalize_host(
                    settings.get("host", DEFAULT_HOST),
                    DEFAULT_HOST,
                )

                if redis_client and read_redis_flag(redis_client, REDIS_KEY_RUNNING):
                    return {"status": "error", "message": "Server is still running after stop attempt"}

                server = MetricsServer(self.collector, port=port, host=host)
                if server.start(settings=settings):
                    return {
                        "status": "success",
                        "message": "Metrics server started successfully",
                        "endpoint": f"http://{host}:{port}/metrics",
                        "health_check": f"http://{host}:{port}/health",
                    }
                return {
                    "status": "error",
                    "message": "Failed to start metrics server. Port may be in use.",
                }

            except Exception as e:
                logger_ctx.error(f"Error starting metrics server: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to start server: {str(e)}"}

        # ── stop_server ──────────────────────────────────────────────────────
        elif action == "stop_server":
            try:
                # Flag manual stop so autostart won't re-launch during this runtime.
                # The flag is cleared on fresh Dispatcharr boot (CLEANUP_REDIS_KEYS).
                if redis_client:
                    try:
                        from .config import REDIS_KEY_MANUAL_STOP
                        redis_client.set(REDIS_KEY_MANUAL_STOP, "1")
                    except Exception:
                        pass

                if current_server and current_server.is_running():
                    if current_server.stop():
                        return {"status": "success", "message": "Metrics server stopped successfully"}

                if redis_client:
                    try:
                        logger_ctx.info("Sending stop signal via Redis")
                        redis_client.set(REDIS_KEY_STOP, "1")

                        for _ in range(50):  # wait up to 5 s
                            if not read_redis_flag(redis_client, REDIS_KEY_RUNNING):
                                logger_ctx.info("Server confirmed shutdown via Redis")
                                return {"status": "success", "message": "Metrics server stopped successfully"}
                            time.sleep(0.1)

                        logger_ctx.warning("Server did not confirm shutdown within 5s, force-cleaning Redis keys")
                        redis_client.delete(REDIS_KEY_RUNNING, REDIS_KEY_HOST, REDIS_KEY_PORT, REDIS_KEY_STOP)
                        return {
                            "status": "warning",
                            "message": "Stop signal sent but server did not confirm. Redis keys cleared.",
                        }
                    except Exception as e:
                        return {"status": "error", "message": f"Failed to signal stop: {str(e)}"}

                return {"status": "error", "message": "No running server found"}

            except Exception as e:
                logger_ctx.error(f"Error stopping metrics server: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to stop server: {str(e)}"}

        # ── server_status ────────────────────────────────────────────────────
        elif action == "server_status":
            try:
                if server_running_redis and server_host and server_port:
                    endpoint = f"http://{server_host}:{server_port}/metrics"
                elif current_server and current_server.host and current_server.port:
                    endpoint = f"http://{current_server.host}:{current_server.port}/metrics"
                else:
                    host = settings.get("host", DEFAULT_HOST) if settings else DEFAULT_HOST
                    port = settings.get("port", DEFAULT_PORT) if settings else DEFAULT_PORT
                    endpoint = f"http://{host}:{port}/metrics"

                if (current_server and current_server.is_running()) or server_running_redis:
                    return {"status": "success", "message": f"Server is running on {endpoint}"}
                return {"status": "success", "message": "Server is not running"}

            except Exception as e:
                logger_ctx.error(f"Error checking server status: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to check status: {str(e)}"}

        return {"status": "error", "message": f"Unknown action: {action}"}

    def stop(self, context: dict):
        """Called when the plugin is disabled or Dispatcharr is shutting down.

        After a ``force_reload`` the module-level ``get_current_server()``
        reference points to ``None`` because the module was re-imported.
        The old server daemon thread is still alive but unreachable by
        direct reference.  We fall back to Redis signaling so the old
        server's monitor loop detects the stop flag and exits.
        """
        current_server = get_current_server()
        if current_server and current_server.is_running():
            logger.info("Plugin stopping, shutting down metrics server")
            current_server.stop()
        else:
            # Redis fallback: signal orphaned server from a previous module load
            redis_client = get_redis_client()
            if redis_client and read_redis_flag(redis_client, REDIS_KEY_RUNNING):
                logger.info("Plugin stopping, sending Redis stop signal to orphaned metrics server")
                redis_client.set(REDIS_KEY_STOP, "1")

        # Clear leader election and dedup keys so the next discovery can re-autostart
        try:
            rc = get_redis_client()
            if rc:
                from .config import REDIS_KEY_LEADER
                rc.delete(REDIS_KEY_LEADER, REDIS_KEY_LEADER + ":autostart_dedup")
        except Exception:
            pass


__version__ = PLUGIN_CONFIG["version"]
__all__ = ["Plugin"]

