import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone as dt_timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, List

from django.db import transaction
from django.utils import timezone

from apps.plugins.models import PluginConfig
from apps.channels.models import Channel, ChannelGroup, ChannelStream, Stream, Logo, ChannelProfile, ChannelProfileMembership
from apps.epg.models import EPGData, EPGSource, ProgramData
from core.models import StreamProfile
from core.scheduling import delete_periodic_task


class Plugin:
    name = "YouTubearr"
    version = "1.20.0"
    description = "Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering"
    author = "Jeff Gooch"
    help_url = "https://github.com/jeff-gooch/youtubearr"

    fields = [
        {
            "id": "info_manual",
            "label": "Manual Stream Addition",
            "type": "info",
            "description": "Add one or more YouTube livestreams by pasting URLs below (newline or comma-separated).",
        },
        {
            "id": "manual_url",
            "label": "Manual YouTube URLs",
            "type": "text",
            "default": "",
            "help_text": "Paste YouTube livestream URLs here (one per line or comma-separated) and click 'Add Streams'. Multiple URLs will be added at once.",
        },
        {
            "id": "info_monitoring",
            "label": "Automatic Monitoring",
            "type": "info",
            "description": "Automatically detect and add livestreams from YouTube channels. Uses yt-dlp (zero API quota).",
        },
        {
            "id": "monitored_channels",
            "label": "Monitored YouTube Channels",
            "type": "text",
            "default": "",
            "help_text": "One channel per line. Format: @channel or @channel=BaseNumber or @channel=BaseNumber:TitleFilter\n\nExamples:\n@NASA=92\n@RyanHallYall=90\n@OfficialYallBot=90\n@VirtualRailfan=91:Horseshoe Curve|La Grange\n\nChannels without =Number get auto-assigned. Multiple channels can share a base number. Title filter uses regex (case-insensitive).",
        },
        {
            "id": "poll_interval_minutes",
            "label": "Poll Interval (minutes)",
            "type": "number",
            "default": 15,
            "min": 5,
            "max": 60,
            "help_text": "How often to check for new/ended livestreams (5-60 minutes).",
        },
        {
            "id": "max_streams_per_channel",
            "label": "Max Streams to Scan per Channel",
            "type": "number",
            "default": 15,
            "min": 5,
            "max": 50,
            "help_text": "Maximum entries to check on the /streams tab per channel per poll (default: 15). Increase only if a channel runs more than 15 simultaneous streams.",
        },
        {
            "id": "info_settings",
            "label": "General Settings",
            "type": "info",
            "description": "Configure stream quality and channel management.",
        },
        {
            "id": "stream_quality",
            "label": "Stream Quality",
            "type": "select",
            "default": "best",
            "options": [
                {"value": "best", "label": "Best Available"},
                {"value": "1080p", "label": "1080p"},
                {"value": "720p", "label": "720p"},
                {"value": "480p", "label": "480p"},
            ],
            "help_text": "Preferred quality for ingested streams",
        },
        {
            "id": "auto_cleanup",
            "label": "Auto-cleanup Ended Streams",
            "type": "boolean",
            "default": True,
            "help_text": "Automatically remove Dispatcharr channels when YouTube livestreams end",
        },
        {
            "id": "url_refresh_interval_seconds",
            "label": "URL Refresh Interval (seconds)",
            "type": "number",
            "default": 3600,
            "min": 300,
            "max": 21600,
            "help_text": "How often to refresh stream URLs to prevent expiration (default: 3600 = 1 hour). YouTube URLs expire after ~6 hours.",
        },
        {
            "id": "channel_group_name",
            "label": "Channel Group",
            "type": "string",
            "default": "YouTube Live",
            "help_text": "Group name for created channels",
        },
        {
            "id": "channel_profile_name",
            "label": "Channel Profile",
            "type": "string",
            "default": "",
            "help_text": "Name of Channel Profile to add created channels to (e.g., 'Primary'). Leave empty to skip.",
        },
        {
            "id": "starting_channel_number",
            "label": "Starting Channel Number",
            "type": "number",
            "default": 2000,
            "min": 1,
            "max": 99999,
            "help_text": "First channel number to assign (default: 2000). Each new stream increments from here.",
        },
        {
            "id": "channel_number_increment",
            "label": "Channel Number Increment",
            "type": "number",
            "default": 1,
            "min": 1,
            "max": 100,
            "help_text": "How much to increment channel numbers for each new stream (default: 1)",
        },
        {
            "id": "channel_numbering_mode",
            "label": "Channel Numbering Mode",
            "type": "select",
            "default": "decimal",
            "options": [
                {"value": "decimal", "label": "Decimal (90.1, 90.2, 90.3)"},
                {"value": "sequential", "label": "Sequential (2000, 2001, 2002)"},
            ],
            "help_text": "Decimal groups streams from the same YouTube channel together. Sequential avoids decimal issues with some systems.",
        },
        {
            "id": "info_webhook",
            "label": "Webhooks",
            "type": "info",
            "description": "Trigger external services when channels are added or removed, and send notifications for new streams.",
        },
        {
            "id": "info_generic_webhooks",
            "label": "Generic Webhooks",
            "type": "info",
            "description": "Configure generic webhook endpoints for media refresh and stream notifications.",
        },
        {
            "id": "media_refresh_webhook_url",
            "label": "Media Refresh Webhook URL",
            "type": "string",
            "default": "",
            "help_text": "URL to POST when channels are added or removed (e.g., Jellyfin, Emby, Plex guide refresh). Sends a structured JSON event body. Leave empty to disable.",
        },
        {
            "id": "media_refresh_webhook_delay_seconds",
            "label": "Media Refresh Webhook Delay (seconds)",
            "type": "number",
            "default": 5,
            "min": 0,
            "max": 60,
            "help_text": "Delay before sending the media refresh webhook to allow Dispatcharr to finish processing (default: 5 seconds).",
        },
        {
            "id": "media_refresh_webhook_headers",
            "label": "Media Refresh Webhook Headers",
            "type": "string",
            "default": "",
            "help_text": "Optional JSON object of extra request headers (e.g., {\"Authorization\": \"Bearer TOKEN\"}). Leave empty for no extra headers.",
        },
        {
            "id": "media_refresh_webhook_body_template",
            "label": "Media Refresh Webhook Body Template",
            "type": "text",
            "default": "",
            "help_text": "Optional static JSON or text body to send. Leave empty to use the default event payload.",
        },
        {
            "id": "notification_webhook_url",
            "label": "Notification Webhook URL",
            "type": "string",
            "default": "",
            "help_text": "URL to POST when a new stream is added. Sends a generic JSON payload suitable for Telegram bots, Discord, Home Assistant, n8n, or any webhook bridge. Leave empty to disable.",
        },
        {
            "id": "notification_base_url",
            "label": "Notification Base URL",
            "type": "string",
            "default": "",
            "help_text": "Base URL for Dispatcharr stream links in the notification payload (e.g., https://tv.example.com). Used to build stream URLs like {base_url}/proxy/ts/stream/{uuid}.",
        },
        {
            "id": "notification_webhook_headers",
            "label": "Notification Webhook Headers",
            "type": "string",
            "default": "",
            "help_text": "Optional JSON object of extra request headers. Leave empty for no extra headers.",
        },
        {
            "id": "info_legacy_webhooks",
            "label": "Legacy Webhook Aliases",
            "type": "info",
            "description": "These fields are kept for backward compatibility. Prefer the generic webhook fields above for new setups.",
        },
        {
            "id": "webhook_url",
            "label": "Webhook URL (Legacy — media refresh alias, bodyless POST)",
            "type": "string",
            "default": "",
            "help_text": "Legacy media refresh alias. Sends a bodyless POST (original Jellyfin-style). Use 'Media Refresh Webhook URL' above for new setups.",
        },
        {
            "id": "webhook_delay_seconds",
            "label": "Webhook Delay (Legacy — media refresh delay alias)",
            "type": "number",
            "default": 5,
            "min": 0,
            "max": 60,
            "help_text": "Legacy media refresh delay alias. Use 'Media Refresh Webhook Delay' above for new setups.",
        },
        {
            "id": "telegram_webhook_url",
            "label": "Telegram Notification URL (Legacy — notification alias)",
            "type": "string",
            "default": "",
            "help_text": "Legacy notification alias. Preserves the original Telegram payload shape for compatibility. Use 'Notification Webhook URL' above for new setups.",
        },
        {
            "id": "dispatcharr_base_url",
            "label": "Dispatcharr Base URL (Legacy — notification base URL alias)",
            "type": "string",
            "default": "",
            "help_text": "Legacy notification base URL alias. Use 'Notification Base URL' above for new setups.",
        },
        {
            "id": "info_epg",
            "label": "EPG Settings",
            "type": "info",
            "description": "Automatically create and assign a Dummy EPG source to YouTube channels.",
        },
        {
            "id": "epg_source_name",
            "label": "EPG Source Name",
            "type": "string",
            "default": "YouTube Live",
            "help_text": "Name for the Dummy EPG source. Will be auto-created if it doesn't exist. Leave empty to skip EPG assignment. Supports {title} (video title) and {channel} (YouTube channel name) placeholders — e.g. '{channel} Live' creates a separate EPG source per YouTube channel. Note: {title} creates one source per individual stream.",
        },
        {
            "id": "info_advanced",
            "label": "Advanced Settings",
            "type": "info",
            "description": "Settings for streams that require additional authentication.",
        },
        {
            "id": "cookies_content",
            "label": "YouTube Cookies",
            "type": "text",
            "default": "",
            "help_text": "Paste YouTube cookies in Netscape format (cookies.txt content). Only used as fallback when streams fail to load without cookies. Get cookies using a browser extension like 'Get cookies.txt LOCALLY'.",
        },
    ]

    actions = [
        {
            "id": "add_manual",
            "label": "Add Streams",
            "description": "Add YouTube livestream(s) using the Manual URLs field (supports multiple URLs)",
            "button_label": "Add Streams",
            "button_color": "blue",
        },
        {
            "id": "start_monitoring",
            "label": "Start Monitoring",
            "description": "Start automatic monitoring of configured YouTube channels",
            "button_label": "Start Monitoring",
            "button_color": "green",
        },
        {
            "id": "stop_monitoring",
            "label": "Stop Monitoring",
            "description": "Stop automatic channel monitoring",
            "confirm": {
                "required": True,
                "title": "Stop Monitoring?",
                "message": "This will stop checking for new livestreams.",
            },
            "button_label": "Stop",
            "button_color": "yellow",
        },
        {
            "id": "refresh",
            "label": "Refresh Now",
            "description": "Immediately check for new/ended livestreams",
            "button_label": "Refresh",
            "button_color": "blue",
        },
        {
            "id": "cleanup",
            "label": "Cleanup Ended Streams",
            "description": "Remove channels for ended streams and clean up orphaned tracked_streams entries",
            "confirm": {
                "required": True,
                "title": "Cleanup Ended Streams?",
                "message": "This will remove channels for ended YouTube streams (live streams will NOT be affected).",
            },
            "button_label": "Cleanup",
            "button_color": "red",
        },
        {
            "id": "reset_all",
            "label": "Reset All Channels",
            "description": "Remove ALL channels created by this plugin and clear tracking data. Use this to start fresh.",
            "confirm": {
                "required": True,
                "title": "Reset All YouTubearr Channels?",
                "message": "This will:\n• Stop monitoring\n• Delete ALL channels in the 'YouTube Live' group\n• Clear all tracked streams data\n\nThis cannot be undone!",
            },
            "button_label": "Reset All",
            "button_color": "red",
        },
        {
            "id": "diagnostics",
            "label": "Diagnostics",
            "description": "Run a non-destructive YouTubearr health check",
            "button_label": "Diagnostics",
            "button_color": "blue",
        },
    ]

    def __init__(self) -> None:
        self._base_dir = Path(__file__).resolve().parent
        self._plugin_key = self._base_dir.name.replace(" ", "_").lower()
        self._log_path = self._base_dir / "youtubearr.log"
        self._log_max_bytes = 5 * 1024 * 1024

        self._channel_group_name = "YouTube Live"
        self._starting_channel_number = 2000

        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_stop_event = threading.Event()
        self._monitoring_active = False  # In-memory flag to prevent race with Dispatcharr form saves
        self._manual_refresh_lock = threading.Lock()

        # Stream profile cache
        self._stream_profile_id: Optional[int] = None

        # Track assigned channel numbers during poll cycle to avoid duplicates
        self._assigned_channel_numbers: set = set()

        # Track video IDs that recently failed metadata extraction to avoid retrying every poll
        self._extraction_failures: Dict[str, float] = {}  # video_id -> unix timestamp of failure

        self._legacy_task_cleanup_done = False

        # Field defaults
        self._field_defaults = {field["id"]: field.get("default") for field in self.fields}

        # Check for yt-dlp binary
        self._ytdlp_path = self._find_ytdlp_binary()

        # Check for QuickJS binary (for YouTube PO token extraction)
        self._qjs_path = self._find_qjs_binary()

    def run(self, action: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for all plugin actions"""
        action = (action or "").lower()

        # Merge params into context settings
        settings = dict(context.get("settings") or {})
        if params:
            settings.update(params)
        context["settings"] = settings

        if action in {"", "status"}:
            response = self._handle_status(context)
        elif action == "add_manual":
            response = self._handle_add_manual(context)
        elif action == "start_monitoring":
            response = self._handle_start_monitoring(context)
        elif action == "stop_monitoring":
            response = self._handle_stop_monitoring(context)
        elif action == "refresh":
            response = self._handle_refresh(context)
        elif action == "cleanup":
            response = self._handle_cleanup(context)
        elif action == "reset_all":
            response = self._handle_reset_all(context)
        elif action == "diagnostics":
            response = self._handle_diagnostics(context)
        else:
            response = {"status": "error", "message": f"Unknown action '{action}'"}

        return response

    def stop(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Called when plugin is disabled/reloaded"""
        if not context or "settings" not in context:
            try:
                cfg = PluginConfig.objects.get(key=self._plugin_key)
                settings = dict(cfg.settings or {})
            except PluginConfig.DoesNotExist:
                settings = {}
            context = {"settings": settings}

        return self._handle_stop_monitoring(context)

    # --- Action Handlers ---

    def _handle_status(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return current status"""
        # Always read fresh settings from DB for auto-restart check
        try:
            cfg = PluginConfig.objects.get(key=self._plugin_key)
            settings = dict(cfg.settings or {})
        except PluginConfig.DoesNotExist:
            settings = context.get("settings", {})

        tracked_streams = settings.get("tracked_streams", {})
        monitoring_active = settings.get("monitoring_active", False)

        # Clean up the bogus Celery beat task left by older plugin versions (once per instance)
        # Must run before any early return, so it fires even when yt-dlp is missing.
        self._cleanup_legacy_celery_task()

        # Check yt-dlp availability
        if not self._ytdlp_path:
            return {
                "status": "error",
                "message": "yt-dlp not found (bundled version may not be working). Check logs.",
            }

        # Self-heal: restart the monitor thread if DB says active but no live thread exists
        self._ensure_monitoring_thread(settings)

        message_parts = []
        if monitoring_active:
            message_parts.append(f"Monitoring active ({len(tracked_streams)} streams tracked)")
        else:
            message_parts.append(f"Monitoring inactive ({len(tracked_streams)} streams tracked)")

        return {
            "status": "running" if monitoring_active else "stopped",
            "message": " | ".join(message_parts) if message_parts else "Ready",
        }

    def _handle_add_manual(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Add YouTube livestream(s) manually - supports multiple URLs"""
        # Check yt-dlp availability
        if not self._ytdlp_path:
            return {
                "status": "error",
                "message": "yt-dlp not found (bundled version may not be working). Check logs.",
            }

        settings = context.get("settings", {})
        urls_raw = settings.get("manual_url", "").strip()

        if not urls_raw:
            return {"status": "error", "message": "No URL provided. Please enter one or more YouTube URLs."}

        # Parse multiple URLs (newline or comma separated)
        urls = re.split(r'[,\n]+', urls_raw)
        urls = [u.strip() for u in urls if u.strip()]

        if not urls:
            return {"status": "error", "message": "No valid URLs found"}

        added_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        tracked_streams = settings.get("tracked_streams", {})
        quality = settings.get("stream_quality", "best")
        cookies_content = settings.get("cookies_content", "")

        for url in urls:
            try:
                # Extract video ID
                video_id = self._extract_video_id(url)
                if not video_id:
                    errors.append(f"Could not extract video ID from: {url[:50]}")
                    error_count += 1
                    continue

                # Check if already tracked
                is_tracked = video_id in tracked_streams

                # If tracked, verify the Dispatcharr channel still exists
                if is_tracked:
                    channel_id_to_check = tracked_streams[video_id].get("channel_id")
                    try:
                        Channel.objects.get(id=channel_id_to_check)
                        self._log(f"Stream {video_id} already tracked (Channel #{channel_id_to_check}), skipping")
                        skipped_count += 1
                        continue  # Channel exists, skip re-adding
                    except Channel.DoesNotExist:
                        self._log(f"Stream {video_id} tracked but channel #{channel_id_to_check} was deleted, checking for existing channel...")

                        # Check if there's already another channel with this video before re-adding
                        try:
                            group_name = settings.get("channel_group_name", self._channel_group_name)
                            channel_group = ChannelGroup.objects.get(name=group_name)
                            existing_channel = None
                            for ch in Channel.objects.filter(channel_group=channel_group):
                                for stream in ch.streams.all():
                                    if stream.url and video_id in stream.url:
                                        existing_channel = ch
                                        break
                                    if stream.name and video_id in stream.name:
                                        existing_channel = ch
                                        break
                                if existing_channel:
                                    break

                            if existing_channel:
                                # Found existing channel - update tracked_streams to point to it
                                self._log(f"Found existing channel #{existing_channel.id} ({existing_channel.channel_number}) with video {video_id}, updating tracked_streams")
                                existing_stream = existing_channel.streams.first()
                                tracked_streams[video_id] = {
                                    "video_id": video_id,
                                    "channel_id": existing_channel.id,
                                    "stream_id": existing_stream.id if existing_stream else None,
                                    "youtube_channel_id": tracked_streams[video_id].get("youtube_channel_id", ""),
                                    "youtube_channel_name": tracked_streams[video_id].get("youtube_channel_name", ""),
                                    "title": tracked_streams[video_id].get("title", ""),
                                    "added_at": tracked_streams[video_id].get("added_at", timezone.now().isoformat()),
                                    "last_url_refresh": timezone.now().isoformat(),
                                    "stream_url": existing_stream.url if existing_stream else "",
                                    "is_live": True,
                                    "channel_number": existing_channel.channel_number,
                                }
                                self._persist_settings({"tracked_streams": tracked_streams})
                                self._log(f"Stream {video_id} already exists as Channel #{existing_channel.channel_number}, skipping")
                                skipped_count += 1
                                continue  # Skip re-adding, we've linked to existing channel
                        except ChannelGroup.DoesNotExist:
                            pass

                        # No existing channel found, remove from tracked_streams so it can be re-added
                        del tracked_streams[video_id]
                        is_tracked = False

                # Extract stream metadata
                metadata = self._extract_stream_metadata(video_id, quality, cookies_content)

                if not metadata:
                    errors.append(f"Failed to extract info for video {video_id}")
                    error_count += 1
                    continue

                if not metadata.get("is_live"):
                    errors.append(f"Stream {video_id} is not currently live")
                    error_count += 1
                    continue

                # Create Dispatcharr Stream and Channel
                stream, channel = self._create_stream_and_channel(metadata, settings)

                # Track the stream
                tracked_streams[video_id] = {
                    "video_id": video_id,
                    "channel_id": channel.id,
                    "stream_id": stream.id,
                    "youtube_channel_id": metadata.get("youtube_channel_id", ""),
                    "youtube_channel_name": metadata.get("youtube_channel_name", ""),
                    "title": metadata.get("title", ""),
                    "added_at": timezone.now().isoformat(),
                    "last_url_refresh": timezone.now().isoformat(),
                    "stream_url": metadata.get("stream_url", ""),
                    "is_live": True,
                    "channel_number": channel.channel_number,
                }

                # Persist immediately to prevent duplicate channel numbers
                self._persist_settings({"tracked_streams": tracked_streams})

                self._log(f"Added stream: {metadata.get('title')} (Channel #{channel.channel_number})")
                added_count += 1

                # Send Telegram notification (use channel.uuid for Dispatcharr URL)
                self._send_telegram_notification(settings, video_id, metadata, channel.channel_number, str(channel.uuid))

            except Exception as exc:
                errors.append(f"Error processing {url[:50]}: {str(exc)[:100]}")
                error_count += 1

        # Trigger webhook if streams were added
        if added_count > 0:
            self._trigger_webhook(settings)

        # Build response message
        message_parts = []
        if added_count > 0:
            message_parts.append(f"{added_count} stream(s) added")
        if skipped_count > 0:
            message_parts.append(f"{skipped_count} already tracked")
        if error_count > 0:
            message_parts.append(f"{error_count} failed")

        message = ", ".join(message_parts) if message_parts else "No streams processed"

        if errors and len(errors) <= 3:
            message += f". Errors: {'; '.join(errors)}"

        return {
            "status": "success" if added_count > 0 else ("warning" if skipped_count > 0 else "error"),
            "message": message,
        }

    def _handle_start_monitoring(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Start background monitoring thread"""
        # Check dependencies
        if not self._ytdlp_path:
            return {
                "status": "error",
                "message": "yt-dlp not found (bundled version may not be working). Check logs.",
            }

        # Read fresh settings from DB to avoid stale state
        try:
            cfg = PluginConfig.objects.get(key=self._plugin_key)
            settings = dict(cfg.settings or {})
        except PluginConfig.DoesNotExist:
            settings = context.get("settings", {})

        # Check if already active (use both DB flag AND heartbeat from any worker)
        # Each Celery worker has its own Plugin instance, so we can't rely on self._monitor_thread
        # Instead, check the heartbeat to see if ANY thread is actively running
        thread_alive = self._monitor_thread and self._monitor_thread.is_alive()

        if settings.get("monitoring_active"):
            # Check heartbeat to see if another worker's thread is running
            heartbeat_str = settings.get("monitoring_heartbeat")
            if heartbeat_str:
                try:
                    heartbeat = datetime.fromisoformat(heartbeat_str.replace("Z", "+00:00"))
                    if isinstance(heartbeat.tzinfo, type(None)):
                        heartbeat = heartbeat.replace(tzinfo=dt_timezone.utc)
                    age_seconds = (datetime.now(dt_timezone.utc) - heartbeat).total_seconds()
                    poll_interval_minutes = settings.get("poll_interval_minutes", 15)
                    heartbeat_threshold = (poll_interval_minutes + 10) * 60
                    if age_seconds < heartbeat_threshold:
                        self._log(f"Monitoring already active (heartbeat {int(age_seconds)}s ago)")
                        return {"status": "running", "message": "Monitoring already active"}
                except (ValueError, TypeError):
                    pass

            # Also check local thread
            if thread_alive:
                return {"status": "running", "message": "Monitoring already active"}

        monitored = settings.get("monitored_channels", "").strip()
        if not monitored:
            return {"status": "error", "message": "No channels to monitor. Add channel IDs/URLs in settings."}

        # Set in-memory flag BEFORE starting thread (prevents race with Dispatcharr form saves)
        self._monitoring_active = True
        self._monitor_stop_event.clear()
        self._extraction_failures.clear()  # Fresh start: retry any previously-failed extractions

        # Update settings in DB
        updates = {
            "monitoring_active": True,
            "last_poll_time": timezone.now().isoformat(),
            "extraction_failures": {},
        }
        self._persist_settings(updates)

        # Start monitoring thread AFTER persisting settings
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(self._plugin_key,),
            daemon=True,
            name="YouTubearr-Monitor"
        )
        self._monitor_thread.start()

        self._log("Monitoring started")
        self._cleanup_legacy_celery_task()

        return {
            "status": "running",
            "message": "Monitoring started",
        }

    def _handle_stop_monitoring(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Stop background monitoring thread"""
        # Check if monitoring is active (either in-memory or DB)
        settings = context.get("settings", {})
        if not self._monitoring_active and not settings.get("monitoring_active"):
            return {"status": "stopped", "message": "Monitoring not active"}

        # Step 1: Set DB flag FIRST - this is what threads in other workers will see
        # Also clear heartbeat so Start Monitoring doesn't think a thread is still running
        updates = {
            "monitoring_active": False,
            "monitoring_heartbeat": None,
        }
        self._persist_settings(updates)

        # Step 2: Set in-memory flag to stop
        self._monitoring_active = False

        # Step 3: Signal thread to stop
        self._monitor_stop_event.set()

        # Step 4: Wait for thread to finish (with timeout)
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        self._log("Monitoring stopped")
        self._cleanup_legacy_celery_task()

        return {
            "status": "stopped",
            "message": "Monitoring stopped",
        }

    def _handle_refresh(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Manually trigger a refresh cycle"""
        self._log(f"!!! REFRESH ACTION TRIGGERED - Plugin version {self.version} !!!")

        # Get settings from database to preserve monitoring_active flag
        try:
            cfg = PluginConfig.objects.get(key=self._plugin_key)
            settings = dict(cfg.settings or {})
        except PluginConfig.DoesNotExist:
            settings = context.get("settings", {})

        # If monitoring is active, the background thread is already polling on its schedule.
        # Running a second concurrent poll blocks the HTTP thread for minutes and causes
        # 504 Gateway Timeouts — especially with many tracked streams.
        if settings.get("monitoring_active"):
            poll_interval = settings.get("poll_interval_minutes", 15)
            last_poll = settings.get("last_poll_time", "")
            last_poll_display = last_poll[:19].replace("T", " ") if last_poll else "unknown"
            return {
                "status": "success",
                "message": f"Monitoring is active (polling every {poll_interval} min). Last poll: {last_poll_display}. No manual refresh needed.",
            }

        if not self._manual_refresh_lock.acquire(blocking=False):
            return {"status": "info", "message": "A manual refresh is already in progress — check logs for progress."}

        def _run():
            try:
                cfg = PluginConfig.objects.get(key=self._plugin_key)
                s = dict(cfg.settings or {})
                added, ended = self._poll_monitored_channels(s)
                if s.get("auto_cleanup", True):
                    self._cleanup_ended_streams(s)
                if added > 0 or ended > 0:
                    self._trigger_webhook(s)
            except Exception as exc:
                self._log_error(f"Manual refresh failed: {exc}")
            finally:
                self._manual_refresh_lock.release()

        threading.Thread(target=_run, daemon=True, name="YouTubearr-ManualRefresh").start()
        return {"status": "success", "message": "Refresh started in background — check logs or wait for the next status update."}

    def _handle_cleanup(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Manually cleanup ended streams and orphaned tracked_streams entries"""
        # Get settings from database to preserve monitoring_active flag
        try:
            cfg = PluginConfig.objects.get(key=self._plugin_key)
            settings = dict(cfg.settings or {})
        except PluginConfig.DoesNotExist:
            settings = context.get("settings", {})

        try:
            # Clean up ended streams (not live streams)
            cleaned = self._cleanup_ended_streams(settings, force=False)

            # Also clean up orphaned entries in tracked_streams where channel was manually deleted
            tracked_streams = settings.get("tracked_streams", {})
            orphaned = []

            for video_id, stream_data in list(tracked_streams.items()):
                channel_id = stream_data.get("channel_id")
                if channel_id:
                    try:
                        Channel.objects.get(id=channel_id)
                    except Channel.DoesNotExist:
                        # Channel was deleted but still in tracked_streams
                        orphaned.append(video_id)

            # Remove orphaned entries
            for video_id in orphaned:
                del tracked_streams[video_id]

            if orphaned:
                self._persist_settings({"tracked_streams": tracked_streams})
                self._log(f"Removed {len(orphaned)} orphaned tracked_streams entries")

            total_cleaned = cleaned + len(orphaned)
            return {
                "status": "success",
                "message": f"Cleaned up {cleaned} ended stream(s), removed {len(orphaned)} orphaned entry(ies)",
            }

        except Exception as exc:
            self._log_error(f"Cleanup failed: {exc}")
            return {"status": "error", "message": f"Cleanup failed: {str(exc)}"}

    def _handle_reset_all(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reset all YouTubearr channels and tracking data to start fresh."""
        try:
            # Step 1: Force-stop monitoring by setting DB flag FIRST
            # This ensures any running thread (even in another worker) will see the stop signal
            try:
                cfg = PluginConfig.objects.get(key=self._plugin_key)
                tracked_count = len(cfg.settings.get("tracked_streams", {}))
                # IMPORTANT: Create new dict to ensure Django detects the change
                # (In-place modification of JSONField may not trigger save properly)
                new_settings = dict(cfg.settings or {})
                new_settings["monitoring_active"] = False
                new_settings["tracked_streams"] = {}  # Clear immediately to prevent re-adds
                cfg.settings = new_settings  # Assign new dict object
                cfg.save(update_fields=["settings", "updated_at"])
                self._log(f"Reset All: Set monitoring_active=False and cleared {tracked_count} tracked_streams")
            except PluginConfig.DoesNotExist:
                tracked_count = 0

            # Step 2: Also call stop monitoring to set in-memory flag and stop event
            self._monitoring_active = False
            self._monitor_stop_event.set()
            self._log("Reset All: Set in-memory stop flags")

            # Step 3: Wait for any running monitoring thread to notice and stop
            # The thread checks DB flag each poll cycle, so we wait a bit
            time.sleep(3)
            self._log("Reset All: Waited for monitoring thread to stop")

            # Step 4: Get the channel group (read from settings, not hardcoded)
            group_name = context.get("settings", {}).get("channel_group_name", self._channel_group_name)
            try:
                channel_group = ChannelGroup.objects.get(name=group_name)
            except ChannelGroup.DoesNotExist:
                channel_group = None

            # Step 5: Delete all channels in the YouTube Live group
            channels_deleted = 0
            streams_deleted = 0

            if channel_group:
                channels = Channel.objects.filter(channel_group=channel_group)
                channels_deleted = channels.count()

                # Get associated streams before deleting channels
                for channel in channels:
                    for stream in channel.streams.all():
                        streams_deleted += 1
                        stream.delete()
                    channel.delete()

                self._log(f"Reset All: Deleted {channels_deleted} channel(s) and {streams_deleted} stream(s)")

            # Step 6: Clean up EPG data for this plugin's EPG source
            epg_source_name = context.get("settings", {}).get("epg_source_name", "YouTube Live").strip()
            epg_cleaned = 0
            if epg_source_name:
                try:
                    from apps.epg.models import EPGData, ProgramData
                    epg_source = EPGSource.objects.filter(name=epg_source_name).first()
                    if epg_source:
                        # Delete program data first
                        ProgramData.objects.filter(epg__epg_source=epg_source).delete()
                        # Then delete EPG data
                        epg_cleaned = EPGData.objects.filter(epg_source=epg_source).count()
                        EPGData.objects.filter(epg_source=epg_source).delete()
                        self._log(f"Reset All: Deleted {epg_cleaned} EPG data entries")
                except Exception as epg_exc:
                    self._log(f"Reset All: EPG cleanup warning: {epg_exc}")

            return {
                "status": "success",
                "message": f"Reset complete: {channels_deleted} channel(s), {streams_deleted} stream(s), {tracked_count} tracked entries cleared",
            }

        except Exception as exc:
            self._log_error(f"Reset All failed: {exc}")
            return {"status": "error", "message": f"Reset failed: {str(exc)}"}

    # --- Diagnostics ---

    def _handle_diagnostics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run a non-destructive health check and return diagnostics details."""
        settings = context.get("settings", {})
        issues: List[str] = []  # "error:<reason>" or "warning:<reason>"
        details: Dict[str, Any] = {}

        # Plugin identity
        details["plugin_version"] = self.version
        details["plugin_key"] = self._plugin_key

        # Monitoring state
        monitoring_active_db = settings.get("monitoring_active", False)
        details["monitoring_active"] = monitoring_active_db
        thread_alive = bool(self._monitor_thread and self._monitor_thread.is_alive())
        details["monitor_thread_alive"] = thread_alive
        details["last_poll_time"] = settings.get("last_poll_time") or "unknown"
        details["monitoring_heartbeat"] = settings.get("monitoring_heartbeat") or "unknown"

        if monitoring_active_db and not thread_alive:
            heartbeat_str = settings.get("monitoring_heartbeat")
            if heartbeat_str:
                try:
                    hb = datetime.fromisoformat(heartbeat_str.replace("Z", "+00:00"))
                    if hb.tzinfo is None:
                        hb = hb.replace(tzinfo=dt_timezone.utc)
                    if (datetime.now(tz=dt_timezone.utc) - hb).total_seconds() > 600:
                        issues.append("warning:monitoring active but heartbeat is stale (>10 min)")
                except Exception:
                    issues.append("warning:monitoring active but heartbeat is unparseable")
            else:
                issues.append("warning:monitoring active but no heartbeat found")

        # Monitored channels / tracked streams
        monitored_raw = settings.get("monitored_channels", "").strip()
        details["monitored_channel_count"] = (
            len([l for l in monitored_raw.splitlines() if l.strip()]) if monitored_raw else 0
        )
        tracked_streams = settings.get("tracked_streams", {})
        details["tracked_stream_count"] = len(tracked_streams)

        # Extraction failures
        failure_count = len(self._extraction_failures)
        details["extraction_failure_count"] = failure_count
        if failure_count > 0:
            try:
                ts_list = [float(t) for t in self._extraction_failures.values()]
                details["extraction_failure_oldest"] = datetime.fromtimestamp(
                    min(ts_list), tz=dt_timezone.utc
                ).isoformat()
                details["extraction_failure_newest"] = datetime.fromtimestamp(
                    max(ts_list), tz=dt_timezone.utc
                ).isoformat()
            except Exception:
                details["extraction_failure_oldest"] = "unavailable"
                details["extraction_failure_newest"] = "unavailable"

        # yt-dlp binary
        details["ytdlp_path"] = self._ytdlp_path or "not found"
        details["ytdlp_version"] = self._get_ytdlp_version()
        if not self._ytdlp_path:
            issues.append("error:yt-dlp binary not found")

        # QuickJS binary
        details["qjs_path"] = self._qjs_path or "not found"
        details["qjs_version"] = self._get_qjs_version()

        # Cookies (configured/present, never expose content)
        cookies_raw = settings.get("cookies_content", "")
        details["cookies_configured"] = bool(cookies_raw and cookies_raw.strip())
        details["cookies_file_present"] = (self._base_dir / "cookies.txt").exists()

        # Webhooks
        media_cfg = self._get_media_refresh_webhook_config(settings)
        details["media_refresh_webhook_configured"] = bool(media_cfg.get("url"))
        details["media_refresh_webhook_is_legacy"] = media_cfg.get("is_legacy", False)
        if settings.get("media_refresh_webhook_headers", "").strip() and not media_cfg.get("headers"):
            issues.append("warning:media refresh webhook headers are invalid JSON")

        notif_cfg = self._get_notification_webhook_config(settings)
        details["notification_webhook_configured"] = bool(notif_cfg.get("url"))
        details["notification_webhook_is_legacy"] = notif_cfg.get("is_legacy", False)
        if settings.get("notification_webhook_headers", "").strip() and not notif_cfg.get("headers"):
            issues.append("warning:notification webhook headers are invalid JSON")

        # DB counts (best effort — defensive against mocked/unavailable Django)
        details["owned_streams"] = self._count_owned_streams()
        details["owned_channels"] = self._count_owned_channels()
        details["owned_programs"] = self._count_owned_programs()
        for key in ("owned_streams", "owned_channels", "owned_programs"):
            if isinstance(details.get(key), str) and "unavailable" in details[key]:
                issues.append(f"warning:{key} count unavailable")
        details["epg_counts"] = self._get_epg_counts(settings)

        # Legacy Celery beat task presence
        try:
            from django_celery_beat.models import PeriodicTask as _PT
            _task_name = f"youtubearr_{self._plugin_key}_health_check"
            present = _PT.objects.filter(name=_task_name).exists()
            details["legacy_celery_health_check_present"] = present
            if present:
                issues.append("warning:legacy Celery beat task present — causes unregistered-task spam; will auto-remove on next status/start action")
        except Exception as _exc:
            details["legacy_celery_health_check_present"] = f"unavailable: {_exc}"

        # Stale stream URLs (live streams whose URL hasn't been refreshed recently)
        _url_refresh_interval = settings.get("url_refresh_interval_seconds", 3600)
        _stale_threshold = 2 * _url_refresh_interval
        _now_utc = datetime.now(dt_timezone.utc)
        stale_count = 0
        oldest_stale_age = 0.0
        for _vid, _sd in tracked_streams.items():
            if not _sd.get("is_live"):
                continue
            _last_str = _sd.get("last_url_refresh")
            if not _last_str:
                stale_count += 1
                continue
            try:
                _lr = datetime.fromisoformat(_last_str.replace("Z", "+00:00"))
                if _lr.tzinfo is None:
                    _lr = _lr.replace(tzinfo=dt_timezone.utc)
                _age = (_now_utc - _lr).total_seconds()
                if _age > _stale_threshold:
                    stale_count += 1
                    oldest_stale_age = max(oldest_stale_age, _age)
            except (ValueError, TypeError):
                stale_count += 1
        details["stale_tracked_stream_url_count"] = stale_count
        if oldest_stale_age:
            details["oldest_url_refresh_age_seconds"] = int(oldest_stale_age)
        if stale_count > 0:
            issues.append(f"warning:{stale_count} live stream URL(s) are stale (monitor may not be refreshing URLs)")

        # Recent log summary
        details["log_summary"] = self._get_recent_log_summary()

        # Status
        errors = [i for i in issues if i.startswith("error:")]
        warnings = [i for i in issues if i.startswith("warning:")]
        if errors:
            status, message = "error", "YouTubearr diagnostics found errors"
        elif warnings:
            status, message = "warning", "YouTubearr diagnostics completed with warnings"
        else:
            status, message = "success", "YouTubearr diagnostics completed: healthy"

        return {"status": status, "message": message, "details": details}

    def _get_ytdlp_version(self) -> str:
        """Return yt-dlp version string, or a safe error description."""
        if not self._ytdlp_path:
            return "unavailable: yt-dlp not found"
        try:
            result = subprocess.run(
                [self._ytdlp_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            ver = result.stdout.strip() or result.stderr.strip()
            return ver if ver else "unknown"
        except FileNotFoundError:
            return "unavailable: binary not found"
        except subprocess.TimeoutExpired:
            return "unavailable: timeout"
        except Exception as exc:
            return f"unavailable: {exc}"

    def _get_qjs_version(self) -> str:
        """Return QuickJS version string from --version output (may exit nonzero)."""
        if not self._qjs_path:
            return "not configured"
        try:
            result = subprocess.run(
                [self._qjs_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            combined = (result.stdout + result.stderr).strip()
            m = re.search(r"QuickJS(?:-ng)?\s+version\s+\S+", combined, re.IGNORECASE)
            if m:
                return m.group(0)
            return combined[:80] if combined else "unknown"
        except FileNotFoundError:
            return "unavailable: binary not found"
        except subprocess.TimeoutExpired:
            return "unavailable: timeout"
        except Exception as exc:
            return f"unavailable: {exc}"

    def _count_owned_streams(self) -> Any:
        try:
            return Stream.objects.filter(custom_properties__owner="youtubearr").count()
        except Exception as exc:
            return f"unavailable: {type(exc).__name__}"

    def _count_owned_channels(self) -> Any:
        try:
            return Channel.objects.filter(
                streams__custom_properties__owner="youtubearr"
            ).distinct().count()
        except Exception as exc:
            return f"unavailable: {type(exc).__name__}"

    def _count_owned_programs(self) -> Any:
        try:
            return ProgramData.objects.filter(custom_properties__owner="youtubearr").count()
        except Exception as exc:
            return f"unavailable: {type(exc).__name__}"

    def _get_epg_counts(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        epg_source_name = settings.get("epg_source_name", "YouTube Live").strip()
        result: Dict[str, Any] = {}
        try:
            source = EPGSource.objects.filter(name=epg_source_name).first()
            if source:
                result["epg_source"] = epg_source_name
                result["epg_data_count"] = EPGData.objects.filter(epg_source=source).count()
                result["program_count"] = ProgramData.objects.filter(epg__epg_source=source).count()
            else:
                result["epg_source"] = f"{epg_source_name} (not found)"
                result["epg_data_count"] = 0
                result["program_count"] = 0
        except Exception as exc:
            result["epg_source"] = f"unavailable: {type(exc).__name__}"
            result["epg_data_count"] = f"unavailable: {type(exc).__name__}"
            result["program_count"] = f"unavailable: {type(exc).__name__}"
        return result

    def _get_recent_log_summary(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"error_count": 0, "recent_errors": [], "status": "ok"}
        if not self._log_path.exists():
            result["status"] = "log file not found"
            return result
        try:
            max_bytes = 32 * 1024
            size = self._log_path.stat().st_size
            with open(self._log_path, "rb") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                raw = f.read(max_bytes)
            text = raw.decode("utf-8", errors="replace")
            lines = text.splitlines()
            if size > max_bytes and lines:
                lines = lines[1:]  # drop possibly-truncated first line
            error_lines = [l for l in lines if "ERROR:" in l]
            result["error_count"] = len(error_lines)
            result["recent_errors"] = [e[-120:] for e in error_lines[-5:]]
            result["lines_scanned"] = len(lines)
        except Exception as exc:
            result["status"] = f"read failed: {type(exc).__name__}"
        return result

    # --- YouTube URL Parsing ---

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats"""
        patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})',
            r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # If no pattern matched, try using yt-dlp subprocess to extract
        if self._ytdlp_path:
            try:
                result = subprocess.run(
                    [str(self._ytdlp_path), "--print", "id", "--no-download", url],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    video_id = result.stdout.strip()
                    if len(video_id) == 11:  # Valid YouTube video ID length
                        return video_id
            except Exception:
                pass

        return None

    def _get_cookies_file(self, cookies_content: str) -> Optional[str]:
        """Write cookies content to a temp file and return the path.

        Returns None if cookies_content is empty or invalid.
        """
        if not cookies_content or not cookies_content.strip():
            return None

        # Write to a file in the plugin's data directory
        cookies_file = self._base_dir / "cookies.txt"
        try:
            cookies_file.write_text(cookies_content.strip() + "\n")
            self._log(f"Wrote cookies to {cookies_file}")
            return str(cookies_file)
        except Exception as exc:
            self._log_error(f"Failed to write cookies file: {exc}")
            return None

    def _extract_stream_metadata(self, video_id: str, quality_preference: str = "best", cookies_content: str = "") -> Optional[Dict[str, Any]]:
        """Extract stream metadata and URL using yt-dlp command-line tool.

        Uses a fallback strategy:
        1. First try without cookies (most streams work this way)
        2. If that fails and cookies are configured, retry with cookies
        """
        if not self._ytdlp_path:
            self._log_error("yt-dlp binary not found. Install with: pip install yt-dlp")
            return None

        url = f"https://www.youtube.com/watch?v={video_id}"
        format_str = self._get_format_string(quality_preference)

        # Build base yt-dlp command
        base_cmd = [
            self._ytdlp_path,
            "--dump-json",
            "--no-warnings",
            "--format", format_str,
        ]

        # Add QuickJS runtime if available (needed for YouTube PO token extraction)
        if self._qjs_path:
            base_cmd.extend(["--js-runtimes", f"quickjs:{self._qjs_path}"])

        # First attempt: try without cookies
        cmd = base_cmd + [url]
        result = self._run_ytdlp_extract(video_id, cmd)

        # If first attempt failed and cookies are available, retry with cookies
        if result is None and cookies_content:
            cookies_file = self._get_cookies_file(cookies_content)
            if cookies_file:
                self._log(f"First attempt failed for {video_id}, retrying with cookies...")
                cmd = base_cmd + ["--cookies", cookies_file, url]
                result = self._run_ytdlp_extract(video_id, cmd, is_retry=True)

        return result

    def _run_ytdlp_extract(self, video_id: str, cmd: list, is_retry: bool = False) -> Optional[Dict[str, Any]]:
        """Execute yt-dlp command and parse the result"""
        retry_label = " (with cookies)" if is_retry else ""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                self._log_error(f"yt-dlp failed for {video_id}{retry_label} (returncode={result.returncode})")
                self._log_error(f"yt-dlp stderr: {result.stderr[:500]}")  # First 500 chars
                if "members" in result.stderr.lower() and "only" in result.stderr.lower():
                    return {"_members_only": True}
                return None

            # Parse JSON output
            self._log(f"yt-dlp succeeded for {video_id}{retry_label}, parsing JSON output...")
            info = json.loads(result.stdout)

            if not info:
                self._log_error(f"yt-dlp returned empty info for {video_id}{retry_label}")
                return None

            # Check live status
            is_live_field = info.get("is_live", False)
            live_status_field = info.get("live_status", "unknown")
            is_live = is_live_field or live_status_field == "is_live"

            self._log(f"yt-dlp live status for {video_id}: is_live={is_live_field}, live_status={live_status_field}, computed_is_live={is_live}")

            # Extract channel name from multiple possible fields
            channel_name = (
                info.get("channel") or
                info.get("uploader") or
                info.get("channel_name") or
                "YouTube"
            )

            # Try to get channel avatar from channel page (yt-dlp doesn't provide it)
            channel_avatar = ""
            channel_url = info.get("channel_url") or info.get("uploader_url", "")
            if channel_url:
                channel_avatar = self._fetch_channel_avatar(channel_url)

            metadata = {
                "video_id": video_id,
                "title": info.get("title", "Unknown"),
                "is_live": is_live,
                "stream_url": info.get("url", ""),
                "thumbnail": info.get("thumbnail", ""),
                "channel_thumbnail": channel_avatar,
                "youtube_channel_id": info.get("channel_id", ""),
                "youtube_channel_name": channel_name,
            }

            self._log(f"Metadata: title='{metadata['title'][:60]}...', channel='{channel_name}'")
            return metadata

        except subprocess.TimeoutExpired:
            self._log_error(f"yt-dlp timed out for {video_id}{retry_label}")
            return None
        except json.JSONDecodeError as exc:
            self._log_error(f"Failed to parse yt-dlp output for {video_id}{retry_label}: {exc}")
            return None
        except Exception as exc:
            self._log_error(f"Failed to extract metadata for {video_id}{retry_label}: {exc}")
            return None

    def _fetch_channel_avatar(self, channel_url: str) -> str:
        """Fetch channel avatar URL by scraping the channel page"""
        try:
            req = urllib.request.Request(
                channel_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            # Look for channel avatar in various patterns
            # Pattern 1: "avatar":{"thumbnails":[{"url":"https://yt3.ggpht.com/...
            patterns = [
                r'"avatar"\s*:\s*\{\s*"thumbnails"\s*:\s*\[\s*\{\s*"url"\s*:\s*"([^"]+)"',
                r'"thumbnails"\s*:\s*\[\s*\{\s*"url"\s*:\s*"(https://yt3\.ggpht\.com/[^"]+)"',
                r'(https://yt3\.ggpht\.com/ytc/[^"\'\\]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    avatar_url = match.group(1)
                    # Clean up the URL (unescape)
                    avatar_url = avatar_url.replace("\\u0026", "&")
                    self._log(f"Found channel avatar: {avatar_url[:80]}...")
                    return avatar_url

            self._log(f"Could not find channel avatar in page HTML")
            return ""

        except Exception as exc:
            self._log(f"Failed to fetch channel avatar: {exc}")
            return ""

    def _get_format_string(self, preference: str) -> str:
        """Get yt-dlp format string for quality preference"""
        formats = {
            "best": "best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480]+bestaudio/best",
        }
        return formats.get(preference, "best")

    # --- Dispatcharr Integration ---

    @transaction.atomic
    def _create_stream_and_channel(
        self,
        metadata: Dict[str, Any],
        settings: Dict[str, Any],
        monitored_channel_id: str = ""
    ) -> tuple[Stream, Channel]:
        """Create Dispatcharr Stream and Channel objects.

        Args:
            metadata: Stream metadata from yt-dlp
            settings: Plugin settings
            monitored_channel_id: The YouTube channel ID being monitored (may differ from
                                  stream's actual channel for aggregated/sub-channels)
        """
        # Lock plugin config to prevent race conditions
        cfg = PluginConfig.objects.select_for_update().get(key=self._plugin_key)

        video_title = metadata.get("title", "YouTube Live")
        video_id = metadata.get("video_id", "")
        stream_url = metadata.get("stream_url", "")
        thumbnail = metadata.get("thumbnail", "")
        channel_thumbnail = metadata.get("channel_thumbnail", "")
        youtube_channel_name = metadata.get("youtube_channel_name", "YouTube")
        youtube_channel_id = metadata.get("youtube_channel_id", "")

        # Create Stream (use video thumbnail for stream logo)
        stream = Stream.objects.create(
            name=video_title,
            url=stream_url,
            logo_url=thumbnail if thumbnail else None,
            tvg_id=None,
            stream_profile_id=self._get_stream_profile_id(settings),
        )

        # Apply YouTubearr ownership tags to stream custom_properties
        try:
            _existing = getattr(stream, 'custom_properties', None)
            stream.custom_properties = self._merge_youtubearr_custom_properties(
                _existing if isinstance(_existing, dict) else {},
                youtube_video_id=video_id,
                youtube_channel_id=youtube_channel_id,
                stream_url_refreshed_at=timezone.now().isoformat(),
            )
            stream.save(update_fields=['custom_properties'])
        except Exception:
            pass  # custom_properties field may not exist on this Dispatcharr version

        # Associate stream with custom M3U account for correct playback routing
        try:
            m3u_account = self._get_custom_m3u_account()
            if m3u_account is not None:
                stream.is_custom = True
                stream.m3u_account = m3u_account
                stream.save(update_fields=['is_custom', 'm3u_account'])
        except Exception:
            pass  # Fields may not exist on this Dispatcharr version

        # Get or create channel group
        group_name = settings.get("channel_group_name", self._channel_group_name)
        group, _ = ChannelGroup.objects.get_or_create(name=group_name)

        # Get channel number using sub-channel mapping (e.g., 90.1, 90.2)
        # Pass monitored_channel_id for mapping (handles sub-channels/aggregated streams)
        # Falls back to stream's youtube_channel_id if not from monitoring
        lookup_channel_id = monitored_channel_id if monitored_channel_id else youtube_channel_id
        channel_number = self._get_channel_number_for_stream(youtube_channel_name, cfg.settings or {}, lookup_channel_id)

        # Format channel name as: {youtube_channel_name} #{stream_number}
        numbering_mode = settings.get("channel_numbering_mode", "decimal")
        if numbering_mode == "decimal":
            # Extract stream number using string-safe parsing (e.g., 93.2 → 2, 93.11 → 11).
            # Float math (decimal_part * 10) gives wrong results for values >= .10.
            stream_number = self._get_subchannel_index(channel_number)
        else:
            # Sequential mode: count ACTIVE streams from this YouTube channel + 1.
            # Only count tracked_streams entries whose channel_id still exists in the DB.
            # Counting all entries (including ended streams) caused #N to start too high
            # when a channel that previously ran N streams goes live again. Since
            # _create_stream_and_channel is @transaction.atomic, the DB is authoritative
            # for channels created earlier in the same poll cycle too.
            group_name = settings.get("channel_group_name", self._channel_group_name)
            active_channel_ids = set(Channel.objects.filter(
                channel_group__name=group_name
            ).values_list('id', flat=True))
            tracked_streams = settings.get("tracked_streams", {})
            stream_count = sum(
                1 for s in tracked_streams.values()
                if s.get("youtube_channel_name", "").lower() == youtube_channel_name.lower()
                and s.get("channel_id") in active_channel_ids
            )
            stream_number = stream_count + 1
        channel_name = f"{youtube_channel_name} #{stream_number}"

        # Create or get Logo from channel thumbnail URL
        logo = None
        logo_url = channel_thumbnail if channel_thumbnail else thumbnail
        if logo_url:
            try:
                # Try to find existing logo with same URL or create new one
                logo, created = Logo.objects.get_or_create(
                    url=logo_url,
                    defaults={"name": youtube_channel_name}
                )
                if created:
                    self._log(f"Created logo for {youtube_channel_name}: {logo_url[:60]}...")
                else:
                    self._log(f"Reusing existing logo for {youtube_channel_name}")
            except Exception as logo_exc:
                self._log(f"Could not create logo: {logo_exc}")

        # Create Channel with formatted name and logo
        channel = Channel.objects.create(
            name=channel_name,
            channel_number=channel_number,
            channel_group=group,
            logo=logo,
            stream_profile_id=self._get_stream_profile_id(settings),
        )

        # Track this channel number to avoid duplicates in same poll cycle
        self._assigned_channel_numbers.add(channel_number)

        # Auto-create and assign EPG if configured
        epg_source_name = settings.get("epg_source_name", "YouTube Live").strip()
        epg_source_name = epg_source_name.replace("{title}", video_title).replace("{channel}", youtube_channel_name)
        if epg_source_name:
            try:
                # Get or create the Dummy EPG source
                epg_source_obj, source_created = EPGSource.objects.get_or_create(
                    name=epg_source_name,
                    defaults={
                        "source_type": "dummy",
                        "is_active": True,
                    }
                )
                if source_created:
                    self._log(f"Created Dummy EPG source: {epg_source_name}")

                # Get or create EPGData entry for this channel.
                # Use channel_number as tvg_id since Dispatcharr uses channel_number as the ID in EPG XML output.
                channel_tvg_id = str(channel_number)
                epg_data, data_created = EPGData.objects.get_or_create(
                    tvg_id=channel_tvg_id,
                    epg_source=epg_source_obj,
                    defaults={
                        "name": video_title,
                    }
                )
                if data_created:
                    self._log(f"Created EPG data entry for: {channel_name} (tvg_id={channel_tvg_id})")
                else:
                    if epg_data.name != video_title:
                        epg_data.name = video_title
                        epg_data.save(update_fields=["name"])

                # Assign to channel - set tvg_id to match channel_number for EPG XML output
                channel.epg_data = epg_data
                channel.tvg_id = channel_tvg_id
                channel.save(update_fields=['epg_data', 'tvg_id'])
                self._log(f"Assigned EPG '{epg_source_name}' to channel with tvg_id={channel_tvg_id}")

                # Ensure a single program exists so the guide shows the stream title.
                now = timezone.now()
                program_obj, _ = ProgramData.objects.update_or_create(
                    epg=epg_data,
                    tvg_id=channel_tvg_id,
                    defaults={
                        "title": video_title,
                        "description": video_title,
                        "start_time": now,
                        "end_time": now + timedelta(hours=12),
                    },
                )
                try:
                    _existing_pp = getattr(program_obj, 'custom_properties', None)
                    program_obj.custom_properties = self._merge_youtubearr_custom_properties(
                        _existing_pp if isinstance(_existing_pp, dict) else {},
                        youtube_video_id=video_id,
                        youtube_channel_id=youtube_channel_id,
                    )
                    program_obj.save(update_fields=['custom_properties'])
                except Exception:
                    pass  # custom_properties may not exist on this Dispatcharr version
            except Exception as epg_exc:
                self._log(f"Could not assign EPG: {epg_exc}")

        # Link Channel to Stream
        ChannelStream.objects.get_or_create(
            channel=channel,
            stream=stream,
            defaults={"order": 0}
        )

        # Add to Channel Profile if configured
        channel_profile_name = settings.get("channel_profile_name", "").strip()
        if channel_profile_name:
            try:
                profile = ChannelProfile.objects.filter(name__iexact=channel_profile_name).first()
                if profile:
                    ChannelProfileMembership.objects.get_or_create(
                        channel_profile=profile,
                        channel=channel,
                        defaults={"enabled": True}
                    )
                    self._log(f"Added channel to profile '{profile.name}'")
                else:
                    self._log(f"Warning: Channel Profile '{channel_profile_name}' not found")
            except Exception as profile_exc:
                self._log_error(f"Failed to add channel to profile: {profile_exc}")

        return stream, channel

    def _parse_channel_number_mapping(self, settings: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Parse channel number mapping from monitored_channels setting.

        Combined format: @Handle or @Handle=BaseNumber or @Handle=BaseNumber:TitleFilter

        Examples:
            @NASA=92
            @RyanHallYall=90
            @VirtualRailfan=91:Horseshoe Curve|La Grange|Glendale

        Channels without =Number are monitored but get auto-assigned numbers.

        Returns dict mapping (channel_id or lowercase name) to:
            {"base": int, "filter": str or None}
        """
        # Read from monitored_channels (combined format)
        mapping_raw = settings.get("monitored_channels", "")
        mapping = {}

        for line in mapping_raw.split("\n"):
            line = line.strip()
            if not line or "=" not in line:
                continue

            try:
                channel_part, rest = line.split("=", 1)
                channel_part = channel_part.strip()
                rest = rest.strip()

                # Check for title filter after ":"
                if ":" in rest:
                    number_part, filter_part = rest.split(":", 1)
                    base_number = int(number_part.strip())
                    title_filter = filter_part.strip() if filter_part.strip() else None
                else:
                    base_number = int(rest)
                    title_filter = None

                mapping_entry = {"base": base_number, "filter": title_filter}

                if channel_part.startswith("@"):
                    # Resolve @handle to channel_id for reliable matching
                    username = channel_part[1:]
                    channel_id = self._resolve_username_to_channel_id(username)
                    if channel_id:
                        mapping[channel_id] = mapping_entry
                        filter_info = f", filter='{title_filter}'" if title_filter else ""
                        self._log(f"Mapping: @{username} ({channel_id}) → base {base_number}{filter_info}")
                    else:
                        # Fallback to lowercase handle name
                        mapping[username.lower()] = mapping_entry
                        filter_info = f", filter='{title_filter}'" if title_filter else ""
                        self._log(f"Mapping: @{username} (unresolved) → base {base_number}{filter_info}")
                else:
                    # Plain channel name - store lowercase for matching
                    mapping[channel_part.lower()] = mapping_entry

            except (ValueError, AttributeError):
                continue

        return mapping

    def _check_title_filter(self, title: str, channel_id: str, settings: Dict[str, Any]) -> bool:
        """Check if a stream title passes the filter for a channel.

        Returns True if:
            - No filter is configured for this channel
            - Title matches the filter pattern (case-insensitive)

        Returns False if filter exists and title doesn't match.
        """
        mapping = self._parse_channel_number_mapping(settings)

        # Find mapping entry for this channel
        entry = mapping.get(channel_id)
        if not entry:
            return True  # No mapping = no filter = allow all

        title_filter = entry.get("filter")
        if not title_filter:
            return True  # No filter = allow all

        # Check if title matches filter (case-insensitive regex)
        try:
            if re.search(title_filter, title, re.IGNORECASE):
                self._log(f"Title filter MATCH: '{title[:50]}...' matches '{title_filter}'")
                return True
            else:
                self._log(f"Title filter SKIP: '{title[:50]}...' does not match '{title_filter}'")
                return False
        except re.error as e:
            self._log_error(f"Invalid title filter regex '{title_filter}': {e}")
            return True  # On regex error, allow the stream

    def _get_next_subchannel_number(self, base_number: int, settings: Dict[str, Any]) -> float:
        """Get the next available sub-channel number for a base (e.g., 90.1, 90.2, etc.)"""
        # Get all channels in this base range [base, base+1)
        # NOTE: We intentionally do NOT check tracked_streams here. tracked_streams can be stale
        # (e.g., written back by an in-flight poll after Reset All). The DB and _assigned_channel_numbers
        # are authoritative: DB has all committed channels, _assigned_channel_numbers has channels
        # created earlier in this same poll cycle that aren't in DB yet.
        existing_subchannels = []

        # Check actual Dispatcharr channels in DB
        group_name = settings.get("channel_group_name", self._channel_group_name)
        try:
            group = ChannelGroup.objects.get(name=group_name)
            for ch_num in Channel.objects.filter(channel_group=group).values_list('channel_number', flat=True):
                if ch_num is not None:
                    try:
                        ch_float = float(ch_num)
                        if base_number <= ch_float < base_number + 1:
                            existing_subchannels.append(ch_float)
                    except (TypeError, ValueError):
                        pass
        except ChannelGroup.DoesNotExist:
            pass

        # Also check channel numbers assigned during this poll cycle (not yet committed to DB)
        for ch_num in self._assigned_channel_numbers:
            try:
                ch_float = float(ch_num)
                if base_number <= ch_float < base_number + 1:
                    existing_subchannels.append(ch_float)
            except (TypeError, ValueError):
                pass

        # Remove duplicates
        existing_subchannels = list(set(existing_subchannels))

        if not existing_subchannels:
            return float(f"{base_number}.1")

        # Extract occupied decimal parts as integers using string representation.
        # This avoids float arithmetic issues (e.g., float("92.10") == float("92.1")),
        # and fills gaps (if 92.1-92.4 are free but 92.5-92.8 are taken, start at 92.1).
        occupied = set()
        for ch_num in existing_subchannels:
            ch_str = str(float(ch_num))
            if '.' in ch_str:
                try:
                    occupied.add(int(ch_str.split('.')[1]))
                except ValueError:
                    pass

        # Find the first available decimal slot starting from 1.
        # Skip multiples of 10 (10, 20, 30...) because float("90.10") == float("90.1"),
        # which would collide with an already-assigned slot.
        next_decimal = 1
        while next_decimal in occupied:
            next_decimal += 1
            if next_decimal % 10 == 0:
                next_decimal += 1

        return float(f"{base_number}.{next_decimal}")

    def _get_next_unmapped_base_number(self, settings: Dict[str, Any]) -> int:
        """Get the next available base channel number for unmapped YouTube channels."""
        starting_number = settings.get("starting_channel_number", self._starting_channel_number)
        increment = settings.get("channel_number_increment", 1)

        try:
            starting_number = int(starting_number)
            increment = int(increment)
        except (TypeError, ValueError):
            starting_number = self._starting_channel_number
            increment = 1

        # Get all mapped base numbers (mapping values are now dicts with "base" key)
        mapping = self._parse_channel_number_mapping(settings)
        mapped_bases = set(entry["base"] for entry in mapping.values())

        # Get all used base numbers from tracked_streams
        tracked_streams = settings.get("tracked_streams", {})
        used_bases = set()
        for stream_data in tracked_streams.values():
            ch_num = stream_data.get("channel_number")
            if ch_num is not None:
                try:
                    used_bases.add(int(float(ch_num)))
                except (TypeError, ValueError):
                    pass

        # Also check actual Dispatcharr channels
        group_name = settings.get("channel_group_name", self._channel_group_name)
        try:
            group = ChannelGroup.objects.get(name=group_name)
            for ch_num in Channel.objects.filter(channel_group=group).values_list('channel_number', flat=True):
                if ch_num is not None:
                    try:
                        used_bases.add(int(float(ch_num)))
                    except (TypeError, ValueError):
                        pass
        except ChannelGroup.DoesNotExist:
            pass

        # Combine mapped and used bases
        all_used = mapped_bases | used_bases

        # Find next available base starting from starting_number
        next_base = starting_number
        while next_base in all_used:
            next_base += increment

        return next_base

    def _get_next_sequential_number(self, settings: Dict[str, Any]) -> int:
        """Get the next available sequential channel number (whole numbers only).

        Used when channel_numbering_mode is 'sequential'. Simply finds the next
        available whole number, ignoring base/sub-channel grouping.
        """
        starting_number = settings.get("starting_channel_number", self._starting_channel_number)
        increment = settings.get("channel_number_increment", 1)

        try:
            starting_number = int(starting_number)
            increment = int(increment)
        except (TypeError, ValueError):
            starting_number = self._starting_channel_number
            increment = 1

        # Get all used channel numbers (as integers)
        used_numbers = set()

        # From tracked_streams
        tracked_streams = settings.get("tracked_streams", {})
        for stream_data in tracked_streams.values():
            ch_num = stream_data.get("channel_number")
            if ch_num is not None:
                try:
                    used_numbers.add(int(float(ch_num)))
                except (TypeError, ValueError):
                    pass

        # From actual Dispatcharr channels in our group
        group_name = settings.get("channel_group_name", self._channel_group_name)
        try:
            group = ChannelGroup.objects.get(name=group_name)
            for ch_num in Channel.objects.filter(channel_group=group).values_list('channel_number', flat=True):
                if ch_num is not None:
                    try:
                        used_numbers.add(int(float(ch_num)))
                    except (TypeError, ValueError):
                        pass
        except ChannelGroup.DoesNotExist:
            pass

        # Find next available number
        next_num = starting_number
        while next_num in used_numbers:
            next_num += increment

        return next_num

    def _get_channel_number_for_stream(self, youtube_channel_name: str, settings: Dict[str, Any], youtube_channel_id: str = "") -> float:
        """Get channel number for a stream, using sub-channel mapping if configured.

        Args:
            youtube_channel_name: Display name from yt-dlp (e.g., "Ryan Hall, Y'all")
            settings: Plugin settings dict
            youtube_channel_id: YouTube channel ID (UC...) for reliable @handle matching

        Returns a decimal channel number (e.g., 90.1, 90.2).
        """
        # Parse the mapping (returns channel_id or lowercase name → base_number)
        mapping = self._parse_channel_number_mapping(settings)

        # Normalize the channel name for lookup
        channel_name_lower = youtube_channel_name.lower()

        # Check if this YouTube channel is mapped
        base_number = None

        # First, try matching by channel_id (most reliable for @handle mappings)
        if youtube_channel_id and youtube_channel_id in mapping:
            base_number = mapping[youtube_channel_id]["base"]
            self._log(f"Channel '{youtube_channel_name}' ({youtube_channel_id}) mapped to base {base_number}")

        # If not found by ID, try matching by display name
        if base_number is None:
            for mapped_key, mapped_entry in mapping.items():
                if mapped_key == channel_name_lower:
                    base_number = mapped_entry["base"]
                    self._log(f"Channel '{youtube_channel_name}' mapped by name to base {base_number}")
                    break

        if base_number is None:
            # Check if we've seen this channel before (in tracked_streams)
            # Check monitored_channel_id first (for sub-channels), then youtube_channel_id, then name
            tracked_streams = settings.get("tracked_streams", {})
            for stream_data in tracked_streams.values():
                # Match by monitored_channel_id (handles sub-channels/aggregated streams)
                if youtube_channel_id and stream_data.get("monitored_channel_id") == youtube_channel_id:
                    ch_num = stream_data.get("channel_number")
                    if ch_num is not None:
                        try:
                            base_number = int(float(ch_num))
                            self._log(f"Channel '{youtube_channel_name}' previously used base {base_number} (by monitored ID)")
                            break
                        except (TypeError, ValueError):
                            pass
                # Match by youtube_channel_id (stream's actual channel)
                elif youtube_channel_id and stream_data.get("youtube_channel_id") == youtube_channel_id:
                    ch_num = stream_data.get("channel_number")
                    if ch_num is not None:
                        try:
                            base_number = int(float(ch_num))
                            self._log(f"Channel '{youtube_channel_name}' previously used base {base_number} (by stream ID)")
                            break
                        except (TypeError, ValueError):
                            pass
                # Fallback to matching by name
                elif stream_data.get("youtube_channel_name", "").lower() == channel_name_lower:
                    ch_num = stream_data.get("channel_number")
                    if ch_num is not None:
                        try:
                            base_number = int(float(ch_num))
                            self._log(f"Channel '{youtube_channel_name}' previously used base {base_number} (by name)")
                            break
                        except (TypeError, ValueError):
                            pass

        if base_number is None:
            # Unmapped channel - assign a new base number
            base_number = self._get_next_unmapped_base_number(settings)
            self._log(f"Channel '{youtube_channel_name}' unmapped, assigning new base {base_number}")

        # Check numbering mode
        numbering_mode = settings.get("channel_numbering_mode", "decimal")

        if numbering_mode == "sequential":
            # Sequential mode: use whole numbers only
            channel_number = float(self._get_next_sequential_number(settings))
            self._log(f"Assigned sequential channel number {int(channel_number)} for '{youtube_channel_name}'")
        else:
            # Decimal mode: use sub-channels (90.1, 90.2, etc.)
            channel_number = self._get_next_subchannel_number(base_number, settings)
            self._log(f"Assigned decimal channel number {channel_number} for '{youtube_channel_name}'")

        return channel_number

    def _get_next_youtube_channel_number(self, settings: Dict[str, Any]) -> float:
        """Legacy function - now returns float for sub-channel support.

        This is kept for backwards compatibility but new code should use
        _get_channel_number_for_stream() which handles mapping.
        """
        return float(self._get_next_unmapped_base_number(settings)) + 0.1

    def _get_stream_profile_id(self, settings: Optional[Dict[str, Any]] = None) -> int:
        """Get or find a suitable stream profile ID.

        Args:
            settings: Plugin settings dict. If stream_profile_name is set, use that profile.
        """
        # Check for user-configured profile name first
        if settings:
            profile_name = settings.get("stream_profile_name", "").strip()
            if profile_name:
                profile = StreamProfile.objects.filter(name__iexact=profile_name).first()
                if profile:
                    self._log(f"Using configured stream profile: {profile.name}")
                    return profile.id
                else:
                    self._log(f"Warning: Stream profile '{profile_name}' not found, falling back to auto-detect")

        # Use cached profile ID if available
        if self._stream_profile_id is not None:
            return self._stream_profile_id

        # Try to find "proxy" profile (common default)
        profile = (
            StreamProfile.objects.filter(name__iexact="proxy").first()
            or StreamProfile.objects.filter(name__icontains="proxy").first()
        )

        if not profile:
            profile = StreamProfile.objects.first()

        if not profile:
            raise RuntimeError("No stream profiles found. Create a stream profile in Dispatcharr.")

        self._stream_profile_id = profile.id
        return self._stream_profile_id

    # --- YouTube Data API Integration ---

    def _poll_monitored_channels(self, settings: Dict[str, Any]) -> tuple[int, int]:
        """Poll monitored channels for new/ended streams. Returns (added, ended) counts.

        Uses yt-dlp two-phase scan to detect live streams - NO YouTube API quota required!
        """
        # Clear assigned channel numbers at start of poll cycle to avoid duplicates
        self._assigned_channel_numbers.clear()

        self._log("=== Starting poll cycle (yt-dlp mode - no API quota) ===")

        # Parse monitored channels
        monitored_raw = settings.get("monitored_channels", "").strip()
        self._log(f"Raw monitored_channels value: '{monitored_raw}'")

        if not monitored_raw:
            self._log("No monitored channels configured")
            return 0, 0

        channel_ids = self._parse_channel_ids(monitored_raw)
        if not channel_ids:
            self._log("No valid channel IDs found to poll")
            return 0, 0

        self._log(f"Parsed {len(channel_ids)} channel(s) to poll: {', '.join(channel_ids[:5])}")  # Show first 5

        # Get username map for yt-dlp (needs @handles, not channel IDs)
        username_map = self._extract_username_map(monitored_raw)

        tracked_streams = settings.get("tracked_streams", {})
        added_count = 0
        ended_count = 0

        for channel_id in channel_ids:
            try:
                # Get the @username for this channel (yt-dlp works better with handles)
                username = username_map.get(channel_id)
                if not username:
                    self._log(f"No @username found for {channel_id}, skipping")
                    continue

                self._log(f"Polling channel: @{username} ({channel_id})")

                # Get live streams — pass per-channel title filter so it can be applied
                # between Phase 1 and Phase 2, avoiding live checks on non-matching streams.
                mapping = self._parse_channel_number_mapping(settings)
                channel_filter = (mapping.get(channel_id) or {}).get("filter")
                live_streams = self._get_live_streams_via_ytdlp(username, settings, title_filter=channel_filter)

                # Handle errors - None means error occurred, skip this channel
                if live_streams is None:
                    self._log_error(f"yt-dlp error for @{username}, skipping ended-stream check to avoid false positives")
                    continue

                self._log(f"Found {len(live_streams)} live stream(s) on @{username}")

                # Check for new streams
                self._log(f"Checking {len(live_streams)} stream(s) against tracked_streams (currently tracking {len(tracked_streams)} streams)")
                for stream_info in live_streams:
                    video_id = stream_info.get("video_id")

                    # Check if stream is in tracked_streams
                    is_tracked = video_id in tracked_streams
                    is_readd = False  # Track if this is a re-add (was tracked but channel deleted)

                    # If tracked, verify the Dispatcharr channel still exists
                    if is_tracked:
                        channel_id_to_check = tracked_streams[video_id].get("channel_id")
                        try:
                            Channel.objects.get(id=channel_id_to_check)
                            self._log(f"Processing stream {video_id}: in_tracked=True, channel exists (#{channel_id_to_check}), skipping")
                            continue  # Channel exists, skip re-adding
                        except Channel.DoesNotExist:
                            self._log(f"Processing stream {video_id}: in_tracked=True but channel #{channel_id_to_check} was deleted")

                            # Check if there's already another channel with this video before re-adding
                            # Look for channels in our group that have a stream containing this video ID
                            try:
                                group_name = settings.get("channel_group_name", self._channel_group_name)
                                channel_group = ChannelGroup.objects.get(name=group_name)
                                existing_channel = None
                                for ch in Channel.objects.filter(channel_group=channel_group):
                                    for stream in ch.streams.all():
                                        if stream.url and video_id in stream.url:
                                            existing_channel = ch
                                            break
                                        if stream.name and video_id in stream.name:
                                            existing_channel = ch
                                            break
                                    if existing_channel:
                                        break

                                if existing_channel:
                                    # Found existing channel - update tracked_streams to point to it
                                    self._log(f"Found existing channel #{existing_channel.id} ({existing_channel.channel_number}) with video {video_id}, updating tracked_streams")
                                    stream_obj = existing_channel.streams.first()
                                    tracked_streams[video_id] = {
                                        "video_id": video_id,
                                        "channel_id": existing_channel.id,
                                        "stream_id": stream_obj.id if stream_obj else None,
                                        "monitored_channel_id": channel_id,
                                        "youtube_channel_id": tracked_streams.get(video_id, {}).get("youtube_channel_id", ""),
                                        "youtube_channel_name": tracked_streams.get(video_id, {}).get("youtube_channel_name", ""),
                                        "title": stream_obj.name if stream_obj else "",
                                        "added_at": tracked_streams.get(video_id, {}).get("added_at", timezone.now().isoformat()),
                                        "last_url_refresh": timezone.now().isoformat(),
                                        "stream_url": stream_obj.url if stream_obj else "",
                                        "is_live": True,
                                        "channel_number": existing_channel.channel_number,
                                    }
                                    self._persist_settings({"tracked_streams": tracked_streams})
                                    continue  # Skip re-adding, we've linked to existing channel
                            except ChannelGroup.DoesNotExist:
                                pass

                            # No existing channel found, proceed with re-adding
                            self._log(f"No existing channel found for {video_id}, will re-add")
                            del tracked_streams[video_id]
                            self._persist_settings({"tracked_streams": tracked_streams})
                            is_tracked = False
                            is_readd = True  # Don't send notification for re-adds

                    self._log(f"Processing stream {video_id}: in_tracked={is_tracked}, is_readd={is_readd}")

                    # Before treating an untracked stream as new, check if a channel already
                    # exists in the group for this video. tracked_streams can be cleared by Reset All
                    # or cleanup while the channel still exists — we should restore tracking rather
                    # than create a duplicate and send a spurious notification.
                    if video_id and not is_tracked:
                        try:
                            group_name = settings.get("channel_group_name", self._channel_group_name)
                            channel_group = ChannelGroup.objects.get(name=group_name)
                            existing_channel = None
                            for ch in Channel.objects.filter(channel_group=channel_group):
                                for stream_obj in ch.streams.all():
                                    if (stream_obj.url and video_id in stream_obj.url) or \
                                       (stream_obj.name and video_id in stream_obj.name):
                                        existing_channel = ch
                                        break
                                if existing_channel:
                                    break

                            if existing_channel:
                                self._log(f"Found existing channel for untracked stream {video_id}, restoring tracking (no notification)")
                                stream_obj = existing_channel.streams.first()
                                tracked_streams[video_id] = {
                                    "video_id": video_id,
                                    "channel_id": existing_channel.id,
                                    "stream_id": stream_obj.id if stream_obj else None,
                                    "monitored_channel_id": channel_id,
                                    "youtube_channel_id": "",
                                    "youtube_channel_name": "",
                                    "title": stream_obj.name if stream_obj else "",
                                    "added_at": timezone.now().isoformat(),
                                    "last_url_refresh": timezone.now().isoformat(),
                                    "stream_url": stream_obj.url if stream_obj else "",
                                    "is_live": True,
                                    "channel_number": existing_channel.channel_number,
                                }
                                self._persist_settings({"tracked_streams": tracked_streams})
                                continue  # Tracking restored, skip re-add and notification
                        except ChannelGroup.DoesNotExist:
                            pass

                    if video_id and not is_tracked:
                        # Skip streams that recently failed metadata extraction.
                        # Prevents re-attempting every poll for inaccessible streams (e.g., members-only).
                        # Cleared when monitoring starts so new cookies take effect immediately.
                        failure_time = self._extraction_failures.get(video_id, 0)
                        if time.time() - failure_time < 86400:  # 24-hour retry window
                            self._log(f"Skipping {video_id}: metadata extraction failed recently (retries in {int(86400 - (time.time() - failure_time)) // 3600}h)")
                            continue

                        # New livestream detected
                        self._log(f"New stream detected: {video_id}, extracting metadata...")
                        quality = settings.get("stream_quality", "best")
                        cookies_content = settings.get("cookies_content", "")
                        metadata = self._extract_stream_metadata(video_id, quality, cookies_content)

                        if not metadata:
                            self._log_error(f"Failed to extract metadata for {video_id} - yt-dlp returned None")
                            self._extraction_failures[video_id] = time.time()
                            self._persist_extraction_failures()
                            continue

                        if metadata.get("_members_only"):
                            self._log(f"Skipping {video_id}: members-only content (retry in 7 days)")
                            # Store time 6 days in the future so the 24h check won't clear it for 7 days total
                            self._extraction_failures[video_id] = time.time() + 86400 * 6
                            self._persist_extraction_failures()
                            continue

                        self._log(f"Metadata extracted for {video_id}: is_live={metadata.get('is_live')}, title={metadata.get('title')}")

                        if metadata.get("is_live"):
                            # Title filter already applied earlier (before metadata extraction)
                            try:
                                # Double-check that the stream wasn't just added by a concurrent poll
                                # Reload settings to get the latest tracked_streams
                                try:
                                    cfg_check = PluginConfig.objects.get(key=self._plugin_key)
                                    current_tracked = dict(cfg_check.settings or {}).get("tracked_streams", {})
                                    if video_id in current_tracked:
                                        self._log(f"Stream {video_id} was already added by another process, skipping")
                                        continue
                                except PluginConfig.DoesNotExist:
                                    pass

                                self._log(f"Creating channel for {video_id}...")
                                # Pass monitored_channel_id for mapping (stream may be from sub-channel)
                                stream, channel = self._create_stream_and_channel(metadata, settings, monitored_channel_id=channel_id)

                                tracked_streams[video_id] = {
                                    "video_id": video_id,
                                    "channel_id": channel.id,
                                    "stream_id": stream.id,
                                    "monitored_channel_id": channel_id,  # The channel being monitored (for mapping)
                                    "youtube_channel_id": metadata.get("youtube_channel_id", ""),  # Stream's actual channel
                                    "youtube_channel_name": metadata.get("youtube_channel_name", ""),
                                    "title": metadata.get("title", ""),
                                    "added_at": timezone.now().isoformat(),
                                    "last_url_refresh": timezone.now().isoformat(),
                                    "stream_url": metadata.get("stream_url", ""),
                                    "is_live": True,
                                    "channel_number": channel.channel_number,
                                }

                                # Persist immediately to prevent duplicates in concurrent polls
                                self._persist_settings({"tracked_streams": tracked_streams})

                                added_count += 1
                                self._log(f"Auto-added stream: {metadata.get('title')} (Channel #{channel.channel_number})")

                                # Send Telegram notification only for truly new streams, not re-adds
                                if not is_readd:
                                    self._send_telegram_notification(settings, video_id, metadata, channel.channel_number, str(channel.uuid))
                                else:
                                    self._log(f"Skipping notification for re-added stream: {video_id}")

                            except Exception as exc:
                                self._log_error(f"Failed to add stream {video_id}: {exc}")
                        else:
                            self._log_error(f"Stream {video_id} is not live (is_live={metadata.get('is_live')}), skipping")

                # Check for ended streams (mark as not live)
                # yt-dlp flat-playlist gets all streams, so no truncation concerns
                current_video_ids = {s.get("video_id") for s in live_streams}
                for video_id, stream_data in list(tracked_streams.items()):
                    if stream_data.get("monitored_channel_id") == channel_id:
                        if video_id not in current_video_ids and stream_data.get("is_live"):
                            # Stream absent from scan — verify directly before marking ended.
                            # Phase 1 flat-playlist is fast but occasionally misses active streams
                            # (rate-limiting, CDN inconsistency). A direct video-level check is
                            # authoritative and avoids false deletions.
                            title = stream_data.get("title", video_id)
                            self._log(f"Stream not in scan results, verifying directly: {title}")
                            if self._verify_video_is_live(video_id):
                                self._log(f"Direct check: still live (scan false negative): {title}")
                            else:
                                stream_data["is_live"] = False
                                ended_count += 1
                                self._log(f"Direct check: confirmed ended: {title}")

            except Exception as exc:
                self._log_error(f"Failed to poll channel {channel_id}: {exc}")

        # Persist updates
        self._persist_settings({
            "tracked_streams": tracked_streams,
            "last_poll_time": timezone.now().isoformat(),
        })

        return added_count, ended_count

    def _verify_video_is_live(self, video_id: str) -> bool:
        """Directly verify whether a specific video is currently live.

        Used when a tracked stream disappears from the flat-playlist scan.
        Much more reliable than the channel /streams tab for ongoing streams.
        Fails safe — returns True (assume live) on any error or timeout.
        """
        try:
            if not self._ytdlp_path:
                return True
            cmd = [
                self._ytdlp_path,
                "--skip-download",
                "--print", "live_status",
                "--no-warnings",
                "--quiet",
            ]
            if self._qjs_path:
                cmd += ["--js-runtimes", f"quickjs:{self._qjs_path}"]
            cmd.append(f"https://www.youtube.com/watch?v={video_id}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            status = result.stdout.strip()
            self._log(f"Direct live check for {video_id}: {status!r}")
            return status == "is_live"
        except subprocess.TimeoutExpired:
            self._log_error(f"Direct live check timed out for {video_id}, assuming live")
            return True
        except Exception as exc:
            self._log_error(f"Direct live check failed for {video_id}: {exc}, assuming live")
            return True

    def _get_live_streams_via_ytdlp(self, channel_handle: str, settings: Dict[str, Any], title_filter: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Get currently live streams for a YouTube channel using two-phase detection.

        Phase 1: flat-playlist scan to collect video IDs from /streams tab (fast, no per-video fetches).
                 When a title_filter is set, scans up to 100 entries so the full channel is covered.
        Phase 2: per-video live_status check — only for title-matched candidates when filter is set,
                 otherwise for all candidates up to max_streams_per_channel.

        Uses NO API quota. Returns list of {video_id, title, thumbnail} dicts for confirmed-live
        streams only, or None on error (caller skips the channel).
        """
        if not channel_handle.startswith("@"):
            channel_handle = f"@{channel_handle}"

        if not self._ytdlp_path:
            self._log_error("yt-dlp binary not found")
            return None

        streams_url = f"https://www.youtube.com/{channel_handle}/streams"
        max_streams = int(settings.get("max_streams_per_channel", 15))

        # When a title filter is set, scan more entries in Phase 1 (cheap — one fast request)
        # so we don't miss matching streams that sit beyond the default cap.
        phase1_limit = 100 if title_filter else max_streams

        self._log(f"Scanning {streams_url} (up to {phase1_limit} entries)")
        try:
            cmd = [
                self._ytdlp_path,
                "--flat-playlist",
                "--dump-json",
                "--playlist-end", str(phase1_limit),
                "--no-warnings",
                "--ignore-errors",
                streams_url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0 and not result.stdout:
                self._log_error(f"yt-dlp scan failed: {result.stderr[:200] if result.stderr else 'no output'}")
                return None

            candidates = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    video_id = entry.get("id")
                    if video_id:
                        title = entry.get("title", "Unknown")
                        thumbnail = entry.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                        candidates.append({"video_id": video_id, "title": title, "thumbnail": thumbnail})
                except json.JSONDecodeError:
                    continue

            if not candidates:
                self._log(f"No entries found on {streams_url}")
                return []

            # Apply title filter between phases — avoids live checks on non-matching streams.
            # This is the key optimisation for channels with many simultaneous streams (e.g.
            # VirtualRailfan's 70+ railcam feeds): Phase 1 fetches all 100, filter cuts to
            # the 4-5 that match, Phase 2 only checks those.
            if title_filter:
                before = len(candidates)
                try:
                    candidates = [c for c in candidates if re.search(title_filter, c["title"], re.IGNORECASE)]
                except re.error as e:
                    self._log_error(f"Invalid title filter regex '{title_filter}': {e}")
                if len(candidates) < before:
                    self._log(f"Title filter: {len(candidates)}/{before} candidates match '{title_filter}'")

            if not candidates:
                self._log(f"No candidates match title filter for {channel_handle}")
                return []

            self._log(f"Phase 1: {len(candidates)} candidate(s), checking live status...")

        except subprocess.TimeoutExpired:
            self._log_error(f"Phase 1 scan timed out for {channel_handle}")
            return None
        except Exception as exc:
            self._log_error(f"Phase 1 scan error for {channel_handle}: {exc}")
            return None

        # Phase 2: check live_status per candidate (lightweight — no format selection or URL extraction)
        live_streams = []
        for candidate in candidates:
            video_id = candidate["video_id"]
            try:
                check_cmd = [
                    self._ytdlp_path,
                    "--skip-download",
                    "--print", "live_status",
                    "--no-warnings",
                    "--quiet",
                ]
                if self._qjs_path:
                    check_cmd += ["--js-runtimes", f"quickjs:{self._qjs_path}"]
                check_cmd.append(f"https://www.youtube.com/watch?v={video_id}")

                check = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
                status = check.stdout.strip()
                if status == "is_live":
                    live_streams.append(candidate)
                    self._log(f"Live confirmed: {candidate['title']} ({video_id})")
                else:
                    self._log(f"Not live ({status or 'no status'}): {candidate['title']}")
            except subprocess.TimeoutExpired:
                self._log_error(f"Live check timed out for {video_id}, skipping")
            except Exception as exc:
                self._log_error(f"Live check failed for {video_id}: {exc}, skipping")

        self._log(f"Found {len(live_streams)} live stream(s) for {channel_handle}")
        return live_streams

    def _extract_username_map(self, raw: str) -> Dict[str, str]:
        """Extract mapping of channel_id -> username from monitored channels input.

        Handles combined format: @channel=90:filter - extracts just the @channel part.
        """
        username_map = {}
        parts = re.split(r'[,;\n]+', raw)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Strip off =number:filter suffix if present (combined format)
            if "=" in part:
                part = part.split("=")[0].strip()

            _part_netloc = urllib.parse.urlparse(part).netloc.lower()
            _is_yt_url = _part_netloc == "youtube.com" or _part_netloc.endswith(".youtube.com")
            username = None
            if part.startswith("@"):
                username = part[1:]
            elif _is_yt_url:
                match = re.search(r'/@([a-zA-Z0-9_-]+)', part)
                if match:
                    username = match.group(1)

            if username:
                # Resolve to channel ID
                channel_id = self._resolve_username_to_channel_id(username)
                if channel_id:
                    username_map[channel_id] = username

        return username_map

    def _parse_channel_ids(self, raw: str) -> List[str]:
        """Parse channel IDs from combined format string.

        Handles: @channel, @channel=90, @channel=90:filter
        Extracts just the channel part, ignoring =number:filter suffix.
        """
        # Split by common separators
        parts = re.split(r'[,;\n]+', raw)

        self._log(f"Parsing monitored channels input: {raw[:100]}")  # Show first 100 chars
        self._log(f"Split into {len(parts)} part(s): {[p.split('=')[0].strip() for p in parts if p.strip()]}")

        channel_ids = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Strip off =number:filter suffix if present (combined format)
            if "=" in part:
                part = part.split("=")[0].strip()

            # Check if it's just @username (without URL)
            if part.startswith("@"):
                username = part[1:]  # Remove the @ symbol
                self._log(f"Detected @username format: @{username}")
                resolved_id = self._resolve_username_to_channel_id(username)
                if resolved_id:
                    channel_ids.append(resolved_id)
                    self._log(f"Resolved @{username} to channel ID: {resolved_id}")
                else:
                    self._log_error(f"Could not resolve @{username} to channel ID. Please use channel ID (UC...) instead.")
                continue

            # Extract channel ID from URL if needed
            _netloc = urllib.parse.urlparse(part).netloc.lower()
            if _netloc == "youtube.com" or _netloc.endswith(".youtube.com") or _netloc == "youtu.be" or _netloc.endswith(".youtu.be"):
                # Try to extract channel ID from URL formats:
                # - /channel/UC...
                # - /@username
                # - /c/channelname

                # Direct channel ID
                match = re.search(r'/channel/([a-zA-Z0-9_-]+)', part)
                if match:
                    channel_ids.append(match.group(1))
                    self._log(f"Parsed channel ID: {match.group(1)} from {part}")
                    continue

                # @username in URL - need to resolve to channel ID
                match = re.search(r'/@([a-zA-Z0-9_-]+)', part)
                if match:
                    username = match.group(1)
                    # Try to resolve @username to channel ID
                    resolved_id = self._resolve_username_to_channel_id(username)
                    if resolved_id:
                        channel_ids.append(resolved_id)
                        self._log(f"Resolved @{username} to channel ID: {resolved_id}")
                    else:
                        self._log_error(f"Could not resolve @{username} to channel ID. Please use channel ID (UC...) instead.")
                    continue

                # /c/ format
                match = re.search(r'/c/([a-zA-Z0-9_-]+)', part)
                if match:
                    channel_name = match.group(1)
                    self._log_error(f"/c/ format not supported. Please find channel ID (UC...) for: {channel_name}")
                    continue

                # Fallback: might be direct channel ID in URL
                self._log_error(f"Could not parse channel ID from URL: {part}")
            else:
                # Assume it's already a channel ID (starts with UC usually)
                if part.startswith("UC") or len(part) == 24:
                    channel_ids.append(part)
                    self._log(f"Using channel ID: {part}")
                else:
                    self._log_error(f"Invalid channel ID format: {part}. Should be 24 characters starting with UC or @username")

        return channel_ids

    def _resolve_username_to_channel_id(self, username: str) -> Optional[str]:
        """Try to resolve @username to channel ID, using cache when available.

        Cache is stored in settings['username_cache'] and persists across restarts.
        """
        # Check cache first
        try:
            cfg = PluginConfig.objects.get(key=self._plugin_key)
            settings = dict(cfg.settings or {})
            username_cache = settings.get("username_cache", {})

            if username in username_cache:
                channel_id = username_cache[username]
                self._log(f"Cache hit: @{username} -> {channel_id}")
                return channel_id
        except PluginConfig.DoesNotExist:
            username_cache = {}

        # Cache miss - scrape the channel page
        try:
            url = f"https://www.youtube.com/@{username}"

            request = urllib.request.Request(url)
            request.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            with urllib.request.urlopen(request, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            channel_id = None

            # Look for channel ID in the HTML
            # Pattern: "channelId":"UCxxxxxxxxxxxxxxxx"
            match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', html)
            if match:
                channel_id = match.group(1)

            # Alternative pattern: "externalId":"UCxxxxxxxxxxxxxxxx"
            if not channel_id:
                match = re.search(r'"externalId":"(UC[a-zA-Z0-9_-]{22})"', html)
                if match:
                    channel_id = match.group(1)

            # Try browse_id pattern
            if not channel_id:
                match = re.search(r'"browseId":"(UC[a-zA-Z0-9_-]{22})"', html)
                if match:
                    channel_id = match.group(1)

            if channel_id:
                self._log(f"Resolved @{username} to {channel_id}")
                # Cache the result
                username_cache[username] = channel_id
                self._persist_settings({"username_cache": username_cache})
                return channel_id

            self._log_error(f"Could not find channel ID in webpage for @{username}")
            return None

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                self._log_error(f"YouTube channel @{username} not found (404)")
            else:
                self._log_error(f"HTTP error resolving @{username}: {exc.code}")
            return None
        except Exception as exc:
            self._log_error(f"Error resolving @{username}: {exc}")
            return None

    # --- URL Refresh ---

    def _refresh_expiring_urls(self, settings: Dict[str, Any]) -> int:
        """Refresh stream URLs that are approaching expiration. Returns count of refreshed URLs"""
        tracked_streams = settings.get("tracked_streams", {})
        refresh_interval = settings.get("url_refresh_interval_seconds", 3600)
        now = datetime.now(dt_timezone.utc)
        refreshed_count = 0

        for video_id, stream_data in tracked_streams.items():
            if not stream_data.get("is_live"):
                continue

            last_refresh_str = stream_data.get("last_url_refresh")
            if not last_refresh_str:
                continue

            try:
                last_refresh = datetime.fromisoformat(last_refresh_str.replace("Z", "+00:00"))
                if isinstance(last_refresh.tzinfo, type(None)):
                    last_refresh = last_refresh.replace(tzinfo=dt_timezone.utc)

                age_seconds = (now - last_refresh).total_seconds()

                if age_seconds > refresh_interval:
                    # Refresh needed
                    quality = settings.get("stream_quality", "best")
                    cookies_content = settings.get("cookies_content", "")
                    metadata = self._extract_stream_metadata(video_id, quality, cookies_content)

                    if metadata and metadata.get("stream_url"):
                        # Update Stream object
                        try:
                            stream = Stream.objects.get(id=stream_data["stream_id"])
                            stream.url = metadata["stream_url"]
                            stream.save(update_fields=["url"])

                            # Update tracked metadata
                            stream_data["stream_url"] = metadata["stream_url"]
                            stream_data["last_url_refresh"] = now.isoformat()
                            # Only update is_live if explicitly present in metadata
                            # Don't default to False as that causes premature cleanup
                            if "is_live" in metadata:
                                stream_data["is_live"] = metadata["is_live"]

                            refreshed_count += 1
                            self._log(f"Refreshed URL for: {stream_data.get('title')}")

                        except Stream.DoesNotExist:
                            self._log_error(f"Stream {stream_data['stream_id']} not found")

            except Exception as exc:
                self._log_error(f"Failed to refresh URL for {video_id}: {exc}")

        # Persist updates
        if refreshed_count > 0:
            self._persist_settings({"tracked_streams": tracked_streams})

        return refreshed_count

    def _refresh_epg_times(self, settings: Dict[str, Any]) -> int:
        """Refresh EPG programme times for all active streams.

        Keeps EPG current by updating start/end times to now + 12 hours.
        Returns count of refreshed programmes.
        """
        tracked_streams = settings.get("tracked_streams", {})
        refreshed_count = 0

        for video_id, stream_data in tracked_streams.items():
            if not stream_data.get("is_live"):
                continue

            channel_id = stream_data.get("channel_id")
            if not channel_id:
                continue

            try:
                from django.utils import timezone as dj_timezone
                channel = Channel.objects.get(id=channel_id)
                if channel.epg_data:
                    prog_now = dj_timezone.now()
                    updated = ProgramData.objects.filter(
                        epg=channel.epg_data
                    ).update(
                        start_time=prog_now,
                        end_time=prog_now + timedelta(hours=12)
                    )
                    if updated > 0:
                        refreshed_count += 1
            except Channel.DoesNotExist:
                pass
            except Exception as exc:
                self._log_error(f"Failed to refresh EPG for channel {channel_id}: {exc}")

        return refreshed_count

    # --- Cleanup ---

    def _cleanup_ended_streams(self, settings: Dict[str, Any], force: bool = False) -> int:
        """Remove channels for ended streams. Returns count of cleaned channels"""
        tracked_streams = settings.get("tracked_streams", {})
        auto_cleanup = settings.get("auto_cleanup", True)

        if not auto_cleanup and not force:
            return 0

        cleaned_count = 0
        to_remove = []

        for video_id, stream_data in tracked_streams.items():
            if not stream_data.get("is_live") or force:
                try:
                    # Delete Channel
                    channel_id = stream_data.get("channel_id")
                    if channel_id:
                        try:
                            channel = Channel.objects.get(id=channel_id)
                            channel.delete()
                            cleaned_count += 1
                            self._log(f"Deleted channel: {stream_data.get('title')}")
                        except Channel.DoesNotExist:
                            pass

                    # Delete Stream (if not used by other channels)
                    stream_id = stream_data.get("stream_id")
                    if stream_id:
                        try:
                            stream = Stream.objects.get(id=stream_id)
                            if not stream.channelstream_set.exists():
                                stream.delete()
                        except Stream.DoesNotExist:
                            pass

                    to_remove.append(video_id)

                except Exception as exc:
                    self._log_error(f"Cleanup failed for {video_id}: {exc}")

        # Remove from tracked streams
        for video_id in to_remove:
            del tracked_streams[video_id]

        # Persist updates
        if cleaned_count > 0:
            self._persist_settings({"tracked_streams": tracked_streams})

        return cleaned_count

    # --- Monitoring Thread ---

    def _monitoring_loop(self, plugin_key: str) -> None:
        """Background monitoring loop (runs in daemon thread)"""
        self._log("Monitoring loop started")

        try:
            # Restore extraction failures that survived from before last container restart
            try:
                cfg = PluginConfig.objects.get(key=plugin_key)
                persisted_failures = dict(cfg.settings or {}).get("extraction_failures", {})
                now = time.time()
                loaded = 0
                for vid, fail_time in persisted_failures.items():
                    if fail_time + 86400 > now and vid not in self._extraction_failures:
                        self._extraction_failures[vid] = fail_time
                        loaded += 1
                if loaded:
                    self._log(f"Restored {loaded} persisted extraction failures from DB")
            except PluginConfig.DoesNotExist:
                pass

            while not self._monitor_stop_event.is_set():
                try:
                    # Check in-memory flag first (authoritative - DB flag can be overwritten by Dispatcharr)
                    if not self._monitoring_active:
                        self._log("Monitoring disabled (in-memory flag), stopping")
                        break

                    # Reload settings from database
                    try:
                        cfg = PluginConfig.objects.get(key=plugin_key)
                        settings = dict(cfg.settings or {})
                    except PluginConfig.DoesNotExist:
                        self._log_error("Plugin config not found, stopping monitoring")
                        break

                    # Check if monitoring was stopped via DB flag (e.g., by Stop button in another worker)
                    if not settings.get("monitoring_active"):
                        self._log("DB shows monitoring_active=False, stopping monitoring thread")
                        self._monitoring_active = False
                        break

                    # Update heartbeat to signal this thread is actively running
                    # This prevents other Celery workers from starting duplicate threads
                    self._persist_settings({"monitoring_heartbeat": timezone.now().isoformat()})

                    # Prune stale extraction failures to keep the dict bounded
                    try:
                        _pruned = self._prune_extraction_failures()
                        if _pruned:
                            self._log(f"Pruned {_pruned} stale extraction failure(s)")
                    except Exception:
                        pass

                    # Poll channels
                    try:
                        added, ended = self._poll_monitored_channels(settings)

                        # Refresh URLs
                        refreshed = self._refresh_expiring_urls(settings)

                        # Keep EPG times current for all active streams
                        self._refresh_epg_times(settings)

                        # Cleanup if enabled
                        if settings.get("auto_cleanup", True):
                            cleaned = self._cleanup_ended_streams(settings)
                        else:
                            cleaned = 0

                        # Trigger webhook if channels changed
                        if added > 0 or cleaned > 0:
                            self._trigger_webhook(settings)

                    except Exception as exc:
                        self._log_error(f"Poll cycle error: {exc}")

                    # Sleep for poll interval
                    poll_interval = settings.get("poll_interval_minutes", 15)
                    sleep_seconds = poll_interval * 60

                    # Sleep in small chunks so we can respond to stop signal
                    for _ in range(int(sleep_seconds)):
                        if self._monitor_stop_event.is_set():
                            break
                        time.sleep(1)

                except Exception as exc:
                    self._log_error(f"Monitoring loop error: {exc}")
                    time.sleep(60)  # Back off on error

        finally:
            # Always clean up flags when thread exits (crash, break, or normal exit)
            self._log("Monitoring loop exiting, cleaning up flags")
            self._monitoring_active = False
            try:
                # Clear both monitoring_active and heartbeat so auto-restart can work on next startup
                self._persist_settings({"monitoring_active": False, "monitoring_heartbeat": None})
            except Exception as cleanup_exc:
                self._log_error(f"Failed to persist monitoring_active=False: {cleanup_exc}")

        self._log("Monitoring loop stopped")

    # --- State Management ---

    def _persist_extraction_failures(self) -> None:
        """Persist non-expired extraction failures to DB so they survive container restarts."""
        now = time.time()
        to_save = {vid: t for vid, t in self._extraction_failures.items() if t + 86400 > now}
        self._persist_settings({"extraction_failures": to_save})

    def _persist_settings(self, updates: Dict[str, Any]) -> None:
        """Persist settings updates to database (thread-safe)"""
        try:
            # Use select_for_update to prevent race conditions
            with transaction.atomic():
                cfg = PluginConfig.objects.select_for_update().get(key=self._plugin_key)
                settings = dict(cfg.settings or {})
                settings.update(updates)
                cfg.settings = settings
                cfg.save(update_fields=["settings", "updated_at"])
        except PluginConfig.DoesNotExist:
            self._log_error("Plugin config not found")

    # --- Operational Helpers ---

    def _prune_extraction_failures(self, ttl_days: int = 7, now: Optional[float] = None) -> int:
        """Remove extraction failure entries older than ttl_days from the in-memory dict.

        Returns count of pruned entries. Malformed timestamps are also pruned.
        Future timestamps (members-only entries stored at now+6days) are preserved.
        """
        if now is None:
            now = time.time()
        cutoff = now - ttl_days * 86400
        to_prune = []
        for vid, fail_time in list(self._extraction_failures.items()):
            try:
                if float(fail_time) < cutoff:
                    to_prune.append(vid)
            except (TypeError, ValueError):
                to_prune.append(vid)  # Malformed timestamp — prune it
        for vid in to_prune:
            del self._extraction_failures[vid]
        return len(to_prune)

    def _get_subchannel_index(self, channel_number, base_channel=None) -> int:
        """Extract subchannel index from channel_number using string parsing, not float math.

        Examples: "90.1" -> 1, "90.11" -> 11, "90.21" -> 21
        Float input is accepted; Python's str() gives the shortest decimal form.
        """
        s = str(channel_number)
        if '.' in s:
            try:
                return int(s.split('.', 1)[1])
            except (ValueError, IndexError):
                return 1
        return 1

    def _cache_bust_image_url(self, url, enabled: bool = True, timestamp=None):
        """Append or replace a ytarr_ts query parameter on an image URL.

        Returns the original value unchanged when url is blank, a data URI,
        a local path, or cache-busting is disabled.
        """
        if not url:
            return url
        if not enabled:
            return url
        if isinstance(url, str) and url.startswith(('data:', '/', 'file:')):
            return url
        ts = str(int(timestamp)) if timestamp is not None else str(int(time.time()))
        if '?' in url:
            base, query = url.split('?', 1)
            params = [p for p in query.split('&') if p and not p.startswith('ytarr_ts=')]
            params.append(f'ytarr_ts={ts}')
            return base + '?' + '&'.join(params)
        return f'{url}?ytarr_ts={ts}'

    def _merge_youtubearr_custom_properties(self, existing, **metadata) -> dict:
        """Return a new dict with YouTubearr ownership fields merged into existing props.

        Stamps owner='youtubearr' and any additional metadata kwargs.
        Does not mutate the input dict. Safe against None or non-dict input.
        Only call on Stream/ProgramData — Channel and EPGSource lack custom_properties.
        """
        result: dict = {}
        if existing:
            try:
                result = dict(existing)
            except (TypeError, ValueError):
                pass
        result['owner'] = 'youtubearr'
        result.update(metadata)
        return result

    def _get_custom_m3u_account(self):
        """Return the custom/built-in M3UAccount for stream association.

        Uses a lazy import so local unit tests without Dispatcharr installed
        never fail at import time. Returns None on any failure.
        """
        try:
            from apps.m3u.models import M3UAccount  # noqa: PLC0415
            try:
                return M3UAccount.get_custom_account()
            except AttributeError:
                account, _ = M3UAccount.objects.get_or_create(
                    name='custom',
                    defaults={'is_active': True, 'locked': True, 'max_streams': 0},
                )
                return account
        except ImportError:
            return None
        except Exception:
            return None

    # --- XMLTV Cache Generation ---

    def _generate_xmltv_cache(self, settings: Dict[str, Any]) -> None:
        """Generate XMLTV cache file for Jellyfin/external EPG readers.

        Jellyfin reads EPG from XMLTV files at /app/media/cached_epg/{source_id}.tmp
        This generates that file from the EPGData/ProgramData in the database.
        """
        epg_source_name_template = settings.get("epg_source_name", "YouTube Live").strip()
        if not epg_source_name_template:
            return

        # If the template contains placeholders, discover all EPG sources associated with
        # channels in our group rather than looking up a single static name. Each resolved
        # placeholder (e.g. "{channel} Live" → "NASA Live", "SpaceX Live") creates a separate
        # EPGSource, and each gets its own XMLTV cache file.
        if "{title}" in epg_source_name_template or "{channel}" in epg_source_name_template:
            group_name = settings.get("channel_group_name", self._channel_group_name)
            try:
                group = ChannelGroup.objects.get(name=group_name)
                epg_sources = list(EPGSource.objects.filter(
                    epgdata__channel__channel_group=group
                ).distinct())
            except ChannelGroup.DoesNotExist:
                return
            if not epg_sources:
                return
        else:
            try:
                epg_sources = [EPGSource.objects.get(name=epg_source_name_template)]
            except EPGSource.DoesNotExist:
                self._log(f"EPG source '{epg_source_name_template}' not found, skipping cache generation")
                return

        def escape_xml(s: str) -> str:
            if not s:
                return ""
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        try:
            for epg_source in epg_sources:
                cache_path = f"/app/media/cached_epg/{epg_source.id}.tmp"
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)

                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                    f.write('<tv generator-info-name="YouTubearr Plugin">\n')

                    # Write channels
                    for epg in EPGData.objects.filter(epg_source=epg_source):
                        name = escape_xml(epg.name)
                        f.write(f'  <channel id="{epg.tvg_id}">\n')
                        f.write(f'    <display-name>{name}</display-name>\n')
                        if epg.icon_url:
                            f.write(f'    <icon src="{escape_xml(epg.icon_url)}"/>\n')
                        f.write('  </channel>\n')

                    # Write programs
                    count = 0
                    for prog in ProgramData.objects.filter(epg__epg_source=epg_source).select_related("epg"):
                        start = prog.start_time.strftime("%Y%m%d%H%M%S +0000")
                        stop = prog.end_time.strftime("%Y%m%d%H%M%S +0000")
                        title = escape_xml(prog.title or "")
                        desc = escape_xml((prog.description or "")[:500])

                        f.write(f'  <programme start="{start}" stop="{stop}" channel="{prog.epg.tvg_id}">\n')
                        f.write(f'    <title>{title}</title>\n')
                        if desc:
                            f.write(f'    <desc>{desc}</desc>\n')
                        f.write('  </programme>\n')
                        count += 1

                    f.write('</tv>\n')

                self._log(f"XMLTV cache generated: {count} programs at {cache_path}")

        except Exception as e:
            self._log_error(f"Failed to generate XMLTV cache: {e}")

    # --- Webhook / Notification ---

    def _parse_webhook_headers(self, raw: str) -> Dict[str, str]:
        """Safely parse a JSON object string into a header dict. Invalid input is logged and ignored."""
        if not raw or not isinstance(raw, str):
            return {}
        raw = raw.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                self._log_error("Webhook headers must be a JSON object string; ignoring")
                return {}
            return {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError as exc:
            self._log_error(f"Invalid webhook headers JSON (ignored): {exc}")
            return {}

    def _get_media_refresh_webhook_config(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve media refresh webhook settings. New keys take precedence over legacy ones."""
        new_url = settings.get("media_refresh_webhook_url", "").strip()
        legacy_url = settings.get("webhook_url", "").strip()
        url = new_url or legacy_url
        is_legacy = bool(legacy_url and not new_url)

        raw_delay = settings.get("media_refresh_webhook_delay_seconds",
                                  settings.get("webhook_delay_seconds", 5))
        try:
            delay = max(0, min(60, int(raw_delay)))
        except (TypeError, ValueError):
            delay = 5

        return {
            "url": url,
            "method": settings.get("media_refresh_webhook_method", "POST"),
            "delay": delay,
            "headers": self._parse_webhook_headers(settings.get("media_refresh_webhook_headers", "")),
            "body_template": settings.get("media_refresh_webhook_body_template", ""),
            "is_legacy": is_legacy,
        }

    def _get_notification_webhook_config(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve notification webhook settings. New keys take precedence over legacy ones."""
        new_url = settings.get("notification_webhook_url", "").strip()
        legacy_url = settings.get("telegram_webhook_url", "").strip()
        url = new_url or legacy_url
        is_legacy = bool(legacy_url and not new_url)

        new_base = settings.get("notification_base_url", "").strip().rstrip("/")
        legacy_base = settings.get("dispatcharr_base_url", "").strip().rstrip("/")
        base_url = new_base or legacy_base

        return {
            "url": url,
            "method": settings.get("notification_webhook_method", "POST"),
            "headers": self._parse_webhook_headers(settings.get("notification_webhook_headers", "")),
            "base_url": base_url,
            "is_legacy": is_legacy,
        }

    def _send_webhook_request(self, url: str, method: str = 'POST',
                               headers: Optional[Dict[str, str]] = None,
                               body: Optional[str] = None, timeout: int = 10) -> tuple:
        """Send a single webhook HTTP request. Returns (status, response_text). May raise."""
        data = body.encode('utf-8') if isinstance(body, str) else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, str(v))
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read().decode('utf-8', errors='replace')

    def _send_webhook_async(self, kind: str, url: str, method: str,
                             headers: Optional[Dict[str, str]], body: Optional[str],
                             delay_seconds: int = 0) -> None:
        """Fire a webhook in a short-lived daemon thread. Never blocks the caller."""
        def _worker():
            try:
                if delay_seconds > 0:
                    self._log(f"[{kind}] Waiting {delay_seconds}s before sending webhook...")
                    time.sleep(delay_seconds)
                self._log(f"[{kind}] Sending webhook: {url}")
                status, _ = self._send_webhook_request(url, method=method,
                                                        headers=headers, body=body, timeout=10)
                if status in [200, 201, 204]:
                    self._log(f"[{kind}] Webhook sent successfully (HTTP {status})")
                else:
                    self._log(f"[{kind}] Webhook returned HTTP {status}")
            except Exception as exc:
                self._log_error(f"[{kind}] Webhook failed: {exc}")

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _trigger_webhook(self, settings: Dict[str, Any]) -> None:
        """Trigger media refresh webhook when channels change. Returns immediately (non-blocking)."""
        # Generate XMLTV cache before triggering webhook so Jellyfin has fresh data
        self._generate_xmltv_cache(settings)

        config = self._get_media_refresh_webhook_config(settings)
        url = config["url"]
        if not url:
            return

        if config["body_template"]:
            body = config["body_template"]
        elif config["is_legacy"]:
            # Legacy Jellyfin-style: bodyless POST
            body = None
        else:
            body = json.dumps({
                "event": "media_refresh_requested",
                "plugin": "youtubearr",
                "reason": "streams_changed",
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            })

        self._send_webhook_async(
            "media_refresh", url, config["method"], config["headers"], body,
            delay_seconds=config["delay"],
        )

    def _send_telegram_notification(self, settings: Dict[str, Any], video_id: str,
                                     metadata: Dict[str, Any], channel_number: int,
                                     channel_uuid: str) -> None:
        """Send notification webhook when a new channel is added."""
        config = self._get_notification_webhook_config(settings)
        url = config["url"]
        if not url:
            return

        base_url = config["base_url"]

        if config["is_legacy"]:
            # Legacy Telegram payload — preserve exact key shape
            if not base_url:
                self._log("Skipping notification: base URL not configured")
                return
            dispatcharr_url = f"{base_url}/proxy/ts/stream/{channel_uuid}"
            payload = {
                "title": metadata.get("title", "YouTube Live Stream"),
                "channel": metadata.get("youtube_channel_name", "YouTube"),
                "url": dispatcharr_url,
                "description": f"Added as Dispatcharr Channel #{channel_number}",
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            }
        else:
            # Generic notification payload
            dispatcharr_url = f"{base_url}/proxy/ts/stream/{channel_uuid}" if base_url else ""
            payload = {
                "event": "stream_added",
                "plugin": "youtubearr",
                "video_id": video_id,
                "title": metadata.get("title", "YouTube Live Stream"),
                "channel_name": metadata.get("youtube_channel_name", "YouTube"),
                "channel_number": str(channel_number),
                "dispatcharr_channel_uuid": channel_uuid,
                "url": dispatcharr_url,
                "thumbnail": metadata.get("thumbnail", ""),
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            }

        self._log(f"Sending notification for: {metadata.get('title', 'stream')[:60]}...")
        self._send_webhook_async(
            "notification", url, config["method"], config["headers"],
            json.dumps(payload), delay_seconds=0,
        )

    # --- Monitoring Self-Healing and Legacy Cleanup ---

    def _cleanup_legacy_celery_task(self) -> None:
        """Delete the bogus Celery beat task registered by older plugin versions.

        Older versions registered a periodic task pointing at a Dispatcharr core task
        that does not exist, causing Celery to spam 'Received unregistered task' errors
        every 5 minutes. This method is idempotent (runs once per Plugin instance) and
        safe to call from any action handler.
        """
        if self._legacy_task_cleanup_done:
            return
        self._legacy_task_cleanup_done = True
        try:
            task_name = f"youtubearr_{self._plugin_key}_health_check"
            deleted = delete_periodic_task(task_name)
            if deleted:
                self._log(f"Removed legacy Celery beat task: {task_name}")
        except Exception as exc:
            self._log_error(f"Legacy Celery task cleanup failed: {exc}")

    def _ensure_monitoring_thread(self, settings: Dict[str, Any]) -> bool:
        """Restart the monitor thread if DB says active but no live thread is running.

        This is the in-plugin self-healing path: it handles container restarts and
        crashed/hung threads without relying on any Celery task. Returns True if a
        new thread was started.
        """
        if not settings.get("monitoring_active"):
            return False

        thread_dead = not self._monitor_thread or not self._monitor_thread.is_alive()
        if not thread_dead:
            return False

        # Another Celery worker's thread may still be running — check the shared heartbeat
        heartbeat_str = settings.get("monitoring_heartbeat")
        if heartbeat_str:
            try:
                heartbeat = datetime.fromisoformat(heartbeat_str.replace("Z", "+00:00"))
                if isinstance(heartbeat.tzinfo, type(None)):
                    heartbeat = heartbeat.replace(tzinfo=dt_timezone.utc)
                age_seconds = (datetime.now(dt_timezone.utc) - heartbeat).total_seconds()
                poll_interval_minutes = settings.get("poll_interval_minutes", 15)
                heartbeat_threshold = (poll_interval_minutes + 10) * 60
                if age_seconds < heartbeat_threshold:
                    self._log(f"Monitoring heartbeat is recent ({int(age_seconds)}s ago, threshold={heartbeat_threshold}s), skipping auto-restart")
                    return False
            except (ValueError, TypeError):
                pass

        channels = settings.get("monitored_channels", "").strip()
        if not channels or not self._ytdlp_path:
            return False

        self._log("Auto-restarting monitoring after service restart")
        self._monitoring_active = True
        self._monitor_stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(self._plugin_key,),
            daemon=True,
            name="YouTubearr-Monitor"
        )
        self._monitor_thread.start()
        return True

    def _log(self, message: str) -> None:
        """Write log message"""
        timestamp = datetime.now().isoformat()
        log_msg = f"[{timestamp}] {message}\n"

        try:
            # Rotate log if too large
            if self._log_path.exists() and self._log_path.stat().st_size > self._log_max_bytes:
                backup = self._log_path.with_suffix(".log.old")
                if backup.exists():
                    backup.unlink()
                self._log_path.rename(backup)

            with open(self._log_path, "a") as f:
                f.write(log_msg)
        except Exception:
            pass

    def _log_error(self, message: str) -> None:
        """Write error log message"""
        self._log(f"ERROR: {message}")

    # --- Binary Finder ---

    def _find_ytdlp_binary(self) -> Optional[str]:
        """Find yt-dlp binary (bundled or system-installed)"""
        # First, check for bundled yt-dlp in plugin directory
        bundled_ytdlp = self._base_dir / "yt-dlp"
        if bundled_ytdlp.exists() and bundled_ytdlp.is_file():
            # Make sure it's executable
            try:
                bundled_ytdlp.chmod(0o755)
                # Test it works
                result = subprocess.run(
                    [str(bundled_ytdlp), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    self._log(f"Using bundled yt-dlp: {bundled_ytdlp}")
                    return str(bundled_ytdlp)
            except Exception as exc:
                self._log_error(f"Bundled yt-dlp failed: {exc}")

        # Fall back to system-installed yt-dlp
        binary_names = ["yt-dlp", "youtube-dl"]

        for binary in binary_names:
            try:
                result = subprocess.run(
                    ["which", binary],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    path = result.stdout.strip()
                    self._log(f"Found system {binary} at: {path}")
                    return path
            except Exception:
                continue

        # Try direct execution
        for binary in binary_names:
            try:
                result = subprocess.run(
                    [binary, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    self._log(f"Found system {binary} (executable)")
                    return binary
            except Exception:
                continue

        self._log_error("yt-dlp not found. Plugin includes bundled version, but it may not be working.")
        return None

    def _find_qjs_binary(self) -> Optional[str]:
        """Find QuickJS binary (bundled only - needed for YouTube PO token extraction)"""
        bundled_qjs = self._base_dir / "qjs"
        if bundled_qjs.exists() and bundled_qjs.is_file():
            try:
                bundled_qjs.chmod(0o755)
                # Test it works - qjs --help returns exit code 1 but prints version info
                result = subprocess.run(
                    [str(bundled_qjs), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Check for QuickJS version string in output (--help exits with 1)
                if "QuickJS" in result.stdout or "QuickJS" in result.stderr:
                    self._log(f"Using bundled QuickJS: {bundled_qjs}")
                    return str(bundled_qjs)
            except Exception as exc:
                self._log_error(f"Bundled QuickJS failed: {exc}")

        self._log("QuickJS (qjs) not found. Some YouTube streams may not work without it.")
        return None
