"""Plugin configuration and field definitions for Dispatcharr Multiview."""

import json
import os

# Constants

PLUGIN_DB_KEY = "multiview"

DEFAULT_SERVER_PORT = 9292
DEFAULT_SERVER_HOST = "127.0.0.1"


def _load_plugin_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "plugin.json")
    with open(config_path, "r") as f:
        return json.load(f)


PLUGIN_CONFIG = _load_plugin_config()

_ENCODER_OPTIONS = [
    {"value": "libx264",    "label": "Software (libx264)"},
    {"value": "h264_nvenc", "label": "NVIDIA NVENC (h264_nvenc)"},
]


# Global fields (always shown)

_GLOBAL_FIELDS = [
    {
        "id": "output_resolution",
        "label": "Output Resolution",
        "type": "select",
        "default": "1920x1080",
        "options": [
            {"value": "1920x1080", "label": "1080p (1920×1080)"},
            {"value": "1280x720",  "label": "720p (1280×720)"},
            {"value": "854x480",   "label": "480p (854×480)"},
        ],
        "description": "Resolution of the tiled output. Lower resolutions reduce CPU and bandwidth.",
    },
    {
        "id": "output_fps",
        "label": "Output Frame Rate",
        "type": "select",
        "default": "30",
        "options": [
            {"value": "24", "label": "24 fps"},
            {"value": "25", "label": "25 fps"},
            {"value": "30", "label": "30 fps"},
            {"value": "50", "label": "50 fps"},
            {"value": "60", "label": "60 fps"},
        ],
        "description": "Frame rate of the tiled output. Higher rates are smoother but use more CPU.",
    },
    {
        "id": "output_bitrate",
        "label": "Output Bitrate (kbps)",
        "type": "number",
        "default": 8000,
        "min": 1000,
        "max": 40000,
        "placeholder": "8000",
        "description": "Target output video bitrate in kbps (CBR). Higher values improve quality at the cost of bandwidth. 8000 is a good baseline for 1080p multiview; 12000-16000 for noticeably sharper tiles.",
    },
    {
        "id": "epg_refresh_hours",
        "label": "Auto-Refresh Interval (hours)",
        "type": "number",
        "default": 24,
        "min": 0,
        "max": 168,
        "placeholder": "24",
        "description": "How often to automatically regenerate M3U and EPG. 0 = manual only (Regenerate M3U button).",
    },
]

_VIDEO_ENCODER_FIELD = {
    "id": "video_encoder",
    "label": "Video Encoder",
    "type": "select",
    "default": "libx264",
    "options": [],  # populated from _ENCODER_OPTIONS in build_plugin_fields
    "description": "Software (libx264) or NVIDIA GPU (h264_nvenc). NVENC requires an NVIDIA GPU with driver support.",
}

# Per-encoder quality / preset fields

def _x264_fields() -> list:
    return [
        {
            "id": "encoder_preset",
            "label": "Encoder Preset",
            "type": "select", "default": "ultrafast",
            "options": [
                {"value": "ultrafast", "label": "Ultrafast (lowest CPU)"},
                {"value": "superfast", "label": "Superfast"},
                {"value": "veryfast",  "label": "Very Fast"},
                {"value": "faster",    "label": "Faster"},
                {"value": "fast",      "label": "Fast"},
                {"value": "medium",    "label": "Medium"},
                {"value": "slow",      "label": "Slow (highest quality)"},
            ],
            "description": "Speed vs quality tradeoff. Ultrafast is recommended for live tiling.",
        },
    ]


def _nvenc_fields() -> list:
    return [
        {
            "id": "encoder_preset",
            "label": "Encoder Preset",
            "type": "select", "default": "p4",
            "options": [
                {"value": "p1", "label": "p1 - Fastest (lowest quality)"},
                {"value": "p2", "label": "p2 - Fast"},
                {"value": "p3", "label": "p3 - Balanced-Fast"},
                {"value": "p4", "label": "p4 - Balanced"},
                {"value": "p5", "label": "p5 - Balanced-Quality"},
                {"value": "p6", "label": "p6 - Slow"},
                {"value": "p7", "label": "p7 - Slowest (highest quality)"},
            ],
            "description": "NVENC encode speed vs quality. p1-p2 recommended for live multiview.",
        },
    ]


