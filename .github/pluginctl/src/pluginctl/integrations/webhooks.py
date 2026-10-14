"""Signed webhook emitter (new capability).

Emits a compact JSON event to ``WEBHOOK_URL`` signed with ``WEBHOOK_SECRET`` via
HMAC-SHA256 over the raw request body. Both settings are optional: with either
unset, :func:`emit` is a silent no-op. A delivery failure never raises, it logs
a ``::warning::``, so the pipeline is never failed by webhook problems.

Header scheme (documented in docs/webhooks.md for the consuming bot):
  X-PluginCtl-Event      <event name>
  X-PluginCtl-Delivery   <uuid4>
  X-PluginCtl-Signature  sha256=<hex hmac of the raw body>
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..core import actions
from ..core.timeutil import now_iso

USER_AGENT = "pluginctl-webhook/1"


def sign(secret: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` HMAC of ``body`` using ``secret`` (utf-8)."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_envelope(event: str, data: dict, repository: str, actor: str) -> dict:
    return {
        "event": event,
        "delivered_at": now_iso(),
        "repository": repository,
        "actor": actor,
        "data": data,
    }


def emit(event: str, data: dict, *, repository: Optional[str] = None,
         actor: Optional[str] = None, url: Optional[str] = None,
         secret: Optional[str] = None, _opener=None) -> bool:
    """Deliver an event. Returns True if sent, False if skipped or failed.

    Configuration falls back to the environment (``WEBHOOK_URL`` /
    ``WEBHOOK_SECRET`` / ``GITHUB_REPOSITORY`` / ``GITHUB_ACTOR``) so callers can
    pass nothing in CI.
    """
    url = url if url is not None else os.environ.get("WEBHOOK_URL", "")
    secret = secret if secret is not None else os.environ.get("WEBHOOK_SECRET", "")
    repository = repository if repository is not None else os.environ.get("GITHUB_REPOSITORY", "")
    actor = actor if actor is not None else os.environ.get("GITHUB_ACTOR", "")

    if not url or not secret:
        return False

    envelope = build_envelope(event, data, repository, actor)
    body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    delivery = str(uuid.uuid4())
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-PluginCtl-Event": event,
            "X-PluginCtl-Delivery": delivery,
            "X-PluginCtl-Signature": sign(secret, body),
        },
    )
    opener = _opener or urllib.request.urlopen
    try:
        with opener(request, timeout=15) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
        if status and 200 <= int(status) < 300:
            actions.log(f"Webhook '{event}' delivered ({delivery}, HTTP {status}).")
            return True
        actions.warning(f"Webhook '{event}' returned HTTP {status} - ignoring.")
        return False
    except (urllib.error.URLError, OSError, ValueError) as exc:  # never fail the pipeline
        actions.warning(f"Webhook '{event}' delivery failed: {exc}")
        return False


# ---- typed event constructors (thin, so call sites stay readable) -----------
def pr_validated(pr, author, result, plugins, checks) -> dict:
    return {"pr": pr, "author": author, "result": result,
            "plugins": plugins, "checks": checks}


def pr_closed_unauthorized(pr, author, reason) -> dict:
    return {"pr": pr, "author": author, "reason": reason}


def pr_quarantined(pr, author, infected) -> dict:
    return {"pr": pr, "author": author, "infected": infected}


def pr_auto_merged(pr, plugins) -> dict:
    return {"pr": pr, "plugins": plugins}


def plugin_published(plugin, version, pr, actor) -> dict:
    return {"plugin": plugin, "version": version, "pr": pr, "actor": actor}


def plugin_yanked(plugin, version, issue, rollback_pr) -> dict:
    return {"plugin": plugin, "version": version, "issue": issue,
            "rollback_pr": rollback_pr}


# ---- Discord Components V2 --------------------------------------------------
DISCORD_COMPONENTS_V2 = 1 << 15
SUPPORTED_DISCORD_EVENTS = {"plugin.published", "pr.auto_merged", "pr.review_required"}
DISCORD_FALLBACK_THUMBNAIL = "https://cdn.discordapp.com/embed/avatars/5.png?size=512"
DISCORD_LIME = 0xB6E85A
DISCORD_YELLOW = 0xFEE75C


def discord_routes(config: Optional[str] = None) -> dict[str, dict]:
    """Parse the secret JSON routing map, returning only well-formed routes."""
    raw = config if config is not None else os.environ.get("DISCORD_WEBHOOKS", "")
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        actions.warning("DISCORD_WEBHOOKS is not valid JSON; Discord delivery skipped.")
        return {}
    if not isinstance(parsed, dict):
        actions.warning("DISCORD_WEBHOOKS must be a JSON object; Discord delivery skipped.")
        return {}
    routes = {}
    for name, route in parsed.items():
        if (isinstance(route, dict) and isinstance(route.get("url"), str)
                and isinstance(route.get("events"), list)
                and all(isinstance(event, str) for event in route["events"])):
            routes[str(name)] = route
        else:
            actions.warning(f"Ignoring invalid Discord webhook route '{name}'.")
    return routes


def discord_url(url: str) -> str:
    """Add Discord's Components V2 opt-in query argument."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["with_components"] = "true"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def discord_payload(event: str, data: dict, repository: str = "") -> dict:
    """Build a compact Components V2 card. This function performs no IO."""
    if event not in SUPPORTED_DISCORD_EVENTS:
        raise ValueError(f"Unsupported Discord event: {event}")
    releases = data.get("releases") if event == "plugin.published" else None
    if isinstance(releases, list):
        return {"flags": DISCORD_COMPONENTS_V2,
                "components": [discord_payload(event, release, repository)["components"][0]
                               for release in releases]}
    pr = str(data.get("pr") or "")
    pr_url = data.get("pr_url") or (f"https://github.com/{repository}/pull/{pr}" if repository and pr else "")
    if event == "plugin.published":
        release_url = data.get("release_url") or data.get("manifest_url") or pr_url
        name = f"**{data.get('plugin', 'plugin')}**"
        version = f"v{data.get('version', '')}"
        title = f"## {name} [{version}]({release_url})" if release_url else f"## {name} {version}"
        status = "**Plugin Published**"
        metadata = data.get("metadata") or "Refresh the in-app plugin browser to download or update."
    elif event == "pr.auto_merged":
        name = data.get("plugin_name") or (data.get("plugins") or ["Plugin"])[0]
        heading = f"**{name}**"
        title = f"## {heading} [#{pr}]({pr_url})" if pr_url else f"## {heading} #{pr}"
        status = "**Auto Merged**"
        metadata = data.get("source_links") or ""
    else:
        name = data.get("plugin_name") or (data.get("plugins") or ["Plugin"])[0]
        heading = f"**{name}**"
        title = f"## {heading} [#{pr}]({pr_url})" if pr_url else f"## {heading} #{pr}"
        status = "**Manual Review Required**"
        metadata = data.get("source_links") or ""
    plugins = data.get("plugins") or ([] if not data.get("plugin") else [data["plugin"]])
    description = str(data.get("description") or "")
    description = description[:247] + ("..." if len(description) > 247 else "")
    text_components: list[dict] = [{"type": 10, "content": title}]
    text_components.append({"type": 10, "content": f"-# By {data.get('author', 'unknown')}"})
    if description:
        text_components.append({"type": 10, "content": f"*{description}*"})
    section: dict = {"type": 9, "components": text_components}
    logo_url = data.get("logo_url")
    if not isinstance(logo_url, str) or not logo_url.startswith("https://"):
        logo_url = DISCORD_FALLBACK_THUMBNAIL
    section["accessory"] = {"type": 11, "media": {"url": logo_url}}
    components: list[dict] = [
        {"type": 10, "content": status},
        {"type": 14, "divider": True, "spacing": 1},
        section,
    ]
    if metadata:
        components.append({"type": 10, "content": metadata})
    attachment = data.get("attachment_filename")
    if attachment:
        components.append({"type": 13, "file": {"url": f"attachment://{attachment}"}})
    container = {"type": 17, "components": components}
    if event == "pr.auto_merged":
        container["accent_color"] = DISCORD_LIME
    elif event == "pr.review_required":
        container["accent_color"] = DISCORD_YELLOW
    return {"flags": DISCORD_COMPONENTS_V2, "components": [container]}


