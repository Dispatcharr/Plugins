"""Emby Stream Cleanup - package root.

Dispatcharr discovers the plugin by importing this package and looking for
the ``Plugin`` class.  The stream monitor, debug server, and auto-start
logic live in their own modules; this file only contains the plugin API.
"""

import logging
import time

from .config import (
    PLUGIN_CONFIG, PLUGIN_FIELDS, build_plugin_fields, PLUGIN_DB_KEY,
    REDIS_KEY_STOP, REDIS_KEY_MONITOR, ALL_PLUGIN_REDIS_KEYS,
    DEFAULT_PORT, DEFAULT_HOST,
)
from .handler import StreamMonitor
from .server import DebugServer, get_current_server
from .autostart import attempt_autostart
from .utils import get_redis_client, read_redis_flag, normalize_host, prune_stale_server_keys

logger = logging.getLogger(__name__)

# Module-level monitor instance shared across actions
_monitor = StreamMonitor()


class Plugin:
    """Dispatcharr Plugin - Emby stream cleanup via activity monitoring."""

    name        = PLUGIN_CONFIG["name"]
    description = PLUGIN_CONFIG["description"]
    version     = PLUGIN_CONFIG["version"]
    author      = PLUGIN_CONFIG["author"]

    @property
    def fields(self):
        """Regenerate fields from current DB settings on every request."""
        try:
            from apps.plugins.models import PluginConfig
            cfg = PluginConfig.objects.get(key=PLUGIN_DB_KEY)
            settings = cfg.settings
        except Exception:
            settings = {}
        return build_plugin_fields(settings)

    actions = [
        {
            "id": "restart_monitor",
            "label": "Restart Monitor",
            "description": "Restart the stream monitor (and debug server if enabled)",
            "button_label": "Restart Monitor",
            "button_variant": "filled",
            "button_color": "orange",
        },
        {
            "id": "reset_settings",
            "label": "Reset Settings",
            "description": "Wipe all saved settings and Redis keys for this plugin",
            "button_label": "Reset All Settings",
            "button_variant": "filled",
            "button_color": "red",
        },
    ]

    # -- Initialisation --------------------------------------------------------

    def __init__(self):
        attempt_autostart(_monitor)

    # -- Action dispatcher -----------------------------------------------------

    def _stop_debug_server(self):
        """Stop the debug server if running in this process.

        Local-only, matching force-fallback's pattern: if a different worker
        is running the server, this doesn't reach it (no cross-worker Redis
        signaling) — that worker keeps its own server until it happens to
        handle a restart/stop action itself.
        """
        server = get_current_server()
        if server and server.is_running():
            server.stop()

    def _prune_media_server_settings(self, settings):
        """Remove media server URL/key settings for servers beyond the current count."""
        try:
            from apps.plugins.models import PluginConfig
            cfg = PluginConfig.objects.get(key=PLUGIN_DB_KEY)
            count = max(1, int(settings.get("media_server_count", 1)))
            if prune_stale_server_keys(cfg.settings, count):
                cfg.save(update_fields=["settings"])
                prune_stale_server_keys(settings, count)
        except Exception as e:
            logger.debug(f"Could not prune media server settings: {e}")

    def run(self, action: str, params: dict, context: dict):
        """Execute a plugin action and return a result dict."""
        logger_ctx = context.get("logger", logger)
        settings   = context.get("settings", {})

        # -- restart_monitor ---------------------------------------------------
        if action == "restart_monitor":
            try:
                # Clean up stale media server keys when count decreases
                self._prune_media_server_settings(settings)

                # Check if the dashboard server was running (in this process) before we stop it
                server = get_current_server()
                dash_was_running = bool(server and server.is_running())

                self._stop_debug_server()

                if _monitor.is_running():
                    _monitor.stop()
                    time.sleep(0.5)

                if not _monitor.start(settings=settings):
                    return {"status": "error", "message": "Failed to start stream monitor"}

                msg = "Stream monitor restarted with current settings"

                # Start dashboard server if enabled
                if settings.get("dash_enabled") == "enabled":
                    port = int(settings.get("dash_port", DEFAULT_PORT))
                    host = normalize_host(settings.get("dash_host", DEFAULT_HOST), DEFAULT_HOST)
                    path = settings.get("dash_path") or "/dash"
                    server = DebugServer(_monitor, port=port, host=host)
                    if server.start():
                        msg += f" | Dashboard on http://{host}:{port}{path}/"
                    else:
                        msg += " | Dashboard failed to start (port may be in use)"
                elif dash_was_running:
                    msg += " | Dashboard stopped (disabled in settings)"

                return {"status": "success", "message": msg}
            except Exception as e:
                logger_ctx.error(f"Error restarting monitor: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to restart monitor: {str(e)}"}

        # -- reset_settings ----------------------------------------------------
        elif action == "reset_settings":
            try:
                result_parts = self._reset_all_settings()
                return {
                    "status": "success",
                    "message": "All plugin settings wiped. " + " | ".join(result_parts)
                        if result_parts else "All plugin settings wiped.",
                }
            except Exception as e:
                logger_ctx.error(f"Error resetting settings: {e}", exc_info=True)
                return {"status": "error", "message": f"Reset failed: {str(e)}"}

        return {"status": "error", "message": f"Unknown action: {action}"}

    def _reset_all_settings(self):
        """Wipe all saved settings from DB and all Redis keys for this plugin."""
        parts = []

        # Stop monitor and debug server first
        if _monitor.is_running():
            _monitor.stop()
            parts.append("monitor stopped")
        self._stop_debug_server()

        # Clear all plugin Redis keys
        redis_client = get_redis_client()
        if redis_client:
            deleted = redis_client.delete(*ALL_PLUGIN_REDIS_KEYS)
            if deleted:
                parts.append(f"{deleted} Redis key(s) deleted")
            # Also clear any autostart dedup key
            redis_client.delete("emby_cleanup:leader:autostart_dedup")

        # Wipe saved settings in DB
        try:
            from apps.plugins.models import PluginConfig
            _plugin_keys = [PLUGIN_DB_KEY, PLUGIN_DB_KEY.replace('_', '-')]
            for _key in _plugin_keys:
                cfg = PluginConfig.objects.filter(key=_key).first()
                if cfg:
                    cfg.settings = {}
                    cfg.save(update_fields=["settings"])
                    parts.append(f"DB settings cleared (key={_key})")
                    break
        except Exception as e:
            parts.append(f"DB clear failed: {e}")

        return parts

    def stop(self, context: dict):
        """Called when the plugin is disabled or Dispatcharr is shutting down.

        After a ``force_reload`` the module-level ``_monitor`` reference
        points to a *new* (idle) instance because the module was re-imported.
        The *old* running monitor thread is still alive but unreachable by
        direct reference. We fall back to Redis signaling so it detects the
        stop flag and exits. The dashboard server has no such fallback (see
        ``server.py``/``_stop_debug_server``) — an orphaned dashboard server
        thread from a previous load only stops if the worker that owns it
        happens to handle a subsequent restart/stop action itself.
        """
        stopped_monitor = False
        if _monitor.is_running():
            logger.info("Plugin stopping, shutting down monitor")
            _monitor.stop()
            stopped_monitor = True

        server = get_current_server()
        if server and server.is_running():
            logger.info("Plugin stopping, shutting down dashboard server")
            server.stop()

        # Redis fallback: signal an orphaned monitor thread from a previous module load
        if not stopped_monitor:
            redis_client = get_redis_client()
            if redis_client and read_redis_flag(redis_client, REDIS_KEY_MONITOR):
                logger.info("Plugin stopping, sending Redis stop signal to orphaned monitor")
                redis_client.set(REDIS_KEY_STOP, "1")

        # Clear leader election and dedup keys so the next discovery can re-autostart
        try:
            rc = get_redis_client()
            if rc:
                from .config import REDIS_KEY_LEADER
                rc.delete(REDIS_KEY_LEADER, REDIS_KEY_LEADER + ":autostart_dedup")
        except Exception:
            pass
