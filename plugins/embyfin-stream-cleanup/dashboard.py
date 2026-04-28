"""Debug dashboard HTML rendering.

All page generation for the debug server lives here.  The server module
(server.py) handles lifecycle and WSGI plumbing and delegates to these
functions for actual content.
"""

import re
import time

from .config import PLUGIN_CONFIG

# ── Masking helpers ──────────────────────────────────────────────────────────

_IP_RE = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')


def _mask_ip(ip):
    """Mask an IP address, keeping the first octet: 192.168.1.50 → 192.*.*.*"""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.*.*.*"
    return "***"


def _mask_url(url):
    """Mask the host portion of a URL: http://192.168.1.50:8096 → http://192.*.*.*:8096"""
    if not url or url == "?":
        return url
    m = re.match(r'(https?://)(.+?)(\:\d+)?(/.*)?\s*$', url, re.IGNORECASE)
    if m:
        scheme, host, port, path = m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""
        if _IP_RE.fullmatch(host):
            host = _mask_ip(host)
        else:
            host = "***"
        return f"{scheme}{host}{port}{path}"
    return "***"


def _mask_username(username):
    """Mask a username: alice → a***e, ab → a*"""
    if not username:
        return username
    if len(username) <= 2:
        return username[0] + "*"
    return username[0] + "***" + username[-1]


# ── Server type registry ────────────────────────────────────────────────────
# Each instance defines visual attributes for a media server type.
# To add a new server type, add an instance here. Everything else adapts.


def _svg(inner, css_class, suffix=""):
    """Wrap SVG inner content in a sized <svg> element."""
    return (
        f'<svg class="{css_class}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'{inner.format(suffix=suffix)}</svg>'
    )


class ServerType:
    """Visual attributes for a media server type."""

    def __init__(self, color, css_class, icon_paths=""):
        self.color = color
        self.css_class = css_class
        self._icon_paths = icon_paths

    @property
    def icon_lg(self):
        if not self._icon_paths:
            return ""
        return _svg(self._icon_paths, "srv-icon", suffix="l") + " "

    @property
    def icon_sm(self):
        if not self._icon_paths:
            return ""
        return _svg(self._icon_paths, "srv-icon-sm", suffix="s")


EMBY = ServerType(
    color="#52b54b",
    css_class="srv-emby",
    icon_paths=(
        '<path d="m97.1 229.4 26.5 26.5L0 379.5l132.4 132.4 26.5-26.5L282.5 609l141.2-141.2'
        '-26.5-26.5L512 326.5 379.6 194.1l-26.5 26.5L229.5 97z" style="fill:#52b54b" '
        'transform="translate(0 -97)"/>'
        '<path d="M196.8 351.2v-193L366 254.7 281.4 303z" style="fill:#fff"/>'
    ),
)

JELLYFIN = ServerType(
    color="#aa5cc3",
    css_class="srv-jellyfin",
    icon_paths=(
        '<linearGradient id="jf{suffix}-a" x1="97.508" x2="522.069" y1="308.135" y2="63.019" '
        'gradientTransform="matrix(1 0 0 -1 0 514)" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" style="stop-color:#aa5cc3"/><stop offset="1" style="stop-color:#00a4dc"/>'
        '</linearGradient>'
        '<path d="M256 196.2c-22.4 0-94.8 131.3-83.8 153.4s156.8 21.9 167.7 0-61.3-153.4-83.9-153.4" '
        'style="fill:url(#jf{suffix}-a)"/>'
        '<linearGradient id="jf{suffix}-b" x1="94.193" x2="518.754" y1="302.394" y2="57.278" '
        'gradientTransform="matrix(1 0 0 -1 0 514)" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" style="stop-color:#aa5cc3"/><stop offset="1" style="stop-color:#00a4dc"/>'
        '</linearGradient>'
        '<path d="M256 0C188.3 0-29.8 395.4 3.4 462.2s472.3 66 505.2 0S323.8 0 256 0m165.6 404.3'
        'c-21.6 43.2-309.3 43.8-331.1 0S211.7 101.4 256 101.4 443.2 361 421.6 404.3" '
        'style="fill:url(#jf{suffix}-b)"/>'
    ),
)

