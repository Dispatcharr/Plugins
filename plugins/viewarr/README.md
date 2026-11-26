# Viewarr plugin for Dispatcharr

The server half of [Viewarr](https://github.com/petebutty/viewarr), the Android TV app for [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr).

Viewarr works without this plugin, but then every TV does all the work itself. With the plugin, Dispatcharr does that work **once for the whole house** and leaves the answers in each person's own Dispatcharr storage. Each TV just reads them, so:

- the TVs are quicker, which helps most on weaker boxes;
- sport recordings and live scores keep going with every TV switched off.

If the plugin is missing or stops, the TVs go back to doing the work themselves. Nothing breaks.

## What it does

### Every 5 minutes

- **Best stream first.** For every channel with more than one stream, the best stream is put first in Dispatcharr, so every app and TV in the house starts on it. See [Best stream first](#best-stream-first).
- **Measuring streams (at night).** Every stream's real picture size and codec, measured with ffprobe in a quiet window so the ranking uses facts rather than name tags. See [Measuring streams](#measuring-streams).
- **Just added.** Once a day it reads what arrived on each streaming service in the UK over the last fortnight (older films newly added, and new seasons of shows), from JustWatch's web feed, and hands it to every TV for Viewarr's "<service> · Just added" rows. TMDB can't do this: it knows which service has a title, not when it arrived. **Behind a VPN** (JustWatch refuses VPN addresses), an admin's TV fetches the lists over your own connection and hands them to the plugin (Viewarr 0.29.9.3 or later); you can then set the Just added source to Off so the plugin stops trying itself.
- **Reports from the TVs.** Wrong guide, guide times out, dead stream, wrong logo or name, reported from Viewarr, are fixed straight away and can be undone. See [Reports from the TV](#reports-from-the-tv).
- **Live now.** It goes through your guide and sports and event groups, and keeps only real live sport:
  - entries the guide marks as live;
  - event channels from 30 minutes before the start;
  - no filler, no "No fixtures today" and no stream-name channels.

  Each TV then applies its own choices: groups, sports, leagues and "Only what I follow".
- **Where every followed game is on.** It collects the teams and leagues anyone in the house follows, then gets their fixtures and scores from ESPN. For each game it works out which of your channels shows it (see [UK football on TV](#uk-football-on-tv)). This feeds Viewarr's Sports page, the game cards and **Watch**.
- **Sport recordings.** For **Record all &lt;team&gt;**, or **Record** on a game the guide doesn't list yet, it creates the recording in Dispatcharr as soon as the guide lists the game. This works even with every TV off.
- **IPTV progress sync (optional, for people without Trakt).** It keeps someone's IPTV watch progress in step with their own Emby, Jellyfin or Plex, in both directions, matched by TMDB id. Finish a film on IPTV and it's ticked in Plex.
  - It only touches titles they've played on IPTV.
  - Each person switches it on for themselves in Viewarr → Settings → Playback → Watch progress.
  - If you use Trakt, leave it off: Trakt already does this.

### Every 45 seconds while a followed game is live

- **Score alerts and live scores:** kick-off, goals, half-time, full time and the result, with sport-aware wording ("Tip-off", "Puck drop", "TOUCHDOWN"). Basketball gets no alert for every basket.
- **Alerts are off for everyone** until they choose a team in Viewarr → Settings → Sports. Each TV shows only the alerts its own person switched on.
- The same scores feed Viewarr's news ticker.

### Every second, while a TV watches live TV

- **Live timeshift:** pause, rewind and fast-forward any live channel, not only ones with catch-up. While a TV watches a channel, ffmpeg copies it from Dispatcharr's own proxy (which shares the provider connection with everyone watching, so no extra connection) into a sliding HLS playlist of the last couple of hours, under `/data/logos/viewarr-ts/<random token>/` (see [where the buffer is kept](#live-timeshift-where-the-buffer-is-kept)). Every TV on that channel shares the one copy. Live TV plays as usual; only a pause or rewind moves the TV onto the copy. A TV asks through its own Dispatcharr app data (`viewarr_timeshift_req`), which the plugin checks every second, and reads the answer from `viewarr_timeshift`. The copy stops, and its files are deleted, as soon as no TV wants it (at once on a channel change, or a minute after a TV goes quiet). Each person can switch it off in Viewarr → Settings → Live TV.

### When asked

- **Backups** of an admin's whole Viewarr setup (Viewarr → Settings → Users & profiles → Backups). The settings are saved, and sign-ins are encrypted with the admin's own Dispatcharr key. The newest 30 are kept, in Dispatcharr's plugin data folder, reachable only by admins.
- **Sports service status** and **Refresh sports now** buttons on the plugin's page in Dispatcharr (a refresh is queued: the service runs the round within a minute).
- **Preview stream order** (shows what would change now, changing nothing) and **Put stream order back**, **Undo a change**, **Recent changes from reports** and **Measure streams now** buttons (see below).
- **What it did last**, in Viewarr (Settings → Plugins → Viewarr, admins only): one line per job with its last run, for example "Best stream first · 15:06 · 2 channels reordered" or "Measuring streams · 06:58 · Last night: 40 streams measured, all done". Anything that failed or needs a look says so. Kept up to date every round (app data key `viewarr_activity`, written for admins only).

## Outside sources (optional)

The plugin contacts **no outside site** unless you choose it in the plugin's settings. Each is a simple choice: **Off** (the default) or its one source. Off, the features that use it work from your Dispatcharr guide only, or not at all.

| Setting | Source to choose | Used for | Off |
|---|---|---|---|
| **Sports data** | ESPN | Sports page fixtures, results and live scores; Live now's headline games; score checks | Games from your guide only |
| **UK TV listings for games** | live-footballontv.com | Which UK channel shows each football game, weeks ahead | Channels from your guide only |
| **Just added** | JustWatch | What's new on each UK streaming service, for Viewarr's Just added rows | No Just added rows |

These are free public sites, not run by this plugin's author, and none of them is sent anything about you or your server beyond the request itself. An install from before these settings existed has all three chosen once on update, so nothing it used stops working.

## Best stream first

Dispatcharr plays a channel's streams in their saved order and only moves on when one fails, so the first stream is the one everybody gets. With **Best stream first** on (it is by default), the plugin ranks the streams of every channel that has more than one, every 5 minutes, and puts the best first:

- **Quality tier**, from the resolution Dispatcharr measured when it has one (see [Measuring streams](#measuring-streams)), else from the stream's name: FHD / 1080, or no tag at all, scores 3; HD / 720 scores 2; SD / 576 / 480 scores 1. 4K / UHD / 2160 scores 0.5 and goes last, because most lines can't carry it. An untagged name counts as full HD because a main provider's streams are often untagged and usually 1080p; the measured picture overrides the name either way.
- **Health**, from what the TVs saw. Each TV keeps the failures and the last good minute of every stream it played, in its user's Dispatcharr storage, and the plugin merges them for the house. A failure in the last day, or three in a week, costs 10 points; a good minute in the last week earns 1; a stream Dispatcharr marks stale costs 20. A **dead** report from a TV counts as a failure.
- **Score** = health + tier × 2. Ties keep the current order.

A channel is only moved when its best stream beats the current first by a whole point, and at most once an hour, so the order doesn't flap. The order each channel had before the plugin first touched it is remembered, and **Put stream order back** restores every channel at once.

Left alone: channels with a single stream, and channels in the groups [Event Channel Managarr](https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin) manages (it orders its own). To pin one channel, add its id to the `keep` list in `_data/viewarr/streamorder.json`.

**Setting a channel's best stream by hand** (Viewarr 0.29.9.5 and later): in live TV, open **Source**, hold OK on a stream and pick **Make this the best stream**. Viewarr puts that stream first for the channel in Dispatcharr (admins only), and the plugin leaves the channel as set: Best stream first skips it and **Put stream order back** doesn't touch it. The pinned channels are shared with every TV, so their own best-source choice follows it too. **Let Viewarr choose again** on the same stream hands the channel back; it's sorted again on the next round. (Each admin's list is kept in their Dispatcharr storage, key `viewarr_stream_pins`.)

## Measuring streams

Dispatcharr only records a stream's picture size and codec (`stream_stats`, shown in Viewarr's Sources menu) when the stream plays through its proxy, so most streams are never measured and Best stream first has to trust the names. With **Measure streams at night** on (the default), the plugin measures them itself:

- **When:** only inside the **Measuring window** (default 01:00-07:00, in the time zone set in Dispatcharr's own settings), one stream at a time, a few seconds each. Empty window: never on a schedule.
- **What:** every stream linked to a real channel whose stats are missing or more than 30 days old. Event Channel Managarr's groups are never measured.
- **Order:** the channel groups in **Measure these channel groups first** (default: Entertainment, Movies, Sports, News, Kids, Music, UK Regional, Club TV), in that order, each group finished before the next; then any other group alphabetically, unless **Measure only the listed groups** is on. Within a group, the **Provider to measure first** (default: the one with the most left) comes first, in channel-number order.
- **Your lines:** the provider counts every connection, including this one. With two or more lines, a probe only runs while one line would still be left free for watching; with a single line, only while nobody is watching. After each probe there's a short pause (longer after a failure), because providers keep counting a connection for a moment after it closes.
- **How:** `ffprobe` with the account's user agent (or Dispatcharr's default), a 20-second limit, reading the first video and audio stream. The result is written exactly as Dispatcharr writes its own (`resolution`, `source_fps`, `video_codec`, `pixel_format`, `audio_codec`, `audio_channels`, `sample_rate`, `stream_type`).
- **Failures:** a stream that can't be measured is left alone for a week; after three failures it counts as a failing stream for Best stream first.

The log says which group it is working through ("Measuring: Entertainment, 212 left"), and **Sports service status** shows tonight's count. **Measure streams now** queues one batch of up to 20 at any time of day: it starts within a minute and takes about 2½ minutes at most, still respecting your lines (the result shows in **Sports service status**).

## Reports from the TV

Anyone watching can report a channel from Viewarr. The plugin reads everybody's reports every 5 minutes and, with **Act on reports from the TVs** on (the default), applies them straight away, no approval step:

| Report | What happens |
|---|---|
| **Wrong guide** with the right entry chosen on the TV | The channel's guide is set to that entry. |
| **Wrong guide** without a choice | A guide entry with the same name (ignoring HD / FHD / SD / "UK -" and the like) in a *different* source is used, if there is exactly one. Otherwise the report goes on the **needs a pick** list that Viewarr shows admins. |
| **Guide times out** by so many minutes | A house-wide offset for that channel, sent to every TV. Nothing changes in Dispatcharr. |
| **Dead stream** | A failure for that stream, which Best stream first uses in the same round. |
| **Wrong logo** | The logo of another of the channel's streams, when one differs. |
| **Wrong name** | The channel is renamed. |
| **Other** | Written to the log only. |

Every change goes to a change log with who reported it and what was there before. Admins undo one from Viewarr, or on the plugin's page with **Recent changes from reports** (shows the last 10 with their ids) and **Undo a change** (paste the id into **Change to undo**, save, press the button). The last 200 changes are kept in `_data/viewarr/reports.json`.

## UK football on TV

The plugin has UK football TV listings built in, so Viewarr knows which channel shows a match **weeks before your guide lists it**. For each game it looks, in order, at:

1. **Your Dispatcharr guide:** the programme on a channel that names both teams, in its title or episode title (Schedules Direct lists "Live: NHL Hockey" with the teams underneath).
2. **UK football TV listings** from [live-footballontv.com](https://www.live-footballontv.com/): every televised match for the next 30 days, on Sky Sports, TNT Sports, Premier Sports, BBC, ITV, Amazon Prime Video and the rest. The listings channel is then matched to the channel in your lineup.
3. **Event channels** named after the match, such as your provider's event feeds or Event Channel Managarr's channels.
4. **The club's own channel** (for example `SPFL - CELTIC TV`, MUTV, LFC TV) for league games that aren't on UK TV, such as Scottish Saturday 3pm kick-offs.

Games caught by the Saturday 3pm blackout are marked **Not on UK TV**, rather than pointing at the wrong channel.

Leagues covered: Scottish Premiership, Championship and cups; Premier League, EFL and cups; Champions, Europa and Conference League; internationals; the big European leagues; MLS; rugby union and league; NBA, NFL, NHL and MLB; F1, golf, tennis and UFC.

You don't need the [UK Sport on TV](https://github.com/petebutty/uk-sport-on-tv) plugin for Viewarr. Use it as well if you want the matches written into Dispatcharr's guide for every other app too.

## Live timeshift: where the buffer is kept

To pause and rewind live TV, the plugin keeps the last part of each channel being watched on your Dispatcharr server. That's the **buffer**. It's deleted as soon as nobody's watching.

### Do I need to do anything?

**No.** The buffer is always kept in **`/data/timeshift`** inside Dispatcharr's container, the same way Dispatcharr keeps recordings in `/data/recordings`. Left alone, that's just a folder in Dispatcharr's data folder, and it works straight away.

To put it on a better disk, map that disk to `/data/timeshift` in Docker. That's the only step; there's nothing to set in the plugin. See [Putting it on a cache disk](#putting-it-on-a-cache-disk).

### How much space it needs

- About **3 GB per hour of buffer for each channel being watched** (HD; less for SD).
- With the default settings (2 hours, up to 3 channels at once) that's up to about **18 GB**.
- The plugin won't start a buffer with less than 10 GB free, and stops one if the disk gets below 5 GB.
- Shorter buffer or fewer channels = less space: see **Live timeshift: buffer length** and **Live timeshift: channels at once** in the settings.

### What makes a good place

- **Fast**: an SSD or NVMe is best. The buffer is written non-stop while someone watches.
- **Never moved**: on Unraid, a **cache-only share** (Primary storage: your cache pool, Secondary storage: **None**), so the mover never touches it. Not a share the mover moves to the array: the mover can shift buffer pieces away while someone's watching, and rewinding then fails.

### Putting it on a cache disk

*Unraid*
1. **Shares → Add Share.** Name it (for example `timeshift`). **Primary storage**: your cache pool. **Secondary storage**: **None**. Add Share.
2. **Docker → Dispatcharr → Edit → Add another Path, Port, Variable…**
   - Config Type: **Path**
   - Container Path: **`/data/timeshift`**
   - Host Path: **`/mnt/cache/timeshift`** (your pool name and share name)
   - Access Mode: **Read/Write**
3. **Save**, then **Apply**. Dispatcharr restarts once.

*Docker Compose*: under the Dispatcharr service's `volumes:` add one line, then run `docker compose up -d`:

```yaml
services:
  dispatcharr:
    volumes:
      - ./data:/data                    # (already there)
      - /srv/timeshift:/data/timeshift  # add this: a folder on a fast disk
```

*Synology, TrueNAS, Portainer, CasaOS and others*: in Dispatcharr's container settings, find **Volumes** (also called Storage, Mounts or Folders) and add one: a folder on a fast disk, mounted at **`/data/timeshift`**, read/write. Save and let the container restart.

**Check it worked:** press **Sports service status**. After **live timeshift** it says **kept in /data/timeshift (its own disk, … GB free)**. If the free space is less than your timeshift settings could need, it says so.

The plugin only ever clears its own buffer folders in `/data/timeshift`; anything else there is left alone.

## TV guide and channel logos

The plugin no longer makes a TV guide or fills in channel logos (both were Sky-based, and were removed in 0.6.8). For a proper guide, with logos, use **Schedules Direct**, which Dispatcharr supports itself (Dispatcharr → EPG → Add → Schedules Direct; it needs a paid Schedules Direct account). On updating, anything the old guide or logos changed is put back: channels pointed at **Viewarr: Sky guide** return to the guide they had, and logos the plugin set return to the earlier ones (unless you changed them yourself since). The **Viewarr: Sky guide** source is deleted once no channel uses it.

## Install

1. Dispatcharr → **Plugins** → **Import**, and choose `viewarr-plugin-<version>.zip` from the [releases](https://github.com/petebutty/viewarr-plugin/releases).
2. **Enable** it. Dispatcharr asks you to approve what it uses:
   - **persistent service:** it runs every few minutes;
   - **outbound network:** it reads the outside sources you choose (ESPN, the UK listings, JustWatch);
   - **user data:** it reads each person's Viewarr setup, stream health and reports, and leaves their answers there.

That's it. Nobody needs to set anything up in Viewarr: each TV finds the plugin by itself. Each person's follows, Live now groups and alert choices reach the plugin through their synced Viewarr setup.

## Settings (all optional)

| Setting | What it does |
|---|---|
| **Live now** | On by default. Works out Live now for the house. Off: Live now is off for the house and Viewarr hides it. |
| **Live now: extra channel groups to search** | The plugin always searches groups whose names sound like sport (Sports, Football, Events, Box Office, EPL…) and Event Channel Managarr's groups. Add others here, such as your provider's event-feed groups. Easier: switch a group on in Viewarr → Settings → Live TV → Live now groups, and the plugin searches it from the next round. |
| **Followed games and where they're on** | On by default. Fixtures of every followed team and league (ESPN) and the channel for each game (the guide, UK football TV listings). Off: no fixtures or listings fetched here; the Sports page places games from each TV's own guide only. Sport recordings and score alerts need it on. |
| **Sport recordings** | On by default. "Record all &lt;team&gt;" and Record on games not yet in the guide, made on the server with the TVs off. Off: Viewarr hides Record all &lt;team&gt; and record-when-listed (recording a game already in the guide still works). |
| **Score alerts and live scores** | On by default. The 45-second score checks for alerts and the ticker's Live scores. Off: the stored alerts are emptied and Viewarr hides score alerts and Live scores. |
| **Event channels: only with a listing** | On by default. Sends the TVs the plugin's event channels (`quiet_channels` in `viewarr_house`), so Viewarr can hide those with nothing listed. Off: an empty list is sent, every event channel is shown and Viewarr hides the option. |
| **Just added (JustWatch)** | On by default. The daily JustWatch fetch for the "&lt;service&gt; · Just added" rows. Off: the stored lists are removed and Viewarr hides the rows. |
| **IPTV progress sync (Plex, Jellyfin, Emby)** | On by default. The house-wide switch for IPTV progress sync; each person still switches it on in Viewarr. Off: no syncing, and Viewarr hides the option. |
| **Best stream first** | On by default. Puts each channel's best stream first in Dispatcharr; see [Best stream first](#best-stream-first). |
| **Act on reports from the TVs** | On by default. Applies reports from Viewarr straight away; see [Reports from the TV](#reports-from-the-tv). |
| **Groups never reported** | Groups that are off air most of the time (club TV). Their streams are never marked failing or measured. Comma-separated. |
| **Change to undo (id)** | Only for the **Undo a change** button on Dispatcharr's page. Viewarr sends the id itself. |
| **Measure streams at night** | On by default. Measures streams with ffprobe inside the window; see [Measuring streams](#measuring-streams). |
| **Measuring window (local time)** | `HH:MM-HH:MM`, default `01:00-07:00`. Empty: never on a schedule. |
| **Measure these channel groups first** | Channel groups in priority order; the rest follow alphabetically. |
| **Measure only the listed groups** | Off by default. On: skip every other group. |
| **Provider to measure first** | M3U account name; empty means the one with the most left. |
| **Live timeshift (pause and rewind live TV)** | On by default. Keeps a buffer of each channel being watched; see above. Off: Viewarr hides it. |
| Live timeshift: channels | All channels (default), or only channels without catch-up (those keep using the provider's catch-up). |
| **Live timeshift: buffer length** | How far back a TV can rewind: 30 minutes to 4 hours, default 2 hours. An HD channel takes about 3 GB an hour on the server while it's watched. |
| **Live timeshift: channels at once** | Default 3. Beyond it a TV has catch-up (if the channel has it) or live only. |
| **Backups** | On by default. Off: Viewarr hides Backups and the plugin refuses them; saved ones are kept. |

Every function can be switched on or off, and its options set, from Viewarr itself (Settings → Plugins → Viewarr, admins). The plugin tells the TVs which functions are on (`functions` in `viewarr_server`); while one is off it's off for the whole house and Viewarr hides it. Only with no plugin at all do the TVs do these jobs themselves, as before.

## Polite to the sources

- **UK listings:** one page, fetched at most every 6 hours. After a "too many requests" or "unavailable" reply it waits an hour. A failed or empty fetch keeps the last good listings.
- **ESPN:** only the leagues and teams someone follows. Live scores are checked only while a followed game is on.
- **TMDB:** about 250 titles a round. Each title is looked up once and remembered.
- **User-Agent:** every request identifies itself with a link to this repo.

## Requirements

- Dispatcharr 0.34 or newer.
- The latest Viewarr for every feature. Older versions use what they understand.

## Licence

MIT. See [LICENSE](LICENSE).


**Groups never reported.** Club TV channels and event channels are off air most of the time by nature, so being unplayable isn't a fault: the plugin never marks their streams as failing, never measures them, and a dead-stream report about one is logged only. The TVs get the same list and don't report them automatically. Set the groups in *Groups never reported* (event groups are always included).
