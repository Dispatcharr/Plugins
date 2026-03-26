"""
Dispatcharr Prometheus Exporter Plugin

Exposes Dispatcharr metrics in Prometheus format for monitoring:
- Active streams and connections
- M3U account statistics
- Channel statistics
- Profile connection usage
- VOD sessions and streams

Runs a lightweight gevent WSGI server on a configurable port to serve
Prometheus metrics independently of Dispatcharr's main web server.
"""

import json
import logging
import os
import threading
import time
from core.utils import RedisClient
from apps.proxy.ts_proxy.constants import ChannelMetadataField

logger = logging.getLogger(__name__)

# Load plugin configuration from plugin.json
def _load_plugin_config():
    """Load plugin configuration from plugin.json file"""
    config_path = os.path.join(os.path.dirname(__file__), 'plugin.json')
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Ensure all required fields exist with defaults
        config.setdefault('min_dispatcharr_version', 'v0.14.0')
        config.setdefault('repo_url', 'https://github.com/sethwv/dispatcharr-exporter')
        config.setdefault('default_port', 9192)
        config.setdefault('default_host', '0.0.0.0')
        config.setdefault('auto_start_default', False)

        return config
    except Exception as e:
        logger.warning(f"Could not load plugin.json, using fallback config: {e}")
        # Fallback configuration if JSON can't be loaded
        return {
            "version": "2.4.1",
            "name": "Dispatcharr Exporter",
            "author": "SethWV",
            "description": "Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring",
            "min_dispatcharr_version": "v0.14.0",
            "repo_url": "https://github.com/sethwv/dispatcharr-exporter",
            "help_url": "https://github.com/sethwv/dispatcharr-exporter",
            "default_port": 9192,
            "default_host": "0.0.0.0",
            "auto_start_default": False,
        }

PLUGIN_CONFIG = _load_plugin_config()

# Global server instance
_metrics_server = None
_auto_start_attempted = False  # Track if auto-start has been attempted in this process


