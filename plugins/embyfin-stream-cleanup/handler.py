"""Stream monitor that polls Dispatcharr client activity.

Periodically scans all active channels for clients matching the configured
client identifier(s).  When a matching client's ``last_active`` timestamp
exceeds the idle timeout, a Redis stop-signal key is set so the stream
generator closes the connection cleanly.

Optionally cross-references with an Emby/Jellyfin Sessions API to detect
orphaned connections that the media server failed to close.
"""

import ipaddress
import json
import logging
import socket
import threading
import time
import urllib.request
import urllib.error

from .config import (
    DEFAULT_CLEANUP_TIMEOUT, DEFAULT_POLL_INTERVAL,
    REDIS_KEY_MONITOR, REDIS_KEY_STOP,
    HEARTBEAT_TTL, PLUGIN_DB_KEY,
)
from .utils import get_redis_client, read_redis_flag, redis_decode

logger = logging.getLogger(__name__)

# ── Feature flags ────────────────────────────────────────────────────────────
# Set to False to disable idle-based termination while keeping pool-absent
# and orphan detection active.
ENABLE_IDLE_TERMINATION = True

# Channel states that indicate the stream is mid-failover or still starting up.
# Clients appear idle during these states because no data is flowing yet.
_GRACE_STATES = frozenset({"initializing", "connecting", "buffering", "waiting_for_clients"})

# NowPlayingItem.Type values that indicate a live TV stream.
# Emby uses "TvChannel"; Jellyfin may use either "TvChannel" or "LiveTvChannel".
_LIVE_TV_TYPES = frozenset({"TvChannel", "LiveTvChannel"})


def _get_failover_grace():
    """Return the failover grace period (seconds) from Dispatcharr proxy config.

    During a stream switch Dispatcharr allows up to
    ``FAILOVER_GRACE_PERIOD + BUFFERING_TIMEOUT`` before disconnecting
    clients.  We use the same window so we don't kill sessions that are
    just waiting for a new upstream to stabilise.
    """
    try:
        from apps.proxy.config import TSConfig
        settings = TSConfig.get_proxy_settings()
        failover = getattr(TSConfig, "FAILOVER_GRACE_PERIOD", 20)
        buffering = settings.get("buffering_timeout", 15)
        return failover + buffering
    except Exception:
        return 35  # safe default: 20 + 15


def _resolve_username(user_id_str, cache):
    """Resolve a Redis user_id string to a Django username.

    Uses *cache* (dict) to avoid repeated DB hits within one poll cycle.
    """
    try:
        uid = int(user_id_str)
        if uid <= 0:
            return ""
        if uid not in cache:
            from apps.accounts.models import User
            cache[uid] = User.objects.get(id=uid).username
        return cache[uid]
    except Exception:
        return ""


