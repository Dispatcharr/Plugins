"""
Automap Channelarr - Dispatcharr plugin

Deterministic, rule-based channel mapper: maps M3U groups to channel-number
blocks, replacing the built-in automapper (auto_channel_sync).

Streams from all M3U accounts in a configured group are pooled, grouped by a
normalized channel name (country prefix, quality markers, '(N)'/'(X)' tags,
punctuation and whitespace removed) or a shared tvg-id, and each group
becomes one channel numbered
from the group's configured start. Re-runs are stable: existing channels keep
their number and identity; new names get the lowest free number in the block.

Event rules map groups of one-off events ('00:55 NFL: Cowboys - Eagles 27/10'):
start time and date are parsed from the stream name, events are keyed by
title + date, laid out chronologically (re-packed once per day), and deleted
a configurable number of hours after they start.
"""

import fcntl
import logging
import os
from dataclasses import replace
from datetime import datetime, timezone as dt_timezone

from .config import DEFAULT_TEMPLATE, load_config
from .names import StreamInfo
from .planner import (
    ChannelInfo,
    CreateChannel,
    CreateGroup,
    DeleteChannel,
    Snapshot,
    UpdateChannel,
    describe,
    headline,
    plan,
)
from .state import load_state, save_state

logger = logging.getLogger(__name__)

_STATE_FILENAME = "state.json"
_LOCK_FILENAME = "run.lock"
_RERUN_FILENAME = "run.rerun"

# ---------------------------------------------------------------------------
# State file (orphan grace tracking + channel identity fallback)
# ---------------------------------------------------------------------------

def _data_dir(context):
    """Durable plugin directory. Dispatcharr passes context['data_dir']
    (<plugins_dir>/_data/<plugin-id>) from the version that introduced it;
    older versions get the same path derived here, so the plugin code
    directory - wiped on every upgrade - never holds state."""
    data_dir = context.get("data_dir") if isinstance(context, dict) else None
    if not data_dir:
        code_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(
            os.path.dirname(code_dir), "_data", os.path.basename(code_dir)
        )
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _state_path(context):
    path = os.path.join(_data_dir(context), _STATE_FILENAME)
    legacy = os.path.join(os.path.dirname(os.path.abspath(__file__)), _STATE_FILENAME)
    if not os.path.exists(path) and os.path.exists(legacy):
        try:
            os.replace(legacy, path)
        except OSError as e:
            logger.warning(f"automap-channelarr: could not move {legacy} to {path}: {e}")
            return legacy
    return path


# ---------------------------------------------------------------------------
# The run itself
# ---------------------------------------------------------------------------

def _execute(settings, log, context, dry_run, triggered_by):
    from django.db import transaction
    from apps.m3u.models import M3UAccount

    prefix = "automap-channelarr"
    account_names = set(M3UAccount.objects.values_list("name", flat=True))
    config, errors, config_warnings = load_config(settings, account_names)
    if errors:
        msg = "Config errors, nothing was changed: " + " | ".join(errors)
        log.error(f"{prefix}: {msg}")
        return {"status": "error", "message": msg}
    if not config.rules and not config.event_rules:
        return {"status": "success", "message": "No rules configured, nothing to do."}

    state_file = _state_path(context)
    state = load_state(state_file)
    now_local = datetime.now(dt_timezone.utc).astimezone()

    run = plan(config, _read_snapshot(config), state, now_local)
    run = replace(run, warnings=tuple(config_warnings) + run.warnings)

    verb = "would " if dry_run else ""
    for action in run.actions:
        log.info(f"{prefix}: {verb}{describe(action)}")
    if not dry_run:
        with transaction.atomic():
            final_state = _apply(run)
        save_state(state_file, final_state)

    for warning in run.warnings:
        log.warning(f"{prefix}: {warning}")
    line = headline(run, dry_run)
    log.info(f"{prefix}: run complete ({triggered_by}): {line} | " + " | ".join(run.summary))

    if not dry_run:
        try:
            from core.utils import send_websocket_update
            send_websocket_update(
                "updates",
                "update",
                {"type": "plugin", "plugin": "automap_channelarr", "message": line},
            )
        except Exception as e:
            log.warning(f"{prefix}: could not send websocket update: {e}")

    return {"status": "success", "message": line}


