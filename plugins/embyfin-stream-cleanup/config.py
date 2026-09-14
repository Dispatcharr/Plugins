"""Plugin configuration, Redis key constants, and field definitions."""

import json
import os


# ── Hard-coded defaults ─────────────────────────────────────────────────────
DEFAULT_PORT: int = 9193
DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_DASH_PATH: str = "/dash"
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
# REDIS_KEY_RUNNING/HOST/PORT (debug-server singleton coordination) were
# dropped when the dashboard server moved to force-fallback's simpler
# local-only lifecycle. REDIS_KEY_STOP stays: it's shared with the monitor's
# own orphaned-thread signaling (handler.py), not debug-server-specific.
REDIS_KEY_STOP     = "emby_cleanup:stop_requested"
REDIS_KEY_LEADER   = "emby_cleanup:leader"
REDIS_KEY_MONITOR  = "emby_cleanup:monitor_running"
REDIS_KEY_MANUAL_STOP = "emby_cleanup:manual_stop"

# Keys to wipe on startup (leader key intentionally excluded so the winning
# worker keeps its claim after cleanup).
CLEANUP_REDIS_KEYS = [
    REDIS_KEY_STOP,
    REDIS_KEY_MONITOR,
    REDIS_KEY_MANUAL_STOP,
]

# Complete set of every key ever written by this plugin
ALL_PLUGIN_REDIS_KEYS = CLEANUP_REDIS_KEYS + [REDIS_KEY_LEADER]

# Leader election TTL.  The winner holds this key for up to LEADER_TTL seconds.
LEADER_TTL = 60  # seconds

# Heartbeat TTL for the monitor's "running" Redis key.  The monitor refreshes
# it on every loop iteration; if the process dies, the key expires and
# autostart can proceed on the next startup.
HEARTBEAT_TTL = 30  # seconds

# ── Plugin field definitions ─────────────────────────────────────────────────

_GLOBAL_SETTINGS_HEADER = {
    "id": "_global_settings_header",
    "label": "── Global Settings ──────────────────────",
    "type": "info",
    "description": "",
}

_GLOBAL_SETTINGS_FIELDS = [
    {
        "id": "cleanup_timeout",
        "label": "Timeout (seconds)",
        "type": "number",
        "default": DEFAULT_CLEANUP_TIMEOUT,
        "min": 1,
        "description": (
            "Seconds a matching client's Dispatcharr connection is allowed to sit idle, or "
            "absent from its media server's active session pool, before it's terminated. "
            "Automatically paused during stream failover or buffering so those don't trigger "
            "a false termination. Takes effect on the next poll cycle, no restart needed."
        ),
        "placeholder": "30",
    },
    {
        "id": "poll_interval",
        "label": "Poll Interval (seconds)",
        "type": "number",
        "default": DEFAULT_POLL_INTERVAL,
        "min": 1,
        "description": (
            "How often to check Dispatcharr client activity and media server session pools. "
            "Lower values react to idle/orphaned clients faster at the cost of more frequent "
            "API calls. Requires the 'Restart Monitor' action (or a Dispatcharr restart) to "
            "take effect."
        ),
        "placeholder": "10",
    },
]

_DASHBOARD_SETTINGS_HEADER = {
    "id": "_dashboard_settings_header",
    "label": "── Dashboard Settings ──────────────────────",
    "type": "info",
    "description": "",
}