UNKNOWN = ServerType(
    color="#888",
    css_class="srv-unknown",
)

SERVER_TYPES = {
    "Emby": EMBY,
    "Jellyfin": JELLYFIN,
}


def _get_server_type(type_name):
    """Look up server type by name, falling back to UNKNOWN."""
    return SERVER_TYPES.get(type_name, UNKNOWN)


def _server_badge(match_server):
    """Build inline server icon + name HTML for match labels."""
    if not match_server:
        return ""
    srv_type = match_server.get("type")
    srv_name = match_server.get("name")
    if not srv_name and not srv_type:
        return ""
    st = _get_server_type(srv_type)
    icon = (st.icon_sm + " ") if st.icon_sm else ""
    label = srv_name or srv_type
    return f'{icon}<span style="color:{st.color}">{label}</span> - '


# ── Client row rendering ────────────────────────────────────────────────────

def render_client_row(client, is_match, timeout=30, poll_interval=10, mask=False):
    """Render a single Dispatcharr client as an HTML row."""
    row_class = "match" if is_match else "unmonitored"
    ip = client.get("ip", "?")
    username = client.get("username", "")
    if mask:
        ip = _mask_ip(ip) if ip != "?" else ip
        username = _mask_username(username) if username else username
    user_agent = client.get("user_agent", "")
    duration = client.get("connected_duration", "")
    match_reason = client.get("match_reason", "")
    match_server = client.get("match_server")
    idle_seconds = client.get("idle_seconds")
    in_grace = client.get("in_grace", False)
    # Don't consider a client idle unless it has been inactive
    # longer than the poll interval; anything below that is just
    # normal jitter between data chunks.
    is_idle = idle_seconds is not None and idle_seconds >= poll_interval

    if mask and match_reason:
        def _mask_match_reason(m):
            val = m.group(1)
            if _IP_RE.fullmatch(val):
                return f"({_mask_ip(val)})"
            return f"({_mask_username(val)})"
        match_reason = re.sub(r'\(([^)]+)\)', _mask_match_reason, match_reason)

    label_html = ""
    srv_badge = _server_badge(match_server) if is_match else ""
    if is_match:
        pool_absent = client.get("pool_absent_seconds")
        if client.get("is_orphan"):
            label_html = f'<span class="match-reason orphan-warn">ORPHAN - {srv_badge}{match_reason} (no active media server session - will terminate)</span>'
        elif in_grace and is_idle and idle_seconds >= timeout:
            label_html = f'<span class="match-reason" style="color:#1565c0">GRACE PERIOD - {srv_badge}{match_reason} (idle {int(idle_seconds)}s - termination paused)</span>'
        elif idle_seconds is not None and idle_seconds >= timeout:
            label_html = f'<span class="match-reason idle-warn">WILL TERMINATE - {srv_badge}{match_reason} (idle {int(idle_seconds)}s / {timeout}s timeout)</span>'
        elif pool_absent is not None and pool_absent >= timeout:
            label_html = f'<span class="match-reason idle-warn">WILL TERMINATE - {srv_badge}{match_reason} (absent from pool {int(pool_absent)}s / {timeout}s timeout)</span>'
        elif pool_absent is not None:
            label_html = f'<span class="match-reason">MONITORED - {srv_badge}{match_reason} - absent from pool {int(pool_absent)}s</span>'
        elif is_idle:
            label_html = f'<span class="match-reason">MONITORED - {srv_badge}{match_reason} - idle {int(idle_seconds)}s</span>'
        else:
            row_class = "compliant"
            label_html = f'<span class="match-reason streaming">{srv_badge}{match_reason}</span>'
    else:
        label_html = '<span class="unmonitored-label">UNMONITORED</span>'

    fields = [f'<span class="client-field"><span class="label">IP:</span> <span class="value">{ip}</span></span>']
    if username:
        fields.append(f'<span class="client-field"><span class="label">User:</span> <span class="value">{username}</span></span>')
    if duration:
        fields.append(f'<span class="client-field"><span class="label">Connected:</span> <span class="value">{duration}</span></span>')

    return f'''<div class="client-row {row_class}">
        {label_html}
        <div class="client-detail">{"".join(fields)}</div>
    </div>'''