def _read_snapshot(config):
    """Every database fact the planner needs, read once."""
    from apps.channels.models import (
        Channel,
        ChannelGroup,
        ChannelGroupM3UAccount,
        ChannelStream,
        Stream,
    )
    from apps.epg.models import EPGData

    rules = config.rules + config.event_rules
    names = {group for rule in rules for _account, group in rule.groups}
    names |= {rule.target for rule in rules if rule.target}
    group_ids = dict(ChannelGroup.objects.filter(name__in=names).values_list("name", "id"))

    streams = {}
    clashes = set()
    for rule in rules:
        for account, group in rule.groups:
            group_id = group_ids.get(group)
            if group_id is None:
                continue
            clash = ChannelGroupM3UAccount.objects.filter(
                channel_group_id=group_id, enabled=True, auto_channel_sync=True
            )
            qs = Stream.objects.filter(channel_group_id=group_id, is_stale=False)
            if account:
                clash = clash.filter(m3u_account__name=account)
                qs = qs.filter(m3u_account__name=account)
            if clash.exists():
                clashes.add((account, group))
            streams[(account, group)] = tuple(
                StreamInfo(**row)
                for row in qs.order_by("id").values(
                    "id", "name", "tvg_id", "m3u_account_id", "logo_url"
                )
            )

    channels = {}
    for row in Channel.objects.values(
        "id", "uuid", "name", "channel_number", "channel_group_id", "tvg_id", "epg_data_id"
    ):
        channels[row["id"]] = ChannelInfo(
            id=row["id"],
            uuid=str(row["uuid"]),
            name=row["name"],
            number=row["channel_number"],
            group_id=row["channel_group_id"],
            tvg_id=row["tvg_id"],
            epg_data_id=row["epg_data_id"],
        )
    links = {}
    for channel_id, stream_id in (
        ChannelStream.objects.order_by("channel_id", "order", "id")
        .values_list("channel_id", "stream_id")
    ):
        links.setdefault(channel_id, []).append(stream_id)

    tvg_ids = {s.tvg_id for pool in streams.values() for s in pool if s.tvg_id}
    epg_ids = {}
    for tvg_id, epg_id in (
        EPGData.objects.filter(tvg_id__in=tvg_ids).order_by("id").values_list("tvg_id", "id")
    ):
        epg_ids.setdefault(tvg_id, epg_id)

    return Snapshot(
        streams=streams,
        group_ids=group_ids,
        auto_sync_clashes=frozenset(clashes),
        channels=channels,
        links={channel_id: tuple(ids) for channel_id, ids in links.items()},
        epg_ids=epg_ids,
    )


def _apply(run):
    """Execute a Plan's actions. Returns the final Mapping state, with the
    uuids of channels created here added."""
    from apps.channels.models import (
        Channel,
        ChannelGroup,
        ChannelProfile,
        ChannelProfileMembership,
        ChannelStream,
        Logo,
    )

    state = run.state
    profiles = list(ChannelProfile.objects.all())
    groups = {}

    def _group(name):
        if name not in groups:
            groups[name], _created = ChannelGroup.objects.get_or_create(name=name)
        return groups[name]

    for action in run.actions:
        if isinstance(action, CreateGroup):
            _group(action.name)
        elif isinstance(action, UpdateChannel):
            channel = Channel.objects.get(id=action.channel_id)
            for field, value in action.fields.items():
                if field == "epg_data":
                    channel.epg_data_id = value
                else:
                    setattr(channel, field, value)
            if action.fields:
                channel.save(update_fields=list(action.fields))
            _sync_streams(channel, action.stream_ids)
        elif isinstance(action, CreateChannel):
            logo = None
            if action.logo_url:
                logo, _created = Logo.objects.get_or_create(
                    url=action.logo_url,
                    defaults={"name": action.name or action.tvg_id or "Unknown"},
                )
            channel = Channel.objects.create(
                channel_number=action.number,
                name=action.name,
                tvg_id=action.tvg_id,
                epg_data_id=action.epg_id,
                logo=logo,
                channel_group=_group(action.group_name),
                user_level=0,
            )
            ChannelStream.objects.bulk_create([
                ChannelStream(channel=channel, stream_id=stream_id, order=order)
                for order, stream_id in enumerate(action.stream_ids)
            ])
            if profiles:
                ChannelProfileMembership.objects.bulk_create([
                    ChannelProfileMembership(
                        channel_profile=profile, channel=channel, enabled=True
                    )
                    for profile in profiles
                ])
            state = state.remember(action.pool_id, action.key, str(channel.uuid))
        elif isinstance(action, DeleteChannel):
            Channel.objects.filter(id=action.channel_id).delete()
    return state


def _sync_streams(channel, stream_ids):
    from apps.channels.models import ChannelStream

    existing = {cs.stream_id: cs for cs in ChannelStream.objects.filter(channel=channel)}
    for stream_id, cs in existing.items():
        if stream_id not in stream_ids:
            cs.delete()
    for order, stream_id in enumerate(stream_ids):
        cs = existing.get(stream_id)
        if cs is None:
            ChannelStream.objects.create(channel=channel, stream_id=stream_id, order=order)
        elif cs.order != order:
            cs.order = order
            cs.save(update_fields=["order"])


