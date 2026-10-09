[Back to All Plugins](../../README.md)

# Segmentarr

**Version:** `1.5.7` | **Author:** Tw1zT3d2four7 | **Last Updated:** Oct 09 2026, 14:25 UTC

HLS-segmenting stream profile for Dispatcharr: splits XC/URL provider streams into segments, repairs timestamp breaks, and delivers clean MPEG-TS through cvlc to a matching Output Profile.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Segmentarr)

## Downloads

### Latest Release

- **Download:** [`segmentarr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/segmentarr-1.5.7/segmentarr-1.5.7.zip)
- **Built:** Oct 09 2026, 14:25 UTC
- **Source Commit:** [`56c2220`](https://github.com/Dispatcharr/Plugins/commit/56c222040c2a2357c79de3d96d4142cbeeed01b6)

**Checksums:**
```
MD5:    b80879859cbc0098a1e6088e75a98574
SHA256: 183da7034a01073b45ad30da5ea7b523ab0b41fbbcc9b469801a40494027ce13
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.5.7` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/segmentarr-1.5.7/segmentarr-1.5.7.zip) | Oct 09 2026, 14:25 UTC | [`56c2220`](https://github.com/Dispatcharr/Plugins/commit/56c222040c2a2357c79de3d96d4142cbeeed01b6) | b80879859cbc0098a1e6088e75a98574 | 183da7034a01073b45ad30da5ea7b523ab0b41fbbcc9b469801a40494027ce13 |
| `1.5.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/segmentarr-1.5.6/segmentarr-1.5.6.zip) | Oct 09 2026, 13:20 UTC | [`1d958a6`](https://github.com/Dispatcharr/Plugins/commit/1d958a655b8c38443e6398ce0c1ef510620d2c7f) | 030ac155c0b3067dcbc1c776e1158d03 | aee5feff4b265ea7634e2818c0939ce3972e447224b025d896e52df016cdef7c |
| `1.5.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/segmentarr-1.5.3/segmentarr-1.5.3.zip) | Oct 08 2026, 21:21 UTC | [`86885f5`](https://github.com/Dispatcharr/Plugins/commit/86885f5a2be0fabda4774ace025470a447f751c3) | acfe8159dc85f145505815f3b994fde4 | 17f56e46804366451b60859a5460ac3306b87aefe297348f05b2a90202b72bfb |

---

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/segmentarr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Segmentarr

Hardware-free **stream stabilizer for [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr)**. It cuts an unstable IPTV provider stream (Xtream Codes or plain URL) into short HLS segments, repairs timestamp corruption segment by segment, and delivers clean MPEG-TS to Dispatcharr through a final `cvlc` stage over `pipe:1`.

```
provider (XC / URL)
   |  ffmpeg: -c copy -f hls   (keyframe-aligned segments in /dev/shm)
   v
supervisor: validate -> resync -> drop corrupt packets -> stitch PCR/PTS/DTS
   |  ffmpeg finalizer (copy)
   v
cvlc (configurable caching)  ->  pipe:1
   v
Dispatcharr Output Profile (audio stage)  ->  clients
```

## What it fixes

- **Timestamp breaks** - backward or forward PCR/PTS/DTS jumps are stitched onto one continuous clock. Healthy streams pass through byte-identical.
- **Corruption** - misaligned bytes are resynced and transport-error packets are replaced with null packets.
- **Provider stalls** - cvlc's network cache smooths short provider hiccups.
- **Falling behind** - if the queue grows past the catch-up limit it jumps back to live.
- **Dead connections** - ffmpeg reconnects on drops, and the supervisor restarts ingest if segments stop arriving.

## Install

1. In Dispatcharr, open **Plugins**, find **Segmentarr**, and install it.
2. Open the plugin settings and choose your options.
3. Press **Apply & Synchronize**.
4. Restart any channel that is already playing.

Apply creates a `Segmentarr Profile - ...` stream profile and a matching `Segmentarr Output - ...` output profile, and makes both the defaults. Older unlocked Segmentarr profiles are replaced; locked ones are left alone.

> Segmentarr and [Profilarr](https://github.com/Tw1zT3d2four7/Profilarr) both set the same default stream and output profiles. Whichever one you press Apply on last owns them.

## Requirements

- `ffmpeg` and `python3` inside the Dispatcharr container
- `cvlc` (VLC) inside the container, unless **CVLC Network Cache** is set to Off
- A tmpfs at `/dev/shm` (falls back to `/tmp`)

## Settings

| Setting | Default | Effect |
|---|---|---|
| Segment Profile | Standard (2s) | Standard 2s, Low Latency 1s, or Resilient 4s (waits for two segments before starting). |
| CVLC Network Cache | 1000 ms | Caching for the final cvlc stage. Off removes cvlc. |
| Stall Timeout | 25s | Restart the provider connection if no segment appears for this long. |
| Max Catch-up Backlog | 20s | Queued media beyond this is dropped to jump back to live. |
| Timeline Gap Tolerance | 1s | Forward PCR jumps up to this are kept; larger breaks are stitched. |
| Reconnect Delay Ceiling | 5s | Longest backoff between provider reconnects. |
| Provider I/O Timeout | 15s | Provider connection treated as dead after this long without data. |
| Stream Probe Time | 3s | How much stream ffmpeg analyses before starting. |
| Audio Transcoding Override | AAC | Audio codec applied by the Output Profile (AAC, AC3, E-AC3, Opus, MP3, Copy). |

Video and audio are copied in the stream stage; audio is transcoded once, in the Output Profile. Settings are baked into the wrapper scripts at Apply time, so re-apply and restart the channel after changing any of them.

## Tradeoffs

- Adds roughly one segment plus a keyframe wait of latency, plus the CVLC cache.
- Segments live in RAM (`/dev/shm`); 30s of an 8 Mbps stream is about 30 MB.

## Source

[github.com/Tw1zT3d2four7/Segmentarr](https://github.com/Tw1zT3d2four7/Segmentarr) - MIT licensed.