def emit_discord(event: str, data: dict, *, repository: Optional[str] = None,
                 url: Optional[str] = None, config: Optional[str] = None, _opener=None) -> bool:
    """Best-effort direct Discord delivery to all routes subscribed to ``event``."""
    repository = repository if repository is not None else os.environ.get("GITHUB_REPOSITORY", "")
    urls = [url] if url else [route["url"] for route in discord_routes(config).values()
                              if event in route["events"] or "*" in route["events"]]
    if not urls:
        return False
    payload = discord_payload(event, data, repository)
    attachment_paths = [data.get("attachment_path")] if data.get("attachment_path") else []
    attachment_paths += [release.get("attachment_path") for release in data.get("releases", [])
                         if release.get("attachment_path")]
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if attachment_paths:
        try:
            boundary = f"pluginctl-{uuid.uuid4().hex}"
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
                    f"Content-Type: application/json\r\n\r\n").encode() + body
            for index, attachment_path in enumerate(attachment_paths):
                filename = Path(attachment_path).name
                content = Path(attachment_path).read_bytes()
                body += (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[{index}]\"; "
                         f"filename=\"{filename}\"\r\nContent-Type: application/zip\r\n\r\n").encode() + content
            body += f"\r\n--{boundary}--\r\n".encode()
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        except OSError as exc:
            actions.warning(f"Discord attachment for '{event}' could not be read: {exc}")
            return False
    opener = _opener or urllib.request.urlopen
    delivered = False
    for destination in urls:
        try:
            request = urllib.request.Request(discord_url(destination), data=body, method="POST",
                                             headers=headers)
            with opener(request, timeout=15) as response:
                status = getattr(response, "status", None) or response.getcode()
            delivered |= bool(status and 200 <= int(status) < 300)
            if not (status and 200 <= int(status) < 300):
                actions.warning(f"Discord webhook '{event}' returned HTTP {status} - ignoring.")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
            except OSError:
                detail = ""
            suffix = f" ({detail})" if detail else ""
            actions.warning(f"Discord webhook '{event}' delivery failed: HTTP {exc.code}{suffix}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            actions.warning(f"Discord webhook '{event}' delivery failed: {exc}")
    return delivered