_DASHBOARD_SETTINGS_FIELDS = [
    {
        "id": "dash_enabled",
        "label": "Web Dashboard",
        "type": "select",
        "default": "disabled",
        "options": [
            {"value": "disabled", "label": "Disabled"},
            {"value": "enabled", "label": "Enabled"},
        ],
        "description": (
            "Serves a mobile-friendly PWA dashboard for viewing live channel/client status "
            "and editing settings, gated behind your Dispatcharr login. Off by default. You "
            "may need to expose the configured port in your docker-compose.yml to reach it "
            "from outside the container. After changing this, the port, or the path, use the "
            "'Restart Monitor' action below (or restart Dispatcharr) to apply it."
        ),
    },
    {
        "id": "mask_sensitive_data",
        "label": "Mask Sensitive Data on Dashboard",
        "type": "select",
        "default": "disabled",
        "options": [
            {"value": "disabled", "label": "Disabled"},
            {"value": "enabled", "label": "Enabled"},
        ],
        "description": (
            "Hides usernames, IPs, and media server URLs on the dashboard's status view. "
            "Takes effect immediately, no restart needed."
        ),
    },
    {
        "id": "dash_port",
        "label": "Dashboard Port",
        "type": "number",
        "default": DEFAULT_PORT,
        "min": 1024,
        "max": 65535,
        "placeholder": str(DEFAULT_PORT),
        "description": (
            "TCP port the embedded dashboard server listens on. Requires the 'Restart "
            "Monitor' action (or a Dispatcharr restart) to take effect."
        ),
    },
    {
        "id": "dash_path",
        "label": "Dashboard Mount Path",
        "type": "string",
        "default": DEFAULT_DASH_PATH,
        "placeholder": DEFAULT_DASH_PATH,
        "description": (
            "URL path the dashboard is served under, e.g. '/dash' gives "
            "http://<host>:<port>/dash/. Takes effect immediately, no restart needed."
        ),
    },
    {
        "id": "dash_host",
        "label": "Dashboard Bind Host",
        "type": "string",
        "default": DEFAULT_HOST,
        "placeholder": DEFAULT_HOST,
        "description": (
            "Host address the dashboard server binds to (0.0.0.0 for all interfaces). "
            "Requires the 'Restart Monitor' action (or a Dispatcharr restart) to take effect."
        ),
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
        "button in the top-right of the My Plugins page to see the new fields."
    ),
    "placeholder": "1",
}


def _build_server_fields(n):
    """Generate the header + URL/key/identifier fields for media server *n* (1-based)."""
    suffix = f"_{n}" if n > 1 else ""
    label_num = f" {n}" if n > 1 else ""
    return [
        {
            "id": f"_media_server_{n}_header",
            "label": f"── Media Server {n} ──────────────────────",
            "type": "info",
            "description": "",
        },
        {
            "id": f"media_server_url{suffix}",
            "label": f"Media Server{label_num} URL",
            "type": "string",
            "default": "",
            "description": (
                f"Base URL of media server{label_num} (e.g. http://192.168.1.100:8096). "
                "Polls the Sessions API to detect orphaned connections. "
                "Leave blank to disable."
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
                "Generate one under Settings > API Keys."
            ),
            "placeholder": "your-api-key",
        },
        {
            "id": f"media_server_identifier{suffix}",
            "label": f"Media Server{label_num} Client Identifier",
            "type": "string",
            "default": "",
            "description": (
                f"The IP, hostname, CIDR block, or username that media server{label_num} uses when "
                "connecting to Dispatcharr (as shown in the Client Identifier column). "
                "Comma-separated for multiple values. "
                "CIDR notation (e.g. 10.0.0.0/24) matches any IP in the range. "
                "This links the server's session pool to its connections for accurate cleanup. "
                "URL, API key, and identifier must all be set for a server to be considered "
                "configured. Changes here are picked up automatically within one poll cycle; "
                "use the 'Restart Monitor' action for it to take effect immediately."
            ),
            "placeholder": "emby-prod, 192.168.1.0/24",
        },
    ]


def build_plugin_fields(settings: dict) -> list:
    """Build the full field list based on current settings."""
    count = max(1, int(settings.get("media_server_count", 1)))

    fields = [_GLOBAL_SETTINGS_HEADER]
    fields.extend(_GLOBAL_SETTINGS_FIELDS)
    fields.append(_DASHBOARD_SETTINGS_HEADER)
    fields.extend(_DASHBOARD_SETTINGS_FIELDS)
    fields.append(_MEDIA_SERVER_COUNT_FIELD)
    for n in range(1, count + 1):
        fields.extend(_build_server_fields(n))
    return fields


# Default field list (1 server) - used by plugin.json and as fallback
PLUGIN_FIELDS = build_plugin_fields({})
