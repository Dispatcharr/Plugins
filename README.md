# Plugin Releases

This branch contains all published plugin releases.

## Quick Access

- [manifest.json](./manifest.json) - Complete plugin registry with metadata
- [metadata/](./metadata/) - Per-plugin manifests and READMEs

## Available Plugins

| Plugin | Version | Author | License | Description |
|--------|---------|-------|---------|-------------|
| [`Channel Mapparr`](#channel-mapparr) | `1.26.2241315` | PiratesIRC | MIT | Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries. |
| [`Could Not Dispatch`](#could-not-dispatch) | `0.1.0` | PilaScat | MIT | Plays a looping image or video when every real stream on a channel has failed, so viewers see a message instead of a black screen. |
| [`Dispatcharr Exporter`](#dispatcharr-exporter) | `3.1.0` | sethwv | MIT | Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring |
| [`Ranked Matchups (Top Games)`](#ranked-matchups-top-games-) | `1.17.0` | Jacob-Lasky | MIT | Never miss a good game. Scores every upcoming game across 37 leagues, tours and competitions (20 of them soccer, plus NFL, NBA, MLB, NHL, NCAA, UFC, boxing, tennis, golf and motorsport), then builds a Top Matchups group holding only the ones worth watching and shows why each game ranked where it did in its EPG description. |
| [`Dispatchwrapparr`](#dispatchwrapparr) | `1.7.6` | jordandalley | MIT | An intelligent DRM/Clearkey capable stream profile for Dispatcharr |
| [`EPG Janitor`](#epg-janitor) | `1.26.2241232` | PiratesIRC | MIT | Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments. |
| [`EPGeditARR`](#epgeditarr) | `0.2.10` | jstevenscl | MIT | Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and provides a full SiriusXM toolkit: fill EPG from the community XMLTV (741 channels, sports smart blocks), sort into official lineup order, assign logos, and rename channels using the official SiriusXM API channel database. |
| [`Event Channel Managarr`](#event-channel-managarr) | `1.26.2251616` | PiratesIRC | MIT | Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG. |
| [`IPTV Checker`](#iptv-checker) | `1.26.2201040` | PiratesIRC | MIT | Check IPTV stream status and quality with ffprobe, then rename, move, restore or delete channels based on the result. Judges a channel by all of its streams, so a working backup never marks it dead. |
| [`Lineuparr`](#lineuparr) | `1.26.2241618` | PiratesIRC | MIT | Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them. |
| [`M3U Expiration Notifier`](#m3u-expiration-notifier) | `1.0.0` | barryanderson | MIT | Checks your M3U account expiration dates on a schedule and emails you before (and when) they expire. |
| [`Multiview`](#multiview) | `0.4.2` | sethwv | MIT | Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg |
| [`Newsflasharr`](#newsflasharr) | `1.26.2241159` | PiratesIRC | MIT | Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry. |
| [`PWS - Pirate Weatharr Station`](#pws-pirate-weatharr-station) | `1.0.0` | dexdeadly | MIT | TV-style weather channels powered by the Pirate Weather API. Runs up to three stations, each with its own location and Dispatcharr channel. |
| [`reservoarr`](#reservoarr) | `6.3.1` | brko7 | MIT | Delay-buffer stream profile that absorbs IPTV CDN gaps so Plex Live TV stops dying |
| [`Stream Dripper`](#stream-dripper) | `1.0.0` | Megamannen | Artistic-2.0 | Automatically drops all active streams once per day at a configured time, with a manual drop-now button. |
| [`Stream-Mapparr`](#stream-mapparr) | `1.26.2241602` | PiratesIRC | MIT | Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup. |
| [`Telegram Alerts`](#telegram-alerts) | `0.4.5` | R3XCHRIS | MIT | Push Dispatcharr channel/stream/VOD events to a Telegram chat via a bot. Includes a manual test action, per-event toggles, and an optional cron-driven daily report (public IP + geo + speedtest + activity + source health). |
| [`Tickarr`](#tickarr) | `0.4.0` | jstevenscl | MIT | Dynamic text overlays for IPTV channels — Satellite Radio Now Playing, Sports Ticker, Custom Text, EAS/JAS Weather Alerts |
| [`Twitcharr`](#twitcharr) | `1.3.2` | eliasbruno124-dev | MIT | Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback. |
| [`VOD to Media Library`](#vod-to-media-library) | `1.16.0` | R3XCHRIS | MIT | Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries. |
| [`Waybill`](#waybill) | `1.3.0` | Matthew-Beckett | MIT | Waybill matches, renames, and organizes any streams no matter the provider. Infinitely configurable pipelines for total control. |
| [`YouTubearr`](#youtubearr) | `1.30.1` | jeff-gooch | Unlicense | Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering |

---

### [Channel Mapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/channel-mapparr/README.md)

**Version:** `1.26.2241315` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 18:50 UTC

Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422963882548265110) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Channel-Maparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2241315`)](https://github.com/Dispatcharr/Plugins/releases/download/channel-mapparr-1.26.2241315/channel-mapparr-1.26.2241315.zip)
- [All Versions (10 available)](./metadata/channel-mapparr)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/channel-mapparr) | **Last Change:** [`e745323`](https://github.com/Dispatcharr/Plugins/commit/e745323441f3a9aa3c7a5712db5c931c5e488383)

---

### [Could Not Dispatch](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/could-not-dispatch/README.md)

**Version:** `0.1.0` | **Author:** PilaScat | **Last Updated:** Aug 10 2026, 20:11 UTC

Plays a looping image or video when every real stream on a channel has failed, so viewers see a message instead of a black screen.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PilaScat/could-not-dispatch)

**Downloads:**
- [Latest Release (`0.1.0`)](https://github.com/Dispatcharr/Plugins/releases/download/could-not-dispatch-0.1.0/could-not-dispatch-0.1.0.zip)
- [All Versions (1 available)](./metadata/could-not-dispatch)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/could-not-dispatch) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/could-not-dispatch/README.md) | **Last Change:** [`6753280`](https://github.com/Dispatcharr/Plugins/commit/67532805aec060ec4ae02d60d874ada54f64c63f)

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

**Version:** `1.17.0` | **Author:** Jacob-Lasky | **Last Updated:** Aug 13 2026, 01:06 UTC

Never miss a good game. Scores every upcoming game across 37 leagues, tours and competitions (20 of them soccer, plus NFL, NBA, MLB, NHL, NCAA, UFC, boxing, tennis, golf and motorsport), then builds a Top Matchups group holding only the ones worth watching and shows why each game ranked where it did in its EPG description.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1508938899865604167) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups)

**Downloads:**
- [Latest Release (`1.17.0`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.17.0/dispatcharr-ranked-matchups-1.17.0.zip)
- [All Versions (10 available)](./metadata/dispatcharr-ranked-matchups)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-ranked-matchups) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatcharr-ranked-matchups/README.md) | **Last Change:** [`167070e`](https://github.com/Dispatcharr/Plugins/commit/167070efe899345536ec04e72306ceb2f6d37833)

---

### [Dispatchwrapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatchwrapparr/README.md)

**Version:** `1.7.6` | **Author:** jordandalley | **Last Updated:** Jul 08 2026, 01:38 UTC

An intelligent DRM/Clearkey capable stream profile for Dispatcharr

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422776847703212132) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jordandalley/dispatchwrapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.25.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.7.6`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatchwrapparr-1.7.6/dispatchwrapparr-1.7.6.zip)
- [All Versions (10 available)](./metadata/dispatchwrapparr)

**Maintainers:** michaelmurfy | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatchwrapparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatchwrapparr/README.md) | **Last Change:** [`9fc5ffc`](https://github.com/Dispatcharr/Plugins/commit/9fc5ffc13904e456ba251ceecc747d3b2d837221)

---

### [EPG Janitor](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epg-janitor/README.md)

**Version:** `1.26.2241232` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 18:14 UTC

Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1420051973994053848) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-EPG-Janitor-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2241232`)](https://github.com/Dispatcharr/Plugins/releases/download/epg-janitor-1.26.2241232/epg-janitor-1.26.2241232.zip)
- [All Versions (6 available)](./metadata/epg-janitor)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epg-janitor) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/epg-janitor/README.md) | **Last Change:** [`990a732`](https://github.com/Dispatcharr/Plugins/commit/990a732418764787445fe9afce6b8d5f31beddf2)

---

### [EPGeditARR](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epgeditarr/README.md)

**Version:** `0.2.10` | **Author:** jstevenscl | **Last Updated:** Jul 25 2026, 18:29 UTC

Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and provides a full SiriusXM toolkit: fill EPG from the community XMLTV (741 channels, sports smart blocks), sort into official lineup order, assign logos, and rename channels using the official SiriusXM API channel database.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/epgeditarr)

**Downloads:**
- [Latest Release (`0.2.10`)](https://github.com/Dispatcharr/Plugins/releases/download/epgeditarr-0.2.10/epgeditarr-0.2.10.zip)
- [All Versions (5 available)](./metadata/epgeditarr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epgeditarr) | **Last Change:** [`d6f94d8`](https://github.com/Dispatcharr/Plugins/commit/d6f94d8babfe12375b616399fad8672690fe757b)

---

### [Event Channel Managarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/event-channel-managarr/README.md)

**Version:** `1.26.2251616` | **Author:** PiratesIRC | **Last Updated:** Aug 13 2026, 16:23 UTC

Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2251616`)](https://github.com/Dispatcharr/Plugins/releases/download/event-channel-managarr-1.26.2251616/event-channel-managarr-1.26.2251616.zip)
- [All Versions (10 available)](./metadata/event-channel-managarr)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/event-channel-managarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/event-channel-managarr/README.md) | **Last Change:** [`148bd03`](https://github.com/Dispatcharr/Plugins/commit/148bd037d02ee8b5a7facd2b69727bea686db59b)

---

### [IPTV Checker](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/iptv-checker/README.md)

**Version:** `1.26.2201040` | **Author:** PiratesIRC | **Last Updated:** Aug 08 2026, 10:47 UTC

Check IPTV stream status and quality with ffprobe, then rename, move, restore or delete channels based on the result. Judges a channel by all of its streams, so a working backup never marks it dead.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2201040`)](https://github.com/Dispatcharr/Plugins/releases/download/iptv-checker-1.26.2201040/iptv-checker-1.26.2201040.zip)
- [All Versions (10 available)](./metadata/iptv-checker)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/iptv-checker) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/iptv-checker/README.md) | **Last Change:** [`d663a41`](https://github.com/Dispatcharr/Plugins/commit/d663a410b27880e3df043156712d3c79652e89f3)

---

### [Lineuparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/lineuparr/README.md)

**Version:** `1.26.2241618` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 17:50 UTC

Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Lineuparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2241618`)](https://github.com/Dispatcharr/Plugins/releases/download/lineuparr-1.26.2241618/lineuparr-1.26.2241618.zip)
- [All Versions (10 available)](./metadata/lineuparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/lineuparr) | **Last Change:** [`5ba093d`](https://github.com/Dispatcharr/Plugins/commit/5ba093de507732b40c6334e995f987fbe540423b)

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

**Version:** `0.4.2` | **Author:** sethwv | **Last Updated:** Jul 21 2026, 17:30 UTC

Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1509200002407465001) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/dispatcharr-multiview)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.27.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`0.4.2`)](https://github.com/Dispatcharr/Plugins/releases/download/multiview-0.4.2/multiview-0.4.2.zip)
- [All Versions (10 available)](./metadata/multiview)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/multiview) | **Last Change:** [`38f5f73`](https://github.com/Dispatcharr/Plugins/commit/38f5f73656df833e60dd9759c230cd957c6b1157)

---

### [Newsflasharr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/newsflasharr/README.md)

**Version:** `1.26.2241159` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 12:05 UTC

Central notification service: other plugins drop events, Newsflasharr routes them to Discord, a webhook, ntfy, Apprise, email, or an on-screen banner over live TV, with deduplication, storm throttling, quiet hours and per-channel retry.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1533575430400114730) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2241159`)](https://github.com/Dispatcharr/Plugins/releases/download/newsflasharr-1.26.2241159/newsflasharr-1.26.2241159.zip)
- [All Versions (4 available)](./metadata/newsflasharr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/newsflasharr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/newsflasharr/README.md) | **Last Change:** [`5c239be`](https://github.com/Dispatcharr/Plugins/commit/5c239be35a9e5d5db0cfbf45f36c9217d097631e)

---

### [PWS - Pirate Weatharr Station](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/pirate-weatharr-station/README.md)

**Version:** `1.0.0` | **Author:** dexdeadly | **Last Updated:** Jul 31 2026, 12:47 UTC

TV-style weather channels powered by the Pirate Weather API. Runs up to three stations, each with its own location and Dispatcharr channel.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/dexdeadly/pirate-weatharr-station/)

**Downloads:**
- [Latest Release (`1.0.0`)](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.0.0/pirate-weatharr-station-1.0.0.zip)
- [All Versions (1 available)](./metadata/pirate-weatharr-station)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/pirate-weatharr-station) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/pirate-weatharr-station/README.md) | **Last Change:** [`6411b97`](https://github.com/Dispatcharr/Plugins/commit/6411b9759caf40f17bcc38e88e358fc669c71488)

---

### [reservoarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/reservoarr/README.md)

**Version:** `6.3.1` | **Author:** brko7 | **Last Updated:** Jul 03 2026, 16:10 UTC

Delay-buffer stream profile that absorbs IPTV CDN gaps so Plex Live TV stops dying

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/brko7/reservoarr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.25.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`6.3.1`)](https://github.com/Dispatcharr/Plugins/releases/download/reservoarr-6.3.1/reservoarr-6.3.1.zip)
- [All Versions (4 available)](./metadata/reservoarr)

**Maintainers:** brko7 | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/reservoarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/reservoarr/README.md) | **Last Change:** [`87eb446`](https://github.com/Dispatcharr/Plugins/commit/87eb4462b4d69c9c7fed119696b027be4b6ed2c2)

---

### [Stream Dripper](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/stream-dripper/README.md)

**Version:** `1.0.0` | **Author:** Megamannen | **Last Updated:** Mar 29 2026, 15:51 UTC

Automatically drops all active streams once per day at a configured time, with a manual drop-now button.

[![License: Artistic-2.0](https://img.shields.io/badge/License-Artistic--2.0-blue?style=flat-square)](https://spdx.org/licenses/Artistic-2.0.html)

**Downloads:**
- [Latest Release (`1.0.0`)](https://github.com/Dispatcharr/Plugins/releases/download/stream-dripper-1.0.0/stream-dripper-1.0.0.zip)
- [All Versions (1 available)](./metadata/stream-dripper)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/stream-dripper) | **Last Change:** [`4e8f1b1`](https://github.com/Dispatcharr/Plugins/commit/4e8f1b108c1e84f60520710d13e54eb2fb519648)

---

### [Stream-Mapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/stream-mapparr/README.md)

**Version:** `1.26.2241602` | **Author:** PiratesIRC | **Last Updated:** Aug 12 2026, 17:13 UTC

Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Stream-Mapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.2241602`)](https://github.com/Dispatcharr/Plugins/releases/download/stream-mapparr-1.26.2241602/stream-mapparr-1.26.2241602.zip)
- [All Versions (10 available)](./metadata/stream-mapparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/stream-mapparr) | **Last Change:** [`dc86bdd`](https://github.com/Dispatcharr/Plugins/commit/dc86bdd35a3992c6a744465854e1c402a9bcc15c)

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

### [Tickarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/tickarr/README.md)

**Version:** `0.4.0` | **Author:** jstevenscl | **Last Updated:** Aug 14 2026, 06:28 UTC

Dynamic text overlays for IPTV channels — Satellite Radio Now Playing, Sports Ticker, Custom Text, EAS/JAS Weather Alerts

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/tickarr)

**Downloads:**
- [Latest Release (`0.4.0`)](https://github.com/Dispatcharr/Plugins/releases/download/tickarr-0.4.0/tickarr-0.4.0.zip)
- [All Versions (10 available)](./metadata/tickarr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/tickarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/tickarr/README.md) | **Last Change:** [`b6631dd`](https://github.com/Dispatcharr/Plugins/commit/b6631dd1ce259173e32c28770fc45ade3cb88a86)

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

### [VOD to Media Library](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/vod2mlib/README.md)

**Version:** `1.16.0` | **Author:** R3XCHRIS | **Last Updated:** Jul 01 2026, 21:57 UTC

Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1503076618078261374) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/R3XCHRIS/VOD2MLIB)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.24.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.16.0`)](https://github.com/Dispatcharr/Plugins/releases/download/vod2mlib-1.16.0/vod2mlib-1.16.0.zip)
- [All Versions (5 available)](./metadata/vod2mlib)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/vod2mlib) | **Last Change:** [`3b8487b`](https://github.com/Dispatcharr/Plugins/commit/3b8487b78899906c8181804749514627eccd2f06)

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

**Version:** `1.30.1` | **Author:** jeff-gooch | **Last Updated:** Jul 31 2026, 23:07 UTC

Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering

[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-blue?style=flat-square)](https://spdx.org/licenses/Unlicense.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jeff-gooch/youtubearr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.30.1`)](https://github.com/Dispatcharr/Plugins/releases/download/youtubearr-1.30.1/youtubearr-1.30.1.zip)
- [All Versions (6 available)](./metadata/youtubearr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/youtubearr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/youtubearr/README.md) | **Last Change:** [`1e79c55`](https://github.com/Dispatcharr/Plugins/commit/1e79c55fd33ce921c6c938990945e0ab23a7ef07)

---


## Deprecated Plugins

These plugins are deprecated and may be removed in the future.

## Using the Manifest

Fetch `manifest.json` to programmatically access plugin metadata and download URLs:

```bash
curl https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

---

*Last updated: Aug 14 2026, 06:28 UTC*
