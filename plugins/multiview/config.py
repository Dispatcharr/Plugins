"""Plugin configuration and field definitions for Dispatcharr Multiview."""

import json
import os


def _load_plugin_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "plugin.json")
    with open(config_path, "r") as f:
        return json.load(f)


PLUGIN_CONFIG = _load_plugin_config()

_ENCODER_OPTIONS = [
    {"value": "libx264",    "label": "Software (libx264)"},
    {"value": "h264_nvenc", "label": "NVIDIA NVENC (h264_nvenc)"},
    {"value": "h264_qsv",   "label": "Intel QSV (h264_qsv)"},
    {"value": "h264_vaapi", "label": "Intel/AMD VAAPI (h264_vaapi)"},
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
    "description": "Software encoder (libx264) or hardware GPU encoder. NVENC requires NVIDIA GPU; QSV/VAAPI require Intel/AMD GPU with /dev/dri support.",
}

# Per-encoder quality / preset fields
#
# ENCODER_PRESETS maps encoder name -> (valid_preset_set, default_preset).
# server.py imports this for validation; values must stay in sync with the
# option lists in the field builders below.
ENCODER_PRESETS: dict[str, tuple[frozenset, str]] = {}


def _register_presets(encoder: str, fields_fn):
    """Populate ENCODER_PRESETS from a field builder's options list."""
    for f in fields_fn():
        if f.get("id") == "encoder_preset":
            vals = frozenset(o["value"] for o in f.get("options", []))
            ENCODER_PRESETS[encoder] = (vals, f.get("default", ""))
            return


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


def _qsv_fields() -> list:
    return [
        {
            "id": "encoder_preset",
            "label": "Encoder Preset",
            "type": "select", "default": "medium",
            "options": [
                {"value": "veryfast", "label": "Very Fast (lowest quality)"},
                {"value": "faster",   "label": "Faster"},
                {"value": "fast",     "label": "Fast"},
                {"value": "medium",   "label": "Medium (recommended)"},
                {"value": "slow",     "label": "Slow (higher quality)"},
            ],
            "description": "QSV encode speed vs quality. Medium is recommended for live multiview.",
        },
    ]


def _vaapi_fields() -> list:
    return []


_ENCODER_EXTRA_FIELDS = {
    "libx264":    _x264_fields,
    "h264_nvenc": _nvenc_fields,
    "h264_qsv":   _qsv_fields,
    "h264_vaapi": _vaapi_fields,
}

# Populate ENCODER_PRESETS from the field definitions above.
for _enc, _fn in _ENCODER_EXTRA_FIELDS.items():
    _register_presets(_enc, _fn)

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


def _get_multiview_profile_params() -> str:
    """Return the ffmpeg parameters string for the globally-enabled default stream profile."""
    try:
        from core.models import CoreSettings, StreamProfile
        default_id = CoreSettings.get_default_stream_profile_id()
        profile = StreamProfile.objects.filter(id=default_id).first()
        return profile.parameters if profile else ""
    except Exception:
        return ""


def _build_warnings_fields(settings: dict) -> list:
    """Return warning info fields for the settings page. Empty list = no warnings = section hidden."""
    warnings = []

    try:
        from . import deps as _deps
        import platform as _platform
        arch = _deps.detect_arch()
        if not arch:
            warnings.append({
                "id": "_warn_pyav_arch", "label": "Media Engine (PyAV)", "type": "info",
                "description": (f"Unsupported CPU architecture ({_platform.machine()}); "
                                f"PyAV is unavailable, streaming will not work."),
            })
        elif not _deps.pyav_status(arch):
            warnings.append({
                "id": "_warn_pyav_missing", "label": "Media Engine (PyAV)", "type": "info",
                "description": (f"PyAV is NOT installed for {arch}. Run the "
                                f"'Install PyAV' action below before streaming."),
            })
    except Exception as e:
        warnings.append({
            "id": "_warn_pyav_unknown", "label": "Media Engine (PyAV)", "type": "info",
            "description": f"PyAV status unknown: {e}",
        })

    params = _get_multiview_profile_params()
    if params and any(t in params for t in ("-c copy", "-c:a copy", "-codec:a copy", "acodec copy")):
        warnings.append({
            "id": "_warn_audio_copy",
            "label": "Audio: multi-track will be dropped",
            "type": "info",
            "description": (
                "The default stream profile uses audio copy (-c copy) without mapping "
                "all tracks. Multi-track audio from multiview will be silently dropped "
                "-- players will only see one audio track. Fix: create a stream profile "
                "that includes '-map 0' or '-map 0:a' and set it as the default."
            ),
        })

    encoder = settings.get("video_encoder", "libx264")
    if encoder == "libx264":
        mv_count = max(1, int(settings.get("multiview_count", 1)))
        heavy_layouts = [
            n for n in range(1, mv_count + 1)
            if max(2, int(settings.get(f"multiview_{n}_channel_count", 4))) > 3
        ]
        if heavy_layouts:
            layout_str = ", ".join(f"Layout {n}" for n in heavy_layouts)
            warnings.append({
                "id": "_warn_sw_encode",
                "label": "Performance: software encoding with 4+ streams",
                "type": "info",
                "description": (
                    f"{layout_str} has more than 3 streams configured with software "
                    f"encoding (libx264). This is CPU-intensive and may cause dropped "
                    f"frames or slow-motion output. Enable a hardware encoder "
                    f"(NVENC, QSV, VAAPI) in Video Settings if available."
                ),
            })

    if not warnings:
        return []

    return [{
        "id": "_warnings_header",
        "label": "── Warnings ──────────────────────────",
        "type": "info",
        "description": "Use the refresh button (top-right) or restart Dispatcharr to re-check warnings.",
    }] + warnings


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


