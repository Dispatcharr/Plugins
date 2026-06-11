# Plugin Releases

This branch contains all published plugin releases.

## Quick Access

- [manifest.json](./manifest.json) - Complete plugin registry with metadata
- [metadata/](./metadata/) - Per-plugin manifests and READMEs

## Available Plugins

| Plugin | Version | Author | License | Description |
|--------|---------|-------|---------|-------------|
| [`Channel Mapparr`](#channel-mapparr) | `1.26.1430910` | PiratesIRC | MIT | Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries. |
| [`Dispatcharr Exporter`](#dispatcharr-exporter) | `3.0.1` | sethwv | MIT | Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring |
| [`Ranked Matchups (Top Games)`](#ranked-matchups-top-games-) | `1.2.0` | Jacob-Lasky | MIT | Cross-sport interestingness curator. Pulls upcoming games per enabled sport, scores them on interestingness, matches to Dispatcharr channels via EPG, and renames+groups them into a Top Matchups channel profile so your guide shows only the games worth watching. |
| [`Dispatchwrapparr`](#dispatchwrapparr) | `1.7.3` | jordandalley | MIT | An intelligent DRM/Clearkey capable stream profile for Dispatcharr |
| [`Embyfin Stream Cleanup`](#embyfin-stream-cleanup) | `1.2.0` | sethwv | MIT | Monitors Dispatcharr client activity and terminates idle Emby/Jellyfin connections |
| [`EPG Janitor`](#epg-janitor) | `1.26.1420824` | PiratesIRC | MIT | Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments. |
| [`EPGeditARR`](#epgeditarr) | `0.2.07` | jstevenscl | MIT | Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and provides a full SiriusXM toolkit: fill EPG from the community XMLTV (741 channels, sports smart blocks), sort into official lineup order, assign logos, and rename channels using the official SiriusXM API channel database. |
| [`Event Channel Managarr`](#event-channel-managarr) | `1.26.1600157` | PiratesIRC | MIT | Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG. |
| [`IPTV Checker`](#iptv-checker) | `1.26.1582047` | PiratesIRC | MIT | A Dispatcharr Plugin that goes through a playlist to check IPTV channels |
| [`Lineuparr`](#lineuparr) | `1.26.1431300` | PiratesIRC | MIT | Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them. |
| [`Multiview`](#multiview) | `0.1.0` | sethwv | MIT | Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg |
| [`Stream Dripper`](#stream-dripper) | `1.0.0` | Megamannen | Artistic-2.0 | Automatically drops all active streams once per day at a configured time, with a manual drop-now button. |
| [`Stream-Mapparr`](#stream-mapparr) | `1.26.1082140` | PiratesIRC | MIT | Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup. |
| [`Telegram Alerts`](#telegram-alerts) | `0.4.5` | R3XCHRIS | MIT | Push Dispatcharr channel/stream/VOD events to a Telegram chat via a bot. Includes a manual test action, per-event toggles, and an optional cron-driven daily report (public IP + geo + speedtest + activity + source health). |
| [`Tickarr`](#tickarr) | `0.1.01` | jstevenscl | MIT | Dynamic text overlays for IPTV channels - SiriusXM Now Playing, Sports Ticker, Custom Text |
| [`Twitcharr`](#twitcharr) | `1.2.25` | eliasbruno124-dev | MIT | Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback. |
| [`VOD to Media Library`](#vod-to-media-library) | `1.15.2` | R3XCHRIS | MIT | Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries. |
| [`Waybill`](#waybill) | `1.3.0` | Matthew-Beckett | MIT | Waybill matches, renames, and organizes any streams no matter the provider. Infinitely configurable pipelines for total control. |
| [`YouTubearr`](#youtubearr) | `1.20.0` | jeff-gooch | Unlicense | Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering |

---

### [Channel Mapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/channel-mapparr/README.md)

**Version:** `1.26.1430910` | **Author:** PiratesIRC | **Last Updated:** May 23 2026, 17:06 UTC

Standardizes broadcast (OTA) and premium/cable channel names using network data and channel lists. Supports M3U stream import, category organization, and fuzzy matching across 42K+ channels in 11 countries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422963882548265110) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Channel-Maparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1430910`)](https://github.com/Dispatcharr/Plugins/releases/download/channel-mapparr-1.26.1430910/channel-mapparr-1.26.1430910.zip)
- [All Versions (2 available)](./metadata/channel-mapparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/channel-mapparr) | **Last Change:** [`309559e`](https://github.com/Dispatcharr/Plugins/commit/309559e7795e3c0447f90067e0c011d8c1eb9d45)

---

### [Dispatcharr Exporter](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatcharr-exporter/README.md)

**Version:** `3.0.1` | **Author:** sethwv | **Last Updated:** May 10 2026, 18:26 UTC

Expose Dispatcharr metrics in Prometheus exporter-compatible format for monitoring

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1451260201775923421) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/dispatcharr-exporter)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.22.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`3.0.1`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-exporter-3.0.1/dispatcharr-exporter-3.0.1.zip)
- [All Versions (3 available)](./metadata/dispatcharr-exporter)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-exporter) | **Last Change:** [`b70abd6`](https://github.com/Dispatcharr/Plugins/commit/b70abd6df9cd520bcc28ad7fced085be135897a9)

---

### [Ranked Matchups (Top Games)](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatcharr-ranked-matchups/README.md)

**Version:** `1.2.0` | **Author:** Jacob-Lasky | **Last Updated:** Jun 11 2026, 14:00 UTC

Cross-sport interestingness curator. Pulls upcoming games per enabled sport, scores them on interestingness, matches to Dispatcharr channels via EPG, and renames+groups them into a Top Matchups channel profile so your guide shows only the games worth watching.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups)

**Downloads:**
- [Latest Release (`1.2.0`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.2.0/dispatcharr-ranked-matchups-1.2.0.zip)
- [All Versions (1 available)](./metadata/dispatcharr-ranked-matchups)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-ranked-matchups) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatcharr-ranked-matchups/README.md) | **Last Change:** [`bea9b43`](https://github.com/Dispatcharr/Plugins/commit/bea9b43cfed545635982722ed6c66f26e26a47f5)

---

### [Dispatchwrapparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/dispatchwrapparr/README.md)

**Version:** `1.7.3` | **Author:** jordandalley | **Last Updated:** Jun 07 2026, 12:42 UTC

An intelligent DRM/Clearkey capable stream profile for Dispatcharr

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1422776847703212132) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jordandalley/dispatchwrapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.25.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.7.3`)](https://github.com/Dispatcharr/Plugins/releases/download/dispatchwrapparr-1.7.3/dispatchwrapparr-1.7.3.zip)
- [All Versions (7 available)](./metadata/dispatchwrapparr)

**Maintainers:** michaelmurfy | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatchwrapparr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/dispatchwrapparr/README.md) | **Last Change:** [`bc522f1`](https://github.com/Dispatcharr/Plugins/commit/bc522f1f01c094273bded4b7b66350dc62d039fa)

---

### [Embyfin Stream Cleanup](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/embyfin-stream-cleanup/README.md)

**Version:** `1.2.0` | **Author:** sethwv | **Last Updated:** May 15 2026, 17:13 UTC

Monitors Dispatcharr client activity and terminates idle Emby/Jellyfin connections

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1491487318832447668) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/embyfin-stream-cleanup)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.22.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.2.0`)](https://github.com/Dispatcharr/Plugins/releases/download/embyfin-stream-cleanup-1.2.0/embyfin-stream-cleanup-1.2.0.zip)
- [All Versions (6 available)](./metadata/embyfin-stream-cleanup)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/embyfin-stream-cleanup) | **Last Change:** [`315a967`](https://github.com/Dispatcharr/Plugins/commit/315a967448ff4db469a66491ebc404bfb8e0bb42)

---

### [EPG Janitor](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epg-janitor/README.md)

**Version:** `1.26.1420824` | **Author:** PiratesIRC | **Last Updated:** May 22 2026, 14:19 UTC

Scans for channels with EPG assignments but no program data. Auto-matches EPG to channels using intelligent fuzzy matching with aliases, removes EPG from hidden channels, and manages EPG assignments.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1420051973994053848) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-EPG-Janitor-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1420824`)](https://github.com/Dispatcharr/Plugins/releases/download/epg-janitor-1.26.1420824/epg-janitor-1.26.1420824.zip)
- [All Versions (2 available)](./metadata/epg-janitor)

**Maintainers:** PiratesIRC | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epg-janitor) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/epg-janitor/README.md) | **Last Change:** [`a5ccaa9`](https://github.com/Dispatcharr/Plugins/commit/a5ccaa94fb0ddb806eb2ef36abef0c8a665afb8d)

---

### [EPGeditARR](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/epgeditarr/README.md)

**Version:** `0.2.07` | **Author:** jstevenscl | **Last Updated:** May 19 2026, 16:17 UTC

Transform and clean your EPG data using regex and find/replace rules. Creates virtual copies of your sources — originals are never touched. Fills placeholder schedules for channels with no EPG, and provides a full SiriusXM toolkit: fill EPG from the community XMLTV (741 channels, sports smart blocks), sort into official lineup order, assign logos, and rename channels using the official SiriusXM API channel database.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/epgeditarr)

**Downloads:**
- [Latest Release (`0.2.07`)](https://github.com/Dispatcharr/Plugins/releases/download/epgeditarr-0.2.07/epgeditarr-0.2.07.zip)
- [All Versions (3 available)](./metadata/epgeditarr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/epgeditarr) | **Last Change:** [`fc6f5f6`](https://github.com/Dispatcharr/Plugins/commit/fc6f5f6fff939c45828f221f47c3355b33cf4b66)

---

### [Event Channel Managarr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/event-channel-managarr/README.md)

**Version:** `1.26.1600157` | **Author:** PiratesIRC | **Last Updated:** Jun 09 2026, 13:28 UTC

Automates channel visibility by hiding channels without events and showing those with events, based on EPG data and channel names. Optionally manages dummy EPG for channels without real EPG.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1600157`)](https://github.com/Dispatcharr/Plugins/releases/download/event-channel-managarr-1.26.1600157/event-channel-managarr-1.26.1600157.zip)
- [All Versions (8 available)](./metadata/event-channel-managarr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/event-channel-managarr) | **Last Change:** [`76083e4`](https://github.com/Dispatcharr/Plugins/commit/76083e4d8945665024f9d01cd14041be1b5ad2ab)

---

### [IPTV Checker](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/iptv-checker/README.md)

**Version:** `1.26.1582047` | **Author:** PiratesIRC | **Last Updated:** Jun 08 2026, 00:12 UTC

A Dispatcharr Plugin that goes through a playlist to check IPTV channels

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1582047`)](https://github.com/Dispatcharr/Plugins/releases/download/iptv-checker-1.26.1582047/iptv-checker-1.26.1582047.zip)
- [All Versions (7 available)](./metadata/iptv-checker)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/iptv-checker) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/iptv-checker/README.md) | **Last Change:** [`78654d4`](https://github.com/Dispatcharr/Plugins/commit/78654d4e375d24bd55d49a800bf417c63e155c17)

---

### [Lineuparr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/lineuparr/README.md)

**Version:** `1.26.1431300` | **Author:** PiratesIRC | **Last Updated:** May 23 2026, 17:06 UTC

Mirror real-world provider channel lineups by creating channel groups, channels, and fuzzy-matching IPTV streams to them.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Dispatcharr-Lineuparr-Plugin)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1431300`)](https://github.com/Dispatcharr/Plugins/releases/download/lineuparr-1.26.1431300/lineuparr-1.26.1431300.zip)
- [All Versions (5 available)](./metadata/lineuparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/lineuparr) | **Last Change:** [`3924cbe`](https://github.com/Dispatcharr/Plugins/commit/3924cbe182e994de221ef776a7c151c5e7bc2c2e)

---

### [Multiview](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/multiview/README.md)

**Version:** `0.1.0` | **Author:** sethwv | **Last Updated:** Jun 04 2026, 16:03 UTC

Tile multiple Dispatcharr channel streams into multi-view outputs using FFmpeg

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Discord](https://img.shields.io/badge/Discord-Discussion-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.com/channels/1340492560220684331/1509200002407465001) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/swvn-dispatch/dispatcharr-multiview)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.22.0-brightgreen?style=flat-square) ![Dispatcharr max](https://img.shields.io/badge/Dispatcharr_max-v0.25.1-orange?style=flat-square)

**Downloads:**
- [Latest Release (`0.1.0`)](https://github.com/Dispatcharr/Plugins/releases/download/multiview-0.1.0/multiview-0.1.0.zip)
- [All Versions (1 available)](./metadata/multiview)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/multiview) | **Last Change:** [`5bddf4e`](https://github.com/Dispatcharr/Plugins/commit/5bddf4e19c75244ea27e321d8a178b1a3107dece)

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

**Version:** `1.26.1082140` | **Author:** PiratesIRC | **Last Updated:** Apr 18 2026, 22:09 UTC

Automatically add matching streams to channels based on name similarity and quality precedence. Supports unlimited stream matching, channel visibility management, and CSV export cleanup.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PiratesIRC/Stream-Mapparr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.26.1082140`)](https://github.com/Dispatcharr/Plugins/releases/download/stream-mapparr-1.26.1082140/stream-mapparr-1.26.1082140.zip)
- [All Versions (2 available)](./metadata/stream-mapparr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/stream-mapparr) | **Last Change:** [`4812211`](https://github.com/Dispatcharr/Plugins/commit/4812211adaa1d7d67b5a2ae8154e857eab5d5b13)

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

**Version:** `0.1.01` | **Author:** jstevenscl | **Last Updated:** Jun 02 2026, 21:10 UTC

Dynamic text overlays for IPTV channels - SiriusXM Now Playing, Sports Ticker, Custom Text

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jstevenscl/tickarr)

**Downloads:**
- [Latest Release (`0.1.01`)](https://github.com/Dispatcharr/Plugins/releases/download/tickarr-0.1.01/tickarr-0.1.01.zip)
- [All Versions (2 available)](./metadata/tickarr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/tickarr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/tickarr/README.md) | **Last Change:** [`489bbb5`](https://github.com/Dispatcharr/Plugins/commit/489bbb5253740ef509a4dd8d8545f03971b289e8)

---

### [Twitcharr](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/twitcharr/README.md)

**Version:** `1.2.25` | **Author:** eliasbruno124-dev | **Last Updated:** Jun 02 2026, 17:16 UTC

Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/eliasbruno124-dev/Twitcharr)

**Downloads:**
- [Latest Release (`1.2.25`)](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.2.25/twitcharr-1.2.25.zip)
- [All Versions (1 available)](./metadata/twitcharr)

**Maintainers:** eliasbruno124-dev | **Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/twitcharr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/twitcharr/README.md) | **Last Change:** [`ff09842`](https://github.com/Dispatcharr/Plugins/commit/ff09842b40864d9a56364f45b9c86618895b6206)

---

### [VOD to Media Library](https://github.com/Dispatcharr/Plugins/blob/releases/metadata/vod2mlib/README.md)

**Version:** `1.15.2` | **Author:** R3XCHRIS | **Last Updated:** Jun 11 2026, 14:01 UTC

Generate .strm files (with optional NFO metadata) from your Dispatcharr VOD catalogue so Jellyfin / Emby / Kodi / ChannelsDVR can index your movies and series. Adds a cron-driven auto-rescan that picks up newly-added episodes nightly. Optional category-nested folder layout for genre-organised libraries.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/R3XCHRIS/VOD2MLIB)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.24.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.15.2`)](https://github.com/Dispatcharr/Plugins/releases/download/vod2mlib-1.15.2/vod2mlib-1.15.2.zip)
- [All Versions (4 available)](./metadata/vod2mlib)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/vod2mlib) | **Last Change:** [`142c867`](https://github.com/Dispatcharr/Plugins/commit/142c8676b719565bb8453c4c3cfa3bd2efd053ff)

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

**Version:** `1.20.0` | **Author:** jeff-gooch | **Last Updated:** Jun 06 2026, 20:08 UTC

Zero-dependency YouTube livestream plugin with automatic monitoring and configurable numbering

[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-blue?style=flat-square)](https://spdx.org/licenses/Unlicense.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jeff-gooch/youtubearr)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-v0.20.0-brightgreen?style=flat-square)

**Downloads:**
- [Latest Release (`1.20.0`)](https://github.com/Dispatcharr/Plugins/releases/download/youtubearr-1.20.0/youtubearr-1.20.0.zip)
- [All Versions (4 available)](./metadata/youtubearr)

**Source:** [Browse](https://github.com/Dispatcharr/Plugins/tree/main/plugins/youtubearr) | [README](https://github.com/Dispatcharr/Plugins/blob/main/plugins/youtubearr/README.md) | **Last Change:** [`0900a37`](https://github.com/Dispatcharr/Plugins/commit/0900a376c840979b09ee5d3834e468d7c117094b)

---

## Using the Manifest

Fetch `manifest.json` to programmatically access plugin metadata and download URLs:

```bash
curl https://raw.githubusercontent.com/Dispatcharr/Plugins/releases/manifest.json
```

---

*Last updated: Jun 11 2026, 14:02 UTC*
