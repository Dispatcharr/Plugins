[Back to All Plugins](../../README.md)

# Newsflasharr

**Version:** `1.26.2241159` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 12:05 UTC

Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1533575430400114730) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

## Downloads

### Latest Release

- **Download:** [`newsflasharr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2241159/newsflasharr-1.26.2241159.zip)
- **Built:** Aug 12 2026, 12:06 UTC
- **Source Commit:** [`5c239be`](https://github.com/Dispatcharr/Plugins/commit/5c239be35a9e5d5db0cfbf45f36c9217d097631e)

**Checksums:**
```
MD5:    35077cbb21fe71e46e3e0c7bc8a5ac1c
SHA256: aedcc20dc974739bd7cdc92586f565cd847fb2da03edcda448cf6c94996dc2f6
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.26.2241159` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2241159/newsflasharr-1.26.2241159.zip) | Aug 12 2026, 12:06 UTC | [`5c239be`](https://github.com/Dispatcharr/Plugins/commit/5c239be35a9e5d5db0cfbf45f36c9217d097631e) | 35077cbb21fe71e46e3e0c7bc8a5ac1c | aedcc20dc974739bd7cdc92586f565cd847fb2da03edcda448cf6c94996dc2f6 |
| `1.26.2191208` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2191208/newsflasharr-1.26.2191208.zip) | Aug 07 2026, 13:49 UTC | [`1df507c`](https://github.com/Dispatcharr/Plugins/commit/1df507c31074da7de450b53082a325fe8e604644) | 5e9a3272ce95845282e4e2f85302db2d | ee926fe8a4bd90518ac00bce29edfdbe8eba84471b802a3a870b8c90d087b6ae |
| `1.26.2171427` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2171427/newsflasharr-1.26.2171427.zip) | Aug 06 2026, 11:42 UTC | [`b8b1f11`](https://github.com/Dispatcharr/Plugins/commit/b8b1f116536b65e2a4394e55491240254d1075a3) | ecf6724f53f31440ff94a76eeef820bf | fac709e3810574cb727d92218fb7308519c2ba65c989bd0144cf535c9d9c11da |
| `1.26.2142011` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2142011/newsflasharr-1.26.2142011.zip) | Aug 02 2026, 20:37 UTC | [`b8a8998`](https://github.com/Dispatcharr/Plugins/commit/b8a8998fd68c1f4ca9491576c11658ead84ed633) | 8d0e25158ba305752e053e7f76922034 | a056087da39ca2dc2fcdd89c2debf2218e20233438a6894254f9f3fc471f97f4 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/newsflasharr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Newsflasharr

Central notification service for Dispatcharr plugins. One plugin owns all
delivery: other plugins drop lightweight events into a file queue, and
Newsflasharr routes them to Discord, a generic webhook, ntfy, Apprise, email,
or a banner drawn over live video. Configured once, in one place, instead of
every plugin re-inventing its own webhook code.

## What it does

- **A calling plugin makes one call and is finished.** That call never blocks
  and never raises, so a caller is unaffected even when Newsflasharr is not
  running.
- **Repeats collapse instead of flooding you.** The same alert arriving over
  and over becomes one message, then a summary when the window closes. An
  alert that gets worse breaks the window and is sent at once, so a warning
  can never swallow the critical that follows it.
- **Quiet hours, an hourly cap and per-channel retry** are configured here
  rather than separately in every plugin.
- **Your provider hostnames are removed from outgoing messages**, using the
  electronic programme guide sources and accounts Dispatcharr already holds.
- **It is read-only on Dispatcharr.** It writes nothing outside its own
  directory, and it never creates or edits an output profile, a channel or a
  stream.

## After installing

**Restart the Dispatcharr container.** This is not optional. The worker that
delivers events starts when the plugin is constructed, and without a restart
the plugin loads and looks healthy while nothing is delivered.

Then enable the plugin, fill in at least one channel, click **Validate
settings**, and click **Send test notification** for each channel you
configured. Saving the settings form on its own arms nothing, because
Dispatcharr gives plugins no hook that runs after a save, and only a real send
proves a channel works.

## Two things to know before relying on it

- **Delivery is at-least-once per channel.** A duplicate is possible after a
  crash. That is a deliberate tradeoff, not a defect.
- **Email is the one channel where a successful send can still be a lie.** A
  mail server accepting a message says nothing about spam filtering. Check the
  inbox and the spam folder before trusting that channel.

## Documentation

Full documentation lives in the plugin's own repository:

- [User guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md)
  for setting up channels, routing rules, quiet hours, redaction, the
  on-screen banner, and a troubleshooting ladder.
- [Caller API](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/API.md)
  for plugin authors who want to send notifications through it.
- [Developer guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/DEVELOPER-GUIDE.md)
  for working on the plugin itself.

Licensed MIT. Source:
<https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin>