class PrometheusMetricsCollector:
    """Collects and formats metrics from Dispatcharr in Prometheus exposition format"""

    def __init__(self):
        self.redis_client = None  # Lazy-load Redis when needed

    def collect_metrics(self, settings: dict = None) -> str:
        """Collect all metrics and return in Prometheus text format"""
        # Get Redis client now, when we actually need it
        if self.redis_client is None:
            try:
                self.redis_client = RedisClient.get_client()
            except Exception as e:
                logger.warning(f"Could not connect to Redis: {e}")
        
        metrics = []
        settings = settings or {}

        # Get Dispatcharr version using the same logic as version check in start()
        dispatcharr_version, dispatcharr_timestamp, full_version = MetricsServer._get_dispatcharr_version()

        # Add metadata
        metrics.append("# HELP dispatcharr_info Dispatcharr version and instance information")
        metrics.append("# TYPE dispatcharr_info gauge")
        metrics.append(f'dispatcharr_info{{version="{full_version}"}} 1')
        metrics.append("")
        
        # Add exporter version info
        # Add exporter settings info (programmatically from Plugin.fields)
        exporter_version = PLUGIN_CONFIG["version"].lstrip('-')
        metrics.append("# HELP dispatcharr_exporter_info Dispatcharr Exporter plugin version information")
        metrics.append("# TYPE dispatcharr_exporter_info gauge")
        metrics.append("# HELP dispatcharr_exporter_settings_info Dispatcharr Exporter plugin settings (for debugging/support)")
        metrics.append("# TYPE dispatcharr_exporter_settings_info gauge")
        metrics.append("# HELP dispatcharr_exporter_port Configured port number for the metrics server")
        metrics.append("# TYPE dispatcharr_exporter_port gauge")
        metrics.append(f'dispatcharr_exporter_info{{version="{exporter_version}"}} 1')
        
        # Build labels programmatically from Plugin fields
        settings_labels = []
        port_value = PLUGIN_CONFIG["default_port"]

        for field in Plugin.fields:
            field_id = field['id']
            field_value = settings.get(field_id, field['default']) if settings else field['default']
            
            # Capture port for separate metric
            if field_id == 'port':
                port_value = field_value
            
            # Convert value to string and escape quotes/backslashes
            if isinstance(field_value, bool):
                value_str = str(field_value).lower()
            elif isinstance(field_value, (int, float)):
                value_str = str(field_value)
            else:
                # String values - escape quotes and backslashes
                value_str = str(field_value).replace('\\', '\\\\').replace('"', '\\"')
            
            settings_labels.append(f'{field_id}="{value_str}"')
        
        metrics.append(f'dispatcharr_exporter_settings_info{{{",".join(settings_labels)}}} 1')
        metrics.append(f'dispatcharr_exporter_port {port_value}')
        metrics.append("")

        # M3U Account metrics (optional, enabled by default)
        if not settings or settings.get('include_m3u_stats', True):
            metrics.extend(self._collect_m3u_account_metrics(settings))
        
        # EPG Source metrics (optional, disabled by default)
        if settings and settings.get('include_epg_stats', False):
            metrics.extend(self._collect_epg_metrics(settings))
        
        # Channel metrics
        metrics.extend(self._collect_channel_metrics())
        
        # Profile connection metrics (part of M3U stats)
        if not settings or settings.get('include_m3u_stats', True):
            metrics.extend(self._collect_profile_metrics())
        
        # Stream metrics with detailed info (includes both live and VOD)
        metrics.extend(self._collect_stream_metrics(settings))
        
        # Client connection metrics (optional, disabled by default; includes both live and VOD)
        if settings and settings.get('include_client_stats', False):
            metrics.extend(self._collect_client_metrics())

        return "\n".join(metrics)
    
    def _collect_m3u_account_metrics(self, settings: dict = None) -> list:
        """Collect M3U account statistics"""
        from apps.m3u.models import M3UAccount
        
        metrics = []
        metrics.append("# HELP dispatcharr_m3u_accounts Total number of M3U accounts")
        metrics.append("# TYPE dispatcharr_m3u_accounts gauge")
        
        include_urls = settings and settings.get('include_source_urls', False)
        
        try:
            # Filter out the default "custom" account
            all_accounts = M3UAccount.objects.exclude(name__iexact="custom")
            total_accounts = all_accounts.count()
            active_accounts = all_accounts.filter(is_active=True).count()
            
            metrics.append(f"dispatcharr_m3u_accounts{{status=\"total\"}} {total_accounts}")
            metrics.append(f"dispatcharr_m3u_accounts{{status=\"active\"}} {active_accounts}")
            
            # Account status breakdown (excluding custom)
            metrics.append("# HELP dispatcharr_m3u_account_status M3U account status breakdown")
            metrics.append("# TYPE dispatcharr_m3u_account_status gauge")
            
            for status_choice in M3UAccount.Status.choices:
                status_value = status_choice[0]
                count = all_accounts.filter(status=status_value).count()
                metrics.append(f'dispatcharr_m3u_account_status{{status="{status_value}"}} {count}')
            
            # Individual account metrics
            include_legacy = settings and settings.get('include_legacy_metrics', False)
            
            if include_legacy:
                metrics.append("# HELP dispatcharr_m3u_account_info Information about each M3U account (legacy format with stream_count as label)")
                metrics.append("# TYPE dispatcharr_m3u_account_info gauge")
            
            metrics.append("# HELP dispatcharr_m3u_account_stream_count Number of streams configured for this M3U account")
            metrics.append("# TYPE dispatcharr_m3u_account_stream_count gauge")
            
            for account in all_accounts:
                account_name = account.name.replace('"', '\\"').replace('\\', '\\\\')
                account_type = account.account_type or 'unknown'
                status = account.status
                is_active = str(account.is_active).lower()
                
                # Count streams from this account
                stream_count = account.streams.count() if hasattr(account, 'streams') else 0
                
                # Base labels for identification
                base_labels = [
                    f'account_id="{account.id}"',
                    f'account_name="{account_name}"',
                    f'account_type="{account_type}"',
                    f'status="{status}"',
                    f'is_active="{is_active}"'
                ]
                
                # Legacy format - Build labels with stream_count included
                legacy_labels = base_labels.copy()
                legacy_labels.append(f'stream_count="{stream_count}"')
                
                # Optionally add username for XC-type accounts
                if include_urls and account_type == 'XC' and hasattr(account, 'username') and account.username:
                    username = account.username.replace('"', '\\"').replace('\\', '\\\\')
                    legacy_labels.append(f'username="{username}"')
                    base_labels.append(f'username="{username}"')
                
                # Optionally add server URL
                if include_urls and account.server_url:
                    server_url = account.server_url.replace('"', '\\"').replace('\\', '\\\\')
                    legacy_labels.append(f'server_url="{server_url}"')
                    base_labels.append(f'server_url="{server_url}"')
                
                # Info metric uses base_labels (no stream_count)
                metrics.append(f'dispatcharr_m3u_account_info{{{",".join(base_labels)}}} 1')
                
                # Add separate gauge for stream count (proper time series)
                metrics.append(f'dispatcharr_m3u_account_stream_count{{{",".join(base_labels)}}} {stream_count}')
            
        except Exception as e:
            logger.error(f"Error collecting M3U account metrics: {e}")
        
        metrics.append("")
        return metrics

    def _collect_channel_metrics(self) -> list:
        """Collect channel statistics"""
        from apps.channels.models import Channel, ChannelGroup
        
        metrics = []
        metrics.append("# HELP dispatcharr_channels Total number of channels")
        metrics.append("# TYPE dispatcharr_channels gauge")
        
        try:
            total_channels = Channel.objects.count()
            
            metrics.append(f"dispatcharr_channels{{status=\"total\"}} {total_channels}")
            
            # Channel groups
            metrics.append("# HELP dispatcharr_channel_groups Total number of channel groups")
            metrics.append("# TYPE dispatcharr_channel_groups gauge")
            channel_groups = ChannelGroup.objects.count()
            metrics.append(f"dispatcharr_channel_groups {channel_groups}")
            
        except Exception as e:
            logger.error(f"Error collecting channel metrics: {e}")
        
        metrics.append("")
        return metrics

    def _collect_profile_metrics(self) -> list:
        """Collect M3U profile connection statistics"""
        from apps.m3u.models import M3UAccountProfile
        from datetime import datetime, timezone
        
        metrics = []
        profile_data = []
        expiry_data = []
        
        try:
            if self.redis_client:
                # Calculate actual profile connections by scanning active streams
                # This is more accurate than the Redis counters which don't update during fallback
                # We need to check BOTH live channel streams AND VOD connections
                actual_profile_connections = {}
                
                # Count live channel streams by scanning channel metadata
                try:
                    pattern = "channel_stream:*"
                    for key in self.redis_client.scan_iter(match=pattern):
                        try:
                            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                            channel_id = key_str.split(':', 1)[1]
                            
                            # Get channel to get its UUID
                            from apps.channels.models import Channel
                            try:
                                channel = Channel.objects.get(id=int(channel_id))
                                channel_uuid = str(channel.uuid)
                                
                                # Get the actual active M3U profile ID from channel metadata
                                metadata_key = f"ts_proxy:channel:{channel_uuid}:metadata"
                                metadata = self.redis_client.hgetall(metadata_key) or {}
                                
                                def get_metadata(field, default=None):
                                    val = metadata.get(field.encode('utf-8') if isinstance(field, str) else field, None)
                                    if val is None:
                                        return default
                                    return val.decode('utf-8') if isinstance(val, bytes) else default
                                
                                m3u_profile_id = get_metadata(ChannelMetadataField.M3U_PROFILE, None)
                                if m3u_profile_id and m3u_profile_id != '0':
                                    try:
                                        profile_id = int(m3u_profile_id)
                                        actual_profile_connections[profile_id] = actual_profile_connections.get(profile_id, 0) + 1
                                    except (ValueError, TypeError):
                                        pass  # Invalid profile ID format
                            except Channel.DoesNotExist:
                                pass  # Channel deleted or not found
                        except Exception as e:
                            logger.debug(f"Error processing stream key for profile counting: {e}")
                except Exception as e:
                    logger.debug(f"Error calculating live channel profile connections: {e}")
                
                # Count VOD connections by scanning persistent connection keys
                try:
                    pattern = "vod_persistent_connection:*"
                    for key in self.redis_client.scan_iter(match=pattern):
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if connection_data:
                                # Handle both bytes and string keys
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
                                
                                # Only count if there are active streams on this connection
                                if m3u_profile_id and int(active_streams) > 0:
                                    try:
                                        profile_id = int(m3u_profile_id)
                                        actual_profile_connections[profile_id] = actual_profile_connections.get(profile_id, 0) + 1
                                    except (ValueError, TypeError):
                                        pass  # Invalid profile ID format
                        except Exception as e:
                            logger.debug(f"Error processing VOD connection key for profile counting: {e}")
                except Exception as e:
                    logger.debug(f"Error calculating VOD profile connections: {e}")
                
                for profile in M3UAccountProfile.objects.all():
                    try:
                        # Skip 'custom' account
                        if profile.m3u_account.name.lower() == 'custom':
                            continue
                        
                        # Use calculated connections (includes both live channels and VOD)
                        current_connections = actual_profile_connections.get(profile.id, 0)
                        max_connections = profile.max_streams
                        
                        profile_name = profile.name.replace('"', '\\"')
                        account_name = profile.m3u_account.name.replace('"', '\\"')
                        
                        profile_data.append(f'dispatcharr_profile_connections{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {current_connections}')
                        profile_data.append(f'dispatcharr_profile_max_connections{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {max_connections}')
                        
                        # Calculate usage ratio (0.0 to 1.0, or 0 if unlimited)
                        if max_connections > 0:
                            usage = current_connections / max_connections
                            profile_data.append(f'dispatcharr_profile_connection_usage{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {usage:.4f}')
                        
                        # For XC profiles, add days to expiry metric
                        if profile.m3u_account.account_type == 'XC':
                            days_remaining = -1  # Default: no expiry set
                            
                            # exp_date is stored in custom_properties['user_info']['exp_date'] as Unix timestamp
                            if profile.custom_properties:
                                user_info = profile.custom_properties.get('user_info', {})
                                exp_date = user_info.get('exp_date')
                                
                                if exp_date:
                                    try:
                                        # Convert Unix timestamp to datetime
                                        expiry = datetime.fromtimestamp(float(exp_date), tz=timezone.utc)
                                        now = datetime.now(timezone.utc)
                                        
                                        days_remaining = (expiry - now).days
                                        # Show 0 if expired (negative days)
                                        days_remaining = max(0, days_remaining)
                                    except (ValueError, TypeError) as e:
                                        logger.debug(f"Error calculating expiry for profile {profile.id}: {e}")
                            
                            expiry_data.append(f'dispatcharr_profile_days_to_expiry{{profile_id="{profile.id}",profile_name="{profile_name}",account_name="{account_name}"}} {days_remaining}')
                        
                    except Exception as e:
                        logger.debug(f"Error getting connections for profile {profile.id}: {e}")
        except Exception as e:
            logger.error(f"Error collecting profile metrics: {e}")
        
        # Only add headers and data if we have profiles to report
        if profile_data:
            metrics.append("# HELP dispatcharr_profile_connections Current connections per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_connections gauge")
            metrics.append("# HELP dispatcharr_profile_max_connections Maximum allowed connections per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_max_connections gauge")
            metrics.append("# HELP dispatcharr_profile_connection_usage Connection usage ratio per M3U profile")
            metrics.append("# TYPE dispatcharr_profile_connection_usage gauge")
            metrics.extend(profile_data)
        
        # Add expiry metrics if we have any
        if expiry_data:
            metrics.append("# HELP dispatcharr_profile_days_to_expiry Days remaining until XC profile expiry (0 if expired, -1 if no expiry set)")
            metrics.append("# TYPE dispatcharr_profile_days_to_expiry gauge")
            metrics.extend(expiry_data)
        
        metrics.append("")
        return metrics

    def _collect_stream_metrics(self, settings: dict = None) -> list:
        """Collect active stream statistics from Redis"""
        from apps.channels.models import Channel, Stream
        from apps.m3u.models import M3UAccount, M3UAccountProfile
        
        settings = settings or {}
        
        metrics = []
        metrics.append("# HELP dispatcharr_active_streams Total number of active streams (live and VOD)")
        metrics.append("# TYPE dispatcharr_active_streams gauge")
        
        include_legacy = settings and settings.get('include_legacy_metrics', False)
        if include_legacy:
            metrics.append("# HELP dispatcharr_stream_info Detailed information about active streams (legacy format with all values as labels)")
            metrics.append("# TYPE dispatcharr_stream_info gauge")
        
        # Channel number as a gauge (for numeric operations/sorting) - live channels only
        metrics.append("# HELP dispatcharr_stream_channel_number Channel number for active stream (live only)")
        metrics.append("# TYPE dispatcharr_stream_channel_number gauge")
        
        # Stream ID as a gauge (for tracking which specific stream is active)
        metrics.append("# HELP dispatcharr_stream_id Active stream ID for channel or session ID for VOD")
        metrics.append("# TYPE dispatcharr_stream_id gauge")
        
        # Index metric showing which stream is active with identifying information - live channels only
        metrics.append("# HELP dispatcharr_stream_index Active stream index for channel (0=primary, >0=fallback) (live only)")
        metrics.append("# TYPE dispatcharr_stream_index gauge")
        
        # Available streams count - live channels only
        metrics.append("# HELP dispatcharr_stream_available_streams Total number of streams configured for channel (live only)")
        metrics.append("# TYPE dispatcharr_stream_available_streams gauge")
        
        # Metadata/info metric with enrichment labels
        metrics.append("# HELP dispatcharr_stream_metadata Stream metadata and enrichment information (type: live/vod, state values: active, waiting_for_clients, buffering, stopping, error, unknown)")
        metrics.append("# TYPE dispatcharr_stream_metadata gauge")
        
        # EPG Program information - live channels only
        metrics.append("# HELP dispatcharr_stream_programming Current EPG program information for active streams (live only)")
        metrics.append("# TYPE dispatcharr_stream_programming gauge")
        
        # Separate gauge metrics for values that change (recommended for proper time series)
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
                # Count active channel streams and collect detailed info
                active_streams = 0
                active_live_streams = 0
                active_vod_streams = 0
                stream_info_metrics = []
                stream_value_metrics = []
                pattern = "channel_stream:*"
                
                try:
                    for key in self.redis_client.scan_iter(match=pattern):
                        active_streams += 1
                        active_live_streams += 1
                        
                        # Extract channel ID from key (format: "channel_stream:channel_id")
                        try:
                            key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                            channel_id = key_str.split(':', 1)[1]
                            
                            # Get stream ID from Redis
                            stream_id = self.redis_client.get(key)
                            if stream_id:
                                stream_id = int(stream_id.decode('utf-8') if isinstance(stream_id, bytes) else stream_id)
                                
                                # Get channel details
                                try:
                                    channel = Channel.objects.select_related('logo', 'channel_group').get(id=int(channel_id))
                                    channel_uuid = str(channel.uuid)
                                    channel_name = channel.name.replace('"', '\\"').replace('\\', '\\\\')
                                    channel_number = getattr(channel, 'channel_number', 'N/A')
                                    channel_group = channel.channel_group.name.replace('"', '\\"').replace('\\', '\\\\') if channel.channel_group else "none"
                                    
                                    # Get logo URL as API cache endpoint
                                    logo_url = ""
                                    if hasattr(channel, 'logo') and channel.logo:
                                        # Construct the API cache endpoint path (always starts with /)
                                        logo_path = f"/api/channels/logos/{channel.logo.id}/cache/"
                                        
                                        # Get base URL from settings if provided
                                        base_url = settings.get('base_url', '').strip()
                                        if base_url:
                                            # Ensure base_url doesn't end with / to avoid double slashes
                                            base_url = base_url.rstrip('/')
                                            # Combine base_url with logo_path (which starts with /)
                                            logo_url = f"{base_url}{logo_path}"
                                        else:
                                            # No base URL - use relative path with leading /
                                            logo_url = logo_path
                                    logo_url = logo_url.replace('"', '\\"').replace('\\', '\\\\')
                                    
                                    # Get stream stats from Redis metadata (uses UUID)
                                    metadata_key = f"ts_proxy:channel:{channel_uuid}:metadata"
                                    metadata = self.redis_client.hgetall(metadata_key) or {}
                                    
                                    def get_metadata(field, default="0"):
                                        val = metadata.get(field.encode('utf-8') if isinstance(field, str) else field, b'0')
                                        return val.decode('utf-8') if isinstance(val, bytes) else default
                                    
                                    # Get ACTUAL active stream ID from metadata (this updates during fallback)
                                    active_stream_id_str = get_metadata(ChannelMetadataField.STREAM_ID, None)
                                    if active_stream_id_str and active_stream_id_str != '0':
                                        try:
                                            # Override stream_id with the actual active stream from metadata
                                            stream_id = int(active_stream_id_str)
                                        except (ValueError, TypeError):
                                            logger.debug(f"Invalid active stream ID in metadata: {active_stream_id_str}")
                                    
                                    # Calculate uptime
                                    init_time = float(get_metadata(ChannelMetadataField.INIT_TIME, '0'))
                                    uptime_seconds = int(time.time() - init_time) if init_time > 0 else 0
                                    
                                    # Get stream profile name (lookup from database)
                                    stream_profile_id = get_metadata(ChannelMetadataField.STREAM_PROFILE, '0')
                                    stream_profile_name = 'Unknown'
                                    if stream_profile_id and stream_profile_id != '0':
                                        try:
                                            from core.models import StreamProfile
                                            profile = StreamProfile.objects.get(id=int(stream_profile_id))
                                            stream_profile_name = profile.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            stream_profile_name = f'Profile-{stream_profile_id}'
                                    
                                    # Get video stats
                                    video_codec = get_metadata(ChannelMetadataField.VIDEO_CODEC, 'unknown')
                                    resolution = get_metadata(ChannelMetadataField.RESOLUTION, 'unknown')
                                    source_fps = get_metadata(ChannelMetadataField.SOURCE_FPS, '0')
                                    video_bitrate = get_metadata(ChannelMetadataField.VIDEO_BITRATE, '0')
                                    ffmpeg_output_bitrate = get_metadata(ChannelMetadataField.FFMPEG_OUTPUT_BITRATE, '0')
                                    ffmpeg_speed = get_metadata(ChannelMetadataField.FFMPEG_SPEED, '0')
                                    
                                    # Get total transfer
                                    total_bytes = int(get_metadata(ChannelMetadataField.TOTAL_BYTES, '0'))
                                    total_mb = round(total_bytes / 1024 / 1024, 2)
                                    
                                    # Calculate average bitrate in bps
                                    avg_bitrate_bps = round((total_bytes * 8 / uptime_seconds), 2) if uptime_seconds > 0 else 0
                                    
                                    # Get client count from Redis (also uses UUID)
                                    client_set_key = f"ts_proxy:channel:{channel_uuid}:clients"
                                    active_clients = self.redis_client.scard(client_set_key) or 0
                                    
                                    # Calculate current bitrate by summing all client current rates
                                    current_bitrate_bps = 0.0
                                    try:
                                        client_ids = self.redis_client.smembers(client_set_key)
                                        for client_id_bytes in client_ids:
                                            try:
                                                client_id = client_id_bytes.decode('utf-8') if isinstance(client_id_bytes, bytes) else client_id_bytes
                                                client_key = f"ts_proxy:channel:{channel_uuid}:clients:{client_id}"
                                                client_data = self.redis_client.hgetall(client_key)
                                                
                                                if client_data and b'current_rate_KBps' in client_data:
                                                    current_rate_kb = float(client_data[b'current_rate_KBps'].decode('utf-8'))
                                                    # Auto-detect bytes/s vs KB/s (same logic as client metrics)
                                                    if current_rate_kb > 50000:
                                                        current_bitrate_bps += current_rate_kb * 8  # bytes/s to bps
                                                    else:
                                                        current_bitrate_bps += current_rate_kb * 8000  # KB/s to bps
                                            except Exception:
                                                pass  # Invalid rate format
                                    except Exception:
                                        pass  # Missing or invalid client metadata
                                    
                                    # Get state
                                    state = get_metadata(ChannelMetadataField.STATE, 'unknown')
                                    
                                    # Get stream details
                                    try:
                                        stream = Stream.objects.select_related('m3u_account').get(id=stream_id)
                                        stream_name = stream.name.replace('"', '\\"').replace('\\', '\\\\')
                                        provider = stream.m3u_account.name.replace('"', '\\"').replace('\\', '\\\\') if stream.m3u_account else "Unknown"
                                        stream_type = stream.m3u_account.account_type if stream.m3u_account else "Unknown"
                                        
                                        # Get stream index from ChannelStream through table
                                        stream_index = 0
                                        try:
                                            from apps.channels.models import ChannelStream
                                            channel_stream = ChannelStream.objects.get(channel_id=channel.id, stream_id=stream_id)
                                            stream_index = channel_stream.order
                                        except Exception:
                                            pass  # ChannelStream relation not found
                                        
                                        # Get profile information from the stream's M3U account
                                        profile_id = None
                                        profile_name = "Unknown"
                                        profile_connections = 0
                                        profile_max = 0
                                        
                                        # Get the actual M3U profile ID from channel metadata (already fetched above)
                                        m3u_profile_id = get_metadata(ChannelMetadataField.M3U_PROFILE, None)
                                        if m3u_profile_id and m3u_profile_id != '0':
                                            try:
                                                profile_id = int(m3u_profile_id)
                                                active_profile = M3UAccountProfile.objects.get(id=profile_id)
                                                profile_name = active_profile.name.replace('"', '\\"').replace('\\', '\\\\')
                                                profile_connections = int(self.redis_client.get(f"profile_connections:{profile_id}") or 0)
                                                profile_max = active_profile.max_streams
                                            except Exception as e:
                                                logger.debug(f"Error getting M3U profile {profile_id}: {e}")
                                        
                                        # Build minimal base labels (for joining across metrics)
                                        base_labels = [
                                            f'type="live"',
                                            f'channel_uuid="{channel_uuid}"',
                                            f'channel_number="{channel_number}"'
                                        ]
                                        base_labels_str = ",".join(base_labels)
                                        
                                        # Parse channel number as float for gauge value
                                        try:
                                            channel_number_value = float(channel_number)
                                        except (ValueError, TypeError):
                                            channel_number_value = 0.0
                                        
                                        # Build metadata labels (all identifying/enrichment information)
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
                                            f'resolution="{resolution}"'
                                        ]
                                        
                                        # Add stream index metric (minimal labels, value = index)
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_index{{{base_labels_str}}} {stream_index}'
                                        )
                                        
                                        # Add available streams count (total configured streams for this channel)
                                        available_streams = channel.streams.count()
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_available_streams{{{base_labels_str}}} {available_streams}'
                                        )
                                        
                                        # Add channel number metric (minimal labels, value = channel_number)
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_channel_number{{{base_labels_str}}} {channel_number_value}'
                                        )
                                        
                                        # Add stream ID metric (minimal labels, value = stream_id)
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_id{{{base_labels_str}}} {stream_id}'
                                        )
                                        
                                        # Build legacy info metric with all values as labels (for backward compatibility)
                                        # Note: bitrate values are converted to bps for consistency
                                        legacy_labels = metadata_labels + [
                                            f'profile_connections="{profile_connections}"',
                                            f'profile_max_connections="{profile_max}"',
                                            f'fps="{source_fps}"',
                                            f'video_bitrate_bps="{float(video_bitrate) * 1000 if video_bitrate and video_bitrate != "0" else 0}"',
                                            f'transcode_bitrate_bps="{float(ffmpeg_output_bitrate) * 1000 if ffmpeg_output_bitrate and ffmpeg_output_bitrate != "0" else 0}"',
                                            f'avg_bitrate_bps="{avg_bitrate_bps}"',
                                            f'current_bitrate_bps="{current_bitrate_bps}"',
                                            f'total_transfer_mb="{total_mb}"',
                                            f'uptime_seconds="{uptime_seconds}"',
                                            f'active_clients="{active_clients}"'
                                        ]
                                        
                                        # Legacy format (only if enabled)
                                        if include_legacy:
                                            stream_info_metrics.append(
                                                f'dispatcharr_stream_info{{{",".join(legacy_labels)}}} 1'
                                            )
                                        
                                        # Create separate gauge metrics for dynamic values
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_uptime_seconds{{{base_labels_str}}} {uptime_seconds}'
                                        )
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_active_clients{{{base_labels_str}}} {active_clients}'
                                        )
                                        
                                        # Video/bitrate metrics (convert kbps to bps)
                                        if source_fps and source_fps != '0':
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_fps{{{base_labels_str}}} {source_fps}'
                                            )
                                        
                                        # Buffering speed (parse value like "1.0x" to float)
                                        if ffmpeg_speed and ffmpeg_speed != '0':
                                            try:
                                                # Remove 'x' suffix and convert to float
                                                speed_value = float(ffmpeg_speed.rstrip('x'))
                                                stream_value_metrics.append(
                                                    f'dispatcharr_stream_buffering_speed{{{base_labels_str}}} {speed_value}'
                                                )
                                            except (ValueError, AttributeError):
                                                pass  # Invalid speed format
                                        
                                        if video_bitrate and video_bitrate != '0':
                                            video_bitrate_bps = float(video_bitrate) * 1000  # Convert kbps to bps
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_video_bitrate_bps{{{base_labels_str}}} {video_bitrate_bps}'
                                            )
                                        if ffmpeg_output_bitrate and ffmpeg_output_bitrate != '0':
                                            ffmpeg_output_bitrate_bps = float(ffmpeg_output_bitrate) * 1000  # Convert kbps to bps
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_transcode_bitrate_bps{{{base_labels_str}}} {ffmpeg_output_bitrate_bps}'
                                            )
                                        if avg_bitrate_bps > 0:
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_avg_bitrate_bps{{{base_labels_str}}} {avg_bitrate_bps}'
                                            )
                                        if current_bitrate_bps > 0:
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_current_bitrate_bps{{{base_labels_str}}} {current_bitrate_bps}'
                                            )
                                        
                                        # Transfer metrics
                                        if total_mb > 0:
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_total_transfer_mb{{{base_labels_str}}} {total_mb}'
                                            )
                                        
                                        # Profile connection metrics (scoped to this stream's context)
                                        if profile_id:
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_profile_connections{{{base_labels_str}}} {profile_connections}'
                                            )
                                            stream_value_metrics.append(
                                                f'dispatcharr_stream_profile_max_connections{{{base_labels_str}}} {profile_max}'
                                            )
                                        
                                        # Add metadata metric last (all identifying/enrichment information)
                                        stream_value_metrics.append(
                                            f'dispatcharr_stream_metadata{{{",".join(metadata_labels)}}} 1'
                                        )
                                        
                                        # Get current EPG program information if available
                                        if hasattr(channel, 'epg_data') and channel.epg_data:
                                            try:
                                                from apps.epg.models import ProgramData
                                                from django.utils import timezone as django_timezone
                                                
                                                # Get current time
                                                now = django_timezone.now()
                                                
                                                # Query for current program (where now is between start and end time)
                                                current_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    start_time__lte=now,
                                                    end_time__gte=now
                                                ).first()
                                                
                                                # Query for previous program (ended before now, get the most recent one)
                                                previous_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    end_time__lt=now
                                                ).order_by('-end_time').first()
                                                
                                                # Query for next program (starts after now, get the nearest one)
                                                next_program = ProgramData.objects.filter(
                                                    epg=channel.epg_data,
                                                    start_time__gt=now
                                                ).order_by('start_time').first()
                                                
                                                # Helper function to escape and format program data
                                                def format_program_data(program, prefix):
                                                    """Format program data into safe label strings"""
                                                    if not program:
                                                        return [
                                                            f'{prefix}_title=""',
                                                            f'{prefix}_subtitle=""',
                                                            f'{prefix}_description=""',
                                                            f'{prefix}_start_time=""',
                                                            f'{prefix}_end_time=""'
                                                        ]
                                                    
                                                    # Escape special characters in strings (order matters: backslash first, then quotes)
                                                    def escape_label_value(value):
                                                        """Escape special characters for Prometheus label values"""
                                                        if not value:
                                                            return ""
                                                        # Order is critical: escape backslashes first, then quotes, then newlines
                                                        return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

                                                    title = escape_label_value(program.title)
                                                    subtitle = escape_label_value(program.sub_title)
                                                    description = escape_label_value(program.description)
                                                    
                                                    # Format times as ISO strings
                                                    start_time = program.start_time.isoformat()
                                                    end_time = program.end_time.isoformat()
                                                    
                                                    return [
                                                        f'{prefix}_title="{title}"',
                                                        f'{prefix}_subtitle="{subtitle}"',
                                                        f'{prefix}_description="{description}"',
                                                        f'{prefix}_start_time="{start_time}"',
                                                        f'{prefix}_end_time="{end_time}"'
                                                    ]
                                                
                                                # Only add the metric if there's actual program data
                                                if previous_program or current_program or next_program:
                                                    # Build EPG program labels for all three programs
                                                    epg_labels = base_labels.copy()
                                                    epg_labels.extend(format_program_data(previous_program, 'previous'))
                                                    epg_labels.extend(format_program_data(current_program, 'current'))
                                                    epg_labels.extend(format_program_data(next_program, 'next'))
                                                    
                                                    # Calculate progress (how far into the current program we are, 0-1)
                                                    progress = 0.0
                                                    if current_program:
                                                        total_duration = (current_program.end_time - current_program.start_time).total_seconds()
                                                        elapsed = (now - current_program.start_time).total_seconds()
                                                        progress = min(1.0, max(0.0, elapsed / total_duration)) if total_duration > 0 else 0.0
                                                    
                                                    # Add program metric with progress as the value (0.0 if no current program)
                                                    stream_value_metrics.append(
                                                        f'dispatcharr_stream_programming{{{",".join(epg_labels)}}} {progress:.4f}'
                                                    )
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
                
                # Now collect VOD streams
                try:
                    from apps.vod.models import Movie, Episode
                    
                    pattern = "vod_persistent_connection:*"
                    for key in self.redis_client.scan_iter(match=pattern):
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if not connection_data:
                                continue
                            
                            # Handle both bytes and string keys
                            if isinstance(list(connection_data.keys())[0], bytes):
                                def get_vod_field(field_name, default=''):
                                    val = connection_data.get(field_name.encode('utf-8') if isinstance(field_name, str) else field_name, b'')
                                    return val.decode('utf-8') if isinstance(val, bytes) else default
                            else:
                                def get_vod_field(field_name, default=''):
                                    return connection_data.get(field_name, default)
                            
                            # Only process connections with active streams
                            active_stream_count = int(get_vod_field('active_streams', '0'))
                            if active_stream_count == 0:
                                continue
                            
                            active_streams += 1  # Add to total count
                            active_vod_streams += 1  # Add to VOD count
                            
                            # Extract VOD session information
                            session_id = key.decode('utf-8') if isinstance(key, bytes) else key
                            session_id = session_id.replace('vod_persistent_connection:', '')
                            
                            # Extract numeric channel_number from session_id (format: vod_TIMESTAMP_RANDOMNUM)
                            # Use the timestamp portion as a numeric identifier
                            try:
                                session_parts = session_id.split('_')
                                if len(session_parts) >= 2:
                                    vod_channel_number = session_parts[1]  # Extract timestamp
                                else:
                                    vod_channel_number = session_id  # Fallback to full session_id
                            except Exception:
                                vod_channel_number = session_id  # Fallback to full session_id
                            
                            content_type = get_vod_field('content_obj_type', 'unknown')
                            content_uuid = get_vod_field('content_uuid', '')
                            content_name = get_vod_field('content_name', 'Unknown')  # Will be overridden below
                            
                            # Get M3U profile information first (needed for category lookups)
                            m3u_profile_id_str = get_vod_field('m3u_profile_id', '')
                            
                            # Query actual content object for additional metadata (logo, video info, category, programming info, etc.)
                            logo_url = ""
                            video_codec = ""
                            resolution = ""
                            stream_profile_name = ""  # VOD doesn't store transcode profile in Redis
                            season_number = None
                            episode_number = None
                            series_name = None
                            channel_group = ""  # Default category
                            
                            # Programming information (for dispatcharr_stream_programming metric)
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
                                    
                                    # Get logo URL if available
                                    if hasattr(content_obj, 'logo') and content_obj.logo:
                                        logo_url = f"/api/vod/vodlogos/{content_obj.logo.id}/cache/"
                                        # Add base URL if provided
                                        base_url = settings.get('base_url', '').strip() if settings else ''
                                        if base_url:
                                            logo_url = f"{base_url.rstrip('/')}{logo_url}"
                                    
                                    # Try to get video metadata from custom_properties
                                    if content_obj.custom_properties:
                                        video_info = content_obj.custom_properties.get('video', {})
                                        if video_info:
                                            video_codec = video_info.get('codec_name', '')
                                            width = video_info.get('width')
                                            height = video_info.get('height')
                                            if width and height:
                                                resolution = f"{width}x{height}"
                                    
                                    # Override channel_name with just the movie name (not the Redis formatted version)
                                    content_name = content_obj.name
                                    
                                    # Get programming information from Movie model
                                    prog_title = content_obj.name  # Use raw name, will escape later
                                    prog_description = content_obj.description or ""
                                    prog_year = str(content_obj.year) if content_obj.year else ""
                                    prog_genre = content_obj.genre or ""
                                    prog_duration_secs = content_obj.duration_secs or 0
                                    
                                    # Strip year from title if present to avoid duplication
                                    # Movie names often contain the year like "Bohemian Rhapsody (2018)" or "Movie Name - 2018"
                                    if prog_year:
                                        # Try to strip patterns like " (2018)" or " - 2018" from the end
                                        year_patterns = [f" ({prog_year})", f" - {prog_year}", f" {prog_year}"]
                                        for pattern in year_patterns:
                                            if prog_title.endswith(pattern):
                                                prog_title = prog_title[:-len(pattern)].strip()
                                                break
                                    
                                    # Build subtitle: "Year - Genre"
                                    subtitle_parts = []
                                    if prog_year:
                                        subtitle_parts.append(prog_year)
                                    if prog_genre:
                                        subtitle_parts.append(prog_genre)
                                    prog_subtitle = " - ".join(subtitle_parts)
                                    
                                    # Get category from M3U relation (use provider from session if available)
                                    if m3u_profile_id_str:
                                        try:
                                            relation = M3UMovieRelation.objects.select_related('category').filter(
                                                movie=content_obj,
                                                m3u_account__profiles__id=int(m3u_profile_id_str)
                                            ).first()
                                            if relation and relation.category:
                                                channel_group = relation.category.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            pass  # M3U relation not found or invalid profile ID
                                
                                elif content_type == 'episode':
                                    from apps.vod.models import M3USeriesRelation
                                    content_obj = Episode.objects.select_related('series', 'series__logo').get(uuid=content_uuid)
                                    season_number = content_obj.season_number
                                    episode_number = content_obj.episode_number
                                    
                                    # Override channel_name with just the series name (not the Redis formatted version)
                                    if content_obj.series:
                                        content_name = content_obj.series.name
                                        series_name = content_obj.series.name.replace('"', '\\"').replace('\\', '\\\\')
                                    else:
                                        series_name = None
                                    
                                    # Get series logo if available
                                    if hasattr(content_obj.series, 'logo') and content_obj.series.logo:
                                        logo_url = f"/api/vod/vodlogos/{content_obj.series.logo.id}/cache/"
                                        # Add base URL if provided
                                        base_url = settings.get('base_url', '').strip() if settings else ''
                                        if base_url:
                                            logo_url = f"{base_url.rstrip('/')}{logo_url}"
                                    
                                    # Try to get video metadata from custom_properties
                                    if content_obj.custom_properties:
                                        video_info = content_obj.custom_properties.get('video', {})
                                        if video_info:
                                            video_codec = video_info.get('codec_name', 'unknown')
                                            width = video_info.get('width')
                                            height = video_info.get('height')
                                            if width and height:
                                                resolution = f"{width}x{height}"
                                    
                                    # Get programming information from Episode model
                                    prog_title = content_obj.series.name if content_obj.series else ""  # Series name as title
                                    prog_description = content_obj.description or ""
                                    prog_duration_secs = content_obj.duration_secs or 0
                                    
                                    # Build subtitle: Remove series name prefix from episode name to avoid duplication
                                    # Episode.name often contains "Series Name - S01E03 - Episode Title" or 
                                    # "Series Name (Year) - Series Name - S01E03 - Episode Title"
                                    # We need to strip both the series name with year AND without year
                                    prog_subtitle = content_obj.name
                                    if prog_title and prog_subtitle.startswith(prog_title):
                                        # Strip exact series name (with year) and the following " - " separator
                                        prog_subtitle = prog_subtitle[len(prog_title):].lstrip(' -')
                                    
                                    # Also try to strip the series name without year (common in episode names)
                                    # Extract series name without year suffix like " (2009)"
                                    series_name_no_year = prog_title
                                    if prog_title:
                                        import re
                                        # Match patterns like " (2009)" at the end
                                        match = re.search(r'\s*\(\d{4}\)$', prog_title)
                                        if match:
                                            series_name_no_year = prog_title[:match.start()].strip()
                                    
                                    # Strip series name without year if present
                                    if series_name_no_year and prog_subtitle.startswith(series_name_no_year):
                                        prog_subtitle = prog_subtitle[len(series_name_no_year):].lstrip(' -')
                                    
                                    # Log for debugging
                                    logger.debug(f"VOD Episode programming: title='{prog_title}', subtitle='{prog_subtitle}', duration={prog_duration_secs}")
                                    
                                    # Get category from series M3U relation (use provider from session if available)
                                    if m3u_profile_id_str and content_obj.series:
                                        try:
                                            relation = M3USeriesRelation.objects.select_related('category').filter(
                                                series=content_obj.series,
                                                m3u_account__profiles__id=int(m3u_profile_id_str)
                                            ).first()
                                            if relation and relation.category:
                                                channel_group = relation.category.name.replace('"', '\\"').replace('\\', '\\\\')
                                        except Exception:
                                            pass  # M3U relation not found or invalid profile ID
                            except (Movie.DoesNotExist, Episode.DoesNotExist):
                                logger.debug(f"VOD content {content_type} {content_uuid} not found in database")
                            except Exception as e:
                                logger.error(f"Error querying VOD content metadata for {content_uuid}: {e}", exc_info=True)
                            
                            # Escape content_name and logo_url for Prometheus labels
                            content_name = content_name.replace('"', '\\"').replace('\\', '\\\\')
                            logo_url = logo_url.replace('"', '\\"').replace('\\', '\\\\')
                            
                            # Get M3U profile information (already fetched above, now just use it)
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
                            
                            # Note: VOD doesn't store stream_profile_id (transcode profile) in Redis
                            # stream_profile_name remains empty unless VOD transcoding is implemented differently
                            
                            # Calculate uptime
                            created_at = float(get_vod_field('created_at', '0'))
                            uptime_seconds = int(time.time() - created_at) if created_at > 0 else 0
                            
                            # Get transfer statistics
                            bytes_sent = int(get_vod_field('bytes_sent', '0'))
                            total_mb = round(bytes_sent / 1024 / 1024, 2)
                            
                            # Calculate average bitrate
                            avg_bitrate_bps = round((bytes_sent * 8 / uptime_seconds), 2) if uptime_seconds > 0 else 0
                            
                            # VOD doesn't have real-time client tracking in the same way, but we know active_streams
                            active_clients = active_stream_count
                            
                            # Build minimal base labels for VOD (matching live TV pattern)
                            # Use full session_id as channel_uuid for uniqueness, numeric timestamp as channel_number
                            base_labels = [
                                f'type="vod"',
                                f'channel_uuid="{session_id}"',
                                f'channel_number="{vod_channel_number}"'
                            ]
                            base_labels_str = ",".join(base_labels)
                            
                            # Build metadata labels for VOD (matching live TV pattern)
                            metadata_labels = base_labels + [
                                f'content_uuid="{content_uuid}"',
                                f'channel_name="{content_name}"',
                                f'channel_group="{channel_group}"',
                                f'content_type="{content_type}"',  # Keep for filtering movies vs episodes
                                f'provider="{provider_name}"',
                                f'provider_type="{provider_type}"',
                                f'state="active"',  # VOD connections are always active if they exist
                                f'logo_url="{logo_url}"',
                                f'profile_id="{profile_id if profile_id else "none"}"',
                                f'profile_name="{profile_name}"',
                                f'stream_profile="{stream_profile_name}"',
                                f'video_codec="{video_codec}"',
                                f'resolution="{resolution}"'
                            ]
                            
                            # Add episode-specific labels if applicable
                            if content_type == 'episode' and season_number is not None and episode_number is not None:
                                metadata_labels.append(f'season_number="{season_number}"')
                                metadata_labels.append(f'episode_number="{episode_number}"')
                                if series_name:
                                    metadata_labels.append(f'series_name="{series_name}"')
                            
                            # Add stream ID metric (using session_id as the identifier)
                            stream_value_metrics.append(
                                f'dispatcharr_stream_id{{{base_labels_str}}} 0'  # VOD uses session_id in labels, value doesn't matter
                            )
                            
                            # Add metadata metric
                            stream_value_metrics.append(
                                f'dispatcharr_stream_metadata{{{",".join(metadata_labels)}}} 1'
                            )
                            
                            # Add uptime metric
                            stream_value_metrics.append(
                                f'dispatcharr_stream_uptime_seconds{{{base_labels_str}}} {uptime_seconds}'
                            )
                            
                            # Add active clients metric
                            stream_value_metrics.append(
                                f'dispatcharr_stream_active_clients{{{base_labels_str}}} {active_clients}'
                            )
                            
                            # Add bitrate metrics
                            if avg_bitrate_bps > 0:
                                stream_value_metrics.append(
                                    f'dispatcharr_stream_avg_bitrate_bps{{{base_labels_str}}} {avg_bitrate_bps}'
                                )
                            
                            # Add transfer metric
                            if total_mb > 0:
                                stream_value_metrics.append(
                                    f'dispatcharr_stream_total_transfer_mb{{{base_labels_str}}} {total_mb}'
                                )
                            
                            # Add profile connection metrics
                            if profile_id:
                                stream_value_metrics.append(
                                    f'dispatcharr_stream_profile_connections{{{base_labels_str}}} {profile_connections}'
                                )
                                stream_value_metrics.append(
                                    f'dispatcharr_stream_profile_max_connections{{{base_labels_str}}} {profile_max}'
                                )
                            
                            # Add programming metric (similar to live TV EPG data) if we have content info
                            logger.debug(f"VOD Programming check for {session_id}: prog_title='{prog_title}', prog_description='{prog_description[:50] if prog_description else ''}'")
                            if prog_title or prog_description:
                                try:
                                    from datetime import datetime, timezone, timedelta
                                    
                                    logger.debug(f"Entering programming metric generation for {session_id}")
                                    
                                    # Helper function to escape special characters (same as live TV)
                                    def escape_label_value(value):
                                        """Escape special characters for Prometheus label values"""
                                        if not value:
                                            return ""
                                        # Order is critical: escape backslashes first, then quotes, then newlines
                                        return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
                                    
                                    # Escape all programming strings
                                    prog_title_safe = escape_label_value(prog_title)
                                    prog_subtitle_safe = escape_label_value(prog_subtitle)
                                    prog_description_safe = escape_label_value(prog_description)
                                    
                                    logger.debug(f"Escaped label values - title: '{prog_title_safe[:30]}', subtitle: '{prog_subtitle_safe[:30]}'")
                                    
                                    # Calculate start and end times based on VOD connection
                                    # Start time = when connection was created
                                    # End time = start + duration (estimated completion)
                                    prog_start_time = ""
                                    prog_end_time = ""
                                    if created_at > 0:
                                        start_dt = datetime.fromtimestamp(created_at, tz=timezone.utc)
                                        prog_start_time = start_dt.isoformat()
                                        
                                        # Calculate estimated end time if we have duration
                                        if prog_duration_secs > 0:
                                            end_dt = start_dt + timedelta(seconds=prog_duration_secs)
                                            prog_end_time = end_dt.isoformat()
                                    
                                    logger.debug(f"Times calculated - start: '{prog_start_time}', end: '{prog_end_time}', duration: {prog_duration_secs}")
                                    
                                    # Build programming labels (reusing live TV field names)
                                    # Leave previous_* and next_* empty (could be used for previous/next episodes in future)
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
                                        'next_end_time=""'
                                    ]
                                    
                                    # Calculate progress (0.0 to 1.0)
                                    # Use time-based progress if we have duration, otherwise 0.0
                                    progress = 0.0
                                    if prog_duration_secs > 0 and uptime_seconds > 0:
                                        progress = min(1.0, max(0.0, uptime_seconds / prog_duration_secs))
                                    
                                    logger.debug(f"Progress calculated: {progress:.4f} (uptime: {uptime_seconds}, duration: {prog_duration_secs})")
                                    
                                    # Add programming metric with progress as the value
                                    programming_metric = f'dispatcharr_stream_programming{{{",".join(programming_labels)}}} {progress:.4f}'
                                    logger.debug(f"Programming metric generated, length: {len(programming_metric)}, first 200 chars: {programming_metric[:200]}")
                                    stream_value_metrics.append(programming_metric)
                                    logger.debug(f"Programming metric appended successfully for {session_id}")
                                except Exception as prog_e:
                                    logger.error(f"Error generating programming metric for {session_id}: {prog_e}", exc_info=True)
                        
                        except Exception as e:
                            logger.debug(f"Error processing VOD connection key {key}: {e}")
                
                except Exception as e:
                    logger.debug(f"Error scanning VOD connection keys: {e}")
                
                # Add total count (live + VOD)
                metrics.append(f"dispatcharr_active_streams {active_streams}")
                
                # Add active streams by type
                metrics.append(f'dispatcharr_active_streams{{type="live"}} {active_live_streams}')
                metrics.append(f'dispatcharr_active_streams{{type="vod"}} {active_vod_streams}')
                
                # Add stream info metrics (static labels)
                for metric in stream_info_metrics:
                    metrics.append(metric)
                
                # Add stream value metrics (dynamic gauges)
                for metric in stream_value_metrics:
                    metrics.append(metric)
                    
        except Exception as e:
            logger.error(f"Error collecting stream metrics: {e}")
        
        metrics.append("")
        return metrics
    
    def _collect_epg_metrics(self, settings: dict = None) -> list:
        """Collect EPG source statistics"""
        from apps.epg.models import EPGSource
        
        metrics = []
        include_urls = settings and settings.get('include_source_urls', False)
        
        try:
            # Total EPG sources (exclude dummy)
            total_sources = EPGSource.objects.exclude(source_type='dummy').count()
            active_sources = EPGSource.objects.filter(is_active=True).exclude(source_type='dummy').count()
            
            metrics.append("# HELP dispatcharr_epg_sources Total number of EPG sources")
            metrics.append("# TYPE dispatcharr_epg_sources gauge")
            metrics.append(f'dispatcharr_epg_sources{{status="total"}} {total_sources}')
            metrics.append(f'dispatcharr_epg_sources{{status="active"}} {active_sources}')
            
            # EPG source status breakdown
            metrics.append("# HELP dispatcharr_epg_source_status EPG source status breakdown")
            metrics.append("# TYPE dispatcharr_epg_source_status gauge")
            
            for status_choice in EPGSource.STATUS_CHOICES:
                status_value = status_choice[0]
                count = EPGSource.objects.filter(status=status_value).exclude(source_type='dummy').count()
                metrics.append(f'dispatcharr_epg_source_status{{status="{status_value}"}} {count}')
            
            # Individual EPG source info (exclude dummy)
            include_legacy = settings and settings.get('include_legacy_metrics', False)
            
            if include_legacy:
                metrics.append("# HELP dispatcharr_epg_source_info Information about each EPG source (legacy format with priority as label)")
                metrics.append("# TYPE dispatcharr_epg_source_info gauge")
            
            metrics.append("# HELP dispatcharr_epg_source_priority Priority value for EPG source (lower is higher priority)")
            metrics.append("# TYPE dispatcharr_epg_source_priority gauge")
            
            for source in EPGSource.objects.exclude(source_type='dummy'):
                source_name = source.name.replace('"', '\\"').replace('\\', '\\\\')
                source_type = source.source_type or 'unknown'
                status = source.status
                is_active = str(source.is_active).lower()
                priority = source.priority
                
                # Base labels for identification
                base_labels = [
                    f'source_id="{source.id}"',
                    f'source_name="{source_name}"',
                    f'source_type="{source_type}"',
                    f'status="{status}"',
                    f'is_active="{is_active}"'
                ]
                
                # Legacy format - Build labels with priority included
                legacy_labels = base_labels.copy()
                legacy_labels.append(f'priority="{priority}"')
                
                # Optionally add source URL
                if include_urls and source.url:
                    source_url = source.url.replace('"', '\\"').replace('\\', '\\\\')
                    legacy_labels.append(f'url="{source_url}"')
                    base_labels.append(f'url="{source_url}"')
                
                # Legacy format (only if enabled)
                if include_legacy:
                    metrics.append(f'dispatcharr_epg_source_info{{{",".join(legacy_labels)}}} 1')
                
                # Add separate gauge for priority (proper time series)
                metrics.append(f'dispatcharr_epg_source_priority{{{",".join(base_labels)}}} {priority}')
        
        except Exception as e:
            logger.error(f"Error collecting EPG metrics: {e}")
        
        metrics.append("")
        return metrics

    def _collect_client_metrics(self) -> list:
        """Collect individual client connection metrics"""
        metrics = []
        
        try:
            from apps.channels.models import Channel
            
            # Client metrics headers
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
            
            # Scan for all active stream channels
            cursor = 0
            current_time = time.time()
            total_clients = 0
            client_metrics = []
            
            while True:
                cursor, keys = self.redis_client.scan(
                    cursor, 
                    match="ts_proxy:channel:*:clients",
                    count=100
                )
                
                for client_set_key in keys:
                    try:
                        # Extract channel UUID from key: ts_proxy:channel:{uuid}:clients
                        parts = client_set_key.decode('utf-8') if isinstance(client_set_key, bytes) else client_set_key
                        parts = parts.split(':')
                        if len(parts) < 4:
                            continue
                        
                        channel_uuid = parts[2]
                        
                        # Get channel details
                        try:
                            channel = Channel.objects.get(uuid=channel_uuid)
                            channel_number = getattr(channel, 'channel_number', 'N/A')
                        except Channel.DoesNotExist:
                            continue
                        
                        # Get all client IDs for this channel
                        client_ids = self.redis_client.smembers(client_set_key)
                        total_clients += len(client_ids)
                        
                        for client_id_bytes in client_ids:
                            try:
                                client_id = client_id_bytes.decode('utf-8') if isinstance(client_id_bytes, bytes) else client_id_bytes
                                
                                # Get client metadata from Redis
                                client_key = f"ts_proxy:channel:{channel_uuid}:clients:{client_id}"
                                client_data = self.redis_client.hgetall(client_key)
                                
                                if not client_data:
                                    continue
                                
                                # Helper to decode Redis values
                                def get_client_field(field, default='unknown'):
                                    val = client_data.get(field.encode('utf-8') if isinstance(field, str) else field, default.encode('utf-8'))
                                    return val.decode('utf-8') if isinstance(val, bytes) else str(default)
                                
                                # Extract client information
                                ip_address = get_client_field('ip_address', 'unknown')
                                user_agent = get_client_field('user_agent', 'unknown')
                                worker_id = get_client_field('worker_id', 'unknown')
                                
                                # Escape special characters for Prometheus labels
                                ip_address_safe = ip_address.replace('"', '\\"').replace('\\', '\\\\')
                                user_agent_safe = user_agent.replace('"', '\\"').replace('\\', '\\\\').replace('\n', ' ').replace('\r', '')
                                client_id_safe = client_id.replace('"', '\\"').replace('\\', '\\\\')
                                worker_id_safe = worker_id.replace('"', '\\"').replace('\\', '\\\\')
                                
                                # Calculate connection duration
                                connection_duration = 0
                                connected_at_str = get_client_field('connected_at', '0')
                                try:
                                    connected_at = float(connected_at_str)
                                    connection_duration = int(current_time - connected_at)
                                except (ValueError, TypeError):
                                    pass  # Invalid timestamp format
                                
                                # Get transfer statistics
                                bytes_sent = 0
                                bytes_sent_str = get_client_field('bytes_sent', '0')
                                try:
                                    bytes_sent = int(bytes_sent_str)
                                except (ValueError, TypeError):
                                    pass  # Invalid bytes_sent value
                                
                                avg_rate_bps = 0.0
                                avg_rate_str = get_client_field('avg_rate_KBps', '0')
                                try:
                                    # Field name suggests KB/s but currently contains bytes/s
                                    # Auto-detect: if value > 50000, assume bytes/s; otherwise KB/s
                                    # Typical streaming: 1-50 Mbps = 125,000-6,250,000 bytes/s or 125-6,250 KB/s
                                    avg_rate_value = float(avg_rate_str)
                                    if avg_rate_value > 50000:
                                        # Likely bytes/s: convert to bps
                                        avg_rate_bps = avg_rate_value * 8
                                    else:
                                        # Likely KB/s: convert to bps
                                        avg_rate_bps = avg_rate_value * 8000
                                except (ValueError, TypeError):
                                    pass  # Invalid rate value
                                
                                current_rate_bps = 0.0
                                current_rate_str = get_client_field('current_rate_KBps', '0')
                                try:
                                    # Field name suggests KB/s but currently contains bytes/s
                                    # Auto-detect: if value > 50000, assume bytes/s; otherwise KB/s
                                    # Typical streaming: 1-50 Mbps = 125,000-6,250,000 bytes/s or 125-6,250 KB/s
                                    current_rate_value = float(current_rate_str)
                                    if current_rate_value > 50000:
                                        # Likely bytes/s: convert to bps
                                        current_rate_bps = current_rate_value * 8
                                    else:
                                        # Likely KB/s: convert to bps
                                        current_rate_bps = current_rate_value * 8000
                                except (ValueError, TypeError):
                                    pass  # Invalid rate value
                                
                                # Minimal labels for joining
                                base_labels = [
                                    f'type="live"',
                                    f'client_id="{client_id_safe}"',
                                    f'channel_uuid="{channel_uuid}"',
                                    f'channel_number="{channel_number}"'
                                ]
                                base_labels_str = ','.join(base_labels)
                                
                                # Info metric with all metadata
                                info_labels = base_labels + [
                                    f'ip_address="{ip_address_safe}"',
                                    f'user_agent="{user_agent_safe}"',
                                    f'worker_id="{worker_id_safe}"'
                                ]
                                client_metrics.append(f'dispatcharr_client_info{{{",".join(info_labels)}}} 1')
                                
                                # Value metrics with minimal labels
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
            
            # Now collect VOD clients
            try:
                # VOD clients are the active_streams on each VOD connection
                pattern = "vod_persistent_connection:*"
                cursor = 0
                
                while True:
                    cursor, keys = self.redis_client.scan(
                        cursor,
                        match=pattern,
                        count=100
                    )
                    
                    for key in keys:
                        try:
                            connection_data = self.redis_client.hgetall(key)
                            if not connection_data:
                                continue
                            
                            # Handle both bytes and string keys
                            if isinstance(list(connection_data.keys())[0], bytes):
                                def get_vod_field(field_name, default=''):
                                    val = connection_data.get(field_name.encode('utf-8') if isinstance(field_name, str) else field_name, b'')
                                    return val.decode('utf-8') if isinstance(val, bytes) else default
                            else:
                                def get_vod_field(field_name, default=''):
                                    return connection_data.get(field_name, default)
                            
                            # Get active streams count (represents multiple HTTP connections from same client)
                            active_stream_count = int(get_vod_field('active_streams', '0'))
                            if active_stream_count == 0:
                                continue
                            
                            # Each VOD session counts as one client (even if multiple active_streams)
                            total_clients += 1
                            
                            # Extract session information
                            session_id = key.decode('utf-8') if isinstance(key, bytes) else key
                            session_id = session_id.replace('vod_persistent_connection:', '')
                            
                            # Extract numeric channel_number from session_id (format: vod_TIMESTAMP_RANDOMNUM)
                            # Use the timestamp portion as a numeric identifier (matching stream metrics)
                            try:
                                session_parts = session_id.split('_')
                                if len(session_parts) >= 2:
                                    vod_channel_number = session_parts[1]  # Extract timestamp
                                else:
                                    vod_channel_number = session_id  # Fallback to full session_id
                            except Exception:
                                vod_channel_number = session_id  # Fallback to full session_id
                            
                            content_type = get_vod_field('content_obj_type', 'unknown')
                            content_uuid = get_vod_field('content_uuid', '')
                            content_name = get_vod_field('content_name', 'Unknown')
                            client_ip = get_vod_field('client_ip', 'unknown')
                            client_user_agent = get_vod_field('client_user_agent', 'unknown')
                            worker_id = get_vod_field('worker_id', 'unknown')
                            
                            # Escape special characters
                            session_id_safe = session_id.replace('"', '\\"').replace('\\', '\\\\')
                            vod_channel_number_safe = vod_channel_number.replace('"', '\\"').replace('\\', '\\\\')
                            content_name_safe = content_name.replace('"', '\\"').replace('\\', '\\\\')
                            client_ip_safe = client_ip.replace('"', '\\"').replace('\\', '\\\\')
                            client_user_agent_safe = client_user_agent.replace('"', '\\"').replace('\\', '\\\\').replace('\n', ' ').replace('\r', '')
                            worker_id_safe = worker_id.replace('"', '\\"').replace('\\', '\\\\')
                            
                            # Calculate connection duration
                            connection_duration = 0
                            created_at = float(get_vod_field('created_at', '0'))
                            if created_at > 0:
                                connection_duration = int(current_time - created_at)
                            
                            # Get transfer statistics
                            bytes_sent = int(get_vod_field('bytes_sent', '0'))
                            
                            # Calculate bitrates
                            avg_rate_bps = 0.0
                            if connection_duration > 0 and bytes_sent > 0:
                                avg_rate_bps = round((bytes_sent * 8 / connection_duration), 2)
                            
                            # Create single client metric for this VOD session
                            # (active_streams represents multiple HTTP requests from same user, not multiple users)
                            client_id_safe = session_id_safe
                            
                            # Minimal labels for joining (matching live TV pattern)
                            base_labels = [
                                f'type="vod"',
                                f'client_id="{client_id_safe}"',
                                f'channel_uuid="{session_id_safe}"',
                                f'channel_number="{vod_channel_number_safe}"'
                            ]
                            base_labels_str = ','.join(base_labels)
                            
                            # Info metric with all metadata
                            info_labels = base_labels + [
                                f'content_uuid="{content_uuid}"',
                                f'channel_name="{content_name_safe}"',
                                f'content_type="{content_type}"',
                                f'ip_address="{client_ip_safe}"',
                                f'user_agent="{client_user_agent_safe}"',
                                f'worker_id="{worker_id_safe}"'
                            ]
                            client_metrics.append(f'dispatcharr_client_info{{{",".join(info_labels)}}} 1')
                            
                            # Value metrics with minimal labels
                            if connection_duration > 0:
                                client_metrics.append(f'dispatcharr_client_connection_duration_seconds{{{base_labels_str}}} {connection_duration}')
                            
                            if bytes_sent > 0:
                                client_metrics.append(f'dispatcharr_client_bytes_sent{{{base_labels_str}}} {bytes_sent}')
                            
                            if avg_rate_bps > 0:
                                client_metrics.append(f'dispatcharr_client_avg_transfer_rate_bps{{{base_labels_str}}} {avg_rate_bps:.2f}')
                                # For VOD, use average rate as current rate (VOD bitrate is typically stable)
                                client_metrics.append(f'dispatcharr_client_current_transfer_rate_bps{{{base_labels_str}}} {avg_rate_bps:.2f}')
                        
                        except Exception as e:
                            logger.debug(f"Error processing VOD connection for clients: {e}")
                    
                    if cursor == 0:
                        break
            
            except Exception as e:
                logger.debug(f"Error scanning VOD connections for clients: {e}")
            
            # Total count (live + VOD), then individual metrics
            metrics.append(f"dispatcharr_active_clients {total_clients}")
            metrics.extend(client_metrics)
            
        except Exception as e:
            logger.error(f"Error collecting client metrics: {e}")
        
        metrics.append("")
        return metrics


