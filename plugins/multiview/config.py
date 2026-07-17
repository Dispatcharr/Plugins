"""Plugin configuration and field definitions for Dispatcharr Multiview."""

import datetime
import json
import os
import secrets


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

_GLOBAL_SETTINGS_FIELDS = [
    {
        "id": "dash_enabled",
        "label": "Web Dashboard",
        "type": "select",
        "default": "disabled",
        "options": [
            {"value": "disabled", "label": "Disabled"},
            {"value": "enabled",  "label": "Enabled"},
        ],
        "description": (
            "Serves a mobile-friendly PWA dashboard on port 9292 (fixed -- "
            "shared with the multiview stream output itself, not "
            "configurable) for editing settings and managing active streams "
            "without the Dispatcharr admin UI. Off by default. You may need "
            "to add 9292:9292 to your docker-compose.yml ports to reach it "
            "from outside the container. Changing this setting requires a "
            "plugin/Dispatcharr reload (e.g. restart Dispatcharr) to take effect."
        ),
    },
    {
        "id": "dash_path",
        "label": "Dashboard Mount Path",
        "type": "string",
        "default": "/dash",
        "placeholder": "/dash",
        "description": (
            "URL path the dashboard is served under, e.g. '/dash' gives "
            "http://<host>:9292/dash/. Takes effect immediately, no restart "
            "needed. Avoid '/stream' and '/internal', which are reserved for "
            "the plugin's own streaming endpoints."
        ),
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

_VIDEO_OUTPUT_FIELDS = [
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
        "After changing this value, save and reload the plugin to see the new layout blocks. "
        "Our own dashboard (/dash) manages layouts directly and hides this field -- "
        "it's only needed when adding a layout from this native settings page."
    ),
    "placeholder": "1",
}

# Per-layout field builders

_LAYOUT_OPTIONS = [
    {"value": "auto",         "label": "Auto Grid"},
    {"value": "featured",     "label": "Featured (main left, others stacked right)"},
    {"value": "top_featured", "label": "Top Featured (main top, others row bottom)"},
]


def _new_layout_id() -> str:
    return secrets.token_hex(4)


_BACKUP_KEYS = ("multiview_pre_migration_backup", "multiview_pre_reconcile_backup")


def _snapshot_before(settings: dict, backup_key: str) -> dict:
    """Stash a single most-recent copy of *settings* under backup_key before a
    destructive change (legacy migration rename, or reconcile_layout_count's
    shrink path deleting layout keys). Manual-recovery safety net only, not a
    version history -- overwrites any prior snapshot under the same key.

    Recovery (Django shell):
        from apps.plugins.models import PluginConfig
        cfg = PluginConfig.objects.get(key="multiview")
        cfg.settings = cfg.settings["multiview_pre_reconcile_backup"]["settings"]
        cfg.save()
    """
    clean = {k: v for k, v in settings.items() if k not in _BACKUP_KEYS}
    new_settings = dict(settings)
    new_settings[backup_key] = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "settings": clean,
    }
    return new_settings


def _backfill_layout_names(settings: dict) -> tuple:
    """Fill in a missing multiview_{id}_name for any layout already in
    multiview_order. Covers layouts that migrated under an earlier build of
    this migration (before it started persisting the name explicitly) --
    without this, a layout stuck in that state would stay nameless forever,
    since ensure_layout_order's migration branch only ever runs once.
    """
    order = settings.get("multiview_order", [])
    missing = [
        (idx, layout_id) for idx, layout_id in enumerate(order)
        if f"multiview_{layout_id}_name" not in settings
    ]
    if not missing:
        return settings, False
    new_settings = dict(settings)
    for idx, layout_id in missing:
        new_settings[f"multiview_{layout_id}_name"] = f"Multiview {idx + 1}"
    return new_settings, True


