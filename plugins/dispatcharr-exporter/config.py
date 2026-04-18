"""Plugin configuration, Redis key constants, and field definitions.

This module is the single source of truth for:
  - PLUGIN_CONFIG: loaded from plugin.json
  - Redis key names used by every module
  - PLUGIN_FIELDS: the settings schema shared by the Plugin class and the collector
"""

import json
import os


# ── Hard-coded defaults ─────────────────────────────────────────────────────
DEFAULT_PORT: int = 9192
DEFAULT_HOST: str = "0.0.0.0"
AUTO_START_DEFAULT: bool = True

# Key used to look up this plugin's settings in Dispatcharr's PluginConfig
# table. Dispatcharr derives the key from the zip folder name, which may be
# "dispatcharr_exporter" or "dispatcharr-exporter" depending on the build
# source. We normalise to the underscore form here; autostart falls back to
# the hyphen form automatically.
PLUGIN_DB_KEY: str = "dispatcharr_exporter"


def _load_plugin_config() -> dict:
    """Load plugin configuration from plugin.json."""
    config_path = os.path.join(os.path.dirname(__file__), 'plugin.json')
    with open(config_path, 'r') as f:
        return json.load(f)


PLUGIN_CONFIG = _load_plugin_config()

# ── Redis key names ──────────────────────────────────────────────────────────
REDIS_KEY_RUNNING = "prometheus_exporter:server_running"
REDIS_KEY_HOST    = "prometheus_exporter:server_host"
REDIS_KEY_PORT    = "prometheus_exporter:server_port"
REDIS_KEY_STOP    = "prometheus_exporter:stop_requested"
REDIS_KEY_LEADER  = "prometheus_exporter:leader"
REDIS_KEY_MANUAL_STOP = "prometheus_exporter:manual_stop"

# Keys to wipe on startup (leader key intentionally excluded so the winning
# worker keeps its claim after cleanup).
CLEANUP_REDIS_KEYS = [
    REDIS_KEY_RUNNING,
    REDIS_KEY_HOST,
    REDIS_KEY_PORT,
    REDIS_KEY_STOP,
    REDIS_KEY_MANUAL_STOP,
    # Historical keys that may exist from older plugin versions
    "prometheus_exporter:autostart_completed",
]

# Leader election TTL.  The winner holds this key for up to LEADER_TTL seconds.
# It only needs to outlast the server startup sequence.
LEADER_TTL = 60  # seconds

# Heartbeat TTL for "running" Redis keys.  The server refreshes its keys on
# every monitoring loop iteration (1s).  If the process dies, the keys expire
# and autostart can proceed on the next startup.
HEARTBEAT_TTL = 30  # seconds

# ── Plugin field definitions ─────────────────────────────────────────────────
# Shared between the Plugin class (used by Dispatcharr UI) and the collector
# (used to build the dispatcharr_exporter_settings_info metric).
PLUGIN_FIELDS = [
    {
        "id": "auto_start",
        "label": "Auto-Start Metrics Server",
        "type": "boolean",
        "default": AUTO_START_DEFAULT,
        "description": "Automatically start the metrics server when plugin loads (recommended)",
    },
    {
        "id": "suppress_access_logs",
        "label": "Suppress Access Logs",
        "type": "boolean",
        "default": True,
        "description": "Suppress HTTP access logs for /metrics requests",
    },
    {
        "id": "port",
        "label": "Metrics Server Port",
        "type": "number",
        "default": DEFAULT_PORT,
        "description": "Port for the metrics HTTP server",
        "placeholder": "9192",
    },
    {
        "id": "host",
        "label": "Metrics Server Host",
        "type": "string",
        "default": DEFAULT_HOST,
        "description": "Host address to bind to (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only)",
        "placeholder": "0.0.0.0",
    },
    {
        "id": "base_url",
        "label": "Dispatcharr Base URL (Optional)",
        "type": "string",
        "default": "",
        "description": (
            "URL for Dispatcharr API (e.g., http://localhost:5656 or "
            "https://dispatcharr.example.com). If set, logo URLs will be "
            "absolute instead of relative paths. Leave empty to use relative paths."
        ),
        "placeholder": "http://localhost:5656",
    },
    {
        "id": "include_m3u_stats",
        "label": "Include M3U Account Statistics",
        "type": "boolean",
        "default": True,
        "description": "Include M3U account and profile metrics in the output",
    },
    {
        "id": "include_epg_stats",
        "label": "Include EPG Source Statistics",
        "type": "boolean",
        "default": False,
        "description": "Include EPG source and status metrics in the output",
    },
    {
        "id": "include_client_stats",
        "label": "Include Client Connection Statistics",
        "type": "boolean",
        "default": False,
        "description": "Include individual client connection information",
    },
    {
        "id": "include_source_urls",
        "label": "Include Provider/Source Information",
        "type": "boolean",
        "default": False,
        "description": (
            "Include server URLs & XC usernames in M3U account and EPG source metrics. "
            "Ensure this is DISABLED if sharing output in Discord for troubleshooting"
        ),
    },
    {
        "id": "include_user_stats",
        "label": "Include User Statistics",
        "type": "boolean",
        "default": False,
        "description": "Include user account metrics (user info, stream limits, active stream counts).",
    },
]
