[Back to All Plugins](../../README.md)

# Tablo Tuner

**Version:** `0.1.0` | **Author:** jkoehler11 | **Last Updated:** Nov 01 2026, 16:21 UTC

Connects a legacy Tablo through tablo-bridge: creates the M3U account, XMLTV source, channels and EPG mapping, and keeps them in sync.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jkoehler11/tablo-dispatcharr-plugin)

## Downloads

### Latest Release

- **Download:** [`tablo-tuner-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/tablo-tuner-0.1.0/tablo-tuner-0.1.0.zip)
- **Built:** Nov 01 2026, 16:22 UTC
- **Source Commit:** [`7c61de3`](https://github.com/Dispatcharr/Plugins/commit/7c61de324ad4d0db9ce863ebc2818277083277b3)

**Checksums:**
```
MD5:    7d3e4ad64e6039cdc6f0d499a10286f8
SHA256: 97740df8e8fac980632a8d8d65014b2aa4b8edae73f60e7ddb52604e4aeb6640
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `0.1.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/tablo-tuner-0.1.0/tablo-tuner-0.1.0.zip) | Nov 01 2026, 16:22 UTC | [`7c61de3`](https://github.com/Dispatcharr/Plugins/commit/7c61de324ad4d0db9ce863ebc2818277083277b3) | 7d3e4ad64e6039cdc6f0d499a10286f8 | 97740df8e8fac980632a8d8d65014b2aa4b8edae73f60e7ddb52604e4aeb6640 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/tablo-tuner)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Tablo Tuner

Connects Dispatcharr to a [tablo-bridge](https://github.com/jkoehler11/tablo-legacy-m3u)
playlist, which exposes a legacy Nuvyyo Tablo (2‑Tuner, firmware 2.2.x) as an
ordinary IPTV source. The bridge handles tuning and session sharing; this plugin
handles everything downstream.

## What it does

- Creates or fixes the **M3U account** pointing at `<bridge>/playlist.m3u`.
- Creates or fixes the **XMLTV source** pointing at `<bridge>/guide.xml`.
- Gives every stream a **channel** (dial number from `tvg-chno`, name from
  `tvg-name`) using the locked **Proxy** profile — Streamlink, VLC and ffmpeg
  profiles all fail on a raw MPEG-TS URL.
- Raises `stream_startup_timeout` and `connection_timeout`, because a Tablo takes
  6–11 s to allocate a tuner and Dispatcharr's 8 s default declares the channel
  dead before the first byte arrives.
- Maps each channel to its guide entry by `tvg-id`, then by display name.
- Optionally adds the channels to a Dispatcharr channel profile.

## Actions

| Action | What it does |
| --- | --- |
| **Set up Tablo live TV** | Idempotent bootstrap. Safe to re-run; reports what it changed. |
| **Re-sync channels** | Refresh the playlist, add new channels, prune links to streams that vanished, retire channels this plugin created. Channels you made yourself are never touched. |
| **Show status** | Read-only: bridge reachability, account/source presence, proxy timeouts, channels without guide data. |

## Requirements

A reachable [tablo-bridge](https://github.com/jkoehler11/tablo-legacy-m3u)
instance (Docker, port 8050 by default) and Dispatcharr 0.33.0 or newer.

### Which hardware this works with

The bridge needs the legacy local REST API on port 8885. `curl -s
http://<tablo-ip>:8885/server/info` returning JSON with a `model` field means the
unit is supported.

| Hardware | Works | Notes |
| --- | --- | --- |
| Legacy network Tablo — 2-Tuner, 4-Tuner, DUAL LITE, QUAD (Nuvyyo era, firmware 2.2.x) | **Yes** | Written against a Tablo 2-Tuner on 2.2.60. No authentication on any endpoint. Set *Concurrent streams (tuners)* to the unit's real tuner count. |
| 4th-generation Tablo (2023+, current models) | **No** | No local API; cloud-managed and cloud-authenticated only, so there is nothing for the bridge to connect to. |
| Legacy HDMI-only models (DUAL HDMI, QUAD HDMI) | **No** (expected) | HDMI output to a TV rather than network streaming; different firmware branch. |
| HDHomeRun and other network tuners | Not applicable | Already speak M3U/HDHomeRun or are natively supported by Dispatcharr — no bridge needed. |

## Notes

The plugin never touches the bridge and never spawns a process — Dispatcharr runs
under gevent/uWSGI, where fork-based process spawning deadlocks.

Source, issues and releases: <https://github.com/jkoehler11/tablo-dispatcharr-plugin>
