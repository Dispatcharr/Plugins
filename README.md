# Plugin Releases

This branch contains all published plugin releases.

## Quick Access

- [manifest.json](./manifest.json) - Complete plugin registry with metadata
- [metadata/](./metadata/) - Per-plugin manifests and READMEs

## Available Plugins

| Plugin | Version | Author | License | Description |
|--------|---------|-------|---------|-------------|
| [`Audio Buffer Tuner`](#audio-buffer-tuner) | `0.3.5` | CtznSniiips | MIT | Speeds up channel startup for low-bitrate (usually audio only) streams by lowering the TS-proxy prebuffer for chosen Channel Groups. |
| [`Channel Mapparr`](#channel-mapparr) | `1.26.2481147` | PiratesIRC | MIT | Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries. |
| [`Clapparr`](#clapparr) | `1.3.0` | v8eta | MIT | The metadata slate for your DVR: writes Kodi/Plex NFO sidecars, posters and episode thumbnails so recordings present with real titles, summaries and artwork instead of 'Episode 08-18'. |
| [`Could Not Dispatch`](#could-not-dispatch) | `0.4.0` | PilaScat | MIT | Plays a looping image or video when every real stream on a channel has failed, so viewers see a message instead of a black screen. With an API key, it later sends the channel back to its first stream. |
| [`Dispatcharr Exporter`](#dispatcharr-exporter) | `3.1.0` | sethwv | MIT | Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring |
| [`Ranked Matchups (Top Games)`](#ranked-matchups-top-games-) | `1.28.0` | Jacob-Lasky | MIT | Never miss a good game. Scores every upcoming game across 39 leagues, tours and competitions (22 of them soccer, plus NFL, NBA, MLB, NHL, NCAA D1 football and basketball, UFC, boxing, tennis, golf and motorsport), then builds a Top Matchups group holding only the ones worth watching and shows why each game ranked where it did in its EPG description. Finished games can clear themselves out and be replaced from a bench of the next-best fixtures. |
| [`Dispatchwrapparr`](#dispatchwrapparr) | `1.7.8` | jordandalley | MIT | An intelligent DRM/Clearkey capable stream profile for Dispatcharr |
| [`Dustarr`](#dustarr) | `1.26.2481620` | PiratesIRC | MIT | Records which channels are actually watched and reports the ones that are not, so you can turn off the dead weight in your lineup. Read only: it never changes a channel and never contacts your provider. |
| [`EPG & Sports Editor`](#epg-sports-editor) | `0.4.02` | jstevenscl | MIT | Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and includes a Sports Editor: automatically renames Auto Channel Sync-created sports channels, assigns matchup logos, and generates real Pregame/Live/Postgame EPG data by matching against a live public schedule (93 leagues — every major US team sport, 30+ soccer competitions, tennis, golf, NASCAR, F1, UFC/MMA/boxing/darts, and more). Renamed from EPGeditARR; existing installs carry their settings forward automatically. |
| [`EPG Janitor`](#epg-janitor) | `1.26.2481223` | PiratesIRC | MIT | Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments. |
| [`Event Channel Managarr`](#event-channel-managarr) | `1.26.2561545` | PiratesIRC | MIT | Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG. |
| [`Gluetun Rotate`](#gluetun-rotate) | `0.2.1` | PilaScat | MIT | Moves Gluetun to another VPN server when the IPTV provider refuses the current exit address. |
| [`IPTV Checker`](#iptv-checker) | `1.26.2481600` | PiratesIRC | MIT | Check IPTV stream status and quality with ffprobe, then rename, move, restore or delete channels based on the result. Judges a channel by all of its streams, so a working backup never marks it dead. |
| [`Lineuparr`](#lineuparr) | `1.26.2561550` | PiratesIRC | MIT | Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them. |
| [`M3U Expiration Notifier`](#m3u-expiration-notifier) | `1.0.0` | barryanderson | MIT | Checks your M3U account expiration dates on a schedule and emails you before (and when) they expire. |
| [`Multiview`](#multiview) | `0.4.3` | sethwv | MIT | Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg |
| [`Newsflasharr`](#newsflasharr) | `1.26.2481646` | PiratesIRC | MIT | Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, a Dispatcharr Connect Integration, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry. |
| [`PWS - Pirate Weatharr Station`](#pws-pirate-weatharr-station) | `1.3.2` | dexdeadly | MIT | TV-style weather channels powered by the Pirate Weather API. Runs up to three stations, each with its own location and Dispatcharr channel. |
| [`Profilarr`](#profilarr) | `1.0.5` | Tw1zT3d2four7 | MIT | Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt); cvlc then buffers and delivers the already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity. |
| [`reservoarr`](#reservoarr) | `6.3.6` | brko7 | MIT | Delay-buffer stream profile that absorbs IPTV CDN gaps so Plex Live TV stops dying |
| [`Stream Dripper`](#stream-dripper) | `2.0.0` | Megamannen | Artistic-2.0 | Automatically drops all active streams once per day at a configured time, with a manual drop-now button. |
| [`Stream-Mapparr`](#stream-mapparr) | `1.26.2491549` | PiratesIRC | MIT | Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup. |
| [`Telegram Alerts`](#telegram-alerts) | `0.4.5` | R3XCHRIS | MIT | Push Dispatcharr channel/stream/VOD events to a Telegram chat via a bot. Includes a manual test action, per-event toggles, and an optional cron-driven daily report (public IP + geo + speedtest + activity + source health). |
| [`Ticker`](#ticker) | `0.5.03` | jstevenscl | MIT | Dynamic text overlays for IPTV channels — Satellite Radio Now Playing, Sports Ticker, Custom Text, EAS/JAS Weather Alerts |
| [`Twitcharr`](#twitcharr) | `1.3.2` | eliasbruno124-dev | MIT | Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback. |
| [`Underfed`](#underfed) | `0.4.0` | PilaScat | MIT | Moves a channel to its next source when the provider keeps delivering the stream, but at a fraction of the bitrate the content needs. |
| [`VOD to Media Library`](#vod-to-media-library) | `1.18.0` | R3XCHRIS | MIT | Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries. |
| [`Waybill`](#waybill) | `1.3.0` | Matthew-Beckett | MIT | Waybill matches, renames, and organizes any streams no matter the provider. Infinitely configurable pipelines for total control. |
| [`YouTubearr`](#youtubearr) | `1.40.1` | jeff-gooch | Unlicense | Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering |

---

### [Audio Buffer Tuner](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/audio-buffer-tuner/README.md)

**Version:** `0.3.5` | **Author:** CtznSniiips | **Last Updated:** Sep 16 2026, 17:11 UTC

Speeds up channel startup for low-bitrate (usually audio only) streams by lowering the TS-proxy prebuffer for chosen Channel Groups.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1549510259775635536) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/CtznSniiips/audio-buffer-tuner)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.31.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`0.3.5`)](https://github.com/Dispatcharr/Plugins/releases/download/audio-buffer-tuner-0.3.5/audio-buffer-tuner-0.3.5.zip)
- [All Versions (1 available)](./metadata/audio-buffer-tuner)

**Maintainers:** CtznSniiips | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/audio-buffer-tuner) | **Last Change:** [`3ceeddd`](https://github.com/Dispatcharr/Plugins/commit/3ceeddd53b4d49d5d14584768f69121e8094d6df)

---

### [Channel Mapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/channel-mapparr/README.md)

**Version:** `1.26.2481147` | **Author:** PiratesIRC | **Last Updated:** Sep 05 2026, 17:24 UTC

Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422963882548265110) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Channel-Maparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2481147`)](https://github.com/Dispatcharr/Plugins/releases/download/channel-mapparr-1.26.2481147/channel-mapparr-1.26.2481147.zip)
- [All Versions (10 available)](./metadata/channel-mapparr)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/channel-mapparr) | **Last Change:** [`ffc025f`](https://github.com/Dispatcharr/Plugins/commit/ffc025f3bfd9396fcd0498d3bc03cec22ef5d7e0)

---

### [Clapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/clapparr/README.md)

**Version:** `1.3.0` | **Author:** v8eta | **Last Updated:** Aug 22 2026, 22:50 UTC

The metadata slate for your DVR: writes Kodi/Plex NFO sidecars, posters and episode thumbnails so recordings present with real titles, summaries and artwork instead of 'Episode 08-18'.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/v8eta/clapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.3.0`)](https://github.com/Dispatcharr/Plugins/releases/download/clapparr-1.3.0/clapparr-1.3.0.zip)
- [All Versions (1 available)](./metadata/clapparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/clapparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/clapparr/README.md) | **Last Change:** [`41752af`](https://github.com/Dispatcharr/Plugins/commit/41752afd9a5678d2f7a9a49f2209331a620e119f)

---

### [Could Not Dispatch](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/could-not-dispatch/README.md)

**Version:** `0.4.0` | **Author:** PilaScat | **Last Updated:** Sep 14 2026, 14:46 UTC

Plays a looping image or video when every real stream on a channel has failed, so viewers see a message instead of a black screen. With an API key, it later sends the channel back to its first stream.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PilaScat/could-not-dispatch)

**Downloads:**
- [Latest Release (`0.4.0`)](https://github.com/Dispatcharr/Plugins/releases/download/could-not-dispatch-0.4.0/could-not-dispatch-0.4.0.zip)
- [All Versions (5 available)](./metadata/could-not-dispatch)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/could-not-dispatch) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/could-not-dispatch/README.md) | **Last Change:** [`3ee82eb`](https://github.com/Dispatcharr/Plugins/commit/3ee82eb1a2a2abf598e570d617b944149cc019ad)

---

### [Dispatcharr Exporter](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatcharr-exporter/README.md)

**Version:** `3.1.0` | **Author:** sethwv | **Last Updated:** Jul 18 2026, 17:29 UTC

Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1451260201775923421) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/dispatcharr-exporter)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.22.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`3.1.0`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-exporter-3.1.0/dispatcharr-exporter-3.1.0.zip)
- [All Versions (4 available)](./metadata/dispatcharr-exporter)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-exporter) | **Last Change:** [`ddffa49`](https://github.com/Dispatcharr/Plugins/commit/ddffa49420c5dd513a9a7876998a72ce295e2242)

---

### [Ranked Matchups (Top Games)](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatcharr-ranked-matchups/README.md)

**Version:** `1.28.0` | **Author:** Jacob-Lasky | **Last Updated:** Sep 07 2026, 03:13 UTC

Never miss a good game. Scores every upcoming game across 39 leagues, tours and competitions (22 of them soccer, plus NFL, NBA, MLB, NHL, NCAA D1 football and basketball, UFC, boxing, tennis, golf and motorsport), then builds a Top Matchups group holding only the ones worth watching and shows why each game ranked where it did in its EPG description. Finished games can clear themselves out and be replaced from a bench of the next-best fixtures.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1508938899865604167) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups)

**Downloads:**
- [Latest Release (`1.28.0`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.28.0/dispatcharr-ranked-matchups-1.28.0.zip)
- [All Versions (10 available)](./metadata/dispatcharr-ranked-matchups)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-ranked-matchups) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatcharr-ranked-matchups/README.md) | **Last Change:** [`15fe238`](https://github.com/Dispatcharr/Plugins/commit/15fe238106424c7c1d836db11adbb78257bafe89)

---

### [Dispatchwrapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatchwrapparr/README.md)

**Version:** `1.7.8` | **Author:** jordandalley | **Last Updated:** Sep 16 2026, 09:25 UTC

An intelligent DRM/Clearkey capable stream profile for Dispatcharr

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422776847703212132) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jordandalley/dispatchwrapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.31.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.7.8`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatchwrapparr-1.7.8/dispatchwrapparr-1.7.8.zip)
- [All Versions (10 available)](./metadata/dispatchwrapparr)

**Maintainers:** michaelmurfy | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatchwrapparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatchwrapparr/README.md) | **Last Change:** [`0543ea1`](https://github.com/Dispatcharr/Plugins/commit/0543ea1f4086b0da4e80e400422b2d0b72c70da9)

---

### [Dustarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dustarr/README.md)

**Version:** `1.26.2481620` | **Author:** PiratesIRC | **Last Updated:** Sep 05 2026, 17:13 UTC

Records which channels are actually watched and reports the ones that are not, so you can turn off the dead weight in your lineup. Read only: it never changes a channel and never contacts your provider.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1542141054080524310) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2481620`)](https://github.com/Dispatcharr/Plugins/releases/download/dustarr-1.26.2481620/dustarr-1.26.2481620.zip)
- [All Versions (2 available)](./metadata/dustarr)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dustarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dustarr/README.md) | **Last Change:** [`8a2dffb`](https://github.com/Dispatcharr/Plugins/commit/8a2dffb328107de46d80063dc81eff7620dab49f)

---

### [EPG & Sports Editor](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epg-and-sports-editor/README.md)

**Version:** `0.4.02` | **Author:** jstevenscl | **Last Updated:** Sep 17 2026, 16:33 UTC

Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and includes a Sports Editor: automatically renames Auto Channel Sync-created sports channels, assigns matchup logos, and generates real Pregame/Live/Postgame EPG data by matching against a live public schedule (93 leagues — every major US team sport, 30+ soccer competitions, tennis, golf, NASCAR, F1, UFC/MMA/boxing/darts, and more). Renamed from EPGeditARR; existing installs carry their settings forward automatically.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/epg-and-sports-editor)

**Downloads:**
- [Latest Release (`0.4.02`)](https://github.com/Dispatcharr/Plugins/releases/download/epg-and-sports-editor-0.4.02/epg-and-sports-editor-0.4.02.zip)
- [All Versions (3 available)](./metadata/epg-and-sports-editor)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epg-and-sports-editor) | **Last Change:** [`5850dde`](https://github.com/Dispatcharr/Plugins/commit/5850dde5699ba2a7ba08495145e2875b1ac4c851)

---

### [EPG Janitor](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epg-janitor/README.md)

**Version:** `1.26.2481223` | **Author:** PiratesIRC | **Last Updated:** Sep 05 2026, 19:57 UTC

Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1420051973994053848) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-EPG-Janitor-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2481223`)](https://github.com/Dispatcharr/Plugins/releases/download/epg-janitor-1.26.2481223/epg-janitor-1.26.2481223.zip)
- [All Versions (8 available)](./metadata/epg-janitor)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epg-janitor) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/epg-janitor/README.md) | **Last Change:** [`ceb7847`](https://github.com/Dispatcharr/Plugins/commit/ceb784785395a3750996e248f9cd24812d52987f)

---

### [Event Channel Managarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/event-channel-managarr/README.md)

**Version:** `1.26.2561545` | **Author:** PiratesIRC | **Last Updated:** Sep 13 2026, 15:50 UTC

Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2561545`)](https://github.com/Dispatcharr/Plugins/releases/download/event-channel-managarr-1.26.2561545/event-channel-managarr-1.26.2561545.zip)
- [All Versions (10 available)](./metadata/event-channel-managarr)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/event-channel-managarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/event-channel-managarr/README.md) | **Last Change:** [`dbd5ce4`](https://github.com/Dispatcharr/Plugins/commit/dbd5ce4e72538e478415e3a02721f5e0d7ae8fa2)

---

### [Gluetun Rotate](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/gluetun-rotate/README.md)

**Version:** `0.2.1` | **Author:** PilaScat | **Last Updated:** Sep 14 2026, 20:12 UTC

Moves Gluetun to another VPN server when the IPTV provider refuses the current exit address.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PilaScat/gluetun-rotate)

**Downloads:**
- [Latest Release (`0.2.1`)](https://github.com/Dispatcharr/Plugins/releases/download/gluetun-rotate-0.2.1/gluetun-rotate-0.2.1.zip)
- [All Versions (1 available)](./metadata/gluetun-rotate)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/gluetun-rotate) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/gluetun-rotate/README.md) | **Last Change:** [`4d30179`](https://github.com/Dispatcharr/Plugins/commit/4d3017960cd2e203ca01cf0c6d210b0fc54a982b)

---

### [IPTV Checker](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/iptv-checker/README.md)

**Version:** `1.26.2481600` | **Author:** PiratesIRC | **Last Updated:** Sep 05 2026, 16:21 UTC

Check IPTV stream status and quality with ffprobe, then rename, move, restore or delete channels based on the result. Judges a channel by all of its streams, so a working backup never marks it dead.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2481600`)](https://github.com/Dispatcharr/Plugins/releases/download/iptv-checker-1.26.2481600/iptv-checker-1.26.2481600.zip)
- [All Versions (10 available)](./metadata/iptv-checker)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/iptv-checker) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/iptv-checker/README.md) | **Last Change:** [`1d17008`](https://github.com/Dispatcharr/Plugins/commit/1d17008721288ae94b2dad5309a91a76a5a20d8a)

---

### [Lineuparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/lineuparr/README.md)

**Version:** `1.26.2561550` | **Author:** PiratesIRC | **Last Updated:** Sep 13 2026, 16:03 UTC

Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Lineuparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2561550`)](https://github.com/Dispatcharr/Plugins/releases/download/lineuparr-1.26.2561550/lineuparr-1.26.2561550.zip)
- [All Versions (10 available)](./metadata/lineuparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/lineuparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/lineuparr/README.md) | **Last Change:** [`e56e990`](https://github.com/Dispatcharr/Plugins/commit/e56e9906c18e092bb424366e0ed361c4bcd07612)

---

### [M3U Expiration Notifier](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/m3u-expiration-notifier/README.md)

**Version:** `1.0.0` | **Author:** barryanderson | **Last Updated:** Jul 17 2026, 00:26 UTC

Checks your M3U account expiration dates on a schedule and emails you before (and when) they expire.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/barryanderson/dispatcharr-m3u-expiration-notifier)

**Downloads:**
- [Latest Release (`1.0.0`)](https://github.com/Dispatcharr/Plugins/releases/download/m3u-expiration-notifier-1.0.0/m3u-expiration-notifier-1.0.0.zip)
- [All Versions (1 available)](./metadata/m3u-expiration-notifier)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/m3u-expiration-notifier) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/m3u-expiration-notifier/README.md) | **Last Change:** [`af83e50`](https://github.com/Dispatcharr/Plugins/commit/af83e5054bf456bbe78b841eabc3a3373abbbae1)

---

### [Multiview](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/multiview/README.md)

**Version:** `0.4.3` | **Author:** sethwv | **Last Updated:** Aug 31 2026, 14:40 UTC

Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1509200002407465001) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/dispatcharr-multiview)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.27.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`0.4.3`)](https://github.com/Dispatcharr/Plugins/releases/download/multiview-0.4.3/multiview-0.4.3.zip)
- [All Versions (10 available)](./metadata/multiview)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/multiview) | **Last Change:** [`5a45cc2`](https://github.com/Dispatcharr/Plugins/commit/5a45cc2f372ca1afb0d5a76f5cb68855d6fc49df)

---

### [Newsflasharr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/newsflasharr/README.md)

**Version:** `1.26.2481646` | **Author:** PiratesIRC | **Last Updated:** Sep 05 2026, 17:22 UTC

Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, a Dispatcharr Connect Integration, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1533575430400114730) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2481646`)](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2481646/newsflasharr-1.26.2481646.zip)
- [All Versions (5 available)](./metadata/newsflasharr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/newsflasharr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/newsflasharr/README.md) | **Last Change:** [`c6b7006`](https://github.com/Dispatcharr/Plugins/commit/c6b7006471cbd1d5f99533347a07b6f05342a084)

---

### [PWS - Pirate Weatharr Station](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/pirate-weatharr-station/README.md)

**Version:** `1.3.2` | **Author:** dexdeadly | **Last Updated:** Aug 18 2026, 04:53 UTC

TV-style weather channels powered by the Pirate Weather API. Runs up to three stations, each with its own location and Dispatcharr channel.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/dexdeadly/pirate-weatharr-station/)

**Downloads:**
- [Latest Release (`1.3.2`)](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.3.2/pirate-weatharr-station-1.3.2.zip)
- [All Versions (2 available)](./metadata/pirate-weatharr-station)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/pirate-weatharr-station) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/pirate-weatharr-station/README.md) | **Last Change:** [`878b01c`](https://github.com/Dispatcharr/Plugins/commit/878b01c6f9a5f53c8c9c9e1e78994b5d7fc69d07)

---

### [Profilarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/profilarr/README.md)

**Version:** `1.0.5` | **Author:** Tw1zT3d2four7 | **Last Updated:** Sep 18 2026, 07:26 UTC

Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt); cvlc then buffers and delivers the already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Profilarr)

**Downloads:**
- [Latest Release (`1.0.5`)](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.5/profilarr-1.0.5.zip)
- [All Versions (5 available)](./metadata/profilarr)

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/profilarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/profilarr/README.md) | **Last Change:** [`1386b91`](https://github.com/Dispatcharr/Plugins/commit/1386b913d17c3a799afbeb114ea2079a1820a24d)

---

### [reservoarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/reservoarr/README.md)

**Version:** `6.3.6` | **Author:** brko7 | **Last Updated:** Sep 14 2026, 15:53 UTC

Delay-buffer stream profile that absorbs IPTV CDN gaps so Plex Live TV stops dying

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/brko7/reservoarr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.25.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`6.3.6`)](https://github.com/Dispatcharr/Plugins/releases/download/reservoarr-6.3.6/reservoarr-6.3.6.zip)
- [All Versions (9 available)](./metadata/reservoarr)

**Maintainers:** brko7 | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/reservoarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/reservoarr/README.md) | **Last Change:** [`3424828`](https://github.com/Dispatcharr/Plugins/commit/3424828c52a1e524a7c460a453804de3ed3690e7)

---

### [Stream Dripper](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/stream-dripper/README.md)

**Version:** `2.0.0` | **Author:** Megamannen | **Last Updated:** Sep 15 2026, 20:02 UTC

Automatically drops all active streams once per day at a configured time, with a manual drop-now button.

[![License: Artistic-2.0](https://img.shields.io/badge/License-Artistic--2.0-blue?style=flat-square)](https://spdx.org/licenses/Artistic-2.0.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Megamannen/dispatcharr-plugin-stream-dripper/)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-0.25.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`2.0.0`)](https://github.com/Dispatcharr/Plugins/releases/download/stream-dripper-2.0.0/stream-dripper-2.0.0.zip)
- [All Versions (2 available)](./metadata/stream-dripper)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/stream-dripper) | **Last Change:** [`846d0fe`](https://github.com/Dispatcharr/Plugins/commit/846d0fea839c1e3c2ebad8e8744c3cb4a0927eaf)

---

### [Stream-Mapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/stream-mapparr/README.md)

**Version:** `1.26.2491549` | **Author:** PiratesIRC | **Last Updated:** Sep 06 2026, 19:42 UTC

Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Stream-Mapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2491549`)](https://github.com/Dispatcharr/Plugins/releases/download/stream-mapparr-1.26.2491549/stream-mapparr-1.26.2491549.zip)
- [All Versions (10 available)](./metadata/stream-mapparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/stream-mapparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/stream-mapparr/README.md) | **Last Change:** [`23d5498`](https://github.com/Dispatcharr/Plugins/commit/23d54985d7c6e71008dc376e87e3c816e5b43687)

---

### [Telegram Alerts](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/telegram-alerts/README.md)

**Version:** `0.4.5` | **Author:** R3XCHRIS | **Last Updated:** Jun 01 2026, 20:07 UTC

Push Dispatcharr channel/stream/VOD events to a Telegram chat via a bot. Includes a manual test action, per-event toggles, and an optional cron-driven daily report (public IP + geo + speedtest + activity + source health).

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/R3XCHRIS/telegram-alerts)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`0.4.5`)](https://github.com/Dispatcharr/Plugins/releases/download/telegram-alerts-0.4.5/telegram-alerts-0.4.5.zip)
- [All Versions (1 available)](./metadata/telegram-alerts)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/telegram-alerts) | **Last Change:** [`04aa4f4`](https://github.com/Dispatcharr/Plugins/commit/04aa4f43926c2ca7cefc5c802166a02fe43b3500)

---

### [Ticker](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/ticker/README.md)

**Version:** `0.5.03` | **Author:** jstevenscl | **Last Updated:** Sep 13 2026, 05:45 UTC

Dynamic text overlays for IPTV channels — Satellite Radio Now Playing, Sports Ticker, Custom Text, EAS/JAS Weather Alerts

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/ticker)

**Downloads:**
- [Latest Release (`0.5.03`)](https://github.com/Dispatcharr/Plugins/releases/download/ticker-0.5.03/ticker-0.5.03.zip)
- [All Versions (4 available)](./metadata/ticker)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/ticker) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/ticker/README.md) | **Last Change:** [`61b5fbb`](https://github.com/Dispatcharr/Plugins/commit/61b5fbb8daa786c8a24e51991355c0cf3c107d1e)

---

### [Twitcharr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/twitcharr/README.md)

**Version:** `1.3.2` | **Author:** eliasbruno124-dev | **Last Updated:** Jul 13 2026, 02:54 UTC

Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/eliasbruno124-dev/Twitcharr)

**Downloads:**
- [Latest Release (`1.3.2`)](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.2/twitcharr-1.3.2.zip)
- [All Versions (4 available)](./metadata/twitcharr)

**Maintainers:** eliasbruno124-dev | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/twitcharr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/twitcharr/README.md) | **Last Change:** [`2d65eb1`](https://github.com/Dispatcharr/Plugins/commit/2d65eb13b1ad72210ca517520c9d0608d2dc342b)

---

### [Underfed](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/underfed/README.md)

**Version:** `0.4.0` | **Author:** PilaScat | **Last Updated:** Sep 15 2026, 11:41 UTC

Moves a channel to its next source when the provider keeps delivering the stream, but at a fraction of the bitrate the content needs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PilaScat/underfed)

**Downloads:**
- [Latest Release (`0.4.0`)](https://github.com/Dispatcharr/Plugins/releases/download/underfed-0.4.0/underfed-0.4.0.zip)
- [All Versions (2 available)](./metadata/underfed)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/underfed) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/underfed/README.md) | **Last Change:** [`c800f7e`](https://github.com/Dispatcharr/Plugins/commit/c800f7e99fea3c625a96061f2ba8a52fe596d4c3)

---

### [VOD to Media Library](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/vod2mlib/README.md)

**Version:** `1.18.0` | **Author:** R3XCHRIS | **Last Updated:** Aug 19 2026, 16:22 UTC

Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1503076618078261374) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/R3XCHRIS/VOD2MLIB)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.24.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.18.0`)](https://github.com/Dispatcharr/Plugins/releases/download/vod2mlib-1.18.0/vod2mlib-1.18.0.zip)
- [All Versions (8 available)](./metadata/vod2mlib)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/vod2mlib) | **Last Change:** [`b7a546e`](https://github.com/Dispatcharr/Plugins/commit/b7a546ea5c82bd2e2889a0a4258c695e82aea041)

---

### [Waybill](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/waybill/README.md)

**Version:** `1.3.0` | **Author:** Matthew-Beckett | **Last Updated:** May 12 2026, 19:36 UTC

Waybill matches, renames, and organizes any streams no matter the provider. Infinitely configurable pipelines for total control.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Matthew-Beckett/waybill)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-0.23.0-brightgreen?style=flat-square) ![Dispatcharr max](https://img.shields.io/badge/Dispatcharr_max-0.24.0-orange?style=flat-square)

**Downloads:**
- [Latest Release (`1.3.0`)](https://github.com/Dispatcharr/Plugins/releases/download/waybill-1.3.0/waybill-1.3.0.zip)
- [All Versions (1 available)](./metadata/waybill)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/waybill) | **Last Change:** [`cdd18dd`](https://github.com/Dispatcharr/Plugins/commit/cdd18dd7f396035b9cd486d3e45375eed3bcc744)

---

### [YouTubearr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/youtubearr/README.md)

**Version:** `1.40.1` | **Author:** jeff-gooch | **Last Updated:** Sep 16 2026, 12:55 UTC

Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering

[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-blue?style=flat-square)](https://spdx.org/licenses/Unlicense.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jeff-gooch/youtubearr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.40.1`)](https://github.com/Dispatcharr/Plugins/releases/download/youtubearr-1.40.1/youtubearr-1.40.1.zip)
- [All Versions (8 available)](./metadata/youtubearr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/youtubearr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/youtubearr/README.md) | **Last Change:** [`e14ea92`](https://github.com/Dispatcharr/Plugins/commit/e14ea92d80763c52784047f843aa76069b45c7c1)

---


## Deprecated Plugins

These plugins are deprecated and may be removed in the future.

## Using the Manifest

Fetch `manifest.json` to programmatically access plugin metadata and download URLs:

```bash
curl https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

---

*Last updated: Sep 18 2026, 07:26 UTC*