class MetricsServer:
    """Lightweight HTTP server to expose Prometheus metrics using gevent"""

    def __init__(self, collector, port=None, host=None):
        self.collector = collector
        self.port = port if port is not None else PLUGIN_CONFIG["default_port"]
        
        # Normalize and validate host parameter
        # Handle None, empty string, or whitespace-only strings
        if host is None or (isinstance(host, str) and not host.strip()):
            self.host = PLUGIN_CONFIG["default_host"]
        else:
            self.host = host.strip() if isinstance(host, str) else str(host)
        
        # Log what we're actually using
        logger.info(f"MetricsServer initialized with host='{self.host}' (type: {type(self.host).__name__}), port={self.port}")
        
        self.server_thread = None
        self.server = None
        self.running = False
        self.settings = {}

    @staticmethod
    def _get_dispatcharr_version():
        """Get Dispatcharr version using the same logic as the dispatcharr_info metric.
        Returns tuple of (version, timestamp, full_version)"""
        dispatcharr_version = "unknown"
        dispatcharr_timestamp = None

        try:
            # Try importing version module (add /app to path if needed)
            import sys
            if '/app' not in sys.path:
                sys.path.insert(0, '/app')
            import version
            dispatcharr_version = getattr(version, '__version__', 'unknown')
            dispatcharr_timestamp = getattr(version, '__timestamp__', None)
        except Exception:
            try:
                # Try reading from file directly
                with open('/app/version.py', 'r') as f:
                    content = f.read()
                    import re
                    version_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if version_match:
                        dispatcharr_version = version_match.group(1)
                    timestamp_match = re.search(r"__timestamp__\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if timestamp_match:
                        dispatcharr_timestamp = timestamp_match.group(1)
            except Exception:
                pass  # Failed to read or parse version file

        # Format version with timestamp if available (dev builds)
        full_version = dispatcharr_version
        if dispatcharr_timestamp:
            full_version = f"v{dispatcharr_version}-{dispatcharr_timestamp}"

        return dispatcharr_version, dispatcharr_timestamp, full_version

    @staticmethod
    def _compare_versions(current, minimum):
        """Compare semantic versions. Returns True if current >= minimum."""
        try:
            # Strip 'v' prefix if present
            current = current.lstrip('v')
            minimum = minimum.lstrip('v')

            # Split versions into parts
            current_parts = [int(x) for x in current.split('.')]
            minimum_parts = [int(x) for x in minimum.split('.')]

            # Pad shorter version with zeros
            while len(current_parts) < len(minimum_parts):
                current_parts.append(0)
            while len(minimum_parts) < len(current_parts):
                minimum_parts.append(0)

            # Compare
            for c, m in zip(current_parts, minimum_parts):
                if c > m:
                    return True
                elif c < m:
                    return False

            # Equal
            return True
        except (ValueError, AttributeError):
            # If we can't parse versions, assume it's okay
            return True
        
    def _verify_stopped(self, timeout=3):
        """Verify the server port is actually free after stopping.
        Returns True if port is confirmed free, False otherwise."""
        import socket
        import time
        
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(0.5)
                sock.bind((self.host, self.port))
                sock.close()
                logger.info(f"Verified port {self.port} is free after server stop")
                return True
            except OSError:
                sock.close()
                time.sleep(0.2)
        
        logger.warning(f"Port {self.port} still in use after {timeout}s — server may not have stopped cleanly")
        return False

    def wsgi_app(self, environ, start_response):
        """WSGI application for serving metrics"""
        path = environ.get('PATH_INFO', '/')
        
        if path == '/metrics':
            try:
                metrics_text = self.collector.collect_metrics(settings=self.settings)
                status = '200 OK'
                headers = [('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')]
                start_response(status, headers)
                return [metrics_text.encode('utf-8')]
            except Exception as e:
                logger.error(f"Error generating metrics: {e}", exc_info=True)
                status = '500 Internal Server Error'
                headers = [('Content-Type', 'text/plain')]
                start_response(status, headers)
                return [f"# Error: {str(e)}\n".encode('utf-8')]
        
        elif path == '/health':
            status = '200 OK'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
            return [b"OK\n"]
        
        elif path == '/':
            status = '200 OK'
            headers = [('Content-Type', 'text/html; charset=utf-8')]
            start_response(status, headers)
            
            # Get plugin info from config
            plugin_name = PLUGIN_CONFIG.get('name', 'Dispatcharr Exporter')
            plugin_version = PLUGIN_CONFIG.get('version', 'unknown version').lstrip('-')
            plugin_description = PLUGIN_CONFIG.get('description', 'This exporter provides Prometheus metrics for Dispatcharr.')
            repo_url = PLUGIN_CONFIG.get('repo_url', 'https://github.com/sethwv/dispatcharr-exporter')
            releases_url = f"{repo_url}/releases"
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{plugin_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            margin-top: 0;
            color: #333;
        }}
        .version {{
            color: #999;
            font-size: 14px;
            margin-top: -10px;
            margin-bottom: 20px;
        }}
        p {{
            color: #666;
            line-height: 1.6;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .links {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
        .links a {{
            display: inline-block;
            margin-right: 20px;
            font-weight: 500;
        }}
        .external-links {{
            margin-top: 20px;
            font-size: 14px;
        }}
        .external-links a {{
            margin-right: 15px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{plugin_name}</h1>
        <div class="version">{plugin_version}</div>
        <p>{plugin_description.split('. ')[0]}.</p>
        <div class="external-links">
            <a href="{repo_url}" target="_blank">GitHub Repository</a>
            <a href="{releases_url}" target="_blank">Releases</a>
        </div>
        <div class="links">
            <a href="/metrics">View Metrics</a>
            <a href="/health">Health Check</a>
        </div>
    </div>
</body>
</html>"""
            return [html.encode('utf-8')]
        
        else:
            status = '404 Not Found'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
            return [b"Not Found\n"]
    
    def start(self, settings=None):
        """Start the metrics server in a background thread"""
        global _metrics_server
        
        if self.running:
            logger.warning("Metrics server is already running")
            return False
        
        # Check if another instance is running via Redis
        try:
            from core.utils import RedisClient
            redis_client = RedisClient.get_client()
            running_flag = redis_client.get("prometheus_exporter:server_running") if redis_client else None
            if running_flag == "1" or running_flag == b"1":
                logger.warning("Another metrics server instance is already running (detected via Redis)")
                return False
        except Exception as e:
            logger.debug(f"Could not check Redis for running server: {e}")
        
        # Check if another instance is running in this process
        if _metrics_server and _metrics_server.is_running():
            logger.warning("Another metrics server instance is already running")
            return False
        
        # Check Dispatcharr version meets minimum requirement
        min_version = PLUGIN_CONFIG.get("min_dispatcharr_version", "1.0.0")
        try:
            # Get Dispatcharr version using the same logic as dispatcharr_info metric
            dispatcharr_version, dispatcharr_timestamp, full_version = self._get_dispatcharr_version()

            # Check version requirement (skip dev builds with timestamp suffix)
            if dispatcharr_version != "unknown":
                # If timestamp exists, this is a dev build - skip version check
                if dispatcharr_timestamp:
                    logger.info(f"Dev build detected ({full_version}), skipping version check")
                elif not self._compare_versions(dispatcharr_version, min_version):
                    logger.error(f"Dispatcharr {dispatcharr_version} does not meet minimum requirement {min_version}")
                    return False
                else:
                    logger.info(f"Dispatcharr {dispatcharr_version} meets minimum requirement {min_version}")
            else:
                logger.warning("Could not determine Dispatcharr version, skipping check")
        except Exception as e:
            logger.warning(f"Could not verify Dispatcharr version: {e}. Proceeding anyway.")
        
        # Check if port is already in use and host is valid
        import socket
        
        # Log exactly what we're trying to bind to
        logger.info(f"Attempting to bind to host='{self.host}' (type: {type(self.host).__name__}, repr: {repr(self.host)}), port={self.port}")
        
        try:
            # First, validate that the host address can be resolved
            try:
                socket.getaddrinfo(self.host, self.port, socket.AF_INET, socket.SOCK_STREAM)
            except socket.gaierror as e:
                logger.error(f"Cannot resolve host '{self.host}': {e}. In Docker, use '0.0.0.0' to bind to all interfaces.")
                return False
            
            # Now check if we can bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.close()
            logger.debug(f"Successfully verified we can bind to {self.host}:{self.port}")
        except OSError as e:
            if e.errno == -2 or 'Name or service not known' in str(e):
                logger.error(f"Cannot resolve host '{self.host}' (repr: {repr(self.host)}): {e}. In Docker, use '0.0.0.0' to bind to all interfaces.")
            else:
                logger.error(f"Cannot bind to {self.host}:{self.port}: {e}")
            return False
        
        self.settings = settings or {}
        
        try:
            from gevent import pywsgi
            
            def run_server():
                try:
                    logger.debug(f"Starting gevent WSGI server on {self.host}:{self.port}")
                    
                    # Check if access logs should be suppressed
                    suppress_logs = self.settings.get('suppress_access_logs', True)
                    server_kwargs = {
                        'listener': (self.host, self.port),
                        'application': self.wsgi_app
                    }
                    if suppress_logs:
                        # Suppress access logs by passing log=None
                        server_kwargs['log'] = None
                    
                    self.server = pywsgi.WSGIServer(**server_kwargs)
                    # Mark as running only after successful bind
                    self.running = True
                    
                    # Set Redis flag so all workers know server is running
                    try:
                        from core.utils import RedisClient
                        redis_client = RedisClient.get_client()
                        if redis_client:
                            redis_client.set("prometheus_exporter:server_running", "1")
                            redis_client.set("prometheus_exporter:server_host", self.host)
                            redis_client.set("prometheus_exporter:server_port", str(self.port))
                    except Exception as e:
                        logger.warning(f"Could not set Redis flag: {e}")
                    
                    logger.info(f"Metrics server started on http://{self.host}:{self.port}/metrics")
                    
                    # Start the server in a separate greenlet so we can monitor for stop signals
                    from gevent import spawn, sleep
                    spawn(self.server.serve_forever)
                    
                    # Monitor for stop signal via Redis
                    # Get Redis client once for the monitor loop
                    try:
                        from core.utils import RedisClient
                        monitor_redis = RedisClient.get_client()
                        logger.debug("Stop signal monitor started with Redis client")
                    except Exception as e:
                        logger.error(f"Could not get Redis client for stop signal monitoring: {e}")
                        monitor_redis = None
                    
                    check_count = 0
                    while self.running:
                        try:
                            if monitor_redis:
                                stop_flag = monitor_redis.get("prometheus_exporter:stop_requested")
                                if stop_flag == "1" or stop_flag == b"1":
                                    logger.info("Stop signal detected via Redis, shutting down metrics server")
                                    self.running = False
                                    try:
                                        self.server.stop(timeout=5)
                                    except Exception as e:
                                        logger.warning(f"Error during server.stop(): {e}")
                                    self._verify_stopped(timeout=3)
                                    break
                            else:
                                # Try to re-acquire Redis client
                                try:
                                    from core.utils import RedisClient
                                    monitor_redis = RedisClient.get_client()
                                    if monitor_redis:
                                        logger.info("Re-acquired Redis client for stop signal monitoring")
                                except Exception:
                                    pass
                            
                            check_count += 1
                            # Log heartbeat every 60 seconds to confirm monitor is alive
                            if check_count % 60 == 0:
                                logger.debug(f"Stop signal monitor alive (check #{check_count}), server running on {self.host}:{self.port}")
                        except Exception as e:
                            logger.warning(f"Error checking stop signal (check #{check_count}): {e}")
                            # Try to re-acquire Redis client on error
                            try:
                                from core.utils import RedisClient
                                monitor_redis = RedisClient.get_client()
                            except Exception:
                                monitor_redis = None
                        
                        sleep(1)  # Check every second
                    
                    # Clean up Redis flags and lock file after actually stopping
                    try:
                        from core.utils import RedisClient
                        redis_client = RedisClient.get_client()
                        if redis_client:
                            redis_client.delete("prometheus_exporter:server_running")
                            redis_client.delete("prometheus_exporter:server_host")
                            redis_client.delete("prometheus_exporter:server_port")
                            redis_client.delete("prometheus_exporter:stop_requested")
                    except Exception as e:
                        logger.warning(f"Could not clear Redis flags on shutdown: {e}")
                    
                    # Remove lock file
                    try:
                        import os
                        lock_file = "/tmp/prometheus_exporter_autostart.lock"
                        if os.path.exists(lock_file):
                            os.remove(lock_file)
                            logger.debug("Removed auto-start lock file")
                    except Exception as e:
                        logger.debug(f"Could not remove lock file on shutdown: {e}")
                    
                    logger.info("Metrics server stopped and cleaned up")
                    
                except Exception as e:
                    logger.error(f"Error running metrics server: {e}", exc_info=True)
                    self.running = False
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Give it a moment to bind and set running=True
            import time
            time.sleep(0.5)
            
            if self.running:
                _metrics_server = self
                return True
            else:
                return False
            
        except ImportError:
            logger.error("gevent is not installed")
            return False
    
    def stop(self):
        """Stop the metrics server"""
        global _metrics_server
        
        if not self.running:
            return False
        
        logger.info("Stopping metrics server...")
        
        if self.server:
            try:
                self.server.stop(timeout=5)
            except Exception as e:
                logger.warning(f"Error during server.stop(): {e}")
            self._verify_stopped(timeout=3)
        
        self.running = False
        _metrics_server = None
        
        # Clear Redis flags
        try:
            from core.utils import RedisClient
            redis_client = RedisClient.get_client()
            if redis_client:
                redis_client.delete("prometheus_exporter:server_running")
                redis_client.delete("prometheus_exporter:server_host")
                redis_client.delete("prometheus_exporter:server_port")
        except Exception as e:
            logger.warning(f"Could not clear Redis flags: {e}")
        
        # Clean up lock file
        try:
            import os
            lock_file = "/tmp/prometheus_exporter_autostart.lock"
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception as e:
            logger.debug(f"Error removing lock file: {e}")
        
        return True
    
    def is_running(self):
        """Check if server is running"""
        return self.running and self.server_thread and self.server_thread.is_alive()


class Plugin:
    """Dispatcharr Plugin for Prometheus metrics export using gevent"""
    
    name = PLUGIN_CONFIG["name"]
    description = PLUGIN_CONFIG["description"]
    version = PLUGIN_CONFIG["version"]
    author = PLUGIN_CONFIG["author"]
    
    fields = [
        {
            "id": "auto_start",
            "label": "Auto-Start Metrics Server",
            "type": "boolean",
            "default": PLUGIN_CONFIG["auto_start_default"],
            "description": "Automatically start the metrics server when plugin loads (recommended)"
        },
        {
            "id": "suppress_access_logs",
            "label": "Suppress Access Logs",
            "type": "boolean",
            "default": True,
            "description": "Suppress HTTP access logs for /metrics requests"
        },
        {
            "id": "port",
            "label": "Metrics Server Port",
            "type": "number",
            "default": PLUGIN_CONFIG["default_port"],
            "description": "Port for the metrics HTTP server",
            "placeholder": "9192"
        },
        {
            "id": "host",
            "label": "Metrics Server Host",
            "type": "string",
            "default": PLUGIN_CONFIG["default_host"],
            "description": "Host address to bind to (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only)",
            "placeholder": "0.0.0.0"
        },
        {
            "id": "base_url",
            "label": "Dispatcharr Base URL (Optional)",
            "type": "string",
            "default": "",
            "description": "URL for Dispatcharr API (e.g., http://localhost:5656 or https://dispatcharr.example.com). If set, logo URLs will be absolute instead of relative paths. Leave empty to use relative paths.",
            "placeholder": "http://localhost:5656"
        },
        {
            "id": "include_m3u_stats",
            "label": "Include M3U Account Statistics",
            "type": "boolean",
            "default": True,
            "description": "Include M3U account and profile metrics in the output"
        },
        {
            "id": "include_epg_stats",
            "label": "Include EPG Source Statistics",
            "type": "boolean",
            "default": False,
            "description": "Include EPG source and status metrics in the output"
        },
        {
            "id": "include_client_stats",
            "label": "Include Client Connection Statistics",
            "type": "boolean",
            "default": False,
            "description": "Include individual client connection information"
        },
        {
            "id": "include_source_urls",
            "label": "Include Provider/Source Information",
            "type": "boolean",
            "default": False,
            "description": "Include server URLs & XC usernames in M3U account and EPG source metrics. Ensure this is DISABLED if sharing output in Discord for troubleshooting"
        },
        {
            "id": "include_legacy_metrics",
            "label": "Include Legacy Metric Formats (Deprecated)",
            "type": "boolean",
            "default": False,
            "description": "Include backward-compatible metrics with dynamic values as labels (e.g., dispatcharr_stream_info with all stats as labels). This format was used in v1.1.0 and earlier. NOT recommended - use the new separate gauge metrics instead for proper time series. Only enable if you have existing dashboards that need migration time"
        }
    ]

    actions = [
        {
            "id": "start_server",
            "label": "Start Metrics Server",
            "description": "Start the HTTP metrics server",
            "button_label": "Start Server",
            "button_variant": "primary",
            "button_color": "green"
        },
        {
            "id": "stop_server",
            "label": "Stop Metrics Server",
            "description": "Stop the HTTP metrics server",
            "button_label": "Stop Server",
            "button_variant": "danger",
            "button_color": "red"
        },
        {
            "id": "restart_server",
            "label": "Restart Metrics Server",
            "description": "Restart the HTTP metrics server",
            "button_label": "Restart Server",
            "button_variant": "primary",
            "button_color": "orange"
        },
        {
            "id": "server_status",
            "label": "Server Status",
            "description": "Check if the metrics server is running and get endpoint URL",
            "button_label": "Check Status",
            "button_variant": "secondary",
            "button_color": "blue"
        },
        {
            "id": "check_for_updates",
            "label": "Check for Updates",
            "description": "Check if a new version is available",
            "button_label": "Check Updates",
            "button_variant": "secondary",
            "button_color": "gray"
        }
    ]

    def _cleanup_root_pycache(self):
        """Detect root-owned __pycache__ directories in this plugin's directory"""
        try:
            import stat
            
            # Check if we're running in a container as non-root user
            if os.getuid() != 0:
                # Find this plugin's directory
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                
                if not os.path.exists(plugin_dir):
                    return
                
                # Find __pycache__ directories owned by root
                root_owned = []
                
                try:
                    for root, dirs, files in os.walk(plugin_dir):
                        if '__pycache__' in dirs:
                            pycache_path = os.path.join(root, '__pycache__')
                            try:
                                stat_info = os.stat(pycache_path)
                                if stat_info.st_uid == 0:
                                    root_owned.append(pycache_path)
                            except (OSError, PermissionError):
                                pass  # Cannot access pycache directory
                except (OSError, PermissionError):
                    pass  # Cannot list plugin directory
                
                if root_owned:
                    logger.warning(
                        f"Detected {len(root_owned)} root-owned __pycache__ directories in plugin. "
                        f"This is caused by Dispatcharr running 'manage.py migrate/collectstatic' as root during startup. "
                        f"Plugin updates may fail. SOLUTION: Add 'PYTHONDONTWRITEBYTECODE=1' to your docker environment "
                        f"or manually run: docker exec -u root <container> find {plugin_dir} -name __pycache__ -exec rm -rf {{}} +"
                    )
                    for path in root_owned:
                        logger.debug(f"Root-owned: {path}")
                        
        except Exception as e:
            logger.debug(f"Could not check for root-owned __pycache__: {e}")
    
    def _check_github_for_updates(self):
        """Helper method to check GitHub for latest release version"""
        import requests
        
        current_version = PLUGIN_CONFIG["version"].lstrip('-').lstrip('v')
        
        # Skip version check for dev builds
        if 'dev' in current_version:
            return {'is_dev': True, 'current': current_version}
        
        repo_url = PLUGIN_CONFIG.get("repo_url", "https://github.com/sethwv/dispatcharr-exporter")
        api_url = f"{repo_url.replace('github.com', 'api.github.com/repos')}/releases/latest"
        
        response = requests.get(
            api_url,
            timeout=5,
            headers={'Accept': 'application/vnd.github.v3+json'}
        )
        
        if not response.ok:
            return {'error': f'HTTP {response.status_code}'}
        
        data = response.json()
        latest_version = data.get('tag_name', '').lstrip('v')
        
        return {
            'current': current_version,
            'latest': latest_version,
            'update_available': latest_version != current_version,
            'repo_url': repo_url
        }
    
    def __init__(self):
        self.collector = PrometheusMetricsCollector()

        # Mitigation for root-owned __pycache__ directories created during Dispatcharr startup
        # This is a workaround for a Dispatcharr issue where migrate/collectstatic run as root
        self._cleanup_root_pycache()

        # Note: Automatic update checks have been removed. Use the "Check for Updates" action button instead.

        # Attempt delayed auto-start with file-based lock to prevent multiple workers from racing
        # Only attempt once per process to avoid multiple threads competing
        global _metrics_server, _auto_start_attempted
        
        if _auto_start_attempted:
            logger.debug("Prometheus exporter: Auto-start already attempted in this process, skipping")
            return
        
        logger.debug("Prometheus exporter: Initializing plugin and starting auto-start thread")
        
        def delayed_auto_start():
            import time
            import os
            import fcntl
            
            global _auto_start_attempted
            
            lock_file = "/tmp/prometheus_exporter_autostart.lock"
            max_retries = 5
            retry_delay = 2
            
            logger.debug("Prometheus exporter: Auto-start thread started, attempting to acquire lock")
            
            # Try to acquire lock - only ONE worker across all processes should succeed
            # Note: lock_fd must stay open to maintain the lock throughout server lifetime
            lock_fd = None
            lock_acquired = False
            try:
                # Create lock file - readable/writable by owner only (not world-readable)
                lock_fd = open(lock_file, 'w')
                try:
                    os.chmod(lock_file, 0o600)  # Security: Owner-only access (not world-readable)
                except OSError:
                    pass  # chmod might fail if we don't own the file
                
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                except BlockingIOError:
                    # Another worker already has the lock
                    lock_fd.close()
                    logger.debug("Prometheus exporter: Auto-start already being handled by another worker")
                    return
                
                logger.debug("Prometheus exporter: Lock acquired, checking config for auto-start")
                
                # We got the lock - we're the chosen worker for auto-start
                try:
                    from core.utils import RedisClient
                    redis_client = RedisClient.get_client()
                    if redis_client:
                        # Check if server is already running
                        running_flag = redis_client.get("prometheus_exporter:server_running")
                        if running_flag == "1" or running_flag == b"1":
                            logger.debug("Prometheus exporter: Server already running (detected via Redis), skipping auto-start")
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                            lock_fd.close()
                            return
                except Exception as e:
                    logger.debug(f"Could not check Redis for running server: {e}")
                
                # Capture the INITIAL auto-start setting to lock in behavior at Dispatcharr startup
                # This prevents runtime setting changes from triggering auto-start
                initial_auto_start_enabled = False
                try:
                    from apps.plugins.models import PluginConfig
                    config = PluginConfig.objects.filter(key='dispatcharr_exporter').first()
                    settings_dict = config.settings if config and config.settings else {}
                    initial_auto_start_enabled = config and config.enabled and settings_dict.get('auto_start', PLUGIN_CONFIG["auto_start_default"])
                    logger.debug(f"Prometheus exporter: Initial auto-start setting captured: config_exists={config is not None}, enabled={config.enabled if config else 'N/A'}, auto_start={initial_auto_start_enabled}")
                except Exception as e:
                    logger.warning(f"Could not read initial auto-start setting: {e}")
                
                # If auto-start was not enabled initially, exit now
                if not initial_auto_start_enabled:
                    logger.debug("Prometheus exporter: Auto-start disabled at startup, will not auto-start")
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                    return
                
                for attempt in range(max_retries):
                    try:
                        time.sleep(retry_delay * (attempt + 1))
                        
                        from apps.plugins.models import PluginConfig
                        config = PluginConfig.objects.filter(key='dispatcharr_exporter').first()
                        
                        # Handle case where settings might be None
                        settings_dict = config.settings if config and config.settings else {}
                        
                        logger.debug(f"Prometheus exporter: Attempt {attempt + 1}/{max_retries} - using initial auto_start={initial_auto_start_enabled}")
                        
                        # Only auto-start if it was enabled at startup (using captured initial value)
                        if config and config.enabled and initial_auto_start_enabled:
                            port = int(settings_dict.get('port', PLUGIN_CONFIG["default_port"]))
                            host = settings_dict.get('host', PLUGIN_CONFIG["default_host"])
                            
                            # Normalize host: handle None, empty string, or whitespace-only
                            if not host or (isinstance(host, str) and not host.strip()):
                                host = PLUGIN_CONFIG["default_host"]
                            elif isinstance(host, str):
                                host = host.strip()
                            
                            logger.debug(f"Auto-start is enabled, attempting to start on {host}:{port}")
                            
                            # Check if port is available before trying to start
                            import socket
                            try:
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                                # Bind to all interfaces (0.0.0.0) for Docker compatibility
                                # Security: Ensure firewall rules are in place for production
                                sock.bind((host, port))
                                sock.close()
                            except OSError:
                                # Port already in use - stop retrying
                                logger.debug(f"Port {port} already in use, cannot auto-start metrics server")
                                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                                lock_fd.close()
                                return
                            
                            server = MetricsServer(self.collector, port=port, host=host)
                            if server.start(settings=settings_dict):
                                logger.info(f"Auto-start successful on http://{host}:{port}/metrics")
                                # Keep lock held to prevent other workers from trying
                                return
                            else:
                                # Start failed but port check passed - unexpected, stop retrying
                                logger.warning(f"Auto-start failed unexpectedly on attempt {attempt + 1}")
                                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                                lock_fd.close()
                                return

                    except Exception as e:
                        logger.warning(f"Prometheus exporter: Auto-start attempt {attempt + 1} failed: {e}")
                        # On any exception, continue to next retry unless it's the last one
                        if attempt == max_retries - 1:
                            logger.warning("Prometheus exporter: Auto-start failed after all retries. Use 'Start Metrics Server' button to start manually.")
                            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                            lock_fd.close()
                            return
                        continue  # Try next attempt
                
                # Release lock if we somehow get here
                if lock_fd:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                    lock_fd.close()
                
            except Exception as e:
                # Any error during lock acquisition or auto-start
                logger.warning(f"Prometheus exporter: Auto-start failed: {e}")
                if lock_fd and lock_acquired:
                    try:
                        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                        lock_fd.close()
                    except Exception:
                        pass  # Best effort cleanup
                elif lock_fd:
                    # File opened but lock not acquired
                    try:
                        lock_fd.close()
                    except Exception:
                        pass  # Best effort cleanup
        
        # Start in daemon thread - only the worker that gets the lock will actually start the server
        import threading
        threading.Thread(target=delayed_auto_start, daemon=True, name="prometheus-auto-start").start()

    def run(self, action: str, params: dict, context: dict):
        """Execute plugin actions"""
        global _metrics_server
        
        # Get logger with context
        logger_ctx = context.get("logger", logger)
        settings = context.get("settings", {})
        
        # Check Redis for server state (works across all workers)
        try:
            from core.utils import RedisClient
            redis_client = RedisClient.get_client()
            running_flag = redis_client.get("prometheus_exporter:server_running") if redis_client else None
            server_running_redis = running_flag == "1" or running_flag == b"1"
            if server_running_redis:
                host_val = redis_client.get("prometheus_exporter:server_host")
                port_val = redis_client.get("prometheus_exporter:server_port")
                server_host = (host_val.decode('utf-8') if isinstance(host_val, bytes) else host_val) or PLUGIN_CONFIG["default_host"]
                server_port = (port_val.decode('utf-8') if isinstance(port_val, bytes) else port_val) or str(PLUGIN_CONFIG["default_port"])
            else:
                server_host = None
                server_port = None
        except Exception as e:
            logger_ctx.debug(f"Could not check Redis for server state: {e}")
            server_running_redis = False
            server_host = None
            server_port = None
        
        if action == "start_server":
            # Check if gevent is available
            try:
                import gevent
                from gevent import pywsgi
            except ImportError:
                return {
                    "status": "error",
                    "message": "gevent is not installed (unexpected - it's a Dispatcharr dependency)",
                    "instructions": "If running a custom setup, install: pip install gevent"
                }
            
            try:
                port = int(settings.get("port", PLUGIN_CONFIG["default_port"]))
                host = settings.get("host", PLUGIN_CONFIG["default_host"])
                
                # Normalize host: handle None, empty string, or whitespace-only
                if not host or (isinstance(host, str) and not host.strip()):
                    host = PLUGIN_CONFIG["default_host"]
                    logger_ctx.info(f"Host was empty/None, using default: {host}")
                elif isinstance(host, str):
                    host = host.strip()
                
                logger_ctx.info(f"Starting server with host='{host}' (repr: {repr(host)}), port={port}")
                
                # Check Redis flag first (works across workers)
                if server_running_redis:
                    return {
                        "status": "error",
                        "message": f"Metrics server is already running on http://{server_host}:{server_port}/metrics"
                    }
                
                # Also check local instance
                if _metrics_server and _metrics_server.is_running():
                    return {
                        "status": "error",
                        "message": f"Metrics server is already running on http://{_metrics_server.host}:{_metrics_server.port}/metrics"
                    }
                
                server = MetricsServer(self.collector, port=port, host=host)
                if server.start(settings=settings):
                    return {
                        "status": "success",
                        "message": "Metrics server started successfully",
                        "endpoint": f"http://{host}:{port}/metrics",
                        "health_check": f"http://{host}:{port}/health",
                        "note": "Metrics are generated fresh on each Prometheus scrape request"
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Failed to start metrics server. Port may already be in use."
                    }
            except Exception as e:
                logger_ctx.error(f"Error starting metrics server: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to start server: {str(e)}"
                }

        elif action == "stop_server":
            try:
                # Try to stop local instance first
                if _metrics_server and _metrics_server.is_running():
                    if _metrics_server.stop():
                        return {
                            "status": "success",
                            "message": "Metrics server stopped successfully"
                        }
                
                # Server is in another worker - signal it to stop via Redis
                if redis_client:
                    try:
                        # Set stop request flag
                        logger_ctx.info("Server is in another worker, sending stop signal via Redis")
                        redis_client.set("prometheus_exporter:stop_requested", "1")
                        logger_ctx.debug("Stop signal set in Redis, waiting for server to confirm shutdown...")
                        
                        # Wait up to 5 seconds for server to stop
                        import time
                        for i in range(50):  # 50 * 0.1 = 5 seconds
                            running_flag = redis_client.get("prometheus_exporter:server_running")
                            if not running_flag or (running_flag != "1" and running_flag != b"1"):
                                # Server has stopped
                                logger_ctx.info("Server confirmed shutdown via Redis")
                                return {
                                    "status": "success",
                                    "message": "Metrics server stopped successfully"
                                }
                            time.sleep(0.1)
                        
                        # Timeout - server didn't stop in time
                        # Force cleanup Redis keys so server can at least be restarted
                        logger_ctx.warning("Server did not confirm shutdown within 5 seconds, force-cleaning Redis keys")
                        try:
                            redis_client.delete("prometheus_exporter:server_running")
                            redis_client.delete("prometheus_exporter:server_host")
                            redis_client.delete("prometheus_exporter:server_port")
                            redis_client.delete("prometheus_exporter:stop_requested")
                            logger_ctx.info("Force-cleaned all Redis keys")
                        except Exception as cleanup_err:
                            logger_ctx.error(f"Failed to force-clean Redis keys: {cleanup_err}")
                        
                        # Clean up lock file
                        try:
                            lock_file = "/tmp/prometheus_exporter_autostart.lock"
                            if os.path.exists(lock_file):
                                os.remove(lock_file)
                                logger_ctx.debug("Removed auto-start lock file")
                        except Exception:
                            pass
                        
                        return {
                            "status": "warning",
                            "message": "Stop signal sent, but server did not confirm shutdown within 5 seconds. Redis keys have been force-cleaned — you can now restart the server. The old server process may still be running but will not conflict."
                        }
                    except Exception as redis_error:
                        logger_ctx.error(f"Failed to signal stop via Redis: {redis_error}")
                        return {
                            "status": "error",
                            "message": f"Failed to signal stop: {str(redis_error)}"
                        }
                else:
                    return {
                        "status": "error",
                        "message": "Cannot stop server: No local instance and Redis unavailable"
                    }
                    
            except Exception as e:
                logger_ctx.error(f"Error stopping metrics server: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to stop server: {str(e)}"
                }

        elif action == "restart_server":
            try:
                # Try to stop local instance first
                if _metrics_server and _metrics_server.is_running():
                    _metrics_server.stop()
                
                # Always clear Redis flags and signal stop
                if redis_client:
                    try:
                        logger_ctx.info("Sending stop signal via Redis for restart")
                        redis_client.set("prometheus_exporter:stop_requested", "1")
                        
                        # Wait up to 5 seconds for server to stop
                        import time
                        stopped = False
                        for i in range(50):
                            running_flag = redis_client.get("prometheus_exporter:server_running")
                            if not running_flag or (running_flag != "1" and running_flag != b"1"):
                                stopped = True
                                break
                            time.sleep(0.1)
                        
                        if not stopped:
                            # Force cleanup so restart can proceed
                            logger_ctx.warning("Server did not confirm shutdown within 5 seconds during restart, force-cleaning Redis keys")
                            redis_client.delete("prometheus_exporter:server_running")
                            redis_client.delete("prometheus_exporter:server_host")
                            redis_client.delete("prometheus_exporter:server_port")
                            redis_client.delete("prometheus_exporter:stop_requested")
                            try:
                                lock_file = "/tmp/prometheus_exporter_autostart.lock"
                                if os.path.exists(lock_file):
                                    os.remove(lock_file)
                            except Exception:
                                pass
                    except Exception as redis_error:
                        logger_ctx.error(f"Failed to signal stop via Redis: {redis_error}")
                        return {
                            "status": "error",
                            "message": f"Failed to stop server: {str(redis_error)}"
                        }
                
                # Small delay to ensure cleanup
                import time
                time.sleep(0.5)
                
                # Clear the stop_requested flag before starting new server
                if redis_client:
                    try:
                        redis_client.delete("prometheus_exporter:stop_requested")
                        logger_ctx.debug("Cleared stop_requested flag before restart")
                    except Exception as e:
                        logger_ctx.warning(f"Failed to clear stop_requested flag: {e}")
                
                # Additional delay to ensure flag is cleared
                time.sleep(0.5)
                
                # Now start the server
                port = int(settings.get('port', PLUGIN_CONFIG["default_port"]))
                host = settings.get('host', PLUGIN_CONFIG["default_host"])
                
                # Normalize host: handle None, empty string, or whitespace-only
                if not host or (isinstance(host, str) and not host.strip()):
                    host = PLUGIN_CONFIG["default_host"]
                    logger_ctx.info(f"Host was empty/None, using default: {host}")
                elif isinstance(host, str):
                    host = host.strip()
                
                # Check if already running (shouldn't be, but check anyway)
                if redis_client:
                    running_flag = redis_client.get("prometheus_exporter:server_running")
                    if running_flag == "1" or running_flag == b"1":
                        return {
                            "status": "error",
                            "message": "Server is still running after stop attempt"
                        }
                
                # Start new server
                server = MetricsServer(self.collector, port=port, host=host)
                if server.start(settings=settings):
                    return {
                        "status": "success",
                        "message": "Metrics server restarted successfully",
                        "endpoint": f"http://{host}:{port}/metrics",
                        "health_check": f"http://{host}:{port}/health"
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Server stopped but failed to restart. Port may be in use."
                    }
                    
            except Exception as e:
                logger_ctx.error(f"Error restarting metrics server: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to restart server: {str(e)}"
                }

        elif action == "server_status":
            try:
                # Determine endpoint URL
                if server_running_redis and server_host and server_port:
                    endpoint = f"http://{server_host}:{server_port}/metrics"
                elif _metrics_server and _metrics_server.host and _metrics_server.port:
                    endpoint = f"http://{_metrics_server.host}:{_metrics_server.port}/metrics"
                else:
                    # Use default from settings or fallback to config defaults
                    host = settings.get('host', PLUGIN_CONFIG["default_host"]) if settings else PLUGIN_CONFIG["default_host"]
                    port = settings.get('port', PLUGIN_CONFIG["default_port"]) if settings else PLUGIN_CONFIG["default_port"]
                    endpoint = f"http://{host}:{port}/metrics"
                
                # Check both local instance and Redis flag
                if (_metrics_server and _metrics_server.is_running()) or server_running_redis:
                    return {
                        "status": "success",
                        "message": f"Server is running on {endpoint}"
                    }
                else:
                    return {
                        "status": "success",
                        "message": f"Server is not running"
                    }
            except Exception as e:
                logger_ctx.error(f"Error checking server status: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to check status: {str(e)}"
                }

        elif action == "check_for_updates":
            try:
                # Use helper method to check for updates
                result = self._check_github_for_updates()
                
                # Handle dev build
                if result.get('is_dev'):
                    return {
                        "status": "success",
                        "message": f"Running development version ({result['current']}). Update checks are disabled for dev builds."
                    }
                
                # Handle errors
                if 'error' in result:
                    return {
                        "status": "error",
                        "message": f"Failed to check for updates ({result['error']})"
                    }
                
                current_version = result['current']
                latest_version = result['latest']
                repo_url = result['repo_url']
                
                if result['update_available']:
                    # Store in Redis for future reference
                    try:
                        from core.utils import RedisClient
                        redis_client = RedisClient.get_client()
                        if redis_client:
                            redis_client.setex(
                                "prometheus_exporter:update_available",
                                60 * 60 * 24,  # 24 hour TTL
                                latest_version
                            )
                    except Exception:
                        pass  # Failed to cache update info in Redis
                    
                    return {
                        "status": "warning",
                        "message": f"Update available! Current: {current_version}, Latest: {latest_version}",
                        "download_url": f"{repo_url}/releases/latest",
                        "note": f"Download from: {repo_url}/releases/latest"
                    }
                else:
                    return {
                        "status": "success",
                        "message": f"You are running the latest version ({current_version})"
                    }
                    
            except Exception as e:
                logger_ctx.error(f"Error checking for updates: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Failed to check for updates: {str(e)}"
                }

        return {"status": "error", "message": f"Unknown action: {action}"}

