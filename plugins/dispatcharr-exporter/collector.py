"""Prometheus metrics collector.

Queries Dispatcharr's Django models and Redis state on every scrape request
and returns the complete metrics output in Prometheus text format.
"""

import logging
import time

from apps.proxy.ts_proxy.constants import ChannelMetadataField

from .config import PLUGIN_CONFIG, PLUGIN_FIELDS, DEFAULT_PORT
from .utils import escape_label, get_dispatcharr_version

logger = logging.getLogger(__name__)


class PrometheusMetricsCollector:
    """Orchestrates all metric collection and formats output."""

    def __init__(self):
        self.redis_client = None  # lazy-loaded on first scrape

    def collect_metrics(self, settings: dict = None) -> str:
        """Collect all metrics and return Prometheus text format."""
        if self.redis_client is None:
            try:
                from core.utils import RedisClient
                self.redis_client = RedisClient.get_client()
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")

        metrics = []
        settings = settings or {}

        dispatcharr_version, dispatcharr_timestamp, full_version = get_dispatcharr_version()

        # Dispatcharr version info
        metrics.append("# HELP dispatcharr_info Dispatcharr version and instance information")
        metrics.append("# TYPE dispatcharr_info gauge")
        metrics.append(f'dispatcharr_info{{version="{full_version}"}} 1')
        metrics.append("")

        # Exporter info / settings snapshot
        exporter_version = PLUGIN_CONFIG["version"].lstrip('-')
        metrics.append("# HELP dispatcharr_exporter_info Dispatcharr Exporter plugin version information")
        metrics.append("# TYPE dispatcharr_exporter_info gauge")
        metrics.append("# HELP dispatcharr_exporter_settings_info Dispatcharr Exporter plugin settings (for debugging/support)")
        metrics.append("# TYPE dispatcharr_exporter_settings_info gauge")
        metrics.append("# HELP dispatcharr_exporter_port Configured port number for the metrics server")
        metrics.append("# TYPE dispatcharr_exporter_port gauge")
        metrics.append(f'dispatcharr_exporter_info{{version="{exporter_version}"}} 1')

        settings_labels = []
        port_value = DEFAULT_PORT

        for field in PLUGIN_FIELDS:
            field_id = field['id']
            field_value = settings.get(field_id, field['default']) if settings else field['default']

            if field_id == 'port':
                port_value = field_value

            if isinstance(field_value, bool):
                value_str = str(field_value).lower()
            elif isinstance(field_value, (int, float)):
                value_str = str(field_value)
            else:
                value_str = str(field_value).replace('\\', '\\\\').replace('"', '\\"')

            settings_labels.append(f'{field_id}="{value_str}"')

        metrics.append(f'dispatcharr_exporter_settings_info{{{",".join(settings_labels)}}} 1')
        metrics.append(f'dispatcharr_exporter_port {port_value}')
        metrics.append("")

        # M3U Account metrics
        if not settings or settings.get('include_m3u_stats', True):
            metrics.extend(self._collect_m3u_account_metrics(settings))

        # EPG Source metrics
        if settings and settings.get('include_epg_stats', False):
            metrics.extend(self._collect_epg_metrics(settings))

        # Channel metrics
        metrics.extend(self._collect_channel_metrics())

        # Profile connection metrics
        if not settings or settings.get('include_m3u_stats', True):
            metrics.extend(self._collect_profile_metrics())

        # Stream metrics (live + VOD)
        metrics.extend(self._collect_stream_metrics(settings))

        # Client connection metrics
        if settings and settings.get('include_client_stats', False):
            metrics.extend(self._collect_client_metrics())

        # User metrics
        if settings and settings.get('include_user_stats', False):
            metrics.extend(self._collect_user_metrics())

        return "\n".join(metrics)

    # ── M3U Account metrics ──────────────────────────────────────────────────

    def _collect_m3u_account_metrics(self, settings: dict = None) -> list:
        """Collect M3U account statistics."""
        from apps.m3u.models import M3UAccount

        metrics = []
        metrics.append("# HELP dispatcharr_m3u_accounts Total number of M3U accounts")
        metrics.append("# TYPE dispatcharr_m3u_accounts gauge")

        include_urls = settings and settings.get('include_source_urls', False)

        try:
            all_accounts = M3UAccount.objects.exclude(name__iexact="custom")
            total_accounts = all_accounts.count()
            active_accounts = all_accounts.filter(is_active=True).count()

            metrics.append(f"dispatcharr_m3u_accounts{{status=\"total\"}} {total_accounts}")
            metrics.append(f"dispatcharr_m3u_accounts{{status=\"active\"}} {active_accounts}")

            metrics.append("# HELP dispatcharr_m3u_account_status M3U account status breakdown")
            metrics.append("# TYPE dispatcharr_m3u_account_status gauge")

            for status_choice in M3UAccount.Status.choices:
                status_value = status_choice[0]
                count = all_accounts.filter(status=status_value).count()
                metrics.append(f'dispatcharr_m3u_account_status{{status="{status_value}"}} {count}')

            metrics.append("# HELP dispatcharr_m3u_account_stream_count Number of streams configured for this M3U account")
            metrics.append("# TYPE dispatcharr_m3u_account_stream_count gauge")

            for account in all_accounts:
                account_name = account.name.replace('"', '\\"').replace('\\', '\\\\')
                account_type = account.account_type or 'unknown'
                status = account.status
                is_active = str(account.is_active).lower()
                stream_count = account.streams.count() if hasattr(account, 'streams') else 0

                base_labels = [
                    f'account_id="{account.id}"',
                    f'account_name="{account_name}"',
                    f'account_type="{account_type}"',
                    f'status="{status}"',
                    f'is_active="{is_active}"',
                ]

                if include_urls and account_type == 'XC' and hasattr(account, 'username') and account.username:
                    username = account.username.replace('"', '\\"').replace('\\', '\\\\')
                    base_labels.append(f'username="{username}"')

                if include_urls and account.server_url:
                    server_url = account.server_url.replace('"', '\\"').replace('\\', '\\\\')
                    base_labels.append(f'server_url="{server_url}"')

                metrics.append(f'dispatcharr_m3u_account_info{{{",".join(base_labels)}}} 1')
                metrics.append(f'dispatcharr_m3u_account_stream_count{{{",".join(base_labels)}}} {stream_count}')

        except Exception as e:
            logger.error(f"Error collecting M3U account metrics: {e}")

        metrics.append("")
        return metrics

    # ── Channel metrics ──────────────────────────────────────────────────────

    def _collect_channel_metrics(self) -> list:
        """Collect channel statistics."""
        from apps.channels.models import Channel, ChannelGroup

        metrics = []
        metrics.append("# HELP dispatcharr_channels Total number of channels")
        metrics.append("# TYPE dispatcharr_channels gauge")

        try:
            total_channels = Channel.objects.count()
            metrics.append(f"dispatcharr_channels{{status=\"total\"}} {total_channels}")

            metrics.append("# HELP dispatcharr_channel_groups Total number of channel groups")
            metrics.append("# TYPE dispatcharr_channel_groups gauge")
            channel_groups = ChannelGroup.objects.count()
            metrics.append(f"dispatcharr_channel_groups {channel_groups}")

        except Exception as e:
            logger.error(f"Error collecting channel metrics: {e}")

        metrics.append("")
        return metrics

    # ── Profile metrics ──────────────────────────────────────────────────────

    def _collect_profile_metrics(self) -> list:
        """Collect M3U profile connection statistics."""
        from apps.m3u.models import M3UAccountProfile
        from datetime import datetime, timezone

        metrics = []
        profile_data = []
        expiry_data = []

        try:
            if self.redis_client:
                actual_profile_connections = {}

                # Count live channel streams
                try:
                    for key in self.redis_client.scan_iter(match="channel_stream:*"):
                        try:
                            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                            channel_id = key_str.split(':', 1)[1]

                            from apps.channels.models import Channel
                            try:
                                channel = Channel.objects.get(id=int(channel_id))
                                channel_uuid = str(channel.uuid)

                                metadata_key = f"ts_proxy:channel:{channel_uuid}:metadata"
                                metadata = self.redis_client.hgetall(metadata_key) or {}

                                def get_metadata(field, default=None):
                                    val = metadata.get(field)
                                    if val is None:
                                        return default
                                    return str(val)

                                m3u_profile_id = get_metadata(ChannelMetadataField.M3U_PROFILE, None)
                                if m3u_profile_id and m3u_profile_id != '0':
                                    try:
                                        profile_id = int(m3u_profile_id)
                                        actual_profile_connections[profile_id] = actual_profile_connections.get(profile_id, 0) + 1
                                    except (ValueError, TypeError):
                                        pass
                            except Channel.DoesNotExist:
                                pass
                        except Exception as e:
                            logger.debug(f"Error processing stream key for profile counting: {e}")
                except Exception as e:
                    logger.debug(f"Error calculating live channel profile connections: {e}")

                # Count VOD connections
                try:
                    for key in self.redis_client.scan_iter(match="vod_persistent_connection:*"):
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if connection_data:
                                if isinstance(list(connection_data.keys())[0], bytes):
                                    m3u_profile_id = connection_data.get(b'm3u_profile_id', b'')
                                    active_streams = connection_data.get(b'active_streams', b'0')
                                    if isinstance(m3u_profile_id, bytes):
                                        m3u_profile_id = m3u_profile_id.decode('utf-8')
                                    if isinstance(active_streams, bytes):
                                        active_streams = active_streams.decode('utf-8')
                                else:
                                    m3u_profile_id = connection_data.get('m3u_profile_id', '')
                                    active_streams = connection_data.get('active_streams', '0')

                                if m3u_profile_id and int(active_streams) > 0:
                                    try:
                                        profile_id = int(m3u_profile_id)
                                        actual_profile_connections[profile_id] = actual_profile_connections.get(profile_id, 0) + 1
                                    except (ValueError, TypeError):
                                        pass
                        except Exception as e:
                            logger.debug(f"Error processing VOD connection key for profile counting: {e}")
                except Exception as e:
                    logger.debug(f"Error calculating VOD profile connections: {e}")

                for profile in M3UAccountProfile.objects.all():
                    try:
                        if profile.m3u_account.name.lower() == 'custom':
                            continue

                        current_connections = actual_profile_connections.get(profile.id, 0)
                        max_connections = profile.max_streams
                        profile_name = profile.name.replace('"', '\\"')
                        account_name = profile.m3u_account.name.replace('"', '\\"')

                        profile_data.append(f'dispatcharr_profile_connections{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {current_connections}')
                        profile_data.append(f'dispatcharr_profile_max_connections{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {max_connections}')

                        if max_connections > 0:
                            usage = current_connections / max_connections
                            profile_data.append(f'dispatcharr_profile_connection_usage{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {usage:.4f}')

                        if profile.m3u_account.account_type == 'XC':
                            days_remaining = -1
                            if profile.custom_properties:
                                user_info = profile.custom_properties.get('user_info', {})
                                exp_date = user_info.get('exp_date')
                                if exp_date:
                                    try:
                                        expiry = datetime.fromtimestamp(float(exp_date), tz=timezone.utc)
                                        now = datetime.now(timezone.utc)
                                        days_remaining = max(0, (expiry - now).days)
                                    except (ValueError, TypeError) as e:
                                        logger.debug(f"Error calculating expiry for profile {profile.id}: {e}")
                            expiry_data.append(f'dispatcharr_profile_days_to_expiry{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {days_remaining}')

                    except Exception as e:
                        logger.debug(f"Error getting connections for profile {profile.id}: {e}")

        except Exception as e:
            logger.error(f"Error collecting profile metrics: {e}")

        if profile_data:
            metrics.append("# HELP dispatcharr_profile_connections Current connections per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_connections gauge")
            metrics.append("# HELP dispatcharr_profile_max_connections Maximum allowed connections per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_max_connections gauge")
            metrics.append("# HELP dispatcharr_profile_connection_usage Connection usage ratio per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_connection_usage gauge")
            metrics.extend(profile_data)

        if expiry_data:
            metrics.append("# HELP dispatcharr_profile_days_to_expiry Days remaining until XC profile expiry (0 if expired, -1 if no expiry set)")
            metrics.append("# TYPE dispatcharr_profile_days_to_expiry gauge")
            metrics.extend(expiry_data)

        metrics.append("")
        return metrics

    # ── Stream metrics ───────────────────────────────────────────────────────

    def _collect_stream_metrics(self, settings: dict = None) -> list:
        """Collect active stream statistics from Redis."""
        from apps.channels.models import Channel, Stream
        from apps.m3u.models import M3UAccount, M3UAccountProfile

        settings = settings or {}

        metrics = []
        metrics.append("# HELP dispatcharr_active_streams Total number of active streams (live and VOD)")
        metrics.append("# TYPE dispatcharr_active_streams gauge")

        metrics.append("# HELP dispatcharr_stream_channel_number Channel number for active stream (live only)")
        metrics.append("# TYPE dispatcharr_stream_channel_number gauge")
        metrics.append("# HELP dispatcharr_stream_id Active stream ID for channel or session ID for VOD")
        metrics.append("# TYPE dispatcharr_stream_id gauge")
        metrics.append("# HELP dispatcharr_stream_index Active stream index for channel (0=primary, >0=fallback) (live only)")
        metrics.append("# TYPE dispatcharr_stream_index gauge")
        metrics.append("# HELP dispatcharr_stream_available_streams Total number of streams configured for channel (live only)")
        metrics.append("# TYPE dispatcharr_stream_available_streams gauge")
        metrics.append("# HELP dispatcharr_stream_metadata Stream metadata (type: live/vod, state values: active, waiting_for_clients, buffering, stopping, error, unknown)")
        metrics.append("# TYPE dispatcharr_stream_metadata gauge")
        metrics.append("# HELP dispatcharr_stream_programming Current EPG program information for active streams (live only)")
        metrics.append("# TYPE dispatcharr_stream_programming gauge")
        metrics.append("# HELP dispatcharr_stream_uptime_seconds Stream uptime in seconds since stream started")
        metrics.append("# TYPE dispatcharr_stream_uptime_seconds counter")
        metrics.append("# HELP dispatcharr_stream_active_clients Number of active clients connected to stream")
        metrics.append("# TYPE dispatcharr_stream_active_clients gauge")
        metrics.append("# HELP dispatcharr_stream_video_bitrate_bps Video bitrate in bits per second")
        metrics.append("# TYPE dispatcharr_stream_video_bitrate_bps gauge")
        metrics.append("# HELP dispatcharr_stream_transcode_bitrate_bps Transcode output bitrate in bits per second")
        metrics.append("# TYPE dispatcharr_stream_transcode_bitrate_bps gauge")
        metrics.append("# HELP dispatcharr_stream_avg_bitrate_bps Average bitrate in bits per second")
        metrics.append("# TYPE dispatcharr_stream_avg_bitrate_bps gauge")
        metrics.append("# HELP dispatcharr_stream_current_bitrate_bps Current bitrate in bits per second (sum of all client rates)")
        metrics.append("# TYPE dispatcharr_stream_current_bitrate_bps gauge")
        metrics.append("# HELP dispatcharr_stream_total_transfer_mb Total data transferred in megabytes")
        metrics.append("# TYPE dispatcharr_stream_total_transfer_mb counter")
        metrics.append("# HELP dispatcharr_stream_fps Stream frames per second")
        metrics.append("# TYPE dispatcharr_stream_fps gauge")
        metrics.append("# HELP dispatcharr_stream_buffering_speed Stream buffering speed multiplier (e.g., 1.0 = realtime, 2.0 = 2x speed)")
        metrics.append("# TYPE dispatcharr_stream_buffering_speed gauge")
        metrics.append("# HELP dispatcharr_stream_profile_connections Current connections for the M3U profile used by this stream")
        metrics.append("# TYPE dispatcharr_stream_profile_connections gauge")
        metrics.append("# HELP dispatcharr_stream_profile_max_connections Maximum connections allowed for the M3U profile")
        metrics.append("# TYPE dispatcharr_stream_profile_max_connections gauge")

        try:
            if self.redis_client:
                active_streams = 0
                active_live_streams = 0
                active_vod_streams = 0
                stream_value_metrics = []

                # ── Live channel streams ─────────────────────────────────────
                try:
                    for key in self.redis_client.scan_iter(match="channel_stream:*"):
                        active_streams += 1
                        active_live_streams += 1

                        try:
                            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                            channel_id = key_str.split(':', 1)[1]

                            stream_id = self.redis_client.get(key)
                            if stream_id:
                                stream_id = int(stream_id.decode('utf-8') if isinstance(stream_id, bytes) else stream_id)

                                try:
                                    channel = Channel.objects.select_related('logo', 'channel_group').get(id=int(channel_id))
                                    channel_uuid = str(channel.uuid)
                                    channel_name = channel.name.replace('"', '\\"').replace('\\', '\\\\')
                                    channel_number = getattr(channel, 'channel_number', 'N/A')
                                    channel_group = channel.channel_group.name.replace('"', '\\"').replace('\\', '\\\\') if channel.channel_group else "none"

                                    logo_url = ""
                                    if hasattr(channel, 'logo') and channel.logo:
                                        logo_path = f"/api/channels/logos/{channel.logo.id}/cache/"
                                        base_url = settings.get('base_url', '').strip()
                                        if base_url:
                                            logo_url = f"{base_url.rstrip('/')}{logo_path}"
                                        else:
                                            logo_url = logo_path
                                    logo_url = logo_url.replace('"', '\\"').replace('\\', '\\\\')

                                    metadata_key = f"ts_proxy:channel:{channel_uuid}:metadata"
                                    metadata = self.redis_client.hgetall(metadata_key) or {}

                                    def get_metadata(field, default="0"):
                                        val = metadata.get(field)
                                        if val is None:
                                            return default
                                        return str(val)

                                    active_stream_id_str = get_metadata(ChannelMetadataField.STREAM_ID, None)
                                    if active_stream_id_str and active_stream_id_str != '0':
                                        try:
                                            stream_id = int(active_stream_id_str)
                                        except (ValueError, TypeError):
                                            logger.debug(f"Invalid active stream ID in metadata: {active_stream_id_str}")

                                    init_time = float(get_metadata(ChannelMetadataField.INIT_TIME, '0'))
                                    uptime_seconds = int(time.time() - init_time) if init_time > 0 else 0

                                    stream_profile_id = get_metadata(ChannelMetadataField.STREAM_PROFILE, '0')
                                    stream_profile_name = 'Unknown'
                                    if stream_profile_id and stream_profile_id != '0':
                                        try:
                                            from core.models import StreamProfile
                                            profile = StreamProfile.objects.get(id=int(stream_profile_id))
                                            stream_profile_name = profile.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            stream_profile_name = f'Profile-{stream_profile_id}'
                                    else:
                                        try:
                                            sp = channel.get_stream_profile()
                                            if sp:
                                                stream_profile_name = sp.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            pass

                                    video_codec = get_metadata(ChannelMetadataField.VIDEO_CODEC, 'unknown')
                                    resolution = get_metadata(ChannelMetadataField.RESOLUTION, 'unknown')
                                    source_fps = get_metadata(ChannelMetadataField.SOURCE_FPS, '0')
                                    video_bitrate = get_metadata(ChannelMetadataField.VIDEO_BITRATE, '0')
                                    ffmpeg_output_bitrate = get_metadata(ChannelMetadataField.FFMPEG_OUTPUT_BITRATE, '0')
                                    ffmpeg_speed = get_metadata(ChannelMetadataField.FFMPEG_SPEED, '0')

                                    total_bytes = int(get_metadata(ChannelMetadataField.TOTAL_BYTES, '0'))
                                    total_mb = round(total_bytes / 1024 / 1024, 2)
                                    avg_bitrate_bps = round((total_bytes * 8 / uptime_seconds), 2) if uptime_seconds > 0 else 0

                                    client_set_key = f"ts_proxy:channel:{channel_uuid}:clients"
                                    active_clients = self.redis_client.scard(client_set_key) or 0

                                    current_bitrate_bps = 0.0
                                    try:
                                        client_ids = self.redis_client.smembers(client_set_key)
                                        for client_id_bytes in client_ids:
                                            try:
                                                client_id = client_id_bytes.decode('utf-8') if isinstance(client_id_bytes, bytes) else client_id_bytes
                                                client_key = f"ts_proxy:channel:{channel_uuid}:clients:{client_id}"
                                                client_data = self.redis_client.hgetall(client_key)
                                                if client_data and 'current_rate_KBps' in client_data:
                                                    current_rate_kb = float(client_data['current_rate_KBps'])
                                                    if current_rate_kb > 50000:
                                                        current_bitrate_bps += current_rate_kb * 8
                                                    else:
                                                        current_bitrate_bps += current_rate_kb * 8000
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass

                                    state = get_metadata(ChannelMetadataField.STATE, 'unknown')

                                    try:
                                        stream = Stream.objects.select_related('m3u_account').get(id=stream_id)
                                        stream_name = stream.name.replace('"', '\\"').replace('\\', '\\\\')
                                        provider = stream.m3u_account.name.replace('"', '\\"').replace('\\', '\\\\') if stream.m3u_account else "Unknown"
                                        stream_type = stream.m3u_account.account_type if stream.m3u_account else "Unknown"

                                        stream_index = 0
                                        try:
                                            from apps.channels.models import ChannelStream
                                            channel_stream = ChannelStream.objects.get(channel_id=channel.id, stream_id=stream_id)
                                            stream_index = channel_stream.order
                                        except Exception:
                                            pass

                                        profile_id = None
                                        profile_name = "Unknown"
                                        profile_connections = 0
                                        profile_max = 0

                                        m3u_profile_id = get_metadata(ChannelMetadataField.M3U_PROFILE, None)
                                        if not m3u_profile_id or m3u_profile_id == '0':
                                            try:
                                                raw = self.redis_client.get(f"stream_profile:{stream_id}")
                                                if raw:
                                                    m3u_profile_id = raw.decode('utf-8') if isinstance(raw, bytes) else str(raw)
                                            except Exception:
                                                pass
                                        if m3u_profile_id and m3u_profile_id != '0':
                                            try:
                                                profile_id = int(m3u_profile_id)
                                                active_profile = M3UAccountProfile.objects.get(id=profile_id)
                                                profile_name = active_profile.name.replace('"', '\\"').replace('\\', '\\\\')
                                                profile_connections = int(self.redis_client.get(f"profile_connections:{profile_id}") or 0)
                                                profile_max = active_profile.max_streams
                                            except Exception as e:
                                                logger.debug(f"Error getting M3U profile {profile_id}: {e}")

                                        base_labels = [
                                            f'type="live"',
                                            f'channel_uuid="{channel_uuid}"',
                                            f'channel_number="{channel_number}"',
                                        ]
                                        base_labels_str = ",".join(base_labels)

                                        try:
                                            channel_number_value = float(channel_number)
                                        except (ValueError, TypeError):
                                            channel_number_value = 0.0

                                        metadata_labels = base_labels + [
                                            f'channel_name="{channel_name}"',
                                            f'channel_group="{channel_group}"',
                                            f'stream_id="{stream_id}"',
                                            f'stream_name="{stream_name}"',
                                            f'provider="{provider}"',
                                            f'provider_type="{stream_type}"',
                                            f'state="{state}"',
                                            f'logo_url="{logo_url}"',
                                            f'profile_id="{profile_id if profile_id else "none"}"',
                                            f'profile_name="{profile_name}"',
                                            f'stream_profile="{stream_profile_name}"',
                                            f'video_codec="{video_codec}"',
                                            f'resolution="{resolution}"',
                                        ]

                                        stream_value_metrics.append(f'dispatcharr_stream_index{{{base_labels_str}}} {stream_index}')
                                        stream_value_metrics.append(f'dispatcharr_stream_available_streams{{{base_labels_str}}} {channel.streams.count()}')
                                        stream_value_metrics.append(f'dispatcharr_stream_channel_number{{{base_labels_str}}} {channel_number_value}')
                                        stream_value_metrics.append(f'dispatcharr_stream_id{{{base_labels_str}}} {stream_id}')

                                        stream_value_metrics.append(f'dispatcharr_stream_uptime_seconds{{{base_labels_str}}} {uptime_seconds}')
                                        stream_value_metrics.append(f'dispatcharr_stream_active_clients{{{base_labels_str}}} {active_clients}')

                                        if source_fps and source_fps != '0':
                                            stream_value_metrics.append(f'dispatcharr_stream_fps{{{base_labels_str}}} {source_fps}')

                                        if ffmpeg_speed and ffmpeg_speed != '0':
                                            try:
                                                speed_value = float(ffmpeg_speed.rstrip('x'))
                                                stream_value_metrics.append(f'dispatcharr_stream_buffering_speed{{{base_labels_str}}} {speed_value}')
                                            except (ValueError, AttributeError):
                                                pass

                                        if video_bitrate and video_bitrate != '0':
                                            stream_value_metrics.append(f'dispatcharr_stream_video_bitrate_bps{{{base_labels_str}}} {float(video_bitrate) * 1000}')
                                        if ffmpeg_output_bitrate and ffmpeg_output_bitrate != '0':
                                            stream_value_metrics.append(f'dispatcharr_stream_transcode_bitrate_bps{{{base_labels_str}}} {float(ffmpeg_output_bitrate) * 1000}')
                                        if avg_bitrate_bps > 0:
                                            stream_value_metrics.append(f'dispatcharr_stream_avg_bitrate_bps{{{base_labels_str}}} {avg_bitrate_bps}')
                                        if current_bitrate_bps > 0:
                                            stream_value_metrics.append(f'dispatcharr_stream_current_bitrate_bps{{{base_labels_str}}} {current_bitrate_bps}')
                                        if total_mb > 0:
                                            stream_value_metrics.append(f'dispatcharr_stream_total_transfer_mb{{{base_labels_str}}} {total_mb}')

                                        if profile_id:
                                            stream_value_metrics.append(f'dispatcharr_stream_profile_connections{{{base_labels_str}}} {profile_connections}')
                                            stream_value_metrics.append(f'dispatcharr_stream_profile_max_connections{{{base_labels_str}}} {profile_max}')

                                        stream_value_metrics.append(f'dispatcharr_stream_metadata{{{",".join(metadata_labels)}}} 1')

                                        # EPG program data
                                        if hasattr(channel, 'epg_data') and channel.epg_data:
                                            try:
                                                from apps.epg.models import ProgramData
                                                from django.utils import timezone as django_timezone

                                                now = django_timezone.now()

                                                current_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    start_time__lte=now,
                                                    end_time__gte=now,
                                                ).first()
                                                previous_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    end_time__lt=now,
                                                ).order_by('-end_time').first()
                                                next_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    start_time__gt=now,
                                                ).order_by('start_time').first()

                                                def format_program_data(program, prefix):
                                                    if not program:
                                                        return [
                                                            f'{prefix}_title=""',
                                                            f'{prefix}_subtitle=""',
                                                            f'{prefix}_description=""',
                                                            f'{prefix}_start_time=""',
                                                            f'{prefix}_end_time=""',
                                                        ]

                                                    return [
                                                        f'{prefix}_title="{escape_label(program.title)}"',
                                                        f'{prefix}_subtitle="{escape_label(program.sub_title)}"',
                                                        f'{prefix}_description="{escape_label(program.description)}"',
                                                        f'{prefix}_start_time="{program.start_time.isoformat()}"',
                                                        f'{prefix}_end_time="{program.end_time.isoformat()}"',
                                                    ]

                                                if previous_program or current_program or next_program:
                                                    epg_labels = base_labels.copy()
                                                    epg_labels.extend(format_program_data(previous_program, 'previous'))
                                                    epg_labels.extend(format_program_data(current_program, 'current'))
                                                    epg_labels.extend(format_program_data(next_program, 'next'))

                                                    progress = 0.0
                                                    if current_program:
                                                        total_duration = (current_program.end_time - current_program.start_time).total_seconds()
                                                        elapsed = (now - current_program.start_time).total_seconds()
                                                        progress = min(1.0, max(0.0, elapsed / total_duration)) if total_duration > 0 else 0.0

                                                    stream_value_metrics.append(f'dispatcharr_stream_programming{{{",".join(epg_labels)}}} {progress:.4f}')
                                            except Exception as e:
                                                logger.debug(f"Error fetching EPG program for channel {channel_id}: {e}")

                                    except Stream.DoesNotExist:
                                        logger.debug(f"Stream {stream_id} not found in database")

                                except Channel.DoesNotExist:
                                    logger.debug(f"Channel {channel_id} not found in database")

                        except Exception as e:
                            logger.debug(f"Error processing stream key {key}: {e}")

                except Exception as e:
                    logger.debug(f"Error scanning stream keys: {e}")

                # ── VOD streams ──────────────────────────────────────────────
                try:
                    from apps.vod.models import Movie, Episode
                    import re as _re

                    for key in self.redis_client.scan_iter(match="vod_persistent_connection:*"):
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if not connection_data:
                                continue

                            if isinstance(list(connection_data.keys())[0], bytes):
                                def get_vod_field(field_name, default=''):
                                    val = connection_data.get(
                                        field_name.encode('utf-8') if isinstance(field_name, str) else field_name,
                                        b'',
                                    )
                                    return val.decode('utf-8') if isinstance(val, bytes) else default
                            else:
                                def get_vod_field(field_name, default=''):
                                    return connection_data.get(field_name, default)

                            active_stream_count = int(get_vod_field('active_streams', '0'))
                            if active_stream_count == 0:
                                continue

                            active_streams += 1
                            active_vod_streams += 1

                            session_id = key.decode('utf-8') if isinstance(key, bytes) else key
                            session_id = session_id.replace('vod_persistent_connection:', '')

                            try:
                                session_parts = session_id.split('_')
                                vod_channel_number = session_parts[1] if len(session_parts) >= 2 else session_id
                            except Exception:
                                vod_channel_number = session_id

                            content_type = get_vod_field('content_obj_type', 'unknown')
                            content_uuid = get_vod_field('content_uuid', '')
                            content_name = get_vod_field('content_name', 'Unknown')
                            m3u_profile_id_str = get_vod_field('m3u_profile_id', '')

                            logo_url = ""
                            video_codec = ""
                            resolution = ""
                            stream_profile_name = ""
                            season_number = None
                            episode_number = None
                            series_name = None
                            channel_group = ""

                            prog_title = ""
                            prog_subtitle = ""
                            prog_description = ""
                            prog_year = ""
                            prog_genre = ""
                            prog_duration_secs = 0

                            try:
                                if content_type == 'movie':
                                    from apps.vod.models import M3UMovieRelation
                                    content_obj = Movie.objects.select_related('logo').get(uuid=content_uuid)
                                    if hasattr(content_obj, 'logo') and content_obj.logo:
                                        logo_url = f"/api/vod/vodlogos/{content_obj.logo.id}/cache/"
                                        base_url = settings.get('base_url', '').strip() if settings else ''
                                        if base_url:
                                            logo_url = f"{base_url.rstrip('/')}{logo_url}"
                                    if content_obj.custom_properties:
                                        video_info = content_obj.custom_properties.get('video', {})
                                        if video_info:
                                            video_codec = video_info.get('codec_name', '')
                                            width = video_info.get('width')
                                            height = video_info.get('height')
                                            if width and height:
                                                resolution = f"{width}x{height}"
                                    content_name = content_obj.name
                                    prog_title = content_obj.name
                                    prog_description = content_obj.description or ""
                                    prog_year = str(content_obj.year) if content_obj.year else ""
                                    prog_genre = content_obj.genre or ""
                                    prog_duration_secs = content_obj.duration_secs or 0
                                    if prog_year:
                                        for pattern in [f" ({prog_year})", f" - {prog_year}", f" {prog_year}"]:
                                            if prog_title.endswith(pattern):
                                                prog_title = prog_title[:-len(pattern)].strip()
                                                break
                                    subtitle_parts = []
                                    if prog_year:
                                        subtitle_parts.append(prog_year)
                                    if prog_genre:
                                        subtitle_parts.append(prog_genre)
                                    prog_subtitle = " - ".join(subtitle_parts)
                                    if m3u_profile_id_str:
                                        try:
                                            relation = M3UMovieRelation.objects.select_related('category').filter(
                                                movie=content_obj,
                                                m3u_account__profiles__id=int(m3u_profile_id_str),
                                            ).first()
                                            if relation and relation.category:
                                                channel_group = relation.category.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            pass

                                elif content_type == 'episode':
                                    from apps.vod.models import M3USeriesRelation
                                    content_obj = Episode.objects.select_related('series', 'series__logo').get(uuid=content_uuid)
                                    season_number = content_obj.season_number
                                    episode_number = content_obj.episode_number
                                    if content_obj.series:
                                        content_name = content_obj.series.name
                                        series_name = content_obj.series.name.replace('"', '\\"').replace('\\', '\\\\')
                                    if hasattr(content_obj.series, 'logo') and content_obj.series.logo:
                                        logo_url = f"/api/vod/vodlogos/{content_obj.series.logo.id}/cache/"
                                        base_url = settings.get('base_url', '').strip() if settings else ''
                                        if base_url:
                                            logo_url = f"{base_url.rstrip('/')}{logo_url}"
                                    if content_obj.custom_properties:
                                        video_info = content_obj.custom_properties.get('video', {})
                                        if video_info:
                                            video_codec = video_info.get('codec_name', 'unknown')
                                            width = video_info.get('width')
                                            height = video_info.get('height')
                                            if width and height:
                                                resolution = f"{width}x{height}"
                                    prog_title = content_obj.series.name if content_obj.series else ""
                                    prog_description = content_obj.description or ""
                                    prog_duration_secs = content_obj.duration_secs or 0
                                    prog_subtitle = content_obj.name
                                    if prog_title and prog_subtitle.startswith(prog_title):
                                        prog_subtitle = prog_subtitle[len(prog_title):].lstrip(' -')
                                    series_name_no_year = prog_title
                                    if prog_title:
                                        match = _re.search(r'\s*\(\d{4}\)$', prog_title)
                                        if match:
                                            series_name_no_year = prog_title[:match.start()].strip()
                                    if series_name_no_year and prog_subtitle.startswith(series_name_no_year):
                                        prog_subtitle = prog_subtitle[len(series_name_no_year):].lstrip(' -')
                                    logger.debug(f"VOD Episode programming: title='{prog_title}', subtitle='{prog_subtitle}', duration={prog_duration_secs}")
                                    if m3u_profile_id_str and content_obj.series:
                                        try:
                                            relation = M3USeriesRelation.objects.select_related('category').filter(
                                                series=content_obj.series,
                                                m3u_account__profiles__id=int(m3u_profile_id_str),
                                            ).first()
                                            if relation and relation.category:
                                                channel_group = relation.category.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            pass

                            except (Movie.DoesNotExist, Episode.DoesNotExist):
                                logger.debug(f"VOD content {content_type} {content_uuid} not found in database")
                            except Exception as e:
                                logger.error(f"Error querying VOD content metadata for {content_uuid}: {e}", exc_info=True)

                            content_name = content_name.replace('"', '\\"').replace('\\', '\\\\')
                            logo_url = logo_url.replace('"', '\\"').replace('\\', '\\\\')

                            profile_id = None
                            profile_name = ""
                            profile_connections = 0
                            profile_max = 0
                            provider_name = ""
                            provider_type = ""

                            if m3u_profile_id_str:
                                try:
                                    profile_id = int(m3u_profile_id_str)
                                    active_profile = M3UAccountProfile.objects.get(id=profile_id)
                                    profile_name = active_profile.name.replace('"', '\\"').replace('\\', '\\\\')
                                    provider_name = active_profile.m3u_account.name.replace('"', '\\"').replace('\\', '\\\\')
                                    provider_type = active_profile.m3u_account.account_type
                                    profile_connections = int(self.redis_client.get(f"profile_connections:{profile_id}") or 0)
                                    profile_max = active_profile.max_streams
                                except Exception as e:
                                    logger.debug(f"Error getting VOD M3U profile {m3u_profile_id_str}: {e}")

                            created_at = float(get_vod_field('created_at', '0'))
                            uptime_seconds = int(time.time() - created_at) if created_at > 0 else 0
                            bytes_sent = int(get_vod_field('bytes_sent', '0'))
                            total_mb = round(bytes_sent / 1024 / 1024, 2)
                            avg_bitrate_bps = round((bytes_sent * 8 / uptime_seconds), 2) if uptime_seconds > 0 else 0
                            active_clients = active_stream_count

                            base_labels = [
                                f'type="vod"',
                                f'channel_uuid="{session_id}"',
                                f'channel_number="{vod_channel_number}"',
                            ]
                            base_labels_str = ",".join(base_labels)

                            metadata_labels = base_labels + [
                                f'content_uuid="{content_uuid}"',
                                f'channel_name="{content_name}"',
                                f'channel_group="{channel_group}"',
                                f'content_type="{content_type}"',
                                f'provider="{provider_name}"',
                                f'provider_type="{provider_type}"',
                                f'state="active"',
                                f'logo_url="{logo_url}"',
                                f'profile_id="{profile_id if profile_id else "none"}"',
                                f'profile_name="{profile_name}"',
                                f'stream_profile="{stream_profile_name}"',
                                f'video_codec="{video_codec}"',
                                f'resolution="{resolution}"',
                            ]

                            if content_type == 'episode' and season_number is not None and episode_number is not None:
                                metadata_labels.append(f'season_number="{season_number}"')
                                metadata_labels.append(f'episode_number="{episode_number}"')
                                if series_name:
                                    metadata_labels.append(f'series_name="{series_name}"')

                            stream_value_metrics.append(f'dispatcharr_stream_id{{{base_labels_str}}} 0')
                            stream_value_metrics.append(f'dispatcharr_stream_metadata{{{",".join(metadata_labels)}}} 1')
                            stream_value_metrics.append(f'dispatcharr_stream_uptime_seconds{{{base_labels_str}}} {uptime_seconds}')
                            stream_value_metrics.append(f'dispatcharr_stream_active_clients{{{base_labels_str}}} {active_clients}')

                            if avg_bitrate_bps > 0:
                                stream_value_metrics.append(f'dispatcharr_stream_avg_bitrate_bps{{{base_labels_str}}} {avg_bitrate_bps}')
                            if total_mb > 0:
                                stream_value_metrics.append(f'dispatcharr_stream_total_transfer_mb{{{base_labels_str}}} {total_mb}')
                            if profile_id:
                                stream_value_metrics.append(f'dispatcharr_stream_profile_connections{{{base_labels_str}}} {profile_connections}')
                                stream_value_metrics.append(f'dispatcharr_stream_profile_max_connections{{{base_labels_str}}} {profile_max}')

                            # VOD programming metric
                            logger.debug(f"VOD Programming check for {session_id}: prog_title='{prog_title}', prog_description='{prog_description[:50] if prog_description else ''}'")
                            if prog_title or prog_description:
                                try:
                                    from datetime import datetime, timezone, timedelta

                                    logger.debug(f"Entering programming metric generation for {session_id}")

                                    prog_title_safe = escape_label(prog_title)
                                    prog_subtitle_safe = escape_label(prog_subtitle)
                                    prog_description_safe = escape_label(prog_description)

                                    prog_start_time = ""
                                    prog_end_time = ""
                                    if created_at > 0:
                                        start_dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
                                        prog_start_time = start_dt.isoformat()
                                        if prog_duration_secs > 0:
                                            prog_end_time = (start_dt + timedelta(seconds=prog_duration_secs)).isoformat()

                                    programming_labels = base_labels + [
                                        'previous_title=""',
                                        'previous_subtitle=""',
                                        'previous_description=""',
                                        'previous_start_time=""',
                                        'previous_end_time=""',
                                        f'current_title="{prog_title_safe}"',
                                        f'current_subtitle="{prog_subtitle_safe}"',
                                        f'current_description="{prog_description_safe}"',
                                        f'current_start_time="{prog_start_time}"',
                                        f'current_end_time="{prog_end_time}"',
                                        'next_title=""',
                                        'next_subtitle=""',
                                        'next_description=""',
                                        'next_start_time=""',
                                        'next_end_time=""',
                                    ]

                                    progress = 0.0
                                    if prog_duration_secs > 0 and uptime_seconds > 0:
                                        progress = min(1.0, max(0.0, uptime_seconds / prog_duration_secs))

                                    programming_metric = f'dispatcharr_stream_programming{{{",".join(programming_labels)}}} {progress:.4f}'
                                    stream_value_metrics.append(programming_metric)
                                    logger.debug(f"Programming metric appended for {session_id}")
                                except Exception as prog_e:
                                    logger.error(f"Error generating programming metric for {session_id}: {prog_e}", exc_info=True)

                        except Exception as e:
                            logger.debug(f"Error processing VOD connection key {key}: {e}")

                except Exception as e:
                    logger.debug(f"Error scanning VOD connection keys: {e}")

                # Emit totals and collected metrics
                metrics.append(f"dispatcharr_active_streams {active_streams}")
                metrics.append(f'dispatcharr_active_streams{{type="live"}} {active_live_streams}')
                metrics.append(f'dispatcharr_active_streams{{type="vod"}} {active_vod_streams}')
                for metric in stream_value_metrics:
                    metrics.append(metric)

        except Exception as e:
            logger.error(f"Error collecting stream metrics: {e}")

        metrics.append("")
        return metrics

    # ── EPG metrics ──────────────────────────────────────────────────────────

    def _collect_epg_metrics(self, settings: dict = None) -> list:
        """Collect EPG source statistics."""
        from apps.epg.models import EPGSource

        metrics = []
        include_urls = settings and settings.get('include_source_urls', False)

        try:
            total_sources = EPGSource.objects.exclude(source_type='dummy').count()
            active_sources = EPGSource.objects.filter(is_active=True).exclude(source_type='dummy').count()

            metrics.append("# HELP dispatcharr_epg_sources Total number of EPG sources")
            metrics.append("# TYPE dispatcharr_epg_sources gauge")
            metrics.append(f'dispatcharr_epg_sources{{status="total"}} {total_sources}')
            metrics.append(f'dispatcharr_epg_sources{{status="active"}} {active_sources}')

            metrics.append("# HELP dispatcharr_epg_source_status EPG source status breakdown")
            metrics.append("# TYPE dispatcharr_epg_source_status gauge")
            for status_choice in EPGSource.STATUS_CHOICES:
                status_value = status_choice[0]
                count = EPGSource.objects.filter(status=status_value).exclude(source_type='dummy').count()
                metrics.append(f'dispatcharr_epg_source_status{{status="{status_value}"}} {count}')

            metrics.append("# HELP dispatcharr_epg_source_priority Priority value for EPG source (lower is higher priority)")
            metrics.append("# TYPE dispatcharr_epg_source_priority gauge")

            for source in EPGSource.objects.exclude(source_type='dummy'):
                source_name = source.name.replace('"', '\\"').replace('\\', '\\\\')
                source_type = source.source_type or 'unknown'
                status = source.status
                is_active = str(source.is_active).lower()
                priority = source.priority

                base_labels = [
                    f'source_id="{source.id}"',
                    f'source_name="{source_name}"',
                    f'source_type="{source_type}"',
                    f'status="{status}"',
                    f'is_active="{is_active}"',
                ]
                if include_urls and source.url:
                    source_url = source.url.replace('"', '\\"').replace('\\', '\\\\')
                    base_labels.append(f'url="{source_url}"')

                metrics.append(f'dispatcharr_epg_source_priority{{{",".join(base_labels)}}} {priority}')

        except Exception as e:
            logger.error(f"Error collecting EPG metrics: {e}")

        metrics.append("")
        return metrics

    # ── Client metrics ───────────────────────────────────────────────────────

    def _collect_client_metrics(self) -> list:
        """Collect individual client connection metrics."""
        metrics = []

        try:
            from apps.channels.models import Channel

            metrics.append("# HELP dispatcharr_active_clients Total number of active client connections (live and VOD)")
            metrics.append("# TYPE dispatcharr_active_clients gauge")
            metrics.append("# HELP dispatcharr_client_info Client connection metadata (type: live/vod)")
            metrics.append("# TYPE dispatcharr_client_info gauge")
            metrics.append("# HELP dispatcharr_client_connection_duration_seconds Duration of client connection in seconds")
            metrics.append("# TYPE dispatcharr_client_connection_duration_seconds gauge")
            metrics.append("# HELP dispatcharr_client_bytes_sent Total bytes sent to client")
            metrics.append("# TYPE dispatcharr_client_bytes_sent counter")
            metrics.append("# HELP dispatcharr_client_avg_transfer_rate_bps Average transfer rate to client in bits per second")
            metrics.append("# TYPE dispatcharr_client_avg_transfer_rate_bps gauge")
            metrics.append("# HELP dispatcharr_client_current_transfer_rate_bps Current transfer rate to client in bits per second")
            metrics.append("# TYPE dispatcharr_client_current_transfer_rate_bps gauge")

            cursor = 0
            current_time = time.time()
            total_clients = 0
            client_metrics = []

            _user_cache = {}  # per-scrape cache: user_id int -> username str

            def _resolve_username(user_id_str):
                try:
                    uid = int(user_id_str)
                    if uid <= 0:
                        return 'anonymous'
                    if uid not in _user_cache:
                        from apps.accounts.models import User
                        _user_cache[uid] = User.objects.get(id=uid).username
                    return _user_cache[uid]
                except Exception:
                    return 'anonymous'

            # Live clients
            while True:
                cursor, keys = self.redis_client.scan(
                    cursor,
                    match="ts_proxy:channel:*:clients",
                    count=100,
                )
                for client_set_key in keys:
                    try:
                        parts = client_set_key.decode('utf-8') if isinstance(client_set_key, bytes) else client_set_key
                        parts = parts.split(':')
                        if len(parts) < 4:
                            continue
                        channel_uuid = parts[2]

                        try:
                            channel = Channel.objects.get(uuid=channel_uuid)
                            channel_number = getattr(channel, 'channel_number', 'N/A')
                        except Channel.DoesNotExist:
                            continue

                        client_ids = self.redis_client.smembers(client_set_key)
                        total_clients += len(client_ids)

                        for client_id_bytes in client_ids:
                            try:
                                client_id = client_id_bytes.decode('utf-8') if isinstance(client_id_bytes, bytes) else client_id_bytes
                                client_key = f"ts_proxy:channel:{channel_uuid}:clients:{client_id}"
                                client_data = self.redis_client.hgetall(client_key)

                                if not client_data:
                                    continue

                                def get_client_field(field, default='unknown'):
                                    val = client_data.get(field)
                                    if val is None:
                                        return default
                                    return str(val)

                                ip_address = get_client_field('ip_address', 'unknown')
                                user_agent = get_client_field('user_agent', 'unknown')
                                worker_id = get_client_field('worker_id', 'unknown')
                                user_id_str = get_client_field('user_id', '0')
                                username = _resolve_username(user_id_str)

                                ip_address_safe = ip_address.replace('"', '\\"').replace('\\', '\\\\')
                                user_agent_safe = user_agent.replace('"', '\\"').replace('\\', '\\\\').replace('\n', ' ').replace('\r', '')
                                client_id_safe = client_id.replace('"', '\\"').replace('\\', '\\\\')
                                worker_id_safe = worker_id.replace('"', '\\"').replace('\\', '\\\\')
                                username_safe = username.replace('"', '\\"').replace('\\', '\\\\')

                                connection_duration = 0
                                try:
                                    connected_at = float(get_client_field('connected_at', '0'))
                                    if connected_at > 0:
                                        connection_duration = max(0, int(current_time - connected_at))
                                except (ValueError, TypeError):
                                    pass

                                bytes_sent = 0
                                try:
                                    bytes_sent = int(get_client_field('bytes_sent', '0'))
                                except (ValueError, TypeError):
                                    pass

                                avg_rate_bps = 0.0
                                try:
                                    avg_rate_value = float(get_client_field('avg_rate_KBps', '0'))
                                    avg_rate_bps = avg_rate_value * 8 if avg_rate_value > 50000 else avg_rate_value * 8000
                                except (ValueError, TypeError):
                                    pass

                                current_rate_bps = 0.0
                                try:
                                    current_rate_value = float(get_client_field('current_rate_KBps', '0'))
                                    current_rate_bps = current_rate_value * 8 if current_rate_value > 50000 else current_rate_value * 8000
                                except (ValueError, TypeError):
                                    pass

                                base_labels = [
                                    f'type="live"',
                                    f'client_id="{client_id_safe}"',
                                    f'channel_uuid="{channel_uuid}"',
                                    f'channel_number="{channel_number}"',
                                ]
                                base_labels_str = ','.join(base_labels)

                                info_labels = base_labels + [
                                    f'ip_address="{ip_address_safe}"',
                                    f'user_agent="{user_agent_safe}"',
                                    f'worker_id="{worker_id_safe}"',
                                    f'user_id="{user_id_str}"',
                                    f'username="{username_safe}"',
                                ]
                                client_metrics.append(f'dispatcharr_client_info{{{",".join(info_labels)}}} 1')

                                if connection_duration > 0:
                                    client_metrics.append(f'dispatcharr_client_connection_duration_seconds{{{base_labels_str}}} {connection_duration}')
                                if bytes_sent > 0:
                                    client_metrics.append(f'dispatcharr_client_bytes_sent{{{base_labels_str}}} {bytes_sent}')
                                if avg_rate_bps > 0:
                                    client_metrics.append(f'dispatcharr_client_avg_transfer_rate_bps{{{base_labels_str}}} {avg_rate_bps}')
                                if current_rate_bps > 0:
                                    client_metrics.append(f'dispatcharr_client_current_transfer_rate_bps{{{base_labels_str}}} {current_rate_bps}')

                            except Exception as e:
                                logger.debug(f"Error processing client {client_id}: {e}")

                    except Exception as e:
                        logger.debug(f"Error processing client set {client_set_key}: {e}")

                if cursor == 0:
                    break

            # VOD clients
            try:
                cursor = 0
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor,
                        match="vod_persistent_connection:*",
                        count=100,
                    )
                    for key in keys:
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if not connection_data:
                                continue

                            if isinstance(list(connection_data.keys())[0], bytes):
                                def get_vod_field(field_name, default=''):
                                    val = connection_data.get(
                                        field_name.encode('utf-8') if isinstance(field_name, str) else field_name,
                                        b'',
                                    )
                                    return val.decode('utf-8') if isinstance(val, bytes) else default
                            else:
                                def get_vod_field(field_name, default=''):
                                    return connection_data.get(field_name, default)

                            active_stream_count = int(get_vod_field('active_streams', '0'))
                            if active_stream_count == 0:
                                continue

                            total_clients += 1

                            session_id = key.decode('utf-8') if isinstance(key, bytes) else key
                            session_id = session_id.replace('vod_persistent_connection:', '')

                            try:
                                session_parts = session_id.split('_')
                                vod_channel_number = session_parts[1] if len(session_parts) >= 2 else session_id
                            except Exception:
                                vod_channel_number = session_id

                            content_type = get_vod_field('content_obj_type', 'unknown')
                            content_uuid = get_vod_field('content_uuid', '')
                            content_name = get_vod_field('content_name', 'Unknown')
                            client_ip = get_vod_field('client_ip', 'unknown')
                            client_user_agent = get_vod_field('client_user_agent', 'unknown')
                            worker_id = get_vod_field('worker_id', 'unknown')
                            user_id_str = get_vod_field('user_id', '0')
                            username = _resolve_username(user_id_str)

                            session_id_safe = session_id.replace('"', '\\"').replace('\\', '\\\\')
                            vod_channel_number_safe = vod_channel_number.replace('"', '\\"').replace('\\', '\\\\')
                            content_name_safe = content_name.replace('"', '\\"').replace('\\', '\\\\')
                            client_ip_safe = client_ip.replace('"', '\\"').replace('\\', '\\\\')
                            client_user_agent_safe = client_user_agent.replace('"', '\\"').replace('\\', '\\\\').replace('\n', ' ').replace('\r', '')
                            worker_id_safe = worker_id.replace('"', '\\"').replace('\\', '\\\\')
                            username_safe = username.replace('"', '\\"').replace('\\', '\\\\')

                            connection_duration = 0
                            created_at = float(get_vod_field('created_at', '0'))
                            if created_at > 0:
                                connection_duration = int(current_time - created_at)

                            bytes_sent = int(get_vod_field('bytes_sent', '0'))
                            avg_rate_bps = 0.0
                            if connection_duration > 0 and bytes_sent > 0:
                                avg_rate_bps = round((bytes_sent * 8 / connection_duration), 2)

                            client_id_safe = session_id_safe
                            base_labels = [
                                f'type="vod"',
                                f'client_id="{client_id_safe}"',
                                f'channel_uuid="{session_id_safe}"',
                                f'channel_number="{vod_channel_number_safe}"',
                            ]
                            base_labels_str = ','.join(base_labels)

                            info_labels = base_labels + [
                                f'content_uuid="{content_uuid}"',
                                f'channel_name="{content_name_safe}"',
                                f'content_type="{content_type}"',
                                f'ip_address="{client_ip_safe}"',
                                f'user_agent="{client_user_agent_safe}"',
                                f'worker_id="{worker_id_safe}"',
                                f'user_id="{user_id_str}"',
                                f'username="{username_safe}"',
                            ]
                            client_metrics.append(f'dispatcharr_client_info{{{",".join(info_labels)}}} 1')

                            if connection_duration > 0:
                                client_metrics.append(f'dispatcharr_client_connection_duration_seconds{{{base_labels_str}}} {connection_duration}')
                            if bytes_sent > 0:
                                client_metrics.append(f'dispatcharr_client_bytes_sent{{{base_labels_str}}} {bytes_sent}')
                            if avg_rate_bps > 0:
                                client_metrics.append(f'dispatcharr_client_avg_transfer_rate_bps{{{base_labels_str}}} {avg_rate_bps:.2f}')
                                client_metrics.append(f'dispatcharr_client_current_transfer_rate_bps{{{base_labels_str}}} {avg_rate_bps:.2f}')

                        except Exception as e:
                            logger.debug(f"Error processing VOD connection for clients: {e}")

                    if cursor == 0:
                        break

            except Exception as e:
                logger.debug(f"Error scanning VOD connections for clients: {e}")

            metrics.append(f"dispatcharr_active_clients {total_clients}")
            metrics.extend(client_metrics)

        except Exception as e:
            logger.error(f"Error collecting client metrics: {e}")

        metrics.append("")
        return metrics

    def _collect_user_metrics(self) -> list:
        """Collect Dispatcharr user information, stream limits, and active stream counts."""
        from apps.accounts.models import User

        metrics = []
        metrics.append("# HELP dispatcharr_user_info Dispatcharr user information")
        metrics.append("# TYPE dispatcharr_user_info gauge")
        metrics.append("# HELP dispatcharr_user_date_joined_timestamp Unix timestamp of when the user account was created")
        metrics.append("# TYPE dispatcharr_user_date_joined_timestamp gauge")
        metrics.append("# HELP dispatcharr_user_stream_limit Configured concurrent stream limit for user (0 = unlimited)")
        metrics.append("# TYPE dispatcharr_user_stream_limit gauge")
        metrics.append("# HELP dispatcharr_user_active_streams Current number of active streams for user")
        metrics.append("# TYPE dispatcharr_user_active_streams gauge")

        # Count active streams per user_id from Redis
        active_streams_by_user = {}
        try:
            redis = self.redis_client
            if not redis:
                raise RuntimeError("Redis client not available")
            # Live client keys
            for key in redis.scan_iter(match="ts_proxy:channel:*:clients:*", count=1000):
                parts = key.split(':')
                if len(parts) >= 5:
                    uid_str = redis.hget(key, 'user_id')
                    if uid_str:
                        try:
                            uid = int(uid_str)
                            active_streams_by_user[uid] = active_streams_by_user.get(uid, 0) + 1
                        except (ValueError, TypeError):
                            pass
            # VOD connection keys
            for key in redis.scan_iter(match="vod_persistent_connection:*", count=1000):
                uid_str = redis.hget(key, 'user_id')
                active_str = redis.hget(key, 'active_streams')
                try:
                    if uid_str and int(active_str or 0) > 0:
                        uid = int(uid_str)
                        active_streams_by_user[uid] = active_streams_by_user.get(uid, 0) + 1
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.error(f"Error counting active streams per user: {e}", exc_info=True)

        try:
            for user in User.objects.filter(is_active=True).order_by('id'):
                # Skip users without an XC password - they have no XC API access
                if not (user.custom_properties or {}).get('xc_password'):
                    continue
                uid = user.id
                username_safe = user.username.replace('\\', '\\\\').replace('"', '\\"')
                user_level = user.user_level
                user_level_name = (
                    "admin" if user_level >= 10
                    else "standard" if user_level >= 1
                    else "streamer"
                )
                is_staff = "true" if user.is_staff else "false"
                date_joined = int(user.date_joined.timestamp()) if user.date_joined else 0

                info_labels = (
                    f'user_id="{uid}",'
                    f'username="{username_safe}",'
                    f'user_level="{user_level_name}",'
                    f'is_staff="{is_staff}"'
                )
                metrics.append(f'dispatcharr_user_info{{{info_labels}}} 1')
                metrics.append(f'dispatcharr_user_date_joined_timestamp{{user_id="{uid}",username="{username_safe}"}} {date_joined}')
                metrics.append(f'dispatcharr_user_stream_limit{{user_id="{uid}",username="{username_safe}"}} {user.stream_limit}')
                metrics.append(f'dispatcharr_user_active_streams{{user_id="{uid}",username="{username_safe}"}} {active_streams_by_user.get(uid, 0)}')

        except Exception as e:
            logger.error(f"Error collecting user metrics: {e}", exc_info=True)

        metrics.append("")
        return metrics