def ensure_layout_order(settings: dict) -> tuple:
    """Ensure *settings* has a `multiview_order` list of stable layout ids.

    Position used to be identity (`multiview_{n}_*`, n = 1..multiview_count),
    but n is baked into the live stream URL and M3U tvg-id, so renumbering on
    delete/reorder silently swapped a viewer's stream on reconnect. This
    migrates any legacy numeric-keyed install to `multiview_{id}_*` keys plus
    an explicit `multiview_order` (a JSON list of ids) that's the only place
    position is recorded, or bootstraps a single fresh layout for a brand new
    install. Runs at most once per install -- a no-op once `multiview_order`
    exists.

    Returns (settings, changed). Callers must persist `settings` back to the
    DB when changed=True, since the migration must not silently re-run (and
    generate different ids) on every request.
    """
    if "multiview_order" in settings:
        return _backfill_layout_names(settings)

    new_settings = dict(settings)

    legacy_count = settings.get("multiview_count")
    is_legacy = legacy_count is not None or any(k.startswith("multiview_1_") for k in settings)
    if is_legacy:
        new_settings = _snapshot_before(new_settings, "multiview_pre_migration_backup")
        count = max(1, int(legacy_count or 1))
        order = []
        for n in range(1, count + 1):
            new_id = _new_layout_id()
            prefix = f"multiview_{n}_"
            for key in list(new_settings.keys()):
                if key.startswith(prefix):
                    suffix = key[len(prefix):]
                    new_settings[f"multiview_{new_id}_{suffix}"] = new_settings.pop(key)
            # The name field is only ever filled in client-side from the
            # field default -- persist it for real so it survives migration
            # instead of depending on that client-side illusion.
            name_key = f"multiview_{new_id}_name"
            if name_key not in new_settings:
                new_settings[name_key] = f"Multiview {n}"
            order.append(new_id)
        new_settings["multiview_order"] = order
        new_settings["multiview_count"] = len(order)
        return new_settings, True

    # Brand new install: bootstrap a single empty layout, same as the old
    # `max(1, int(settings.get("multiview_count", 1)))` default.
    new_settings["multiview_order"] = [_new_layout_id()]
    new_settings["multiview_count"] = 1
    return new_settings, True


def reconcile_layout_count(settings: dict) -> tuple:
    """Grow/shrink multiview_order to match multiview_count.

    multiview_count is the only layout-management control exposed on
    Dispatcharr's native plugin settings page. That page fully overwrites
    PluginConfig.settings on save (PluginManager.update_settings()) with no
    visibility into multiview_order, so a native-page edit to the count is
    reconciled here, lazily, the next time any of our own settings-read call
    sites runs (mirrors ensure_layout_order's own call pattern -- call this
    right after it, persist if either reports a change).
    """
    order = list(settings.get("multiview_order", []))
    desired = settings.get("multiview_count")
    if desired is None:
        return settings, False
    desired = max(1, int(desired))
    if desired == len(order):
        return settings, False

    new_settings = dict(settings)
    if desired > len(order):
        for _ in range(desired - len(order)):
            new_id = _new_layout_id()
            position = len(order) + 1
            new_settings[f"multiview_{new_id}_name"] = f"Multiview {position}"
            new_settings[f"multiview_{new_id}_layout"] = "auto"
            new_settings[f"multiview_{new_id}_selector_type"] = "classic"
            new_settings[f"multiview_{new_id}_channel_count"] = 4
            new_settings[f"multiview_{new_id}_epg_source_mode"] = "dummy"
            order.append(new_id)
    else:
        new_settings = _snapshot_before(new_settings, "multiview_pre_reconcile_backup")
        while len(order) > desired:
            removed_id = order.pop()
            prefix = f"multiview_{removed_id}_"
            for key in list(new_settings.keys()):
                if key.startswith(prefix):
                    new_settings.pop(key, None)

    new_settings["multiview_order"] = order
    new_settings["multiview_count"] = len(order)
    return new_settings, True


