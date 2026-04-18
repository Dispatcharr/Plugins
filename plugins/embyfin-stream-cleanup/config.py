"""Plugin configuration, Redis key constants, and field definitions.

Single source of truth for:
  - PLUGIN_CONFIG: loaded from plugin.json
  - Redis key names used by every module
  - PLUGIN_FIELDS: the settings schema shared by the Plugin class and the monitor
"""

import json
import os


# ── Hard-coded defaults ─────────────────────────────────────────────────────
DEFAULT_PORT: int = 9193
DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_CLEANUP_TIMEOUT: int = 30  # seconds
DEFAULT_POLL_INTERVAL: int = 10    # seconds

# Key used to look up this plugin's settings in Dispatcharr's PluginConfig
# table.  Dispatcharr derives the key from the zip folder name, which is
# built from the plugin name in plugin.json (lowercased, spaces to underscores).
PLUGIN_DB_KEY: str = "embyfin_stream_cleanup"


def _load_plugin_config() -> dict:
    """Load plugin configuration from plugin.json."""
    config_path = os.path.join(os.path.dirname(__file__), 'plugin.json')
    with open(config_path, 'r') as f:
        return json.load(f)


PLUGIN_CONFIG = _load_plugin_config()

# ── Redis key names ──────────────────────────────────────────────────────────
REDIS_KEY_RUNNING  = "emby_cleanup:server_running"
REDIS_KEY_HOST     = "emby_cleanup:server_host"
REDIS_KEY_PORT     = "emby_cleanup:server_port"
REDIS_KEY_STOP     = "emby_cleanup:stop_requested"
REDIS_KEY_LEADER   = "emby_cleanup:leader"
REDIS_KEY_MONITOR  = "emby_cleanup:monitor_running"
REDIS_KEY_MANUAL_STOP = "emby_cleanup:manual_stop"

# Keys to wipe on startup (leader key intentionally excluded so the winning
# worker keeps its claim after cleanup).
CLEANUP_REDIS_KEYS = [
    REDIS_KEY_RUNNING,
    REDIS_KEY_HOST,
    REDIS_KEY_PORT,
    REDIS_KEY_STOP,
    REDIS_KEY_MONITOR,
    REDIS_KEY_MANUAL_STOP,
]

# Complete set of every key ever written by this plugin
ALL_PLUGIN_REDIS_KEYS = CLEANUP_REDIS_KEYS + [REDIS_KEY_LEADER]

# Leader election TTL.  The winner holds this key for up to LEADER_TTL seconds.
LEADER_TTL = 60  # seconds

# Heartbeat TTL for "running" Redis keys.  The monitor and server refresh
# their keys on every loop iteration.  If the process dies, the keys expire
# and autostart can proceed on the next startup.
HEARTBEAT_TTL = 30  # seconds

# ── Plugin field definitions ─────────────────────────────────────────────────

# Fields that appear before the media server section
_FIELDS_BEFORE_SERVERS = [
    {
        "id": "cleanup_timeout",
        "label": "Timeout (seconds)",
        "type": "number",
        "default": DEFAULT_CLEANUP_TIMEOUT,
        "description": (
            "Seconds before a matching client's Dispatcharr connection is terminated. "
            "Applies to idle connections (no data flowing) and connections whose "
            "channel is no longer in the media server's active session pool. "
            "Paused automatically during stream failover or buffering"
        ),
        "placeholder": "30",
    },
    {
        "id": "poll_interval",
        "label": "Poll Interval (seconds)",
        "type": "number",
        "default": DEFAULT_POLL_INTERVAL,
        "description": "How often to check client activity",
        "placeholder": "10",
    },
]

_MEDIA_SERVER_COUNT_FIELD = {
    "id": "media_server_count",
    "label": "Number of Media Servers",
    "type": "number",
    "default": 1,
    "min": 1,
    "description": (
        "Number of Emby/Jellyfin servers to monitor for orphan detection. "
        "After changing this value, save settings and click the blue refresh "
        "button in the top-right of the My Plugins page to see the new fields"
    ),
    "placeholder": "1",
}

# Fields that appear after the media server section
_FIELDS_AFTER_SERVERS = [
    {
        "id": "enable_debug_server",
        "label": "Enable Debug Server",
        "type": "boolean",
        "default": False,
        "description": "Start an HTTP server for the debug dashboard (optional)",
    },
    {
        "id": "mask_sensitive_data",
        "label": "Mask Sensitive Data in Debug Page",
        "type": "boolean",
        "default": False,
        "description": "Hide usernames, IPs, and URLs in the debug dashboard",
    },
    {
        "id": "port",
        "label": "Debug Server Port",
        "type": "number",
        "default": DEFAULT_PORT,
        "description": "Port for the debug HTTP server",
        "placeholder": "9193",
    },
    {
        "id": "host",
        "label": "Debug Server Host",
        "type": "string",
        "default": DEFAULT_HOST,
        "description": "Host address to bind the debug server to (0.0.0.0 for all interfaces)",
        "placeholder": "0.0.0.0",
    },
]


def _build_server_fields(n):
    """Generate URL + API key fields for media server *n* (1-based)."""
    suffix = f"_{n}" if n > 1 else ""
    label_num = f" {n}" if n > 1 else ""
    return [
        {
            "id": f"media_server_url{suffix}",
            "label": f"Media Server{label_num} URL",
            "type": "string",
            "default": "",
            "description": (
                f"Base URL of media server{label_num} (e.g. http://192.168.1.100:8096). "
                "Polls the Sessions API to detect orphaned connections. "
                "Leave blank to disable"
            ),
            "placeholder": "http://192.168.1.100:8096",
        },
        {
            "id": f"media_server_api_key{suffix}",
            "label": f"Media Server{label_num} API Key",
            "type": "string",
            "input_type": "password",
            "default": "",
            "description": (
                f"API key for media server{label_num}. "
                "Generate one under Settings > API Keys"
            ),
            "placeholder": "your-api-key",
        },
        {
            "id": f"media_server_identifier{suffix}",
            "label": f"Media Server{label_num} Client Identifier",
            "type": "string",
            "default": "",
            "description": (
                f"The IP, hostname, or label that media server{label_num} uses when "
                "connecting to Dispatcharr (as shown in the Client Identifier column). "
                "Comma-separated for multiple values. "
                "This links the server's session pool to its connections for accurate cleanup"
            ),
            "placeholder": "emby-prod, 192.168.1.100",
        },
    ]


def build_plugin_fields(server_count=1):
    """Build the complete field list for *server_count* media servers."""
    count = max(1, int(server_count))
    fields = list(_FIELDS_BEFORE_SERVERS)
    fields.append(_MEDIA_SERVER_COUNT_FIELD)
    for n in range(1, count + 1):
        fields.extend(_build_server_fields(n))
    fields.extend(_FIELDS_AFTER_SERVERS)
    return fields


# Default field list (1 server) - used by plugin.json and as fallback
PLUGIN_FIELDS = build_plugin_fields(1)