def _clear_rerun_request(rerun_path):
    """Remove the rerun marker; True when one was present."""
    try:
        os.remove(rerun_path)
        return True
    except OSError:
        return False


def _locked_execute(settings, log, context, dry_run, triggered_by):
    try:
        data_dir = _data_dir(context)
        rerun_path = os.path.join(data_dir, _RERUN_FILENAME)
        fh = open(os.path.join(data_dir, _LOCK_FILENAME), "w")
    except OSError as e:
        return {"status": "error", "message": f"Could not open lock file: {e}"}
    try:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if dry_run:
                return {
                    "status": "success",
                    "message": "Another Automap Channelarr run is already in progress, skipping.",
                }
            # Ask the running instance to go again once it finishes, so streams
            # from a later M3U refresh are not left unmapped until the next one.
            try:
                open(rerun_path, "w").close()
            except OSError:
                pass
            return {
                "status": "success",
                "message": "Another Automap Channelarr run is in progress, "
                           "it will run again when done.",
            }
        _clear_rerun_request(rerun_path)
        result = _execute(settings, log, context, dry_run, triggered_by)
        while not dry_run and _clear_rerun_request(rerun_path):
            log.info("automap-channelarr: rerun requested by an overlapping trigger")
            result = _execute(settings, log, context, dry_run, "rerun")
        return result
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        except Exception:
            pass
        fh.close()


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------