def ensure_custom_layout_order(settings: dict) -> tuple:
    """Ensure *settings* has a `multiview_custom_layouts_order` list of
    style ids, mirroring `ensure_layout_order`'s rationale: dict key order
    on `multiview_custom_layouts` isn't a reliable place to record display
    order (not guaranteed to round-trip through JSON storage), so an
    explicit ordered id list is kept alongside it instead. Migrates once
    from the dict's existing keys if the order list is missing, and appends
    any "orphan" ids present in the dict but absent from the order list
    (e.g. a style added directly via API without going through this path).

    Returns (settings, changed). Callers must persist `settings` back to
    the DB when changed=True.
    """
    layouts = settings.get("multiview_custom_layouts", {})
    order = settings.get("multiview_custom_layouts_order")
    if order is None:
        new_settings = dict(settings)
        new_settings["multiview_custom_layouts_order"] = list(layouts.keys())
        return new_settings, True

    orphans = [style_id for style_id in layouts.keys() if style_id not in order]
    if not orphans:
        return settings, False

    new_settings = dict(settings)
    new_settings["multiview_custom_layouts_order"] = [*order, *orphans]
    return new_settings, True


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
            if settings.get(f"pyav_consent_{arch}"):
                desc = (
                    f"PyAV is not currently installed for {arch}. Since you've "
                    f"previously installed it, the plugin will automatically "
                    f"reinstall it in the background on next load."
                )
                err = settings.get("pyav_auto_install_error")
                if err:
                    desc += (f" Last automatic attempt failed: {err}. You can also "
                             f"click 'Install PyAV' below to retry immediately.")
            else:
                desc = (f"PyAV is NOT installed for {arch}. Run the "
                        f"'Install PyAV' action below before streaming.")
            warnings.append({
                "id": "_warn_pyav_missing", "label": "Media Engine (PyAV)", "type": "info",
                "description": desc,
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
        order = settings.get("multiview_order", [])
        heavy_layouts = [
            idx + 1 for idx, layout_id in enumerate(order)
            if max(2, int(settings.get(f"multiview_{layout_id}_channel_count", 4))) > 3
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

    try:
        from apps.proxy.config import BaseConfig as _ProxyConfig
        proxy_settings = _ProxyConfig.get_proxy_settings()
        grace = int(proxy_settings.get("channel_init_grace_period", 5))
        if grace < 8:
            warnings.append({
                "id": "_warn_channel_init_timeout",
                "label": "Proxy: Channel Initialization Timeout is too low",
                "type": "info",
                "description": (
                    f"Channel Initialization Timeout is set to {grace}s in Dispatcharr's "
                    f"Proxy Settings. Values under 8s can cause multiview tiles to fail on "
                    f"startup before channels finish initializing. "
                    f"Set it to at least 10s in Settings → Proxy (higher on lower-power systems)."
                ),
            })
    except Exception:
        pass

    if not warnings:
        return []

    return [{
        "id": "_warnings_header",
        "label": "── Warnings ──────────────────────────",
        "type": "info",
        "description": "Use the refresh button (top-right) or restart Dispatcharr to re-check warnings.",
    }] + warnings


def _get_multiview_channel_ids() -> set:
    """Return the set of Channel IDs backed by the Dispatcharr Multiview M3U account."""
    try:
        from apps.m3u.models import M3UAccount
        from apps.channels.models import Channel
        acct = M3UAccount.objects.filter(name="Dispatcharr Multiview").first()
        if not acct:
            return set()
        return set(
            Channel.objects.filter(streams__m3u_account=acct)
            .values_list("id", flat=True)
            .distinct()
        )
    except Exception:
        return set()


def _get_streamless_channel_ids() -> set:
    """Return the set of Channel IDs with no streams assigned."""
    try:
        from django.db.models import Count
        from apps.channels.models import Channel
        return set(
            Channel.objects.annotate(n_streams=Count("streams"))
            .filter(n_streams=0)
            .values_list("id", flat=True)
        )
    except Exception:
        return set()


def _build_channel_options() -> list:
    """Return channel select options from the live DB, excluding multiview output channels."""
    excluded = _get_multiview_channel_ids() | _get_streamless_channel_ids()
    opts = [{"value": "_none", "label": "Select a channel"}]
    try:
        from apps.channels.models import Channel
        for ch in Channel.objects.order_by("channel_number").values("id", "name", "channel_number").distinct():
            if ch["id"] in excluded:
                continue
            num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
            opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
    except Exception:
        pass
    return opts


def _build_layout_channel_options(layout_id: str, settings: dict, ch_count: int, selector_type: str, regex_pattern: str) -> list:
    """Return channel options scoped to the channels actually in this layout."""
    opts = [{"value": "_none", "label": "Select a channel"}]
    seen = set()
    try:
        from apps.channels.models import Channel
        if selector_type == "regex" and regex_pattern:
            excluded = _get_multiview_channel_ids() | _get_streamless_channel_ids()
            for ch in (
                Channel.objects.filter(name__iregex=regex_pattern)
                .exclude(id__in=excluded)
                .order_by("channel_number")[:ch_count]
                .values("id", "name", "channel_number")
                .distinct()
            ):
                if ch["id"] in seen:
                    continue
                seen.add(ch["id"])
                num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
                opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
        else:
            for m in range(1, ch_count + 1):
                ch_id = settings.get(f"multiview_{layout_id}_channel_{m}", "_none")
                if ch_id and ch_id != "_none" and ch_id not in seen:
                    try:
                        ch = Channel.objects.values("id", "name", "channel_number").get(id=int(ch_id))
                        seen.add(ch_id)
                        num = int(ch["channel_number"]) if ch["channel_number"] is not None else ""
                        opts.append({"value": str(ch["id"]), "label": f"{num} - {ch['name']}"})
                    except Channel.DoesNotExist:
                        pass
    except Exception:
        pass
    return opts


def _build_multiview_block(layout_id: str, position: int, ch_count: int, selector_type: str = "classic", regex_pattern: str = "", epg_source_mode: str = "dummy", layout_channel_options: list = None, layout_style_options: list = None) -> list:
    """Return the list of fields for multiview layout *layout_id* with *ch_count* channel slots.

    *position* is only for human-readable labels ("Layout 2 Name") -- the
    stable *layout_id* is what's baked into field ids/settings keys, so
    reordering/deleting other layouts never renames this one's keys.
    """
    is_regex = selector_type == "regex"
    n = position  # short alias for the label text below

    fields = [
        {
            "id": f"multiview_{layout_id}_header",
            "label": f"── Layout {n} ──────────────────────",
            "type": "info",
            "description": "",
        },
        {
            "id": f"multiview_{layout_id}_name",
            "label": f"Layout {n} Name",
            "type": "string",
            "default": f"Multiview {n}",
            "description": "Name shown in the M3U playlist",
            "placeholder": f"Multiview {n}",
        },
        {
            "id": f"multiview_{layout_id}_layout",
            "label": f"Layout {n} Style",
            "type": "select",
            "default": "auto",
            "options": layout_style_options or _LAYOUT_OPTIONS,
            "description": (
                "Auto Grid: square-ish tile grid sized automatically from channel count. "
                "Featured: first channel large on the left, remaining channels stacked on the right"
            ),
        },
        {
            "id": f"multiview_{layout_id}_selector_type",
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
            "id": f"multiview_{layout_id}_channel_count",
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
                "id": f"multiview_{layout_id}_regex_pattern",
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
                    "id": f"multiview_{layout_id}_channel_{m}",
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
            "id": f"multiview_{layout_id}_audio_source",
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
            "id": f"multiview_{layout_id}_epg_source_mode",
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
                "id": f"multiview_{layout_id}_epg_forward_channel",
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
                "id": f"multiview_{layout_id}_epg_title",
                "label": f"Layout {n} EPG Title",
                "type": "string",
                "default": "",
                "placeholder": f"Multiview {n}",
                "description": "Program title shown in the EPG. Leave blank to use the layout name.",
            },
            {
                "id": f"multiview_{layout_id}_epg_subtitle",
                "label": f"Layout {n} EPG Subtitle",
                "type": "string",
                "default": "",
                "placeholder": "",
                "description": "Optional subtitle shown below the title in the EPG.",
            },
            {
                "id": f"multiview_{layout_id}_epg_categories",
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


_GLOBAL_SETTINGS_HEADER = {
    "id": "_global_settings_header",
    "label": "── Global Settings ──────────────────────",
    "type": "info",
    "description": "",
}

_VIDEO_SETTINGS_HEADER = {
    "id": "_video_settings_header",
    "label": "── Video Settings ───────────────────────",
    "type": "info",
    "description": "",
}


def build_plugin_fields(settings: dict) -> list:
    """Build the full field list based on current settings.

    Callers must run `ensure_layout_order()` on *settings* (and persist it if
    changed) before calling this -- this function just renders whatever
    `multiview_order` is already there.
    """
    order = settings.get("multiview_order", [])
    encoder  = settings.get("video_encoder", "libx264")

    custom_layouts = settings.get("multiview_custom_layouts", {})
    layout_style_options = _LAYOUT_OPTIONS + [
        {"value": f"custom:{style_id}", "label": f"Custom: {info.get('name') or style_id}"}
        for style_id, info in custom_layouts.items()
        if info.get("elements")
    ]

    enc_field = dict(_VIDEO_ENCODER_FIELD)
    enc_field["options"] = _ENCODER_OPTIONS

    count_field = dict(_MULTIVIEW_COUNT_FIELD)
    count_field["default"] = len(order)

    fields = _build_warnings_fields(settings)
    fields.append(_GLOBAL_SETTINGS_HEADER)
    fields.extend(_GLOBAL_SETTINGS_FIELDS)
    fields.append(count_field)
    fields.append(_VIDEO_SETTINGS_HEADER)
    fields.extend(_VIDEO_OUTPUT_FIELDS)
    fields.append(enc_field)

    extra_fn = _ENCODER_EXTRA_FIELDS.get(encoder, _x264_fields)
    fields.extend(extra_fn())

    for idx, layout_id in enumerate(order):
        position = idx + 1
        ch_count = max(2, int(settings.get(f"multiview_{layout_id}_channel_count", 4)))
        selector_type = settings.get(f"multiview_{layout_id}_selector_type", "classic")
        regex_pattern = settings.get(f"multiview_{layout_id}_regex_pattern", "")
        epg_source_mode = settings.get(f"multiview_{layout_id}_epg_source_mode", "dummy")
        layout_ch_opts = _build_layout_channel_options(layout_id, settings, ch_count, selector_type, regex_pattern)
        fields.extend(_build_multiview_block(layout_id, position, ch_count, selector_type, regex_pattern, epg_source_mode, layout_ch_opts, layout_style_options))

    return fields


# Default field list (1 layout, 4 channels) used as plugin.json fallback
PLUGIN_FIELDS = build_plugin_fields({})
