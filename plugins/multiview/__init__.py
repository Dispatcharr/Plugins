"""Dispatcharr Multiview plugin.

Tiles multiple Dispatcharr channel streams into a single MPEG-TS output
using FFmpeg. Supports multiple named layouts, each with a configurable
number of channel inputs and either an auto-grid or featured arrangement.
"""

import json
import logging
import os
import socket

logger = logging.getLogger(__name__)

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_PLUGIN_DIR, "plugin.json")) as _f:
    _PLUGIN_CONFIG = json.load(_f)

PLUGIN_DB_KEY = "multiview"
DEFAULT_SERVER_PORT = 9292
DEFAULT_SERVER_HOST = "127.0.0.1"


def _config():
    import importlib
    return importlib.import_module(".config", package=__package__)


def _server():
    import importlib
    return importlib.import_module(".server", package=__package__)


def _epg():
    import importlib
    return importlib.import_module(".epg", package=__package__)


class Plugin:
    """Dispatcharr Plugin: Multiview stream tiling via FFmpeg."""

    name        = _PLUGIN_CONFIG["name"]
    description = _PLUGIN_CONFIG["description"]
    version     = _PLUGIN_CONFIG["version"]
    author      = _PLUGIN_CONFIG["author"]

    actions = [
        {
            "id": "generate_m3u",
            "label": "Regenerate M3U & EPG",
            "description": "Write multiview.m3u and multiview_epg.xml, then refresh the M3U account and EPG source in Dispatcharr",
            "button_label": "Regenerate M3U & EPG",
            "button_variant": "filled",
            "button_color": "green",
        },
        {
            "id": "install_pyav_amd64",
            "label": "Install / Update PyAV (amd64 / x86_64)",
            "description": "Download and install the PyAV media dependency for x86_64 hosts. Required before streaming. Needs internet access.",
            "button_label": "Install PyAV (amd64)",
            "button_variant": "filled",
            "button_color": "blue",
        },
        {
            "id": "install_pyav_arm64",
            "label": "Install / Update PyAV (arm64 / aarch64)",
            "description": "Download and install the PyAV media dependency for aarch64 hosts. Required before streaming. Needs internet access.",
            "button_label": "Install PyAV (arm64)",
            "button_variant": "filled",
            "button_color": "blue",
        },
    ]

    # Lifecycle (init)

    def __init__(self):
        try:
            self._autostart()
        except Exception as e:
            logger.warning(f"Multiview server auto-start skipped: {e}")

    def _autostart(self):
        existing = _server().get_server()
        if existing and existing.is_running():
            return
        try:
            with socket.create_connection(("127.0.0.1", DEFAULT_SERVER_PORT), timeout=0.5):
                return
        except OSError:
            pass
        result = self._start_server()
        if result.get("status") == "success":
            logger.info(f"Multiview auto-start: {result['message']}")
            try:
                from apps.plugins.models import PluginConfig
                cfg = PluginConfig.objects.get(key=PLUGIN_DB_KEY)
                interval_hours = int(cfg.settings.get("epg_refresh_hours", 24))
            except Exception:
                interval_hours = 24
            self._schedule_auto_refresh(interval_hours)
        else:
            logger.warning(f"Multiview auto-start failed: {result['message']}")

    # Dynamic fields

    @property
    def fields(self):
        """Regenerate fields from current DB settings on every request."""
        try:
            from apps.plugins.models import PluginConfig
            cfg = PluginConfig.objects.get(key=PLUGIN_DB_KEY)
            settings = cfg.settings
        except Exception:
            settings = {}
        fields = _config().build_plugin_fields(settings)
        return [self._pyav_status_field()] + fields

    def _pyav_status_field(self) -> dict:
        """Info field showing whether the PyAV media engine is installed."""
        try:
            deps = self._deps()
            arch = deps.detect_arch()
            if not arch:
                import platform
                desc = (f"⚠ Unsupported CPU architecture ({platform.machine()}); "
                        f"PyAV is unavailable, streaming will not work.")
            elif deps.pyav_status(arch):
                desc = f"✓ PyAV {deps.pyav_status(arch)} installed for {arch}."
            else:
                desc = (f"⚠ PyAV is NOT installed for {arch}. Run the "
                        f"'Install PyAV' action below before streaming.")
        except Exception as e:  # noqa: BLE001
            desc = f"PyAV status unknown: {e}"
        return {"id": "_pyav_status", "label": "Media Engine (PyAV)",
                "type": "info", "description": desc}

    # Action dispatcher

    def run(self, action: str, params: dict, context: dict):
        if action == "generate_m3u":
            return self._generate_m3u()
        if action == "install_pyav_amd64":
            return self._deps().install_pyav("linux-x86_64")
        if action == "install_pyav_arm64":
            return self._deps().install_pyav("linux-aarch64")

        return {"status": "error", "message": f"Unknown action: {action}"}

    @staticmethod
    def _deps():
        import importlib
        return importlib.import_module(".deps", package=__package__)

    # generate_m3u

    def _generate_m3u(self) -> dict:
        try:
            from apps.plugins.models import PluginConfig
            cfg = PluginConfig.objects.get(key=PLUGIN_DB_KEY)
            settings = cfg.settings
        except Exception:
            settings = {}
        mv_count = max(1, int(settings.get("multiview_count", 1)))

        lines = ["#EXTM3U"]
        for n in range(1, mv_count + 1):
            name = settings.get(f"multiview_{n}_name", f"Multiview {n}") or f"Multiview {n}"
            stream_url = f"http://localhost:{DEFAULT_SERVER_PORT}/stream/{n}"
            lines.append(f'#EXTINF:-1 tvg-id="multiview_{n}" tvg-name="{name}",{name}')
            lines.append(stream_url)

        m3u_content = "\n".join(lines) + "\n"

        m3u_path = os.path.join(_PLUGIN_DIR, "multiview.m3u")
        try:
            with open(m3u_path, "w") as f:
                f.write(m3u_content)
        except OSError as e:
            return {"status": "error", "message": f"Failed to write M3U file: {e}"}

        source_id = None
        try:
            source_id = _epg().generate_epg(settings, _PLUGIN_DIR)
        except Exception as e:
            logger.warning(f"EPG generation failed: {e}")

        try:
            from apps.m3u.models import M3UAccount
            account, created = M3UAccount.objects.update_or_create(
                name="Dispatcharr Multiview",
                defaults={
                    "file_path": m3u_path,
                    "is_active": True,
                    "account_type": "STD",
                    "refresh_interval": 0,
                },
            )
            verb = "created" if created else "updated"
            self._refresh_m3u_then_epg(account.id, source_id)
            return {
                "status": "success",
                "message": f"M3U written to {m3u_path} | M3U account {verb} in Dispatcharr",
            }
        except Exception as e:
            logger.error(f"Failed to create M3U account: {e}", exc_info=True)
            return {
                "status": "success",
                "message": f"M3U written to {m3u_path} (could not create M3U account: {e})",
            }

    def _refresh_m3u_then_epg(self, account_id, source_id) -> None:
        """Refresh the M3U account, then the EPG source, in sequence.

        Firing both refreshes at once collides on Dispatcharr's shared celery DB
        connection ("the last operation didn't produce records (command status:
        INSERT 0 N)"). A celery chain serializes them; M3U first so the multiview
        channels exist before the EPG maps programs onto them.
        """
        try:
            from celery import chain
            from apps.m3u.tasks import refresh_single_m3u_account
            if source_id is not None:
                from apps.epg.tasks import refresh_epg_data
                chain(refresh_single_m3u_account.si(account_id),
                      refresh_epg_data.si(source_id)).delay()
            else:
                refresh_single_m3u_account.delay(account_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not trigger M3U/EPG refresh chain: {e}")
            try:  # best-effort fallback: at least refresh the M3U
                from apps.m3u.tasks import refresh_single_m3u_account
                refresh_single_m3u_account.delay(account_id)
            except Exception:
                pass

    # start_server

    def _start_server(self) -> dict:
        srv = _server()
        existing = srv.get_server()
        if existing and existing.is_running():
            existing.stop()

        server = srv.MultiviewServer(host=DEFAULT_SERVER_HOST, port=DEFAULT_SERVER_PORT)
        if server.start():
            return {
                "status": "success",
                "message": f"Multiview server started on http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}/",
            }
        return {
            "status": "error",
            "message": f"Failed to start server on {DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}; port may be in use",
        }

    # Auto-refresh

    def _refresh_loop(self, interval_secs: int):
        import time
        while True:
            time.sleep(interval_secs)
            try:
                self._generate_m3u()
            except Exception as e:
                logger.warning(f"Multiview auto-refresh failed: {e}")

    def _schedule_auto_refresh(self, interval_hours: int):
        if interval_hours <= 0:
            return
        interval_secs = interval_hours * 3600
        try:
            import gevent
            gevent.spawn(self._refresh_loop, interval_secs)
        except ImportError:
            import threading
            t = threading.Thread(target=self._refresh_loop, args=(interval_secs,), daemon=True)
            t.start()

    # Lifecycle

    def stop(self, context: dict):
        """Called when the plugin is disabled or Dispatcharr shuts down."""
        srv = _server()
        server = srv.get_server()
        if server and server.is_running():
            logger.info("Plugin stopping, shutting down multiview server")
            server.stop()
