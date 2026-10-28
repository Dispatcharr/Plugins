# Automap Channelarr

A Dispatcharr plugin that maps M3U groups to channel-number blocks with
deterministic, rule-based logic. It replaces the built-in automapper
(auto channel sync) for the groups you configure.

No curated channel databases, no fuzzy matching, no network access: streams are
pooled by a normalized name, and each normalized name becomes exactly one
channel at a predictable number.

Groups of one-off events (`00:55 NFL: Cowboys - Eagles 27/10`) get their own
rules: each event becomes a channel ordered by start time and is removed once
it is over. See [Event rules](#event-rules).

## What it does

For each configured group, on every run:

1. **Pools** all non-stale streams in the group - from every M3U account,
   unless the rule is account-qualified. Two providers' `SVT1` streams become
   one channel with both streams attached, ordered for failover.
2. **Normalizes** each stream name into a grouping key: country prefix removed
   (`SE:`, `SWE |`), trailing uppercase country code removed (`TV4 SE`,
   `Kanal 5 | SWE`), quality and codec markers removed (4K, UHD, FHD, HD, SD,
   HEVC, H265, 50FPS, plus your own tokens), lower-cased, punctuation and
   whitespace stripped. `SE: SVT 1 FHD`, `SVT1 SE` and `svt1 hd` all become
   `svt1`. See [Country codes](#country-codes) for what counts as a code.
3. **Creates one channel per key**, numbered upward from the rule's start
   number in provider playlist order. The display name is the cleaned original
   (`SVT 1`), picked as the most frequent variant among the pooled streams.
4. **Keeps runs stable**: existing channels keep their number and identity
   forever. New names get the lowest free number in the block. Numbers held by
   channels the plugin does not own are skipped and reported, never stolen.
5. **Syncs streams and EPG** on every run: the channel's stream list is made to
   exactly match the pool, ordered 4K/UHD > FHD > HD > unmarked > SD; `tvg-id`
   and EPG linkage follow the best stream. The display name, logo, and group
   are set at creation and never overwritten, so manual edits stick.
6. **Deletes orphans carefully**: a channel whose streams disappear from the
   provider is deleted only after staying gone for the configured grace period
   (default 7 days). If the key reappears first, the timer resets.

## Rules

One rule per line in the **Rules** setting:

```
# comments and blank lines are ignored
Sports; Sport HD = 100
News = 200
ProviderX/Kids = 300
Movies = 400 -> My Movies
```

- `Group = start` - map one M3U group to a block starting at that number.
- `Group A; Group B = start` - pool several groups into one block.
- `Account/Group = start` - only streams from that M3U account. A leading
  `Something/` is treated as an account name only when an account with that
  exact name exists, so group names like `24/7 Movies` work unqualified.
- `... = start -> Name` - put the channels in the channel group `Name`,
  created if it does not exist. Without it, channels go in the rule's first
  source group. The group is set when a channel is created, so changing the
  target later does not move existing channels.

A target may be the rule's own source group, and several rules may share a
target. A target that is a source group of another rule is an error.

## Event rules

The **Event rules** setting uses the same syntax as Rules, including `;`
pooling, `Account/Group` and `-> Name`. A group or start number may be used in
Rules or Event rules, not both.

```
PPV Events = 5000
NXT IPTV/Live Sports = 6000 -> Events
```

### Start time and date

The start time and date are read from each stream name:

- **Time**: `HH:MM` in 24h (`20:00`) or 12h with AM/PM (`10:00 PM`,
  `10:00 p.m.`). A timezone abbreviation right after the time is converted to
  server time: UTC, GMT, EST, EDT, CST, CDT, MST, MDT, PST, PDT, WET, WEST,
  BST, CET, CEST, EET, EEST, AEST, AEDT. Abbreviations are taken literally
  (`EST` is always UTC-5). Times without one are server-local.
- **Date**: `2026-10-27`, or `27/10` / `10/27` / `27.10`, optionally with a
  2- or 4-digit year (`27/10/26`). Whether `D/M` or `M/D` is meant is decided
  once for all event streams in a run: a value over 12 settles it; otherwise
  the position that matches the current month is the month; failing that,
  day first.
- **No year**: the year that puts the date closest to today, so `31/12` read
  on January 2nd is four days ago, not next December.
- **No date**: today.
- **No time**: the event has no start time. Its channel is named after the
  title alone, sorts after timed events, and is removed only by the orphan
  grace period.

**Event regex** overrides the built-in detection. It must contain a
named group `(?P<time>...)`; `(?P<date>...)` is optional (no date = today).
Streams it does not match fall back to the built-in parser.

```
^(?P<time>\d{1,2}:\d{2}).*?(?P<date>\d{1,2}/\d{1,2})
```

### Titles and names

The title is the stream name with the matched time and date removed, then
cleaned:

- **Event strip tokens** are removed (`;`-separated, like Strip tokens).
  When the setting is empty, Strip tokens are used instead. Quality and
  codec markers (4K, UHD, FHD, HD, SD, HEVC, H265, 50FPS) are always removed.
- A trailing uppercase country code is removed (`... Jones USA`).
- A leading prefix is **kept**: a league tag like `NFL:` looks the same as a
  country prefix, so `NFL: Cowboys - Eagles` stays intact.

Two `;`-separated lists override this per stream. Each entry matches when the
stream name contains it, ignoring case:

- **Event as is**: the stream name becomes the channel name unchanged - no
  stripping, no name template. The start time is still read, so the channel
  is ordered and removed like any other event.
- **Event not**: the stream is skipped. This wins over Event as is.

```
Event as is:  RedZone; Big Fight Night
Event not:    Replay; Highlights
```

Streams with the same normalized title and the same date are pooled into one
event channel, the same way regular channels pool by name. The same title on
another date is a separate event.

The channel name comes from **Event name template** (default
`{date} {time} {title}`, giving `27/10 00:55 NFL: Cowboys - Eagles`):

| Token | Example |
|---|---|
| `{title}` | `NFL: Cowboys - Eagles` |
| `{time}` | `22:00` |
| `{time12}` | `10:00 PM` |
| `{date}` | `27/10` |
| `{usdate}` | `10/27` |
| `{isodate}` | `2026-10-27` |
| `{weekday}` | `Tue` |
| `{weekday:Man,Tis,Ons,Tor,Fre,Lor,Son}` | `Tis` - your own 7 names, Monday first |

Times are shown in server time. Unknown tokens are left as written and
reported as a warning. Unlike regular channels, event channel names are
updated on every run to match the template.

### Lifecycle

- **Created** at most **Event lead time** hours before the start time
  (default 36). `0` creates everything the provider lists.
- **Removed** **Event removal** hours after the start time (default 6), even
  if the provider still lists the event. If the event
  disappears from the provider first, the orphan grace period applies.
  Whichever comes first wins.
- **Renumbered** once a day: on the first run of each server-local day, every
  event block is renumbered from its start number in start-time order. Events
  added later that day take the lowest free number in the block until the
  next day's renumbering. Numbers held by channels the plugin does not own are
  skipped and reported.

## Sample configuration

A working setup: one country block, one foreign-language block, and one event
block pooling four provider groups. Auto-run is on; everything not listed keeps
its default.

**Rules**

```
Finland = 1 -> Suomi
Russia = 400 -> Россия
```

**Strip tokens** - provider tags that would otherwise split one channel into
several:

```
(B);(Multi);(Game Time Only);NXTFI
```

**Preferred max quality**: `FHD` - 4K/UHD streams are left out whenever a
channel has anything else.

**Event rules** - four event groups pooled into one block from 1000, placed in
a channel group named `Event`. The first group's name contains `|`, which is
fine; `;` is the separator:

```
Yle Areena | Urheilu | Ruutu;MTV Katsomo NXT FI;Viaplay NXT FI;Disney+ Suomi NXT FI = 1000 -> Event
```

**Event strip tokens** - the Strip tokens plus the provider names, so
`Viaplay: NHL: Panthers - Oilers` and `MTV Katsomo NHL: Panthers - Oilers`
pool into one event:

```
(B);(Multi);(Game Time Only);NXTFI;Disney;Viaplay;Katsomo
```

**Event as is** - streams that are containers rather than single events keep
their raw name:

```
(Live Events Only)
```

**Event not** - provider junk lines that are not events:

```
↓;Update your playlist;Welcome to NXT
```

**Event name template** - local weekday names:

```
{weekday:ma,ti,ke,to,pe,la,su} {time} {title}
```

giving event channels like `ti 21:00 NHL: Panthers - Oilers`.

## Country codes

Only ISO 3166-1 codes count as country codes: the 2- and 3-letter codes
(`SE`, `SWE`, `GB`, `GBR`), plus `UK`, which is not ISO but common in
playlists. `TV` (Tuvalu) is left out, because it is a common real suffix.

- **Prefix**: a code followed by `:` or `|`, in any case (`SE:`, `swe |`).
  Anything else stays part of the name (`NBA: League Pass`).
- **Suffix**: an uppercase code at the end of the name (`TV4 SE`,
  `BBC One UK`). `Nick JR`, `Disney XD` and `Axess TV` keep their endings.

## Config errors

Any of these aborts the whole run with an error, so nothing is half-applied:

- bad syntax or a start number that is not a whole number >= 1
- a group or start number used twice, within or across Rules and Event rules
- an empty `->` target, or a target that is another rule's source group
- a custom event regex that does not compile or lacks `(?P<time>...)`

A group that exists but currently matches no streams is skipped with a warning.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| Run automatically after each M3U refresh | off | Runs the mapper after every successful M3U refresh |
| Rules | empty | The mapping rules described above |
| Strip tokens | empty | Additional `;`-separated tokens removed before grouping |
| Preferred max quality | Unlimited | Streams marked above this are left out of channels, unless they are all a channel has. Unmarked streams are never dropped. Applies to events too |
| Orphan grace period (days) | 7 | Days a mapped channel must stay gone from the provider before deletion; 0 deletes immediately. Applies to events too |
| Event rules | empty | Rules for event groups, same syntax |
| Event strip tokens | empty | `;`-separated tokens removed from event titles; empty uses Strip tokens |
| Event as is | empty | `;`-separated texts; matching event streams keep their stream name as channel name |
| Event not | empty | `;`-separated texts; matching event streams are skipped |
| Event regex | empty | Overrides the built-in time/date detection for event streams |
| Event name template | `{date} {time} {title}` | Name of each event channel |
| Event lead time (hours before start) | 36 | Events further ahead are not created yet; 0 creates all |
| Event removal (hours after start) | 6 | Event channels are deleted this long after their start time |

## Actions

- **Run Now** - apply the rules immediately (asks for confirmation).
- **Dry Run** - log every planned create, update, and delete without changing
  anything. Check the Dispatcharr log for the line-by-line detail.
- **Auto Run Hook** - fires by itself after each M3U refresh when the auto-run
  setting is on; clicking it manually behaves like Run Now.

Each real run posts a one-line summary notification in the UI; details go to
the Dispatcharr log.

## Replacing the built-in automapper

Disable **auto channel sync** on every group you configure here (M3U account
group settings). The plugin still runs if you forget, but warns on every run:
the built-in sync rebuilds its own one-channel-per-stream layout before each
refresh completes, and the two will fight indefinitely.

## Requirements

- Dispatcharr v0.20.0+ (the auto-run hook needs the plugin event support added
  in v0.20.0; everything else works from v0.19.0)

## Installation

1. Download the plugin zip.
2. In Dispatcharr, go to **Plugins -> Import Plugin** and upload it.
3. Enable the plugin, add rules, and start with a **Dry Run**.

## State

The plugin keeps a small `state.json` in its data directory to track channel
identity, orphan grace timers and the date of the last event renumbering.
Removing a rule from the config stops the plugin managing those channels but
never deletes them.

## License

Artistic-2.0
