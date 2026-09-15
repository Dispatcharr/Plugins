[Back to All Plugins](../../README.md)

# Underfed

**Version:** `0.4.0` | **Author:** PilaScat | **Last Updated:** Sep 15 2026, 11:41 UTC

Moves a channel to its next source when the provider keeps delivering the stream, but at a fraction of the bitrate the content needs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/PilaScat/underfed)

## Downloads

### Latest Release

- **Download:** [`underfed-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/underfed-0.4.0/underfed-0.4.0.zip)
- **Built:** Sep 15 2026, 11:41 UTC
- **Source Commit:** [`c800f7e`](https://github.com/Dispatcharr/Plugins/commit/c800f7e99fea3c625a96061f2ba8a52fe596d4c3)

**Checksums:**
```
MD5:    f2fd14dbcdc951499290bd391f0d8d43
SHA256: 191c82987939f14ee6c477e069037e0d02609c09793718b2e60bff8fd2e94967
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `0.4.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/underfed-0.4.0/underfed-0.4.0.zip) | Sep 15 2026, 11:41 UTC | [`c800f7e`](https://github.com/Dispatcharr/Plugins/commit/c800f7e99fea3c625a96061f2ba8a52fe596d4c3) | f2fd14dbcdc951499290bd391f0d8d43 | 191c82987939f14ee6c477e069037e0d02609c09793718b2e60bff8fd2e94967 |
| `0.3.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/underfed-0.3.2/underfed-0.3.2.zip) | Sep 14 2026, 20:13 UTC | [`68f1181`](https://github.com/Dispatcharr/Plugins/commit/68f11812be1864f33d9fc130497071908dbdca97) | 597f324791f1f7c5ea471e262b062e7e | a6451dcc46d5be26958cc8cd3a318797499509de713f8f0f04c9bf0dd424dd19 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/underfed)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Underfed

A Dispatcharr plugin that moves a channel to its next source when the provider keeps
delivering the stream, but at a fraction of the bitrate the content needs.

Every failover in the chain waits for a source to *fail*. This one never does. The bytes
keep arriving, just not enough of them: the picture needs 4.4 Mbps and 1.0 Mbps shows up.
Nothing times out, nothing errors, nothing switches. The buffer drains, the player runs
out of segments, and viewers sit there watching a stall that no log explains.

Underfed reads the number that already exists and that nothing else acts on. It also reads
a second one: the timestamp discontinuities ffmpeg logs when a source's sound drifts away
from the picture.

## Requirements

- Dispatcharr with the plugin system (the Plugins page)
- [reservoarr](https://github.com/brko7/reservoarr) as the stream profile, which writes the
  telemetry this plugin reads
- A Dispatcharr API key

## Install

From the Plugin Hub, or by unzipping the release into `/data/plugins`, which creates the
`underfed` folder, and pressing refresh on the Plugins page. Enable the plugin, fill in the API key, press **Apply**.

**Leave Observe only on for the first evening.** It records what it would have switched and
changes nothing. Read the journal under Check status, then turn it off.

## Settings

| Setting | What it does |
|---|---|
| API key | A Dispatcharr API key, from Settings → Users. The watcher needs it to read channel status and to change source |
| Observe only | Records what it would have done without doing it |
| Trigger below | Share of the content rate under which a source counts as underfed. 70 is a sensible floor: a healthy source sits at 100 |
| Confirm for | How long a shortfall, or the timestamp discontinuities, must last before acting. Short dips recover on their own |
| Switches per hour | Per channel, over the last hour, restarts of the watcher included. Stops it bouncing between two sources that are both weak |
| Ignore first | Right after a channel opens the measured content rate is not trustworthy yet |
| Stable after | A source that holds up this long is treated as recovered. A shorter recovery keeps the shortfall counting, so a source that flickers is still caught |
| Timestamp discontinuities | Per minute, per source. A healthy source logs a handful, one whose sound drifts away from the picture hundreds. At this many, for Confirm for, the source is switched. 0 turns it off |
| Excluded channels | One channel name per line |
| reservoarr log | Where reservoarr writes `delaybuf.log`. Change it only if `RESV_LOG_DIR` was moved |
| Dispatcharr URL | Reached from inside the container |

## Actions

| Action | What it does |
|---|---|
| Apply settings | Starts the watcher, or restarts it with the new settings. Saving a setting changes nothing until Apply runs |
| Check status | Whether the watcher is running, and the journal of what it switched, skipped and failed |
| Replay the log | Runs the current thresholds over the whole log and reports how many times each source would have triggered. Nothing is touched, so it is the safe way to try a threshold before it goes live. It counts triggers, not switches: viewers, exclusions, the slate and the hourly limit are not in the log |
| Restart watcher | Starts it again if it is down, with the settings of the last Apply and the API key as saved now. Also runs by itself when a channel starts, at most once a minute |
| Stop watcher | Stops it. Channels keep whatever source they are on |

## How it works

reservoarr holds a cushion of stream and prints a line every fifteen seconds for every feed
it is pulling:

```
2026-09-08T20:18:57+0000 [202121.ts] cushion=0s(pcr) buf=0.1MB out=1.18Mbps
in=1.00Mbps crate=4.44Mbps in_total=1589MB reconnects=2 ccerr=1 ...
```

`crate` is what the picture needs. `cushion` is how many seconds of stream are left in hand.
What the provider is sending is read off `in_total`, the bytes the feed has taken in so far:
the difference over the last 45 seconds. `in` says the same thing averaged over two minutes,
so after a sudden drop it lags by a minute or more; it is used only until a feed has 30
seconds of `in_total` behind it, and for lines without the counter. When the ingest sits well
under `crate` and the cushion has reached zero, the source is being starved and the viewer is
about to see it. A feed whose `crate` is under 0.5 Mbps is never judged: a content rate that
low is not trustworthy.

The watcher follows that file, and when a feed stays under the threshold for the
confirmation window it calls `POST /proxy/ts/next_stream/<uuid>`, which is the same thing
the Dispatcharr interface does when you change source by hand. The channel moves to the next
entry in its chain and the viewer keeps watching.

Some sources arrive with their audio and video timestamps minutes apart. ffmpeg keeps one
offset for the whole input and flips it on every packet, so each packet gets the time ffmpeg
expected: a gap in the video disappears instead of freezing the picture, and the sound falls
behind by that much. Every gap adds to it, and reopening the channel only starts the count
again. reservoarr's ffmpeg logs it in `delaybuf.log`, in pairs:

```
2026-09-14T17:35:25+0000 [542059.ts] ffmpeg: [vist#0:0/h264 @ …] timestamp discontinuity (stream id=256): 331826689, new offset= 0
2026-09-14T17:35:25+0000 [542059.ts] ffmpeg: [aist#0:1/aac @ …] timestamp discontinuity (stream id=257): -331826689, new offset= 331826689
```

A healthy source logs a handful of these a minute; that one logged up to 1,836. When a source
stays at Timestamp discontinuities or above for the confirmation window, counted over the last
minute, the watcher moves the channel on the same way.

It refuses to act when any of these is true:

- the channel is not streaming, or nobody is watching it
- the channel is in Excluded channels
- the watcher has seen the source for less than the warm-up window, where `crate` may still be settling: it counts from the first telemetry line it reads for that source, so it starts over after a gap of more than 45 seconds in the log or a watcher restart
- the channel has already been switched too often this hour
- the next entry in the chain is the fallback slate
- there is no entry after the current one

Everything it does, and everything it declines to do, goes to a journal with the numbers
that justified it.

## What this does not fix

A chain whose sources all come from the same upstream. If `Sky Sport Uno FHD`, `HD`, `SD`
and `HEVC` are four encodes of one feed, moving between them moves nothing. Underfed can
only reach for what the chain offers, so put a genuinely different list second.

It also cannot help a source that stops dead. That case already has a watchdog: reservoarr
reconnects after `RESV_STALL_S`, and Dispatcharr walks the chain after three failed attempts.

## Development

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
pytest && mypy . && ruff check . && python scripts/build_zip.py
```

The same four checks run in CI on every push. Decisions, traps and the release routine are in
[docs/MEMORY.md](https://github.com/PilaScat/underfed/blob/master/docs/MEMORY.md).

## License

MIT
