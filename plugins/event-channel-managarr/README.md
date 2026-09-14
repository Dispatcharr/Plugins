# Event Channel Managarr

Automates channel visibility in Dispatcharr for event-driven channels, the kind
whose names carry a date and a fixture rather than a permanent station identity.
It hides channels that currently have no event on them and shows the ones that
do, deciding from EPG program data and from the channel name itself. It can also
generate dummy EPG entries for channels that have no real guide data.

- Source repository: https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin
- Minimum Dispatcharr version: v0.20.0
- License: MIT

## What it does

Event channels are usually named for a specific fixture on a specific day. Once
that event has passed, the channel stays in the lineup with nothing on it. This
plugin scans the channel groups you select, works out whether each channel has a
live or upcoming event, and sets its visibility in the chosen channel profile
accordingly.

Two sources of truth are available and can be combined. The plugin can read the
EPG program data attached to a channel, and it can parse the date out of the
channel name. Channel names are read in the timezone you configure, which matters
because providers commonly label event channels in a timezone other than your
own.

Preview first. The Dry Run action reports exactly which channels would be hidden
and which shown, and changes nothing.

## Actions

| Action | What it does |
|---|---|
| Validate Configuration | Tests every setting and the database connection before anything else runs |
| Update Schedule | Saves settings and rewrites the scheduled run times |
| Dry Run | Reports which channels would be hidden or shown, without making any change |
| Run Now | Scans immediately and applies channel visibility from current EPG data |
| Run After M3U Refresh | Runs a visibility scan automatically after each M3U refresh, when the auto-rescan setting is on |
| Remove EPG From Hidden | Strips EPG data from every channel hidden in the selected profile |
| Clear CSV Exports | Deletes every CSV export this plugin has written |
| Cleanup Periodic Tasks | Removes orphaned scheduled tasks left behind by older versions of the plugin |
| Check Scheduler Status | Shows the scheduler thread state and diagnostic information |

## Settings

**Scope.** `Channel Profile Names` is required and names the profile whose
visibility is changed. `Channel Groups` limits which channels are considered.
`Name Source` and `Date Format in Channel Names` tell the plugin how to read a
date out of a channel name.

**Hide rules.** `Hide Rules Priority` orders the rules against each other. Three
regular expression settings give direct control: one lists channels to ignore
entirely, one marks channels inactive, and one forces channels visible whatever
else decides. `Past Date Grace Period` keeps a channel visible for a set number
of hours after its event has finished.

**Duplicates.** `Duplicate Handling Strategy` and `Keep Duplicate Channels`
decide what happens when several channels describe the same event.

**EPG management.** `Auto-Remove EPG on Hide` strips guide data when a channel is
hidden. `Manage Dummy EPG` generates placeholder guide entries for channels with
no real EPG, with the entry length set by `Event Duration` and the channel naming
set by `Channel Name Format`. `Channel Name Event Timezone` is the timezone the
provider uses in its channel names, which is often not your local one.
`Override Empty Existing EPG` allows replacing an EPG assignment that carries no
programs.

**Scheduling and export.** `Scheduled Run Times` takes 24-hour times for
unattended runs. `Enable Scheduled CSV Export` writes a CSV on each scheduled
run. `Auto-rescan after M3U refresh` triggers a scan whenever an M3U source
refreshes.

**Advanced.** `Rate Limiting` slows database writes on large runs.

## Two things that catch people out

**A channel named for tomorrow's event is visible on purpose.** The rule that
handles upcoming events, `[FutureDate:2]`, hides a channel only when its date is
more than two days away, so a fixture tomorrow stays on the lineup today. If you
want a channel to appear only on the day of its event, change that tag to
`[FutureDate:0]`.

**Hiding only affects Dispatcharr's profile-scoped outputs.** A client such as
Jellyfin, Plex or Emby must be pointed at the URLs for the profile you are
managing, and it must be given the guide URL rather than the playlist URL:

| Client field | URL |
|---|---|
| Tuner / M3U playlist | `http://<dispatcharr>:<port>/output/m3u/<Profile>` |
| Guide / XMLTV provider | `http://<dispatcharr>:<port>/output/epg/<Profile>` |

Putting the M3U URL into the guide field is the single most common mistake: an
XMLTV parser cannot read a playlist, so the client ends up with no guide and
keeps the channel list it imported previously. Clients also cache, so run their
guide refresh after a change rather than waiting for the nightly one.

Note that Dispatcharr's own TV Guide page shows hidden channels when its filter
is set to All Profiles. Select the managed profile to see what your clients get.

## Reading a run

Every run writes a CSV giving the action, the reason and the rule that decided
each channel. Two things are reported that would otherwise be silent: channel
group names that matched no channels, and regular expression settings that
matched nothing. A setting that is quietly doing nothing shows up rather than
looking like it works.

`Channel Groups` is comma-separated. The `|` character belongs only in the three
regular expression settings; using it to separate group names joins them into one
name that matches nothing.

## Getting started

1. Install the plugin and open its page in Dispatcharr.
2. Set `Channel Profile Names` to the profile you want managed. This setting is
   required and nothing runs without it.
3. Set `Channel Groups` to the groups holding your event channels.
4. Set `Channel Name Event Timezone` to the timezone your provider uses in its
   channel names, not your own, unless they happen to be the same.
5. Run Validate Configuration, then Dry Run, and read the result.
6. When the preview looks right, run Run Now, and only then set
   `Scheduled Run Times` for unattended operation.

## Full documentation

The source repository carries the complete
[user guide](https://github.com/PiratesIRC/Dispatcharr-Event-Channel-Managarr-Plugin/blob/main/docs/USER-GUIDE.md),
covering every setting and action, the hide rules in detail, the managed dummy
EPG, client setup, file locations, the CSV format, and troubleshooting by symptom.
