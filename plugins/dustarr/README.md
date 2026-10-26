<img src="https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/master/dustarr/logo.png" alt="The Dustarr logo: a dark radar scope with a green sweep line and coloured blips scattered across it" width="110" align="right">

A Dispatcharr plugin that records which channels are actually watched, and reports the ones that are not, so you can turn off the dead weight in your lineup.

> [!TIP]
> **New to Dispatcharr plugins?** Start with the **[Dispatcharr Plugin Workflow guide](https://piratesirc.github.io/Dispatcharr-Plugin-Workflow/)**.
> It explains what each plugin and tool does, where they overlap, and what order to use them in.

**It never changes anything in Dispatcharr.** It reads which channels have viewers, writes its own report files, and keeps the state for the anonymous usage count in /data/plugin_stats/dustarr/. Nothing else.

## What it does

**Recording what is watched**
* **A leader elected collector** samples Dispatcharr's live proxy state every 15 seconds and turns raw client counts into watch sessions. Exactly one collector runs at a time across all worker processes, so nothing is double counted.
* **Watches and tunes are separate.** A session counts as a watch only once it has run for two minutes, so flipping through channels looking for something does not inflate the numbers. A shorter session is still recorded, as a tune, and that distinction is what produces the broken channel list below.
* **Player hiccups do not split a watch.** A player may drop to zero clients for up to 90 seconds, during a reconnect or a retry, without the session being treated as finished.
* **It never blocks Dispatcharr.** The collector runs on its own, and reporting is a separate scheduled job rather than something that happens while you are waiting for a page.

**The lists it produces**
* **Never watched**: the dead weight, grouped by channel group so you can act on a whole group at once.
* **Tuned but never qualified**: channels you tried to watch and gave up on within two minutes. This list is not "barely used", it is almost certainly **broken**: a dead source, a black screen, or a provider connection being dropped. Treat these as bug reports rather than turning them off.
* **Channels going cold**: watched at some point, but not lately. Entries that are still being tuned are listed apart, because that shape also means broken rather than unwanted.
* **Too new to judge** and **most / least used** round it out.

**Not judging channels that only look unused**
* **Pay per view and live event slots** sit idle between events, and an M3U sync renames the same channel row in place, so a slot that idled on "NO EVENT" for a month would otherwise read as permanently dead.
* **Local and over the air news** is the emergency broadcast tier. It is supposed to sit unused.
* **Sports** has a legitimate off season.
* **Channels the collector cannot see at all** (a stream profile set to Redirect writes none of the state the collector reads) are reported separately as unobservable rather than being counted as never watched. That is decided from the profile's structure, not from its name.

**Seeing what happened**
* **A self contained HTML report**: sortable tables, collapsible sections and inline charts, with no external stylesheet, script, font or image. It opens straight off disk, and renders the same offline, on a television, or as an email attachment.
* **A CSV export** of the same data, for a spreadsheet. It opens with a commented preamble recording what the run found and which settings it used, so tell your spreadsheet to skip lines beginning with a hash when you import it.
* **Housekeeping for old reports**, off by default. Set a number of days and the dated copies are deleted after each build. The report just written is never deleted and at least one of each kind always survives.
* **Emailed reports**, optionally, delivered by the [Newsflasharr](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin) plugin. Off by default.
* **A loud banner when the numbers cannot be trusted**, rather than a clean looking report claiming your household watches nothing.

See the **[user guide](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/USER-GUIDE.md)** for how to use these, and for every setting and every button.

### The report

The page opens as an index: the logo beside the title, the tracking window and sampling verdict, then seven sections that each start collapsed and carry their own count.

![The Dustarr report as it opens: the logo beside the title, the tracking window and coverage on one line, a Report number chip, a four segment bar splitting the judged channels into never watched, watched, too new and tuned but never qualified, a sampling density meter with a sampling OK verdict beside it, and seven collapsed section headings each carrying a count](https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/master/docs/images/report-index.png)

Click a heading and its tables appear.

![The same report with the Never watched section expanded, showing a per group rollup table with a share bar, and below it a sortable table of seven channels with their group, watch count, hours, average minutes, tune count, age in days, days since last watch, last watched date and reason](https://raw.githubusercontent.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/master/docs/images/report-expanded.png)

*Sample data, shown here in dark mode; the page follows whichever theme your reader uses. Click any column heading to sort by it. Numeric columns compare as numbers, so 9 sorts before 10 rather than after 100. The chip under the title is the running total of reports this installation has written.*

## Requirements

* Dispatcharr v0.20.0+
* The only internet access is the anonymous usage count: an HTTPS request to plugin-stats.dpas.workers.dev, which you can switch off (see [Anonymous usage counts](#anonymous-usage-counts)). The plugin never contacts your provider, never checks for its own updates, and fetches nothing when rendering a report.
* The [Newsflasharr](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin) plugin, only if you want emailed reports. It is what actually sends the mail. Dustarr does not require it: with Newsflasharr absent or disabled, nothing is sent and nothing fails.

## Installation

Dustarr is listed on the **Dispatcharr Plugin Hub**, so the easiest route is the plugin browser:

1. Log in to Dispatcharr's web UI.
2. Navigate to **Plugins**, find **Dustarr** in the browser, and install it.
3. Enable the plugin after installation.

To install from a file instead, download the zip from the [latest release](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/releases/latest), then use **Import Plugin** on the same page. Both routes deliver the same archive: the Hub re-hosts the release asset, byte for byte.

**Restart the Dispatcharr container after installing or upgrading.** This is not optional, and the reason is in [Updating the plugin](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/USER-GUIDE.md#updating-the-plugin).

## What to expect at first

**Your first month of reports will carry a red "not trustworthy" banner, and that is the plugin working rather than failing.** The unused threshold defaults to 30 days, and a dataset younger than that cannot honestly call anything unused. There is no way to shorten this by importing history: Dispatcharr does not keep the state Dustarr reads, so a fresh installation really does start at zero. Wait it out, or lower the threshold if you are comfortable judging on a shorter window.

**Most of a typical lineup is excluded from judgment, and that is the point.** On a normal installation roughly 70 percent of channels are held back for the reasons listed above. The answer you can act on is drawn from the remaining 30 percent, not from the whole lineup.

## Safety

This is the part worth reading before installing anything that watches what your household watches.

* **It never writes to Dispatcharr's database.** That is not a promise in a README. `tests/test_no_mutations.py` reads the syntax tree of every shipped module on every run and fails the build on any write shaped database call it can prove, on `subprocess` and its relatives, and on any stream probe. It proves the receiver is a Dispatcharr model or queryset rather than banning method names, so it is not fooled by a dictionary that happens to have an `update` method. What it cannot see: a call made through reflection or `eval`, a queryset arriving as a function parameter, or a write issued through a library it does not know about. It is a strong structural guarantee against the natural ways an author would reach for a write, not a formal proof.
* **It never contacts your provider.** No stream requests and no probes. A single probe consumes one of your provider connections and drops whoever is currently watching.
* **Credentials are redacted.** Provider credentials live inside stream URLs in a typical Dispatcharr setup, so every string that can reach a notification or a logged error passes through a redactor first, and the report renders an allowlisted set of fields only: channel name, group, counts and timestamps, never a stream URL.
* **Nothing is served over HTTP.** The report is a file in a folder you already have mounted. An earlier version wrote it where Dispatcharr's own web server publishes files to the whole local network with no login, which made an unauthenticated page naming every channel your household watches.
* **If the collector goes blind, the report says so loudly**, rather than quietly reporting that every channel is dead.

## Where things are written

The report and the CSV land in `/config/dustarr/`. `/config` is Dispatcharr's existing bind mount, so that is a real folder on your host: open the report by double clicking it. When `/config` cannot be written, they go to `/data/dustarr/reports/` instead. The full list of paths is in the [user guide](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/USER-GUIDE.md#where-the-files-are-written).

## Anonymous usage counts

The Reports Built and Active Installs badges count every install that leaves the
"Share anonymous usage counts" setting (on by default) ticked and runs at least one
action or builds at least one scheduled report.

Reports Built counts the reports this plugin has written on the install. Its total
is kept in /data/dustarr/report_count.json and only goes up, short of deleting that
file: deleting old report files with the retention setting does not lower it. A report counts only once its
HTML file is confirmed on disk, so a run that wrote nothing adds nothing. Emails
are not counted.

When an action finishes or a report is built, the plugin sends this install's
Reports Built total and a random id for this plugin on this install to the plugin
author's counter at plugin-stats.dpas.workers.dev. It sends at most once an hour after
a successful send, or ten minutes after the last successful send when a report has just been built.
A run that finishes inside that gap is not sent later: the total goes out with the
first later action or report build that is an hour past the last successful send,
or with a later report build once ten minutes have passed.

The server stores that id with the total and the date of the last report, and keeps
them until this install unticks the setting and the delete succeeds, or until the
plugin author removes them by hand. An install that stops reporting still counts
toward Reports Built. The connection shows the server your public IP address; the
server uses it only to limit abuse and does not store it in its database, though
when an install first registers it keeps a salted one-way hash of it (of its /64
block for IPv6) for up to three days. Cloudflare, which hosts the server, keeps its
own request logs. No names, channels, streams, URLs, providers or settings are sent.
The figures are self-reported by installs and capped by the server, not verified.

What counts as an active install: an install that sent at least one usage count in the
last 30 UTC days. A badge changes after the server's hourly recount, which runs at
the start of each UTC hour, and Shields may cache the badge for up to an hour more,
so a new report can take up to about two hours to show.

The setting is the last one in the settings form, in its own section. Unticking it
takes effect the next time an action runs or a report is built; the plugin then asks
the server to delete this install's figures. Once the server confirms the delete,
the plugin forgets its id, and ticking the setting again later starts a new one; if
the delete could not reach the server, the plugin keeps the id and retries. The
plugin keeps that id and the timing of its reports in /data/plugin_stats/dustarr/.
To start a new id, untick the setting and let an action run so the server deletes
this install's figures; deleting that folder while the setting is ticked leaves
the old figures on the server, and the new id then sends the full total again, so
the badge counts it twice.

## Documentation

* **[User guide](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/USER-GUIDE.md)**: a first run, reading the report, every setting, every button.
* **[Troubleshooting](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/troubleshooting.md)**: arranged by symptom.
* **[Changelog](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/CHANGELOG.md)**: what changed in each version.
* **[Development notes](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/DEVELOPMENT.md)**: how the plugin is put together, and the constraints that are not obvious from one file.
* **[Open work](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/TODO.md)**: what is planned, what is deliberately not, and the known limitations.
* **[Contributing](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/CONTRIBUTING.md)** before opening an issue or a pull request, and **[Security](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/SECURITY.md)** for what the plugin can reach and how to report a vulnerability privately.

## Versioning

Calendar versioning, `Major.YY.DDDHHMM`: major version, two digit year, day of year, then the UTC time the version was cut. `1.26.2241505` is major version 1, built on day 224 of 2026 at 15:05 UTC. A later version string is always a later build.

## Sponsor

This plugin is free and always will be. If it saves you time and you would like to support the work, you can sponsor it at [github.com/sponsors/PiratesIRC](https://github.com/sponsors/PiratesIRC).

Sponsoring buys no priority, no private support and no influence over what gets built. Bug reports and pull requests are just as welcome from everyone.

## License

MIT. See [LICENSE](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/LICENSE).