# ── Debug page ───────────────────────────────────────────────────────────────

def render_debug_page(debug_state, settings):
    """Build the full debug dashboard HTML from monitor state.

    Returns the HTML as a string.
    """
    now = time.time()
    plugin_name = PLUGIN_CONFIG.get('name', 'Emby Stream Cleanup')
    mask = settings.get("mask_sensitive_data", False)
    timeout = debug_state.get("timeout", 30)
    poll_interval = debug_state.get("poll_interval", 10)
    monitor_running = debug_state.get("running", False)

    # Monitor status
    monitor_badge = (
        '<span class="badge active">Running</span>' if monitor_running
        else '<span class="badge idle">Stopped</span>'
    )

    # Media server status
    emby_configured = debug_state.get("emby_configured", False)
    emby_active_count = debug_state.get("emby_active_count")
    emby_error = debug_state.get("emby_error")
    media_servers = debug_state.get("media_servers", [])
    recording_count_by_url = debug_state.get("recording_count_by_url", {})
    total_recordings = sum(recording_count_by_url.values())
    emby_html = ""
    media_server_cards = ""
    if emby_configured:
        if emby_error:
            emby_html = '<tr><td>Media Server Pool</td><td><span class="warn">Error (see below)</span></td></tr>'
        elif emby_active_count is not None:
            total_pool = emby_active_count + total_recordings
            emby_html = f'<tr><td>Media Server Pool</td><td><span>{total_pool} session(s)</span></td></tr>'
        else:
            emby_html = '<tr><td>Media Server Pool</td><td><span>Connecting...</span></td></tr>'

        # Build per-server cards
        if media_servers:
            media_server_cards = '<h2>Media Servers</h2>'
            server_identifiers = debug_state.get("server_identifiers", {})
            for srv in media_servers:
                srv_num = srv.get("num", "?")
                srv_type = srv.get("type")
                srv_name = srv.get("name")
                srv_url = srv.get("url", "")
                st = _get_server_type(srv_type)
                srv_label = srv_name or f'Server {srv_num}'
                srv_icon = st.icon_lg
                if not srv_name and srv_type:
                    srv_label += f' ({srv_type})'
                srv_url_display = _mask_url(srv_url) if mask else srv_url
                srv_idents = server_identifiers.get(srv_num, [])
                idents_display = ", ".join(
                    (_mask_ip(i) if _IP_RE.fullmatch(i) else _mask_username(i)) if mask else i
                    for i in srv_idents
                ).upper() if srv_idents else "(no identifier)"
                srv_active = srv.get("active")
                srv_error = srv.get("error")
                srv_rec_count = recording_count_by_url.get(srv_url, 0)
                if srv_error:
                    srv_class = "srv-unknown"
                    srv_badge = '<span class="badge pending">Error</span>'
                    err_display = _mask_url(srv_error) if mask else srv_error
                    srv_detail = f'<span class="warn">{err_display}</span>'
                elif srv_active is not None:
                    srv_class = st.css_class
                    srv_total = srv_active + srv_rec_count
                    srv_badge = f'<span class="badge active">{srv_total} session(s)</span>'
                    rec_detail = f' ({srv_active} live, {srv_rec_count} DVR)' if srv_rec_count else ""
                    srv_detail = f'{srv_total} active stream(s) detected{rec_detail}'
                else:
                    srv_class = "srv-unknown"
                    srv_badge = '<span class="badge idle">Connecting</span>'
                    srv_detail = 'Waiting for first poll...'
                media_server_cards += (
                    f'<div class="card {srv_class}">'
                    f'<div class="card-header">'
                    f'<span class="channel-num">{srv_icon}{srv_label}</span>'
                    f'{srv_badge}'
                    f'</div>'
                    f'<div class="status-desc">{srv_url_display} - {srv_detail}</div>'
                    f'<div class="status-desc">Identifier: <strong>{idents_display}</strong></div>'
                    f'</div>'
                )

    # Build channel cards from last scan
    scan = debug_state.get("scan", {})
    recording_channels = debug_state.get("recording_channels", set())
    channels_html = ""
    if scan:
        for ch_uuid, ch_data in sorted(scan.items(), key=lambda x: x[1].get("channel_number", "")):
            channel_name = ch_data.get("channel_name", "")
            channel_number = ch_data.get("channel_number", "?")
            ch_in_grace = ch_data.get("in_grace", False)
            ch_state = ch_data.get("channel_state", "")
            clients = ch_data.get("clients", [])

            matched_clients = [c for c in clients if c.get("is_target_match")]
            other_clients = [c for c in clients if not c.get("is_target_match")]

            # Determine card status based on idle state of matched clients
            has_idle = any(
                (c.get("idle_seconds") or 0) >= poll_interval
                for c in matched_clients
            )

            if ch_in_grace:
                status_class = "grace"
                status_label = f"Grace period ({ch_state})"
                status_desc = "Channel is buffering or switching streams - terminations paused"
            elif has_idle:
                status_class = "pending"
                status_label = "Idle matched clients detected"
                status_desc = "Matching clients will be terminated when timeout expires"
            elif matched_clients:
                status_class = "active"
                status_label = f"{len(matched_clients)} matched client(s) active"
                status_desc = "Clients are streaming data normally"
            else:
                status_class = "idle"
                status_label = "No matched clients"
                status_desc = "No clients on this channel match the configured identifier"

            name_html = f' <span class="channel-name">{channel_name}</span>' if channel_name else ""
            is_recording = channel_number in recording_channels
            rec_badge = ' <span class="badge rec" title="Active DVR recording">&#9679; DVR</span>' if is_recording else ""
            card_html = f'''
            <div class="card {status_class}">
                <div class="card-header">
                    <span class="channel-num">CH {channel_number}{name_html}{rec_badge}</span>
                    <span class="badge {status_class}">{status_label}</span>
                </div>
                <div class="status-desc">{status_desc}</div>'''

            if matched_clients:
                card_html += f'<div class="section-label target">Matched Clients ({len(matched_clients)})</div>'
                if ch_in_grace:
                    card_html += '<div class="client-note grace-note">Terminations PAUSED during failover/buffering</div>'
                elif has_idle:
                    card_html += '<div class="client-note target-note">Idle clients WILL be terminated after timeout</div>'
                for c in matched_clients:
                    card_html += render_client_row(c, is_match=True, timeout=timeout, poll_interval=poll_interval, mask=mask)

            if other_clients:
                card_html += f'<div class="section-label other">Other Clients ({len(other_clients)})</div>'
                card_html += '<div class="client-note other-note">These connections are not monitored</div>'
                for c in other_clients:
                    card_html += render_client_row(c, is_match=False, timeout=timeout, mask=mask)

            card_html += '</div>'
            channels_html += card_html
    else:
        channels_html = '<div class="empty">No active channels with clients found.</div>'

    # Recent terminations
    stopped_log = debug_state.get("stopped_log", [])
    log_html = ""
    if stopped_log:
        log_html = '<h2>Recent Terminations</h2>'
        for entry in reversed(stopped_log):
            from datetime import datetime, timezone
            ts = entry.get("time", 0)
            ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%H:%M:%S UTC')
            ago = int(now - ts)
            reason = entry.get("reason", "idle")
            is_orphan = reason.startswith("orphan")
            reason_label = '<span class="orphan-warn">[ORPHAN]</span> ' if is_orphan else ""
            log_ip = _mask_ip(entry.get("ip", "?")) if mask else entry.get("ip", "?")
            log_user = _mask_username(entry.get("username", "?")) if mask else entry.get("username", "?")
            log_html += (
                f'<div class="log-entry">'
                f'<span class="log-time">{ts_str} ({ago}s ago)</span> '
                f'{reason_label}'
                f'{entry.get("channel", "?")} '
                f'<span class="log-detail">ip={log_ip} '
                f'user={log_user} '
                f'{reason}</span>'
                f'</div>'
            )

    # Last scan time
    scan_time = debug_state.get("scan_time", 0)
    scan_ago = f"{int(now - scan_time)}s ago" if scan_time > 0 else "never"

    refresh_interval = min(poll_interval, 5)

    return _debug_html(
        plugin_name, monitor_badge,
        timeout, poll_interval, scan_ago, channels_html, log_html,
        refresh_interval, emby_html, media_server_cards
    )


