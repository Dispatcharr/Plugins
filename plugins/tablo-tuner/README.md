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

A reachable tablo-bridge instance (Docker, port 8050 by default). Tested against
Dispatcharr 0.33.0.

## Notes

The plugin never touches the bridge and never spawns a process — Dispatcharr runs
under gevent/uWSGI, where fork-based process spawning deadlocks.

Source, issues and releases: <https://github.com/jkoehler11/tablo-dispatcharr-plugin>