_ENCODER_EXTRA_FIELDS = {
    "libx264":    _x264_fields,
    "h264_nvenc": _nvenc_fields,
}

_MULTIVIEW_COUNT_FIELD = {
    "id": "multiview_count",
    "label": "Number of Multiview Layouts",
    "type": "number",
    "default": 1,
    "min": 1,
    "description": (
        "How many multiview streams to define. "
        "After changing this value, save and refresh to see the new layout blocks"
    ),
    "placeholder": "1",
}

# Per-layout field builders

_LAYOUT_OPTIONS = [
    {"value": "auto",         "label": "Auto Grid"},
    {"value": "featured",     "label": "Featured (main left, others stacked right)"},
    {"value": "top_featured", "label": "Top Featured (main top, others row bottom)"},
]


def _get_multiview_channel_ids() -> set:
    """Return the set of Channel IDs that belong to the Dispatcharr Multiview M3U account."""
    try:
        from apps.m3u.models import M3UAccount
        from apps.channels.models import Channel
        acct = M3UAccount.objects.filter(name="Dispatcharr Multiview").first()
        if not acct:
            return set()
        for field in ("m3u_account", "account", "m3u_account_id", "source"):
            try:
                ids = set(Channel.objects.filter(**{field: acct}).values_list("id", flat=True))
                return ids
            except Exception:
                continue
    except Exception:
        pass
    return set()


def _build_channel_options() -> list:
    """Return channel select options from the live DB, excluding multiview output channels."""
    excluded = _get_multiview_channel_ids()
    opts = [{"value": "_none", "label": "Select a channel"}]
    try:
        from apps.channels.models import Channel
        for ch in Channel.objects.order_by("channel_number").values("id", "name", "channel_number"):
            if ch["id"] in excluded:
                continue
            num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
            opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
    except Exception:
        pass
    return opts


