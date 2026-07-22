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

import datetime
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional

from ..core import actions

USER_AGENT = "pluginctl-webhook/1"


def sign(secret: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` HMAC of ``body`` using ``secret`` (utf-8)."""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def build_envelope(event: str, data: dict, repository: str, actor: str) -> dict:
    return {
        "event": event,
        "delivered_at": datetime.datetime.now(datetime.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
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