class Plugin:
    name = "Automap Channelarr"
    version = "0.4.2"
    description = (
        "Deterministic rule-based channel mapper: pools each M3U group's streams "
        "by normalized name and lays them out as channels from a configured "
        "start number. Event groups become schedule-ordered, self-cleaning "
        "channel blocks. Replaces the built-in automapper."
    )
    author = "Megamannen"

    fields = [
        {
            "id": "auto_run",
            "label": "Run automatically after each M3U refresh",
            "type": "boolean",
            "default": False,
        },
        {
            "id": "rules_info",
            "label": "Rules",
            "type": "info",
            "description": (
                "One rule per line: 'Group = start'. Pool several groups into one "
                "block with ';' ('Sports; Sport HD = 100'). Restrict a group to one "
                "M3U account with 'Account/Group = 100'. Append '-> Name' to place "
                "the channels in that channel group ('Sports = 100 -> My Sports'), "
                "created if missing. Lines starting with # are comments. Disable "
                "the built-in auto channel sync on these groups."
            ),
        },
        {
            "id": "rules",
            "label": "Rules",
            "type": "text",
            "default": "",
            "placeholder": "# Sports; Sport HD = 100\n# News = 200\n# ProviderX/Kids = 300",
        },
        {
            "id": "extra_tokens",
            "label": "Strip tokens",
            "type": "string",
            "default": "",
            "placeholder": "RAW; VIP; Multi",
            "help_text": (
                "Extra tokens removed from names before grouping, separated by ';'. "
                "Also used for event titles when Event strip tokens is empty. "
                "4K, UHD, FHD, HD, SD, 2160p, 1080p/i, 720p, 576p/i, 480p/i, "
                "HEVC, H265 and 50FPS are always removed, and so are '(N)' / "
                "'(X)' tags on regular channels."
            ),
        },
        {
            "id": "max_quality",
            "label": "Preferred max quality",
            "type": "select",
            "default": "unlimited",
            "options": [
                {"value": "unlimited", "label": "Unlimited"},
                {"value": "fhd", "label": "FHD"},
                {"value": "hd", "label": "HD"},
                {"value": "sd", "label": "SD"},
            ],
            "help_text": (
                "Streams marked above this quality are left out of channels - "
                "unless they are all a channel has. Saves bandwidth by skipping "
                "e.g. 4K when an FHD stream exists. Applies to event channels too."
            ),
        },
        {
            "id": "orphan_grace_days",
            "label": "Orphan grace period (days)",
            "type": "number",
            "default": 7,
            "help_text": (
                "A mapped channel whose streams disappear from the provider is "
                "deleted only after being gone this many days in a row. "
                "0 deletes immediately. Event channels are deleted at once."
            ),
        },
        {
            "id": "event_rules_info",
            "label": "Event rules",
            "type": "info",
            "description": (
                "Same syntax as Rules, for groups of one-off events ('00:55 NFL: "
                "Cowboys - Eagles 27/10'). Start time and date are parsed from each "
                "stream name; events become channels sorted by start time and are "
                "removed after they have started. A group may appear in Rules or "
                "Event rules, not both."
            ),
        },
        {
            "id": "event_rules",
            "label": "Event rules",
            "type": "text",
            "default": "",
            "placeholder": "# PPV Events = 5000\n# NXT IPTV/Live Sports = 6000 -> Events",
        },
        {
            "id": "event_strip_tokens",
            "label": "Event strip tokens",
            "type": "string",
            "default": "",
            "placeholder": "NXTSE; Viaplay SE; Disney SE",
            "help_text": (
                "Tokens removed from event titles, separated by ';'. Empty uses "
                "Strip tokens. 4K, UHD, FHD, HD, SD, 2160p, 1080p/i, 720p, "
                "576p/i, 480p/i, HEVC, H265 and 50FPS are always removed."
            ),
        },
        {
            "id": "event_as_is",
            "label": "Event as is",
            "type": "string",
            "default": "",
            "placeholder": "RedZone; Big Fight Night",
            "help_text": (
                "Event streams whose name contains any of these ';'-separated "
                "texts (case-insensitive) keep their stream name as channel name: "
                "no stripping, no name template. The start time is still read "
                "for ordering and removal."
            ),
        },
        {
            "id": "event_not",
            "label": "Event not",
            "type": "string",
            "default": "",
            "placeholder": "Replay; Highlights",
            "help_text": (
                "Event streams whose name contains any of these ';'-separated "
                "texts (case-insensitive) are skipped. Wins over Event as is."
            ),
        },
        {
            "id": "event_regex",
            "label": "Event regex",
            "type": "string",
            "default": "",
            "placeholder": r"^(?P<time>\d{1,2}:\d{2}).*?(?P<date>\d{1,2}/\d{1,2})",
            "help_text": (
                "Optional. Overrides the built-in time/date detection for event "
                "streams. Must contain a named group (?P<time>...); (?P<date>...) "
                "is optional (no date = today). Streams it does not match fall "
                "back to the built-in parser."
            ),
        },
        {
            "id": "event_name_template",
            "label": "Event name template",
            "type": "string",
            "default": DEFAULT_TEMPLATE,
            "placeholder": DEFAULT_TEMPLATE,
            "help_text": (
                "Tokens: {title}, {time} 22:00, {time12} 10:00 PM, {date} 27/10, "
                "{usdate} 10/27, {isodate} 2026-10-27, {weekday} Mon. Custom "
                "weekday names: {weekday:Man,Tis,Ons,Tor,Fre,Lor,Son} (7 names, "
                "Monday first). Times are server-local."
            ),
        },
        {
            "id": "event_lead_hours",
            "label": "Event lead time (hours before start)",
            "type": "number",
            "default": 36,
            "help_text": (
                "Events starting further ahead than this are not created yet. "
                "0 creates everything the provider publishes."
            ),
        },
        {
            "id": "event_stale_hours",
            "label": "Event removal (hours after start)",
            "type": "number",
            "default": 6,
            "help_text": (
                "An event channel is deleted this many hours after its start "
                "time, even if the provider still lists it. Checked on every run."
            ),
        },
    ]

    actions = [
        {
            "id": "run_now",
            "label": "Run Now",
            "description": "Apply the mapping rules immediately.",
            "button_label": "Run Now",
            "button_variant": "filled",
            "button_color": "blue",
            "confirm": {
                "required": True,
                "title": "Run Automap Channelarr?",
                "message": (
                    "This will create, renumber and delete channels according to "
                    "the configured rules. Run a Dry Run first if unsure."
                ),
            },
        },
        {
            "id": "dry_run",
            "label": "Dry Run",
            "description": "Compute and log every planned change without touching anything.",
            "button_label": "Dry Run",
            "button_variant": "outline",
            "button_color": "gray",
        },
        {
            "id": "m3u_refresh_hook",
            "label": "Auto Run Hook",
            "description": (
                "Fires automatically after each M3U refresh when 'Run automatically' "
                "is enabled. Clicking it manually behaves like Run Now."
            ),
            "button_label": "Trigger Hook",
            "button_variant": "subtle",
            "button_color": "gray",
            "events": ["m3u_refresh"],
        },
    ]

    def run(self, action: str, params: dict, context: dict):
        log = context.get("logger", logger)
        settings = context.get("settings", {}) or {}

        try:
            if action == "run_now":
                return _locked_execute(settings, log, context, dry_run=False, triggered_by="manual")

            if action == "dry_run":
                return _locked_execute(settings, log, context, dry_run=True, triggered_by="dry-run")

            if action == "m3u_refresh_hook":
                is_event = bool((params or {}).get("event"))
                if is_event and not settings.get("auto_run", False):
                    log.debug("automap-channelarr: m3u_refresh received but auto run is disabled")
                    return {"status": "success", "message": "Auto run disabled, skipped."}
                triggered_by = "m3u_refresh" if is_event else "manual hook"
                return _locked_execute(settings, log, context, dry_run=False, triggered_by=triggered_by)
        except Exception as e:
            log.exception(f"automap-channelarr: action '{action}' failed")
            return {"status": "error", "message": f"Run failed: {e}"}

        return {"status": "error", "message": f"Unknown action: {action}"}