def _debug_html(plugin_name, monitor_badge,
                timeout, poll_interval, scan_ago, channels_html, log_html,
                refresh_interval, emby_html, media_server_cards):
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{plugin_name} - Debug</title>
    <meta http-equiv="refresh" content="{refresh_interval}">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #e0e0e0;
        }}
        .container {{
            background: #16213e;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }}
        h1 {{ margin-top: 0; color: #e0e0e0; font-size: 22px; }}
        h2 {{ color: #a0a0b0; font-size: 16px; margin-top: 25px; border-bottom: 1px solid #2a2a4a; padding-bottom: 8px; }}
        .nav {{ margin-bottom: 20px; font-size: 13px; }}
        a {{ color: #64b5f6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .config-table {{ font-size: 13px; color: #a0a0b0; margin-bottom: 20px; width: 100%; }}
        .config-table td {{ padding: 3px 0; }}
        .config-table td:first-child {{ color: #707090; width: 140px; }}
        .config-table span {{ color: #e0e0e0; font-weight: 500; }}
        .explainer {{
            background: #1a2744;
            border: 1px solid #2a3a5a;
            border-radius: 6px;
            padding: 14px 16px;
            font-size: 13px;
            color: #90b0d0;
            margin-bottom: 20px;
            line-height: 1.6;
        }}
        .explainer strong {{ color: #b0d0f0; }}
        .card {{
            border: 1px solid #2a2a4a;
            border-radius: 6px;
            padding: 14px 18px;
            margin-bottom: 12px;
            background: #1c2541;
        }}
        .card.active {{ border-left: 4px solid #4caf50; }}
        .card.pending {{ border-left: 4px solid #ff9800; }}
        .card.idle {{ border-left: 4px solid #555; }}
        .card.grace {{ border-left: 4px solid #42a5f5; }}
        .card.srv-emby {{ border-left: 4px solid #52b54b; }}
        .card.srv-jellyfin {{ border-left: 4px solid #aa5cc3; }}
        .card.srv-unknown {{ border-left: 4px solid #555; }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .channel-num {{ font-weight: 600; font-size: 15px; color: #e0e0e0; display: flex; align-items: center; gap: 6px; }}
        .srv-icon {{ width: 20px; height: 20px; flex-shrink: 0; }}
        .srv-icon-sm {{ width: 10px; height: 10px; vertical-align: -1px; flex-shrink: 0; }}
        .channel-name {{ font-weight: 400; color: #707090; font-size: 13px; margin-left: 6px; }}
        .status-desc {{ font-size: 12px; color: #707090; margin-top: 4px; font-style: italic; }}
        .badge {{
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 500;
            white-space: nowrap;
        }}
        .badge.active {{ background: #1b3a1b; color: #66bb6a; }}
        .badge.pending {{ background: #3a2a10; color: #ffb74d; }}
        .badge.idle {{ background: #2a2a2a; color: #888; }}
        .badge.grace {{ background: #1a2a3a; color: #64b5f6; }}
        .badge.rec {{ background: #3a1a1a; color: #ef5350; font-size: 11px; padding: 2px 7px; }}
        .grace-note {{ color: #64b5f6; }}
        .section-label {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 12px;
            margin-bottom: 4px;
            padding-top: 10px;
            border-top: 1px solid #2a2a4a;
        }}
        .section-label.target {{ color: #e0e0e0; }}
        .section-label.other {{ color: #707090; }}
        .client-note {{
            font-size: 11px;
            font-style: italic;
            margin-bottom: 6px;
        }}
        .target-note {{ color: #ffb74d; }}
        .other-note {{ color: #707090; }}
        .client-row {{
            font-size: 12px;
            padding: 6px 10px;
            margin: 3px 0;
            border-radius: 4px;
            font-family: monospace;
        }}
        .client-row.match {{
            background: #2a2010;
            border: 1px solid #4a3a1a;
        }}
        .client-row.compliant {{
            background: #1a2a1a;
            border: 1px solid #2a4a2a;
        }}
        .client-row.unmonitored {{
            background: #1e1e2e;
            border: 1px solid #333;
        }}
        .client-detail {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px 16px;
        }}
        .client-field {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 11px;
        }}
        .client-field .label {{ color: #707090; }}
        .client-field .value {{ color: #e0e0e0; font-weight: 500; }}
        .match-reason {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 11px;
            color: #ffb74d;
            font-weight: 500;
        }}
        .unmonitored-label {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            font-size: 11px;
            color: #707090;
            font-weight: 500;
        }}
        .match-reason.streaming {{
            color: #66bb6a;
        }}
        .idle-warn {{
            color: #ffb74d;
            font-weight: 600;
        }}
        .orphan-warn {{
            color: #ef5350;
            font-weight: 600;
        }}
        .empty {{ color: #707090; font-style: italic; padding: 20px 0; text-align: center; }}
        .refresh-note {{ font-size: 11px; color: #505060; text-align: center; margin-top: 15px; }}
        .warn {{ color: #ffb74d; font-weight: 500; }}
        .log-entry {{
            font-size: 12px;
            padding: 4px 0;
            border-bottom: 1px solid #2a2a4a;
        }}
        .log-time {{ color: #707090; font-size: 11px; }}
        .log-detail {{ color: #a0a0b0; font-family: monospace; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="nav"><a href="/">&larr; Home</a></div>
        <h1>Debug {monitor_badge}</h1>

        <table class="config-table">
            <tr><td>Timeout</td><td><span>{timeout}s</span></td></tr>
            <tr><td>Poll Interval</td><td><span>{poll_interval}s</span></td></tr>
            <tr><td>Last Scan</td><td><span>{scan_ago}</span></td></tr>
            {emby_html}
        </table>

        <div class="explainer">
            <strong>How it works:</strong>
            The monitor polls all active Dispatcharr channels every <strong>{poll_interval}s</strong>.
            Each configured media server has client identifiers that link its session pool to
            Dispatcharr connections. When a connection's channel is no longer in its server's
            active session pool for <strong>{timeout}s</strong>, the connection is terminated.
            Connections with no data flowing are terminated after <strong>{timeout * 2}s</strong>.
            Orphaned connections (no matching media server session) are also cleaned up.
            Non-matching clients are <strong>never</strong> affected.
        </div>

        {media_server_cards}

        <h2>Active Channels</h2>
        {channels_html}
        {log_html}
        <div class="refresh-note">Auto-refreshes every {refresh_interval} seconds</div>
    </div>
</body>
</html>"""


# ── Landing page ─────────────────────────────────────────────────────────────

def render_landing_page(monitor):
    """Build the landing page HTML.

    Returns the HTML as a string.
    """
    plugin_name = PLUGIN_CONFIG.get('name', 'Emby Stream Cleanup')
    plugin_version = PLUGIN_CONFIG.get('version', 'unknown version').lstrip('-')
    plugin_description = PLUGIN_CONFIG.get('description', '')
    repo_url = PLUGIN_CONFIG.get('repo_url', 'https://github.com/sethwv/emby-stream-cleanup')

    monitor_status = "Running" if monitor.is_running() else "Stopped"

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{plugin_name}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            background: #1a1a2e;
            color: #e0e0e0;
        }}
        .container {{
            background: #16213e;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }}
        h1 {{ margin-top: 0; color: #e0e0e0; }}
        .version {{ color: #707090; font-size: 14px; margin-top: -10px; margin-bottom: 20px; }}
        p {{ color: #a0a0b0; line-height: 1.6; }}
        a {{ color: #64b5f6; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .links {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #2a2a4a; }}
        .links a {{ display: inline-block; margin-right: 20px; font-weight: 500; }}
        .status {{ font-size: 13px; color: #a0a0b0; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{plugin_name}</h1>
        <div class="version">{plugin_version}</div>
        <p>{plugin_description}</p>
        <p class="status">Monitor: <strong>{monitor_status}</strong></p>
        <div class="links">
            <a href="/debug">Debug Dashboard</a>
            <a href="/health">Health Check</a>
            <a href="{repo_url}" target="_blank">GitHub</a>
        </div>
    </div>
</body>
</html>"""