def _build_multiview_block(n: int, ch_count: int, selector_type: str = "classic", regex_pattern: str = "") -> list:
    """Return the list of fields for multiview layout block *n* with *ch_count* channel slots."""
    is_regex = selector_type == "regex"

    fields = [
        {
            "id": f"multiview_{n}_header",
            "label": f"── Layout {n} ──────────────────────",
            "type": "info",
            "description": "",
        },
        {
            "id": f"multiview_{n}_name",
            "label": f"Layout {n} Name",
            "type": "string",
            "default": f"Multiview {n}",
            "description": "Name shown in the M3U playlist",
            "placeholder": f"Multiview {n}",
        },
        {
            "id": f"multiview_{n}_layout",
            "label": f"Layout {n} Style",
            "type": "select",
            "default": "auto",
            "options": _LAYOUT_OPTIONS,
            "description": (
                "Auto Grid: square-ish tile grid sized automatically from channel count. "
                "Featured: first channel large on the left, remaining channels stacked on the right"
            ),
        },
        {
            "id": f"multiview_{n}_selector_type",
            "label": f"Layout {n} Channel Selection",
            "type": "select",
            "default": "classic",
            "options": [
                {"value": "classic", "label": "Classic (dropdown)"},
                {"value": "regex",   "label": "Regex (dynamic match)"},
            ],
            "description": (
                "Classic: select channels from dropdowns. "
                "Regex: channels matching a pattern are selected automatically at stream time. "
                "After changing, save and refresh to see the relevant fields."
            ),
        },
        {
            "id": f"multiview_{n}_channel_count",
            "label": f"Layout {n} Max Channels" if is_regex else f"Layout {n} Channel Count",
            "type": "number",
            "default": 4,
            "min": 2,
            "max": 9,
            "description": (
                f"Maximum number of matching channels to tile in layout {n}. "
                "Recommended maximum is 4; higher counts may not start correctly."
            ) if is_regex else (
                f"Number of channels to tile in layout {n}. "
                "Recommended maximum is 4; higher counts may not start correctly. "
                "After changing, save and refresh to see the new channel slots."
            ),
            "placeholder": "4",
        },
    ]

    if is_regex:
        fields.append(
            {
                "id": f"multiview_{n}_regex_pattern",
                "label": f"Layout {n} Channel Pattern",
                "type": "string",
                "default": "",
                "placeholder": r"e.g. TSN\s*\d or ^CA \|",
                "description": (
                    "Case-insensitive regex matched against channel names. "
                    "Channels are sorted by channel number before tiling."
                ),
            }
        )
        audio_opts = [
            {"value": "all",         "label": "All channels (selectable in player)"},
            {"value": "regex_first", "label": "First matched channel"},
            {"value": "regex_lowest","label": "Lowest channel number"},
        ]
        audio_default = "regex_first"
    else:
        channel_options = _build_channel_options()
        for m in range(1, ch_count + 1):
            fields.append(
                {
                    "id": f"multiview_{n}_channel_{m}",
                    "label": f"Layout {n}: Channel {m}",
                    "type": "select",
                    "default": "_none",
                    "options": channel_options,
                    "description": "",
                }
            )
        audio_opts = [{"value": "all", "label": "All channels (selectable in player)"}]
        for m in range(1, ch_count + 1):
            audio_opts.append({"value": str(m - 1), "label": f"Channel {m}"})
        audio_default = "0"

    fields.append(
        {
            "id": f"multiview_{n}_audio_source",
            "label": f"Layout {n} Audio Source",
            "type": "select",
            "default": audio_default,
            "options": audio_opts,
            "description": (
                "Which channel's audio to include. "
                "'All channels' outputs one audio track per tile; "
                "players that support multi-track (VLC, Infuse, etc.) can switch between them."
            ),
        }
    )

    fields += [
        {
            "id": f"multiview_{n}_epg_title",
            "label": f"Layout {n} EPG Title",
            "type": "string",
            "default": "",
            "placeholder": f"Multiview {n}",
            "description": "Program title shown in the EPG. Leave blank to use the layout name.",
        },
        {
            "id": f"multiview_{n}_epg_subtitle",
            "label": f"Layout {n} EPG Subtitle",
            "type": "string",
            "default": "",
            "placeholder": "",
            "description": "Optional subtitle shown below the title in the EPG.",
        },
        {
            "id": f"multiview_{n}_epg_categories",
            "label": f"Layout {n} EPG Categories",
            "type": "string",
            "default": "",
            "placeholder": "Sports, News",
            "description": (
                "Comma-separated category tags. "
                "EPG apps use these for colour coding (e.g. 'Sports' turns entries green in most players)."
            ),
        },
    ]

    return fields


def build_plugin_fields(settings: dict) -> list:
    """Build the full field list based on current settings."""
    mv_count = max(1, int(settings.get("multiview_count", 1)))
    encoder  = settings.get("video_encoder", "libx264")

    enc_field = dict(_VIDEO_ENCODER_FIELD)
    enc_field["options"] = _ENCODER_OPTIONS

    fields = list(_GLOBAL_FIELDS)
    fields.append(enc_field)

    extra_fn = _ENCODER_EXTRA_FIELDS.get(encoder, _x264_fields)
    fields.extend(extra_fn())

    fields.append(_MULTIVIEW_COUNT_FIELD)

    for n in range(1, mv_count + 1):
        ch_count = max(2, int(settings.get(f"multiview_{n}_channel_count", 4)))
        selector_type = settings.get(f"multiview_{n}_selector_type", "classic")
        regex_pattern = settings.get(f"multiview_{n}_regex_pattern", "")
        fields.extend(_build_multiview_block(n, ch_count, selector_type, regex_pattern))

    return fields


# Default field list (1 layout, 4 channels) used as plugin.json fallback
PLUGIN_FIELDS = build_plugin_fields({})