class StreamMonitor:
    """Background poller that watches Dispatcharr client activity and
    terminates idle connections matching the configured identifier."""

    def __init__(self):
        self._thread = None
        self._running = False
        self._settings = {}
        # Per-client tracking: {(channel_uuid, client_id): first_idle_ts}
        # Records when we first noticed a client was idle so we can
        # measure idle duration across poll cycles.
        self._idle_since = {}
        # Per-client orphan tracking: {(channel_uuid, client_id): first_orphan_ts}
        self._orphaned_since = {}
        # Snapshot for the debug page (updated each poll cycle)
        self._last_scan = {}
        self._last_scan_time = 0
        self._stopped_log = []  # recent terminations for debug display
        self._stop_logged = set()      # cross-cycle: {"uuid:client_id"}
        # Media server session state (updated each poll cycle)
        self._emby_active_count = None  # None=not configured, int=session count
        self._emby_error = None  # last error message, if any
        self._media_server_status = []  # per-server status dicts for debug page
        self._active_recording_channels = set()  # channel numbers with in-progress DVR recordings
        self._recording_count_by_url = {}  # {server_url: int} for dashboard display

    # ── Identifier helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_identifiers(client_identifier):
        """Split a comma-separated identifier string into lowercased values."""
        if not client_identifier:
            return []
        return [v.strip().lower() for v in client_identifier.split(",") if v.strip()]

    @staticmethod
    def _is_cidr(ident):
        """Return True if *ident* looks like a CIDR block (e.g. 10.0.0.0/24)."""
        if "/" not in ident:
            return False
        try:
            ipaddress.ip_network(ident, strict=False)
            return True
        except ValueError:
            return False

    @staticmethod
    def _ip_in_cidr(ip, cidr):
        """Return True if *ip* falls within the *cidr* network."""
        try:
            return ipaddress.ip_address(ip.strip()) in ipaddress.ip_network(cidr.strip(), strict=False)
        except ValueError:
            return False

    @staticmethod
    def _resolve_identifiers(identifiers):
        """Resolve any hostnames in *identifiers* to IP addresses.
        CIDR blocks and plain IPs are skipped (not hostnames)."""
        resolved = set()
        for ident in identifiers:
            # Skip CIDR blocks and plain IP addresses
            if "/" in ident:
                continue
            try:
                ipaddress.ip_address(ident)
                continue  # plain IP, no resolution needed
            except ValueError:
                pass
            try:
                for info in socket.getaddrinfo(ident, None):
                    resolved.add(info[4][0])
            except (socket.gaierror, OSError):
                pass
        return resolved

    @staticmethod
    def _match_client(ip, username, identifiers, resolved_ips,
                      ident_to_server=None, resolved_ip_to_server=None):
        """Check if a client matches any configured identifier.
        Supports plain IPs, usernames, hostnames, and CIDR blocks.
        Returns (matched: bool, reason: str, server_info: dict or None)."""
        if "all" in identifiers:
            srv = (ident_to_server or {}).get("all")
            return True, "ALL (matches every client)", srv
        ip_lower = ip.strip().lower()
        uname_lower = username.strip().lower()
        for ident in identifiers:
            if "/" in ident:
                try:
                    if ipaddress.ip_address(ip_lower) in ipaddress.ip_network(ident, strict=False):
                        srv = (ident_to_server or {}).get(ident)
                        return True, f"CIDR match ({ident})", srv
                except ValueError:
                    pass
                continue
            if ip_lower == ident:
                srv = (ident_to_server or {}).get(ident)
                return True, f"IP match ({ident})", srv
            if uname_lower == ident:
                srv = (ident_to_server or {}).get(ident)
                return True, f"username match ({ident})", srv
        if ip in resolved_ips:
            srv = (resolved_ip_to_server or {}).get(ip)
            return True, "hostname resolves to IP", srv
        return False, "", None

    # ── Media server session helpers ─────────────────────────────────────────

    def _get_media_server_configs(self):
        """Return a list of (url, api_key, identifiers) tuples for all configured servers.

        ``identifiers`` is a set of lowercased client identifiers tied to this
        server (from the per-server identifier config field).
        """
        count = max(1, int(self._settings.get("media_server_count", 1)))
        servers = []
        seen_idents = set()
        for n in range(1, count + 1):
            suffix = f"_{n}" if n > 1 else ""
            url = (self._settings.get(f"media_server_url{suffix}") or "").strip().rstrip("/")
            key = (self._settings.get(f"media_server_api_key{suffix}") or "").strip()
            ident_raw = (self._settings.get(f"media_server_identifier{suffix}") or "").strip()
            # Migrate legacy field names from single-server config
            if n == 1 and not url:
                url = (self._settings.get("emby_url") or "").strip().rstrip("/")
            if n == 1 and not key:
                key = (self._settings.get("emby_api_key") or "").strip()
            if url and key:
                idents = {v.strip().lower() for v in ident_raw.split(",") if v.strip()}
                # Drop identifiers already claimed by a lower-numbered server
                dupes = idents & seen_idents
                if dupes:
                    logger.warning(
                        f"Server {n}: ignoring duplicate identifier(s) "
                        f"{', '.join(sorted(dupes))} (already on a lower-numbered server)"
                    )
                    idents -= seen_idents
                if idents:
                    seen_idents.update(idents)
                    servers.append((url, key, idents))
        return servers

    @staticmethod
    def _detect_server_info(url):
        """Probe /System/Info/Public to determine server type and name.

        Returns ``(type, name)`` where *type* is ``"Emby"`` or
        ``"Jellyfin"`` and *name* is the configured server name, or
        ``(None, None)`` on failure.
        """
        try:
            req = urllib.request.Request(
                f"{url}/System/Info/Public",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                info = json.loads(resp.read().decode("utf-8"))
                # Jellyfin includes ProductName; Emby does not
                product = info.get("ProductName", "")
                name = info.get("ServerName") or None
                if "jellyfin" in product.lower():
                    return "Jellyfin", name
                return "Emby", name
        except Exception:
            return None, None

    def _fetch_media_server_sessions(self):
        """Fetch active sessions from all configured Emby/Jellyfin servers.

        Returns a list of session dicts, or ``None`` if no servers are configured.
        Sets ``self._emby_error`` on failure.
        """
        servers = self._get_media_server_configs()
        if not servers:
            self._media_server_status = []
            return None

        all_sessions = []
        errors = []
        per_server = []
        for idx, (url, api_key, _idents) in enumerate(servers, 1):
            endpoint = f"{url}/Sessions"
            # Detect server type and name on first encounter or after error
            cached = getattr(self, "_server_info", {}).get(url)
            if cached is not None:
                server_type, server_name = cached
            else:
                server_type, server_name = self._detect_server_info(url)
                if not hasattr(self, "_server_info"):
                    self._server_info = {}
                if server_type:
                    self._server_info[url] = (server_type, server_name)
            try:
                req = urllib.request.Request(endpoint, headers={
                    "Accept": "application/json",
                    # Emby accepts ?api_key; Jellyfin accepts X-Emby-Token header.
                    # Sending both ensures compatibility with either server.
                    "X-Emby-Token": api_key,
                })
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    sessions = data if isinstance(data, list) else []
                    live = [s for s in sessions
                            if s.get("NowPlayingItem", {}).get("Type") in _LIVE_TV_TYPES]
                    # Tag each session with its source server URL for per-IP pool mapping
                    for s in live:
                        s["_source_url"] = url
                    all_sessions.extend(live)
                    active = len(live)
                    per_server.append({"num": idx, "url": url, "type": server_type, "name": server_name, "active": active, "error": None})
            except Exception as e:
                errors.append(f"Server {idx}: {e}")
                logger.warning(f"Failed to fetch media server sessions from server {idx}: {e}")
                per_server.append({"num": idx, "url": url, "type": server_type, "name": server_name, "active": None, "error": str(e)})

        self._media_server_status = per_server
        self._emby_error = "; ".join(errors) if errors else None
        return all_sessions

    @staticmethod
    def _count_active_streams(sessions):
        """Count live TV sessions with an active NowPlayingItem."""
        if not sessions:
            return 0
        return sum(1 for s in sessions
                   if s.get("NowPlayingItem", {}).get("Type") in _LIVE_TV_TYPES)

    def _fetch_active_recording_channels(self):
        """Return channel numbers for active in-progress DVR recordings.

        Calls GET /LiveTv/Recordings?IsInProgress=true on each configured
        media server.  Returns a list of dicts with 'channel_number' and
        '_source_url' keys so callers can map them back to server identifiers.
        """
        servers = self._get_media_server_configs()
        if not servers:
            return []
        results = []
        for url, api_key, _ in servers:
            endpoint = f"{url}/LiveTv/Recordings?IsInProgress=true&Fields=ChannelNumber&Limit=200"
            try:
                req = urllib.request.Request(endpoint, headers={
                    "Accept": "application/json",
                    "X-Emby-Token": api_key,
                })
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    items = data.get("Items", []) if isinstance(data, dict) else []
                    for item in items:
                        ch_num = item.get("ChannelNumber")
                        if ch_num:
                            ch_num = str(ch_num).strip()
                            try:
                                num = float(ch_num)
                                ch_num = str(int(num)) if num == int(num) else ch_num
                            except (ValueError, TypeError):
                                pass
                            results.append({"channel_number": ch_num, "_source_url": url})
            except Exception as e:
                logger.debug(f"Could not fetch active recordings from {url}: {e}")
        return results

    @staticmethod
    def _signal_client_stop(channel_uuid, client_id, redis_client):
        """Set the Redis stop-signal key for a client WITHOUT removing it.

        ``ChannelService.stop_client()`` immediately deletes the client from
        the Redis client set and metadata hash.  This means the client
        becomes invisible to the next scan even though its TCP connection
        may still be open.  The media server then reconnects with a new
        ``client_id``, creating a flicker cycle.

        By setting only the stop-signal key we let the stream generator
        detect it on its next chunk yield, close the connection cleanly,
        and let Dispatcharr's own cleanup remove the client from Redis.
        The client stays visible in the scan until the connection actually
        closes.
        """
        try:
            from apps.proxy.ts_proxy.redis_keys import RedisKeys
            stop_key = RedisKeys.client_stop(channel_uuid, client_id)
            redis_client.setex(stop_key, 30, "true")
            return True
        except Exception as e:
            logger.error(f"Error setting stop signal for {client_id}: {e}")
            return False

    @staticmethod
    def _pool_channels_for_client(ip, username, pool_channels_by_ident):
        """Find the pool channel set that covers this client.

        Checks the client's IP, username (lowercased), resolved hostname,
        and CIDR blocks against the ``pool_channels_by_ident`` mapping
        which is keyed by identifier strings (IPs, usernames, hostnames,
        or CIDR blocks).

        Returns the matching channel set, or ``None`` if no identifier matches.
        """
        if not pool_channels_by_ident:
            return None
        ip_lower = ip.strip().lower()
        uname_lower = (username or "").strip().lower()
        if ip_lower in pool_channels_by_ident:
            return pool_channels_by_ident[ip_lower]
        if uname_lower and uname_lower in pool_channels_by_ident:
            return pool_channels_by_ident[uname_lower]
        # Check CIDR blocks and resolved hostname identifiers
        for ident, ch_set in pool_channels_by_ident.items():
            if "/" in ident:
                try:
                    if ipaddress.ip_address(ip_lower) in ipaddress.ip_network(ident, strict=False):
                        return ch_set
                except ValueError:
                    pass
                continue
            try:
                for info in socket.getaddrinfo(ident, None):
                    if info[4][0] == ip_lower:
                        return ch_set
            except (socket.gaierror, OSError):
                pass
        return None

    def _detect_orphans(self, scan_result, sessions, now, pool_channels_by_ident=None, redis_client=None):
        """Compare Dispatcharr matched connections against active media server
        sessions by channel number.  Connections on channels the media server
        is no longer watching are orphan candidates.

        When ``pool_channels_by_ident`` is provided, only channels from the
        client's own media server are considered (per-identifier pool protection).

        Orphans must also be idle and are confirmed over multiple poll cycles
        before termination to avoid race conditions during channel switches.
        """
        # Build flat set of channel numbers (fallback when no per-IP mapping)
        active_channel_numbers = set()
        for s in (sessions or []):
            npi = s.get("NowPlayingItem", {})
            ch_num = npi.get("ChannelNumber")
            if ch_num:
                ch_num = str(ch_num).strip()
                try:
                    num = float(ch_num)
                    ch_num = str(int(num)) if num == int(num) else ch_num
                except (ValueError, TypeError):
                    pass
                active_channel_numbers.add(ch_num)

        # Collect all matched clients across all channels (skip grace channels)
        all_matched = []
        for ch_uuid, ch_data in scan_result.items():
            if ch_data.get("in_grace"):
                continue
            for client in ch_data.get("clients", []):
                if client.get("is_target_match"):
                    all_matched.append((ch_uuid, ch_data, client))

        if not all_matched:
            return

        # Determine orphan candidates per client
        orphan_candidates = []
        non_orphans = []
        for item in all_matched:
            ch_num = item[1].get("channel_number", "")
            client_ip = (item[2].get("ip") or "")
            client_uname = (item[2].get("username") or "")

            # Find pool channels for this client by checking which identifier
            # it matched against (could be IP, username, or resolved hostname)
            if pool_channels_by_ident:
                client_channels = self._pool_channels_for_client(
                    client_ip, client_uname, pool_channels_by_ident
                )
                if client_channels is None:
                    # Client doesn't match any configured server identifier,
                    # not covered by pool, so it's a potential orphan
                    client_channels = set()
            else:
                client_channels = active_channel_numbers

            if ch_num in client_channels:
                non_orphans.append(item)
            else:
                orphan_candidates.append(item)

        # Clear tracking for non-orphans
        for ch_uuid, _, client in non_orphans:
            self._orphaned_since.pop((ch_uuid, client["client_id"]), None)

        if not orphan_candidates:
            return

        poll_interval = max(int(self._settings.get("poll_interval", DEFAULT_POLL_INTERVAL)), 1)
        timeout = int(self._settings.get("cleanup_timeout", DEFAULT_CLEANUP_TIMEOUT))
        # Orphans must persist for the full idle timeout before termination
        confirm_threshold = max(timeout, poll_interval * 2)

        for ch_uuid, ch_data, client in orphan_candidates:
            ck = (ch_uuid, client["client_id"])
            client["is_orphan"] = True

            if ck not in self._orphaned_since:
                self._orphaned_since[ck] = now
                logger.info(
                    f"Potential orphan: client {client['client_id']} on "
                    f"CH {ch_data.get('channel_number', '?')} "
                    f"(no matching media server session, "
                    f"connected {client.get('connected_duration', '?')})"
                )
                continue

            orphan_age = now - self._orphaned_since[ck]
            if orphan_age < confirm_threshold:
                continue  # not yet confirmed

            channel_number = ch_data.get("channel_number", "?")
            channel_name = ch_data.get("channel_name", "")
            client_id = client["client_id"]
            sig_key = f"{ch_uuid}:{client_id}"

            # Only signal once per client; the stop key has a 30s TTL and
            # tells the stream generator to close the connection.  Re-signal
            # each cycle to keep the TTL refreshed while the client persists.
            if redis_client:
                self._signal_client_stop(ch_uuid, client_id, redis_client)

            if sig_key not in self._stop_logged:
                reason = f"orphan: no media server session for {orphan_age:.0f}s"
                logger.info(
                    f"Terminating orphaned client {client_id} on CH "
                    f"{channel_number} ({channel_name}): {reason} "
                    f"(ip={client.get('ip', '?')}, user={client.get('username', '?')})"
                )
                self._stopped_log.append({
                    "time": now,
                    "channel": f"CH {channel_number} ({channel_name})",
                    "ip": client.get("ip", ""),
                    "username": client.get("username", ""),
                    "reason": reason,
                })
                if len(self._stopped_log) > 20:
                    self._stopped_log = self._stopped_log[-20:]
                self._stop_logged.add(sig_key)

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self, settings=None):
        """Start the background polling thread."""
        if self._running:
            logger.warning("Stream monitor is already running")
            return False

        self._settings = settings or {}

        # Prune stale media server keys from in-memory settings
        count = max(1, int(self._settings.get("media_server_count", 1)))
        stale = [k for k in list(self._settings.keys())
                 if k.startswith(("media_server_url_", "media_server_api_key_", "media_server_identifier_"))]
        for k in stale:
            suffix = k.rsplit("_", 1)[-1]
            try:
                if int(suffix) > count:
                    del self._settings[k]
                    logger.debug(f"Pruned stale setting from live config: {k}")
            except (ValueError, TypeError):
                pass

        self._running = True
        self._idle_since.clear()
        self._orphaned_since.clear()
        self._stopped_log.clear()
        self._stop_logged = set()
        self._emby_active_count = None
        self._emby_error = None
        self._active_recording_channels = set()
        self._recording_count_by_url = {}

        # Mark as running in Redis (with heartbeat TTL so the key expires
        # if this process dies without cleaning up).
        redis_client = get_redis_client()
        if redis_client:
            redis_client.set(REDIS_KEY_MONITOR, "1", ex=HEARTBEAT_TTL)
            # Clear any stale stop signal
            redis_client.delete(REDIS_KEY_STOP)

        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="emby-stream-monitor",
        )
        self._thread.start()
        logger.info("Stream monitor started")
        return True

    def stop(self):
        """Stop the background polling thread."""
        if not self._running:
            return True
        self._running = False
        redis_client = get_redis_client()
        if redis_client:
            redis_client.delete(REDIS_KEY_MONITOR)
        # Thread will exit on next cycle check
        logger.info("Stream monitor stopping")
        return True

    def is_running(self):
        return self._running

    def update_settings(self, settings):
        """Update settings without restarting."""
        self._settings = settings or {}

    def _refresh_settings(self):
        """Re-read settings from the database and prune stale keys.

        Called each poll cycle so that UI changes (e.g. reducing
        media_server_count) take effect without a manual restart.
        """
        try:
            from apps.plugins.models import PluginConfig
            _plugin_keys = [PLUGIN_DB_KEY, PLUGIN_DB_KEY.replace('_', '-')]
            cfg = None
            for _key in _plugin_keys:
                cfg = PluginConfig.objects.filter(key=_key).first()
                if cfg is not None:
                    break
            if cfg is None or not cfg.enabled:
                return
            new_settings = cfg.settings or {}

            # Prune stale media server keys from DB
            count = max(1, int(new_settings.get("media_server_count", 1)))
            changed = False
            stale = [
                k for k in list(new_settings.keys())
                if k.startswith(("media_server_url_", "media_server_api_key_", "media_server_identifier_"))
            ]
            for k in stale:
                suffix = k.rsplit("_", 1)[-1]
                try:
                    if int(suffix) > count:
                        del new_settings[k]
                        changed = True
                except (ValueError, TypeError):
                    pass
            if changed:
                cfg.settings = new_settings
                cfg.save(update_fields=["settings"])
                logger.debug("Pruned stale media server keys from database")

            self._settings = new_settings
        except Exception as e:
            logger.debug(f"Could not refresh settings from DB: {e}")

    # ── Poll loop ────────────────────────────────────────────────────────────

    def _poll_loop(self):
        """Main polling loop. Runs in a daemon thread."""
        logger.info("Stream monitor poll loop started")
        while self._running:
            try:
                # Check for Redis stop signal (cross-worker shutdown)
                redis_client = get_redis_client()
                if redis_client and read_redis_flag(redis_client, REDIS_KEY_STOP):
                    logger.info("Stream monitor received stop signal via Redis")
                    self._running = False
                    redis_client.delete(REDIS_KEY_MONITOR, REDIS_KEY_STOP)
                    break

                # Refresh heartbeat so the key doesn't expire while we're alive
                if redis_client:
                    redis_client.set(REDIS_KEY_MONITOR, "1", ex=HEARTBEAT_TTL)

                # Re-read settings from DB so UI changes take effect
                self._refresh_settings()

                self._poll_once()
            except Exception as e:
                logger.error(f"Stream monitor poll error: {e}", exc_info=True)

            interval = int(self._settings.get("poll_interval", DEFAULT_POLL_INTERVAL))
            interval = max(1, interval)
            time.sleep(interval)

        logger.info("Stream monitor poll loop exited")

    def _poll_once(self):
        """Single poll cycle: scan channels, check idle matched clients, terminate."""
        redis_client = get_redis_client()
        if not redis_client:
            return

        # Require at least one fully configured media server (URL + key + identifier)
        servers = self._get_media_server_configs()
        if not servers:
            return

        # Build unified identifier set and per-identifier server mapping
        identifiers = set()
        ident_to_server = {}
        for _url, _key, idents in servers:
            identifiers.update(idents)
        if not identifiers:
            return

        resolved_ips = self._resolve_identifiers(identifiers)
        timeout = int(self._settings.get("cleanup_timeout", DEFAULT_CLEANUP_TIMEOUT))
        now = time.time()

        # Read Dispatcharr proxy settings for failover grace period
        failover_grace = _get_failover_grace()

        try:
            from apps.proxy.ts_proxy.redis_keys import RedisKeys
        except ImportError:
            return

        # Build channel model cache for names
        channel_model_cache = {}
        _user_cache = {}  # per-scan cache: user_id int -> username str
        try:
            from apps.channels.models import Channel
            for ch in Channel.objects.only("channel_number", "name", "uuid"):
                channel_model_cache[str(ch.uuid)] = {
                    "name": ch.name,
                    "number": str(int(ch.channel_number)) if ch.channel_number == int(ch.channel_number) else str(ch.channel_number),
                }
        except Exception:
            pass

        # Find all active channels by scanning channel_stream:* keys
        scan_result = {}
        active_keys = set()

        # Fetch media server sessions early so idle termination can cross-check
        sessions = self._fetch_media_server_sessions()

        # Build ident→server mapping now that _media_server_status is populated
        for ms in self._media_server_status:
            ms_url = ms.get("url", "")
            for _url, _key, idents in servers:
                if _url == ms_url:
                    srv_info = {"num": ms["num"], "name": ms.get("name"), "type": ms.get("type")}
                    for ident in idents:
                        ident_to_server[ident] = srv_info
                    break
        # Map resolved IPs to the server that owns the resolving identifier.
        # Skip CIDR blocks and plain IPs (only resolve hostnames).
        resolved_ip_to_server = {}
        for ident, srv_info in ident_to_server.items():
            if "/" in ident:
                continue  # CIDR block, not a hostname
            try:
                ipaddress.ip_address(ident)
                continue  # plain IP, no resolution needed
            except ValueError:
                pass
            try:
                for info in socket.getaddrinfo(ident, None):
                    ip = info[4][0]
                    if ip not in resolved_ip_to_server:
                        resolved_ip_to_server[ip] = srv_info
            except (socket.gaierror, OSError):
                pass
        media_server_channel_numbers = None  # flat set for orphan detection
        # Per-identifier channel sets: {identifier: set(channel_numbers)}
        # Only clients whose IP/hostname matches a server's identifier get pool protection
        pool_channels_by_ident = {}
        if sessions is not None:
            media_server_channel_numbers = set()
            servers = self._get_media_server_configs()
            # Build mapping: server URL → set of identifiers
            url_to_idents = {}
            for url, _key, idents in servers:
                url_to_idents[url] = idents

            for s in sessions:
                npi = s.get("NowPlayingItem", {})
                ch_num = npi.get("ChannelNumber")
                if ch_num:
                    ch_num = str(ch_num).strip()
                    try:
                        num = float(ch_num)
                        ch_num = str(int(num)) if num == int(num) else ch_num
                    except (ValueError, TypeError):
                        pass
                    media_server_channel_numbers.add(ch_num)
                    # Tag this channel to the identifiers of the server that reported it
                    source_url = s.get("_source_url", "")
                    for ident in url_to_idents.get(source_url, set()):
                        pool_channels_by_ident.setdefault(ident, set()).add(ch_num)

            # Also protect channels with active in-progress DVR recordings.
            # The recording backend connects to Dispatcharr as a client but
            # never appears as a regular playback session, so without this its
            # channel would be absent from the pool and terminated.
            recording_channels = set()
            recording_count_by_url = {}
            for rec in self._fetch_active_recording_channels():
                ch_num = rec["channel_number"]
                source_url = rec.get("_source_url", "")
                media_server_channel_numbers.add(ch_num)
                recording_channels.add(ch_num)
                recording_count_by_url[source_url] = recording_count_by_url.get(source_url, 0) + 1
                for ident in url_to_idents.get(source_url, set()):
                    pool_channels_by_ident.setdefault(ident, set()).add(ch_num)
            self._active_recording_channels = recording_channels
            self._recording_count_by_url = recording_count_by_url

        try:
            for key in redis_client.scan_iter(match="channel_stream:*"):
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                # key format: channel_stream:{channel_id}
                parts = key_str.split(":", 1)
                if len(parts) < 2:
                    continue
                channel_id_raw = parts[1]

                # channel_id_raw might be numeric ID, need to find UUID
                # Look up UUID from channel model cache by checking all channels
                channel_uuid = None
                channel_name = ""
                channel_number = ""

                # Try treating channel_id_raw as a UUID directly
                if channel_id_raw in channel_model_cache:
                    channel_uuid = channel_id_raw
                    channel_name = channel_model_cache[channel_id_raw]["name"]
                    channel_number = channel_model_cache[channel_id_raw]["number"]
                else:
                    # It's a numeric ID; look up the channel
                    try:
                        ch = Channel.objects.filter(pk=int(channel_id_raw)).only("uuid", "name", "channel_number").first()
                        if ch:
                            channel_uuid = str(ch.uuid)
                            channel_name = ch.name
                            channel_number = str(int(ch.channel_number)) if ch.channel_number == int(ch.channel_number) else str(ch.channel_number)
                    except (ValueError, Exception):
                        pass

                if not channel_uuid:
                    continue

                # ── Failover / buffering protection ──────────────────────────
                # Read channel metadata to check if the stream is mid-failover
                # or still buffering.  Clients appear idle during these states
                # because no data is flowing, so we must not terminate them.
                ch_meta_key = RedisKeys.channel_metadata(channel_uuid)
                ch_meta = redis_client.hgetall(ch_meta_key) or {}
                ch_state = redis_decode(
                    ch_meta.get(b"state") or ch_meta.get("state")
                ).lower()
                in_grace = ch_state in _GRACE_STATES

                if not in_grace:
                    # Even if state is "active", a recent stream switch means
                    # data may have just resumed and last_active hasn't caught up.
                    switch_raw = redis_decode(
                        ch_meta.get(b"stream_switch_time") or ch_meta.get("stream_switch_time")
                    )
                    try:
                        switch_ts = float(switch_raw) if switch_raw else 0
                    except (ValueError, TypeError):
                        switch_ts = 0
                    if switch_ts and (now - switch_ts) < failover_grace:
                        in_grace = True

                # Read clients for this channel
                client_ids = redis_client.smembers(RedisKeys.clients(channel_uuid)) or []
                if not client_ids:
                    continue

                channel_clients = []
                for raw_id in client_ids:
                    client_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)
                    meta_key = RedisKeys.client_metadata(channel_uuid, client_id)
                    cdata = redis_client.hgetall(meta_key)
                    if not cdata:
                        continue

                    ip = redis_decode(cdata.get(b"ip_address") or cdata.get("ip_address"))
                    user_id_str = redis_decode(cdata.get(b"user_id") or cdata.get("user_id"))
                    username = _resolve_username(user_id_str, _user_cache)
                    user_agent = redis_decode(cdata.get(b"user_agent") or cdata.get("user_agent"))
                    connected_at = redis_decode(cdata.get(b"connected_at") or cdata.get("connected_at"))
                    last_active_raw = redis_decode(cdata.get(b"last_active") or cdata.get("last_active"))
                    bytes_sent = redis_decode(cdata.get(b"bytes_sent") or cdata.get("bytes_sent"))

                    matched, match_reason, match_server = self._match_client(
                        ip, username, identifiers, resolved_ips,
                        ident_to_server, resolved_ip_to_server,
                    )

                    # Calculate last_active age
                    try:
                        last_active_ts = float(last_active_raw) if last_active_raw else 0
                    except (ValueError, TypeError):
                        last_active_ts = 0
                    idle_seconds = (now - last_active_ts) if last_active_ts > 0 else None

                    # Calculate connected duration
                    connected_duration = ""
                    try:
                        if connected_at:
                            dur = now - float(connected_at)
                            if dur >= 3600:
                                connected_duration = f"{int(dur // 3600)}h {int((dur % 3600) // 60)}m"
                            elif dur >= 60:
                                connected_duration = f"{int(dur // 60)}m {int(dur % 60)}s"
                            else:
                                connected_duration = f"{int(dur)}s"
                    except (ValueError, TypeError):
                        pass

                    client_info = {
                        "client_id": client_id,
                        "ip": ip,
                        "username": username,
                        "user_agent": user_agent,
                        "connected_at_raw": connected_at,
                        "connected_duration": connected_duration,
                        "bytes_sent": bytes_sent,
                        "is_target_match": matched,
                        "match_reason": match_reason,
                        "match_server": match_server,
                        "idle_seconds": round(idle_seconds, 1) if idle_seconds is not None else None,
                        "in_grace": in_grace,
                        "is_orphan": False,
                        "pool_absent_seconds": None,
                    }
                    channel_clients.append(client_info)

                    # Track and act on matched clients
                    if matched:
                        ck = (channel_uuid, client_id)
                        active_keys.add(ck)
                        should_terminate = False
                        reason = ""

                        if not in_grace:
                            # Check media server pool (if configured)
                            # Only apply pool protection if this client's
                            # identifier matches a configured media server
                            client_pool_channels = self._pool_channels_for_client(
                                ip, username, pool_channels_by_ident
                            )
                            if client_pool_channels is not None:
                                if channel_number not in client_pool_channels:
                                    # Track how long absent from this client's server pool
                                    if ck not in self._idle_since:
                                        self._idle_since[ck] = now
                                        logger.debug(
                                            f"Client {client_id} ({ip}) on CH {channel_number} "
                                            f"not in its media server pool - tracking"
                                        )
                                        client_info["pool_absent_seconds"] = 0
                                    else:
                                        absent_seconds = now - self._idle_since[ck]
                                        client_info["pool_absent_seconds"] = round(absent_seconds, 1)
                                        if absent_seconds >= timeout:
                                            should_terminate = True
                                            reason = (
                                                f"absent from media server pool "
                                                f"{absent_seconds:.0f}s >= {timeout}s timeout"
                                            )
                            elif media_server_channel_numbers is not None:
                                # Media servers configured but this client's IP
                                # doesn't match any -- no pool protection
                                pass

                            # Check idle_seconds (always, regardless of media server)
                            # Use 2x timeout so idle kills are less aggressive
                            # than pool-absent termination.
                            idle_threshold = timeout * 2
                            if (ENABLE_IDLE_TERMINATION
                                    and not should_terminate
                                    and idle_seconds is not None
                                    and idle_seconds >= idle_threshold):
                                should_terminate = True
                                reason = f"idle {idle_seconds:.0f}s >= {idle_threshold}s idle timeout"

                        if should_terminate:
                            sig_key = f"{channel_uuid}:{client_id}"

                            # Set the stop-signal key (idempotent; refreshes
                            # the 30s TTL each cycle while the client persists).
                            self._signal_client_stop(channel_uuid, client_id, redis_client)

                            # Log only once per client_id
                            if sig_key not in self._stop_logged:
                                logger.info(
                                    f"Requesting termination of client {client_id} on CH {channel_number} "
                                    f"({channel_name}): {reason} "
                                    f"(ip={ip}, user={username})"
                                )
                                self._stopped_log.append({
                                    "time": now,
                                    "channel": f"CH {channel_number} ({channel_name})",
                                    "ip": ip,
                                    "username": username,
                                    "reason": reason,
                                })
                                if len(self._stopped_log) > 20:
                                    self._stopped_log = self._stopped_log[-20:]
                                self._stop_logged.add(sig_key)
                        elif not in_grace:
                            # Not terminating - check if tracking should be cleared
                            client_pool_channels = self._pool_channels_for_client(
                                ip, username, pool_channels_by_ident
                            )
                            in_pool = (client_pool_channels is not None
                                       and channel_number in client_pool_channels)
                            not_idle = (idle_seconds is not None and idle_seconds < timeout * 2)
                            if in_pool and not_idle:
                                self._idle_since.pop(ck, None)
                            elif idle_seconds is None and in_pool:
                                # No idle data but channel in pool - safe
                                self._idle_since.pop(ck, None)
                            elif client_pool_channels is None and media_server_channel_numbers is None:
                                # No media server configured at all, track idle start
                                if idle_seconds is not None and ck not in self._idle_since:
                                    self._idle_since[ck] = now

                if channel_clients:
                    scan_result[channel_uuid] = {
                        "channel_name": channel_name,
                        "channel_number": channel_number,
                        "channel_state": ch_state,
                        "in_grace": in_grace,
                        "clients": channel_clients,
                    }

        except Exception as e:
            logger.error(f"Error during poll scan: {e}", exc_info=True)

        # Prune idle_since entries for clients that disappeared
        stale = [k for k in self._idle_since if k not in active_keys]
        for k in stale:
            self._idle_since.pop(k, None)

        # Prune cross-cycle tracking for clients that disappeared from scan
        active_str_keys = {f"{uuid}:{cid}" for uuid, cid in active_keys}
        self._stop_logged = self._stop_logged & active_str_keys

        # ── Media server orphan detection ────────────────────────────────
        if sessions is not None:
            emby_active = self._count_active_streams(sessions)
            self._emby_active_count = emby_active
            self._detect_orphans(scan_result, sessions, now, pool_channels_by_ident, redis_client=redis_client)
        elif self._get_media_server_configs():
            # Configured but fetch failed -- keep last count, don't orphan-kill
            pass
        else:
            self._emby_active_count = None

        # Prune orphaned_since entries for clients that disappeared
        stale_orphans = [k for k in self._orphaned_since if k not in active_keys]
        for k in stale_orphans:
            self._orphaned_since.pop(k, None)

        self._last_scan = scan_result
        self._last_scan_time = now

    # ── Debug state ──────────────────────────────────────────────────────────

    def get_debug_state(self):
        """Return current state for the debug page."""
        servers = self._get_media_server_configs()
        # Build per-server identifier info for display
        all_identifiers = set()
        server_identifiers = {}  # server_num -> set of identifiers
        for url, _key, idents in servers:
            all_identifiers.update(idents)
            # Find the server number from media_server_status
            for ms in self._media_server_status:
                if ms.get("url") == url:
                    server_identifiers[ms["num"]] = sorted(idents)
                    break
        resolved_ips = self._resolve_identifiers(all_identifiers)
        timeout = int(self._settings.get("cleanup_timeout", DEFAULT_CLEANUP_TIMEOUT))
        poll_interval = int(self._settings.get("poll_interval", DEFAULT_POLL_INTERVAL))

        return {
            "running": self._running,
            "scan": self._last_scan,
            "scan_time": self._last_scan_time,
            "timeout": timeout,
            "poll_interval": poll_interval,
            "identifier_configured": bool(all_identifiers),
            "identifiers": sorted(all_identifiers),
            "server_identifiers": server_identifiers,
            "resolved_ips": sorted(resolved_ips) if resolved_ips else [],
            "stopped_log": list(self._stopped_log),
            "emby_configured": bool(servers),
            "emby_active_count": self._emby_active_count,
            "emby_error": self._emby_error,
            "media_servers": list(self._media_server_status),
            "recording_channels": set(self._active_recording_channels),
            "recording_count_by_url": dict(self._recording_count_by_url),
        }