def _build_layout_channel_options(n: int, settings: dict, ch_count: int, selector_type: str, regex_pattern: str) -> list:
    """Return channel options scoped to the channels actually in layout n."""
    opts = [{"value": "_none", "label": "Select a channel"}]
    try:
        from apps.channels.models import Channel
        if selector_type == "regex" and regex_pattern:
            for ch in (
                Channel.objects.filter(name__iregex=regex_pattern)
                .order_by("channel_number")[:ch_count]
                .values("id", "name", "channel_number")
            ):
                num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
                opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
        else:
            for m in range(1, ch_count + 1):
                ch_id = settings.get(f"multiview_{n}_channel_{m}", "_none")
                if ch_id and ch_id != "_none":
                    try:
                        ch = Channel.objects.values("id", "name", "channel_number").get(id=int(ch_id))
                        num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
                        opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
                    except Channel.DoesNotExist:
                        pass
    except Exception:
        pass
    return opts


def _build_multiview_block(n: int, ch_count: int, selector_type: str = "classic", regex_pattern: str = "", epg_source_mode: str = "dummy", layout_channel_options: list = None) -> list:
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

    fields.append(
        {
            "id": f"multiview_{n}_epg_source_mode",
            "label": f"Layout {n} EPG Source",
            "type": "select",
            "default": "dummy",
            "options": [
                {"value": "dummy",   "label": "Placeholder (built-in)"},
                {"value": "forward", "label": "Forward from channel"},
            ],
            "description": (
                "Placeholder emits a simple built-in programme entry. "
                "Forward copies real EPG data from a source channel onto this layout. "
                "After changing, save and refresh to see the relevant fields."
            ),
        }
    )

    if epg_source_mode == "forward":
        fields.append(
            {
                "id": f"multiview_{n}_epg_forward_channel",
                "label": f"Layout {n} EPG Source Channel",
                "type": "select",
                "default": "_none",
                "options": layout_channel_options or _build_channel_options(),
                "description": (
                    "Channel whose EPG will be displayed for this layout. "
                    "Falls back to a placeholder entry if the channel has no EPG data."
                ),
            }
        )
    else:
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


_VIDEO_SETTINGS_HEADER = {
    "id": "_video_settings_header",
    "label": "── Video Settings ───────────────────────",
    "type": "info",
    "description": "",
}


def build_plugin_fields(settings: dict) -> list:
    """Build the full field list based on current settings."""
    mv_count = max(1, int(settings.get("multiview_count", 1)))
    encoder  = settings.get("video_encoder", "libx264")

    enc_field = dict(_VIDEO_ENCODER_FIELD)
    enc_field["options"] = _ENCODER_OPTIONS

    fields = _build_warnings_fields(settings)
    fields.append(_VIDEO_SETTINGS_HEADER)
    fields.extend(_GLOBAL_FIELDS)
    fields.append(enc_field)

    extra_fn = _ENCODER_EXTRA_FIELDS.get(encoder, _x264_fields)
    fields.extend(extra_fn())

    fields.append(_MULTIVIEW_COUNT_FIELD)

    for n in range(1, mv_count + 1):
        ch_count = max(2, int(settings.get(f"multiview_{n}_channel_count", 4)))
        selector_type = settings.get(f"multiview_{n}_selector_type", "classic")
        regex_pattern = settings.get(f"multiview_{n}_regex_pattern", "")
        epg_source_mode = settings.get(f"multiview_{n}_epg_source_mode", "dummy")
        layout_ch_opts = _build_layout_channel_options(n, settings, ch_count, selector_type, regex_pattern)
        fields.extend(_build_multiview_block(n, ch_count, selector_type, regex_pattern, epg_source_mode, layout_ch_opts))

    return fields


# Default field list (1 layout, 4 channels) used as plugin.json fallback
PLUGIN_FIELDS = build_plugin_fields({})
