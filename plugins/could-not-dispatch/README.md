# Could Not Dispatch

A Dispatcharr plugin that plays a looping image or video when every real stream on a
channel has failed, so viewers see a message instead of a black screen.

When all of a channel's streams are down, Dispatcharr runs out of alternatives and drops
the client with a 503. From the sofa that looks the same as a broken router. This plugin
adds one more stream to the end of every channel — a stream that always works — so the
failover lands on a card that explains what is going on.

The message lives in the picture you supply. The plugin does not draw text.

## Requirements

- Dispatcharr with the plugin system (the Plugins page)
- `ffmpeg` and `ffprobe`, both already in the Dispatcharr image

## Install

From the Plugin Hub, or by unzipping the release into `/data/plugins/could-not-dispatch`
and pressing refresh on the Plugins page. Enable the plugin, fill in the settings, press
**Apply**.

## Settings

| Setting | What it does |
|---|---|
| Image or video | A path inside the data volume, such as `/data/offline.png`, or an `http(s)` link that is downloaded and cached |
| Local port | Where the fallback listens inside the container. Change it only on a conflict |
| Width, Height | Leave both at 0 to match the picture, up to 1920x1080. Set both to force a size; the picture is fitted inside and padded to keep its shape |
| Frames per second | 5 is plenty for a still card |
| Stream bitrate | kbit/s, default 2000. Lower it only if bandwidth matters more than the picture |
| Excluded groups | One channel group name per line |
| Excluded channels | One channel number or channel name per line |
| Cover new channels automatically | Attaches the fallback to channels added by an M3U refresh |

## Actions

| Action | What it does |
|---|---|
| Apply settings | Starts the fallback and attaches it, last in order, to every channel that is not excluded. Saving a setting changes nothing until Apply runs, and a viewer already watching the card keeps the old encode until they reopen the channel |
| Check status | Reports whether the fallback is running and how many channels carry it |
| Cover new channels | Attaches it to channels that do not carry it yet. Also runs by itself after an M3U refresh |
| Restart fallback | Starts it again if it is down. Also runs by itself when a channel starts, at most once a minute |
| Remove fallback | Detaches it everywhere, stops it, deletes its stream |

## How it works

The plugin runs a small process next to Dispatcharr. That process keeps one `ffmpeg`
alive, looping your file into MPEG-TS, and serves it over HTTP at
`http://127.0.0.1:<port>/slate.ts`. Every viewer of the fallback shares that one encode.
The encoder starts when the first viewer arrives and stops fifteen seconds after the last
one leaves, so an idle server costs nothing.

That URL is registered as a Dispatcharr custom stream and attached to each channel with
the highest order number, which puts it last in the failover list. Dispatcharr's own
failover does the rest: it walks the channel's streams in order, and the fallback is the
only one that cannot fail.

A custom stream belongs to the built-in `custom` M3U account, which has no connection
limit, so the fallback never competes for a slot with your provider.

### How long the card takes to appear

Dispatcharr buffers four 256 KB chunks — one megabyte — before it sends a client
anything. A still picture compresses to almost nothing, so an ordinary encode of it would
trickle out at some 15 kbit/s and the viewer would wait about nine minutes.

The fallback therefore encodes at a genuinely constant bitrate, padding each frame with
H.264 filler data (`nal-hrd=cbr:filler=1`). The padding lives inside the video, so it
survives the remux that Dispatcharr's default `ffmpeg` stream profile performs — transport
stream stuffing would not, because `-c copy` discards null packets.

Sending that megabyte at the stream's own rate would take two seconds, so the fallback
does not wait: ffmpeg reads the first seconds of input as fast as it can
(`-readrate_initial_burst`, sized from the bitrate so the burst always covers a megabyte),
and a viewer arriving while the encoder is already running is handed the last stretch of
stream from a rolling buffer, starting at a keyframe.

Measured inside the Dispatcharr image, the megabyte lands **0.29 s** after a cold
connection and **0.01 s** for a viewer joining a running encoder. What remains is
Dispatcharr's own failover — three connection attempts on the dead stream before it
switches — which is roughly a second and a half and is not the plugin's to shorten.

### Dark backgrounds

A card on a dark gradient is the hardest thing to encode here: flat near-black areas band
and break into blocks long before anything else does. Two settings decide how bad it gets,
and both are free.

x264's `stillimage` tune weakens deblocking, which is the opposite of what a gradient
needs, so the encoder does not use it. And the VBV buffer is four seconds rather than one,
which lets a keyframe spend what it needs instead of being clipped to a single second of
budget.

Measured on the dark quadrant of a 1080p card, the two together are worth about as much as
doubling the bitrate: 61.4 dB at 2000 kbit/s against 56.1 with the `stillimage` tune and a
one-second buffer, and 65.5 against 61.8 at 4000.

No `-tune` is set at all, which matters more than either. `zerolatency`, the obvious choice
for a stream that has to start fast, switches off x264's lookahead: the rate control then
works frame by frame and the picture visibly pulses between clear and banded. Keeping the
lookahead flattens that — at 2000 kbit/s the spread across frames is 2.6 dB rather than
8.2, and the worst frame 63.1 rather than 57.9 — which is why the default rate is 2000 and
not 4000: with the lookahead, 2000 beats 4000 without it, at half the bytes on the wire.

Lookahead costs startup latency, which is what `zerolatency` would have avoided. The
initial burst pays for it instead: it is sized to cover the lookahead as well as the
megabyte, so nothing is given up.

## What to expect

**A channel carrying the fallback never reports as down.** The fallback is a healthy
stream, so Dispatcharr considers the channel up. To spot real outages, watch the
`channel_failover` system events rather than channel state.

**Playback does not return to the provider on its own.** Once a viewer is on the card
they stay there until they change channel. This is deliberate: cutting away mid-message
would be worse than leaving it up.

**One edge case in failover order.** Dispatcharr rotates the alternate list starting from
the current stream and wraps around. If the first stream of a channel was unavailable
when the viewer connected, the rotation can reach the fallback before retrying the
streams that sit *before* the current one. It only happens when M3U profiles are at
capacity, and it costs one retry.

**The HDHomeRun tuner count grows by one.** Dispatcharr adds custom streams to the number
of tuners it advertises.

**Restarting Dispatcharr leaves the fallback down until it is needed.** The next channel
start brings it back by itself; **Restart fallback** does it immediately.

**The plugin keeps a small state file** at `.runtime/state.json` inside its own folder,
holding the process it started and the stream it created. It cannot live in the plugin
settings: saving those replaces the whole object, which would erase it.

## Source and licence

[github.com/PilaScat/could-not-dispatch](https://github.com/PilaScat/could-not-dispatch) — MIT.
