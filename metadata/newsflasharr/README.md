[Back to All Plugins](../../README.md)

# Newsflasharr

**Version:** `1.26.2821932` | **Author:** PiratesIRC | **Last Updated:** Oct 09 2026, 19:57 UTC

Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, a Dispatcharr Connect Integration, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1533575430400114730) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

## Downloads

### Latest Release

- **Download:** [`newsflasharr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2821932/newsflasharr-1.26.2821932.zip)
- **Built:** Oct 09 2026, 19:58 UTC
- **Source Commit:** [`a495c83`](https://github.com/Dispatcharr/Plugins/commit/a495c83cccc3b7157f91c882097d8066ccd636f7)

**Checksums:**
```
MD5:    1079635341f319eeb4fa61bea2a5a3a1
SHA256: 057f7b59bdb5e429ee7e74446f2ba18fd3bd255246aa2b7e4a195ae46828778d
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.26.2821932` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2821932/newsflasharr-1.26.2821932.zip) | Oct 09 2026, 19:58 UTC | [`a495c83`](https://github.com/Dispatcharr/Plugins/commit/a495c83cccc3b7157f91c882097d8066ccd636f7) | 1079635341f319eeb4fa61bea2a5a3a1 | 057f7b59bdb5e429ee7e74446f2ba18fd3bd255246aa2b7e4a195ae46828778d |
| `1.26.2481646` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2481646/newsflasharr-1.26.2481646.zip) | Sep 05 2026, 17:22 UTC | [`c6b7006`](https://github.com/Dispatcharr/Plugins/commit/c6b7006471cbd1d5f99533347a07b6f05342a084) | a71e154142d18e3b1612521562af1066 | 1dec53fd867101fef01e44cc4dfe1bfdd2e822987712f2d34c5911b1d55757c4 |
| `1.26.2241159` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2241159/newsflasharr-1.26.2241159.zip) | Aug 12 2026, 12:06 UTC | [`5c239be`](https://github.com/Dispatcharr/Plugins/commit/5c239be35a9e5d5db0cfbf45f36c9217d097631e) | 35077cbb21fe71e46e3e0c7bc8a5ac1c | aedcc20dc974739bd7cdc92586f565cd847fb2da03edcda448cf6c94996dc2f6 |
| `1.26.2191208` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2191208/newsflasharr-1.26.2191208.zip) | Aug 07 2026, 13:49 UTC | [`1df507c`](https://github.com/Dispatcharr/Plugins/commit/1df507c31074da7de450b53082a325fe8e604644) | 5e9a3272ce95845282e4e2f85302db2d | ee926fe8a4bd90518ac00bce29edfdbe8eba84471b802a3a870b8c90d087b6ae |
| `1.26.2171427` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2171427/newsflasharr-1.26.2171427.zip) | Aug 06 2026, 11:42 UTC | [`b8b1f11`](https://github.com/Dispatcharr/Plugins/commit/b8b1f116536b65e2a4394e55491240254d1075a3) | ecf6724f53f31440ff94a76eeef820bf | fac709e3810574cb727d92218fb7308519c2ba65c989bd0144cf535c9d9c11da |
| `1.26.2142011` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2142011/newsflasharr-1.26.2142011.zip) | Aug 02 2026, 20:37 UTC | [`b8a8998`](https://github.com/Dispatcharr/Plugins/commit/b8a8998fd68c1f4ca9491576c11658ead84ed633) | 8d0e25158ba305752e053e7f76922034 | a056087da39ca2dc2fcdd89c2debf2218e20233438a6894254f9f3fc471f97f4 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/newsflasharr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

<!-- The logo sits ABOVE the title, not floated beside it. GitHub draws a
     full-width rule under a level-1 heading, and align="right" floats the
     image into that rule, so the line appeared to run through the logo. -->
<p align="center">
  <img src="https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/main/newsflasharr/logo.png" alt="Newsflasharr" width="128">
</p>

<h1 align="center">Newsflasharr</h1>

> [!TIP]
> **New to Dispatcharr plugins?** Start with the **[Dispatcharr Plugin Workflow guide](https://piratesirc.github.io/Dispatcharr-Plugin-Workflow/)**.
> It explains what each plugin and tool does, where they overlap, and what order to use them in.

<sub>The **newsflashes** badge is the number of notifications Newsflasharr has delivered on the maintainer's own installation, counted from its delivery ledger and refreshed twice a day. One notification that went to several channels at once counts once, whether it left over Apprise, email, a Discord or generic webhook, a Dispatcharr Connect Integration, ntfy, or the on-screen ticker. Duplicates collapsed into a digest, banners the ticker declined, events no rule routed anywhere, and anything that failed are all excluded, so the number is deliveries rather than activity. It is one installation's total, not a project metric.</sub>

Central notification service for Dispatcharr plugins. One plugin
owns all delivery: other plugins (Sentinelarr, Dustarr, Stream-Mapparr, ...)
drop lightweight JSON events into a file spool; Newsflasharr routes them to
any of seven destinations (Discord, a generic webhook, a Dispatcharr Connect
Integration, ntfy, Apprise, email, and an on-screen banner over live video)
with deduplication, storm throttling,
quiet hours, and retry. Configured once, in one place, instead of every plugin
re-inventing its own webhook code.

This page covers what the plugin is and what it does. Setting it up lives in
the **[user guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md)**, and sending events to it from your
own plugin lives in the **[caller API](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/API.md)**. The full list is under
[Documentation](#documentation) below.

## What it does

- **A calling plugin makes one call and is finished.** `notify(...)` writes a
  small file and returns. It never blocks and never raises, so a caller is
  unaffected even when Newsflasharr is not running.
- **Repeats collapse instead of flooding you.** The same alert arriving
  repeatedly becomes one message plus a summary when the window closes. An
  alert that gets worse breaks the window and is sent at once, so a warning
  can never swallow the critical that follows it.
- **Quiet hours, an hourly cap, and per-channel retry** are configured once
  here rather than separately in every plugin.
- **Your provider hostnames are removed from outgoing messages**, using the
  EPG sources and accounts Dispatcharr already holds.
- **It is read-only on Dispatcharr.** It writes nothing outside its own
  `/data/newsflasharr/` directory, and it never creates or edits an Output
  Profile, a channel or a stream.
- **Delivery is at-least-once per channel.** A duplicate is possible after a
  crash. That is a deliberate tradeoff, described in the
  [caller API](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/API.md).

## What it looks like

The plugin card in Dispatcharr, under Plugins then My Plugins:

<img src="https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/main/docs/screenshots/plugin-card.png" alt="The Newsflasharr plugin card in Dispatcharr, showing the version and the Settings, Actions and Uninstall buttons" width="520">

The Actions tab. Every action writes its complete output to a file, because
the pop-up notification holds only about 280 characters:

<img src="https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/main/docs/screenshots/actions.png" alt="The Actions tab, listing Validate settings, Send test notification, Test on-screen ticker, Ticker filter and Show redaction list" width="700">

The settings screens appear in the [user guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md), beside
the instructions for filling them in.

## Install

1. Download `Newsflasharr.zip` from the
   [Releases page](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/releases).
   The archive contains a single folder named `newsflasharr`, which is the
   name Dispatcharr keys the plugin on, so do not rename it.
2. In Dispatcharr, go to **Plugins**, then **My Plugins**, and use **Import
   Plugin** to upload the file.
3. **Restart the Dispatcharr container.** This one is not optional. The worker
   that collects and delivers events starts when the plugin is constructed in
   each web worker, and a hot reload does not reliably re-run that. Without a
   restart the plugin loads and looks healthy while nothing is delivered.
4. Enable the plugin, then open its settings and fill in at least one channel.
5. Click **Validate settings**. Saving the form on its own arms nothing,
   because Dispatcharr gives plugins no hook that runs after a save.
6. Click **Send test notification** for each channel you configured, naming
   one channel at a time. Only a real send proves a channel works.

The [user guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md) covers each of those steps in full,
including installing by copying the folder yourself instead of using the
archive, and what to check when a notification does not arrive.

## Documentation

| Page | For |
|---|---|
| **[User guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md)** | Setting up channels, routing rules, quiet hours, redaction, the on-screen ticker, and the troubleshooting ladder. |
| **[Caller API](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/API.md)** | The contract another plugin codes against to send events. |
| **[Developer guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/DEVELOPER-GUIDE.md)** | How the plugin is put together, how to run the tests, and how to contribute. |
| **[Changelog](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/CHANGELOG.md)** | What changed between versions. |

## Disclaimer

**Newsflasharr provides no television content of any kind.** It supplies no
channels, no playlists, no streams, no electronic programme guide data and no
provider accounts, and it contains no list of where to obtain any of those. It
is a notification service: it reads status information that Dispatcharr already
holds about the sources **you** configured, and it sends short messages about
that status to destinations **you** configured.

The plugin never contacts a media provider. It never opens, fetches, decodes,
records, restreams or redistributes any stream. The only outbound connections
it makes are to the notification destinations you enter yourself, such as a
Discord webhook, a Dispatcharr Connect Integration, an ntfy topic, an Apprise
gateway or your own mail server.

**You are responsible for what you connect Dispatcharr to.** Whether a
particular provider, subscription, playlist or stream is lawful for you to use
depends on your agreement with that provider and on the law where you live. Use
only sources you are authorised to use. Nothing in this project is intended to
enable, encourage or assist access to content you have no right to access.

All product names, channel names, trademarks and registered trademarks
mentioned in this project or appearing in its examples are the property of their
respective owners. This project is an independent, community-built plugin. It is
not affiliated with, endorsed by, or sponsored by any television network,
broadcaster, streaming service or IPTV provider, and it is not affiliated with
the Dispatcharr project beyond being a plugin written for it.

The software is provided as-is, without warranty of any kind, as set out in the
licence below. This section describes the design of the software and the
author's intent. It is not legal advice. If you need to know whether your own
use is lawful, ask someone qualified in your jurisdiction.

## License

MIT. See [`LICENSE`](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/LICENSE).
