## Check IPTV stream status, analyze stream quality, and manage channels based on results

## Warning: back up your database first

This plugin renames, moves and can permanently delete channels. Before using it,
**[make a backup of your Dispatcharr database](https://dispatcharr.github.io/Dispatcharr-Docs/troubleshooting/?h=backup#how-can-i-make-a-backup-of-the-database)**.

## What it does

Probes every stream behind your channels with `ffprobe`, records what it finds, and lets you act on
the result.

It answers three questions per stream, and keeps them apart because acting on the wrong one
deletes channels that work:

- Alive. The stream plays. Resolution, framerate, codecs and bitrate are recorded and synced
  back into Dispatcharr so the channel menu can show them.
- Dead. The stream does not play, or it plays but shows nothing worth watching: a blank picture,
  a frozen picture, silence, or a fixed-duration placeholder file. Those last four are opt-in.
- Skipped. The checker could not judge it. That covers a provider rate-limit response, a
  radio station with no video track, and hosts `ffprobe` cannot read at all. **Skipped is never
  treated as dead**, so nothing destructive touches a stream that was merely throttled.

**A channel is judged by all of its streams, never by one of them.** Most channels carry a primary
and one or more backups, and Dispatcharr fails over between them. A channel is only reported dead
when **every** stream failed, so one dead backup never marks a working channel for deletion.

Other things it does:

- Scheduled checks, including overnight windows that pause at a set time and resume where they
  left off on the next window.
- An HTML report written to `/config/iptv_checker/report.html`, grouped by what you should do
  about each finding, and optionally emailed through the
  [Newsflasharr](https://github.com/PiratesIRC) plugin. It is one self-contained file that fetches
  nothing from the internet, so it reads the same in a mail client and on a television browser, and
  it follows a light or dark theme on its own.
- CSV export with a preamble that says what the run did before it says how it was configured, so
  every run leaves a record. Old exports can be deleted automatically after a number of days you
  choose.
- Rename, move, restore and delete actions. Only deleting is irreversible, and only that button is
  red.
- Self-healing: a channel that comes back to life is renamed back and moved to its original
  group automatically.

## Requirements

- Dispatcharr v0.20.0 or newer, with channels and groups already configured.
- `ffprobe` in the container, and `ffmpeg` as well if you enable blank-screen, frozen-video or
  silent-audio detection.
- `pytz` for the scheduler, which is normally already present.

```bash
docker exec dispatcharr which ffprobe
docker exec dispatcharr which ffmpeg
```

No API credentials are needed. The plugin runs inside Dispatcharr with direct database access.

## Install

1. Log in to Dispatcharr and go to **Plugins**.
2. Click **Import Plugin** and upload the release zip.
3. Enable the plugin.

**To update**, delete the old plugin in the Plugins page, restart the container
(`docker restart dispatcharr`), then import the new zip. Your settings are preserved.

## Quick start

1. Set **Channel Groups** and **Channel Groups Mode**. Leave the box empty to check every group.
2. Click **Validate** to confirm the plugin can see your groups. It reports how many groups will be
   checked.
3. Click **Load Groups**, then **Start Check**.
4. Watch **View Progress**, then read **View Results** or **Email Report**.

## Documentation

**[Full user guide](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/blob/main/docs/USER-GUIDE.md)** covers every setting and button, the detection modes,
scheduling and windowed runs, the HTML report and email delivery, and troubleshooting.

- [Development workflow](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/blob/main/DEVELOPMENT.md)
- [Release notes](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/releases)

## Versioning

Calver `1.26.{DDD}{HHMM}`, being the UTC day-of-year and UTC hour-minute, matching the Lineuparr,
Channel-Mapparr and EPG-Janitor plugins. Releases before `1.26.1081815` used semver.

## Contributing

Issues and pull requests are welcome. When reporting a problem, please include your Dispatcharr
version, the relevant container logs
(`docker logs dispatcharr | grep "IPTV Checker"`), and the exact error text.

Contribution steps, the CI gates, and how updates reach the Dispatcharr plugin marketplace are in
[DEVELOPMENT.md](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/blob/main/DEVELOPMENT.md).

## Disclaimer

This plugin makes bulk changes to your channel database, including permanent deletion when you
enable it. Test on a small group first, keep a database backup, and read what an action says it will
do before confirming it.

## Anonymous usage counts

The Streams Checked and Active Installs badges count every install that leaves
the "Share anonymous usage counts" setting (on by default) ticked and runs at
least one action or check. When an action or check finishes, at most once an
hour, or ten minutes after the last report when a check has just checked
streams, the plugin sends this plugin's Streams Checked total and a random id
for this plugin on this install to the plugin author's counter at
plugin-stats.dpas.workers.dev. The server stores that id with the total and the
date of the last report. The connection shows the server your public IP
address; the server uses it only to limit abuse and does not store it in its
database, though when an install first registers it keeps a salted one-way hash
of it (of its /64 block for IPv6) for up to three days. Cloudflare, which hosts
the server, keeps its own request logs. No names, channels, streams, URLs,
providers or settings are sent. The figures are self-reported by installs and
capped by the server, not verified. Untick the setting to stop sending; this
install's figures are deleted from the server the next time an action or check
finishes after you untick. Details: [User Guide](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/blob/main/docs/USER-GUIDE.md#anonymous-usage-counts).

## License

MIT. See [LICENSE](https://github.com/PiratesIRC/Dispatcharr-IPTV-Checker-Plugin/blob/main/LICENSE).
