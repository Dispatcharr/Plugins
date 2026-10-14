# Plugin registry webhooks

`pluginctl` can emit a signed JSON event after key lifecycle points so an
external consumer (for example a Discord bot) can react to registry activity.

Emission is **opt-in and best-effort**:

- Configure two repository settings: `secrets.WEBHOOK_SECRET` and
  `vars.WEBHOOK_URL`.
- If either is unset, emission is a silent no-op.
- A delivery failure never fails the pipeline, it logs a `::warning::` and the
  workflow continues.

## Discord Components V2

Discord delivery is separate from the signed generic webhook above. Configure
the `DISCORD_WEBHOOKS` **repository secret** as a JSON routing map. Webhook URLs
are credentials and must never be stored in repository variables.

```json
{
  "releases": {"url": "https://discord.com/api/webhooks/...", "events": ["plugin.published"]},
  "maintainers": {"url": "https://discord.com/api/webhooks/...", "events": ["pr.auto_merged", "pr.review_required"]},
  "audit": {"url": "https://discord.com/api/webhooks/...", "events": ["*"]}
}
```

Supported events are `plugin.published`, `pr.auto_merged`, and
`pr.review_required`. Each matching route receives a Components V2 card. A
route containing `"*"` receives every supported event.

Preview without sending:

```bash
PYTHONPATH=.github/pluginctl/src python -m pluginctl discord-webhook --event plugin.published
PYTHONPATH=.github/pluginctl/src python -m pluginctl discord-webhook --event pr.review_required --random
```

Use `--send --webhook-url <url>` for a one-off destination, or set
`DISCORD_WEBHOOKS` for configured routes. Passing URLs on the command line can
expose their credentials in shell history, so environment configuration is
preferred.

## Transport

Each event is a single `POST` to `WEBHOOK_URL` with a compact JSON body and
these headers:

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-PluginCtl-Event` | the event name (e.g. `plugin.published`) |
| `X-PluginCtl-Delivery` | a per-delivery UUIDv4 |
| `X-PluginCtl-Signature` | `sha256=<hex>` HMAC-SHA256 of the **raw request body** using `WEBHOOK_SECRET` |

Verify the signature over the exact bytes received, before parsing JSON.

## Envelope

```json
{
  "event": "plugin.published",
  "delivered_at": "2026-07-21T12:00:00Z",
  "repository": "Dispatcharr/Plugins",
  "actor": "octocat",
  "data": { }
}
```

## Events

| Event | `data` fields |
|---|---|
| `pr.validated` | `pr`, `author`, `result` (`pass`\|`fail`), `plugins[]`, `checks` (`{codeql,clamav,title}`) |
| `pr.closed_unauthorized` | `pr`, `author`, `reason` |
| `pr.quarantined` | `pr`, `author`, `infected` |
| `pr.auto_merged` | `pr`, `plugins[]` |
| `plugin.published` | `plugin`, `version`, `pr`, `actor` (one per changed plugin) |
| `plugin.yanked` | `plugin`, `version`, `issue`, `rollback_pr` |

## Reference verifier

The signature is HMAC-SHA256 of the raw body. Any language works; here is the
Python equivalent of what the consumer must do:

```python
import hashlib
import hmac

def verify(secret: str, raw_body: bytes, signature_header: str) -> bool:
    """signature_header is the value of X-PluginCtl-Signature, e.g. 'sha256=abcd...'."""
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256="):])
```

Node.js:

```js
const crypto = require("crypto");

function verify(secret, rawBody, signatureHeader) {
  if (!signatureHeader.startsWith("sha256=")) return false;
  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const got = signatureHeader.slice("sha256=".length);
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(got));
}
```

Always compare with a constant-time function (`hmac.compare_digest` /
`crypto.timingSafeEqual`).
