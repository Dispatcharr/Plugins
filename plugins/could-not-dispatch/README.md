# Could Not Dispatch

A Dispatcharr plugin that plays a looping image or video when every stream on a channel has
failed, so viewers see a message instead of an error. It can show a second card when the
provider is full, list the channels in use, and send channels back to their stream.

| Every stream failed | Provider full, with the channels in use |
|---|---|
| ![Card for a channel whose streams failed](https://raw.githubusercontent.com/PilaScat/could-not-dispatch/v0.7.3/docs/images/card-offline.png) | ![Card for a full provider, listing the channels in use](https://raw.githubusercontent.com/PilaScat/could-not-dispatch/v0.7.3/docs/images/card-full.png) |

The message is part of your picture. The plugin writes only the channels in use.

## Requirements

Dispatcharr with the Plugins page, and `ffmpeg` and `ffprobe`, already in its image.

## Install

From the Plugin Hub, or unzip the release into `/data/plugins` and press refresh on the
Plugins page. Enable the plugin, fill in the settings, press **Apply**.

## Settings

| Setting | What it does |
|---|---|
| Image or video | A path in the data volume or an `http(s)` link |
| Image or video when the provider is full | Optional second card, for channels that found no free connection. Needs the API key |
| Show the channels in use | Writes them on the second card, with the programme on now |
| Height of the channels in use (%) | Where the first line starts, from the top. 58.5 by default |
| Font for the channels in use | Optional `.ttf`, `.otf` or `.ttc`. Empty: the container's sans-serif |
| Local port | Change it only on a conflict |
| Width, Height | Both at 0 to match the picture, up to 1920x1080 |
| Frames per second | 25 by default. Keep your channels' rate: Jellyfin keeps a session's first one |
| Stream bitrate | kbit/s, 2000 by default |
| Excluded groups, Excluded channels | One group, or one channel number or name, per line |
| Cover new channels automatically | Covers the channels an M3U refresh adds |
| API key | A Dispatcharr API key, needed to send channels back |

## Actions

| Action | What it does |
|---|---|
| Apply settings | Starts the card and adds it, last, to every channel not excluded |
| Check status | Says whether the card runs and how many channels carry it |
| Cover new channels | Covers channels that lack it. Runs after every M3U refresh |
| Restart fallback | Restarts the card if it is down. Runs when a channel starts |
| Remove fallback | Detaches the card and deletes its streams |

## What to expect

- **Each channel gets one more stream**, last in its failover list, which Dispatcharr counts
  as an HDHomeRun tuner. Your provider's limit is unchanged.
- **With an API key, channels go back.** After 30 seconds on the card, then after 1, 2 and
  every 5 minutes, the plugin opens the channel's streams in order and switches it to the first
  that sends data, so a dead stream does not interrupt the viewer. The check uses a free
  connection, counted like any other, or waits for one.
- **A full provider gets the second card**, for a channel whose streams are all on accounts at
  their limit, and the channel goes back as soon as a connection frees up.
- **The channels in use** are centred lines, 50 px high on a 1080p card, in grey `#606469`:
  leave that part of the picture empty.
- **Jellyfin can stall after a switch** with the `FFmpeg` stream profile, which starts the
  timestamps again near zero
  ([Dispatcharr#1946](https://github.com/Dispatcharr/Dispatcharr/issues/1946)). A
  [Reservoarr](https://github.com/PilaScat/reservoarr) profile with
  `RESV_TS_CHANNEL={channelId}` keeps them going forwards.
- **A card costs CPU only while watched**: about 0.4 core for a 1080p picture and 0.55 for a
  1080p video, under a 1 CPU limit.
- **A channel on the card never reports as down**: watch the `channel_failover` events.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m mypy could_not_dispatch plugin.py
.venv/bin/python -m ruff check .
.venv/bin/python scripts/build_zip.py
```

Decisions, traps and the release routine are in
[docs/MEMORY.md](https://github.com/PilaScat/could-not-dispatch/blob/master/docs/MEMORY.md).

## Licence

MIT. See [LICENSE](https://github.com/PilaScat/could-not-dispatch/blob/master/LICENSE).
