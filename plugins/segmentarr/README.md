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
