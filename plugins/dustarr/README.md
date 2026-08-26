# Dustarr

Records which channels are actually watched, and reports the ones that are not, so you can turn off the dead weight in your lineup.

**It never changes anything in Dispatcharr.** It reads which channels have viewers, reads the channel list, and writes its own report files. Nothing else.

## What it produces

A self-contained HTML report and a CSV export, written to `/config/dustarr/`. The HTML page opens as an index of seven collapsed sections, each with its own count:

| Section | What it holds |
|---|---|
| **Never watched** | The dead weight, grouped by channel group so you can act on a whole group at once. |
| **Channels going cold** | Watched at some point, but not lately. |
| **Too new to judge** | Created too recently to fairly call unused. |
| **Tuned but never qualified** | Channels you tried to watch and gave up on within two minutes. These are almost certainly **broken**, not unpopular: a dead source, a black screen, or a provider connection being dropped. Treat them as bug reports rather than turning them off. |
| **Least used** and **Most used** | The ordinary leaderboard, by watch count and hours. |
| **Excluded and unobservable** | Held back from judgment, or invisible to the collector. |

Nothing in the report is fetched from the internet: no external stylesheet, script, font or image. It renders the same offline, on a television, or as an email attachment.

## How it decides what counts

A leader-elected collector samples Dispatcharr's live-proxy state every 15 seconds and turns raw client counts into watch sessions. Exactly one collector runs at a time across all worker processes.

A session counts as a **watch** only once it has run for two minutes, so flipping through channels looking for something does not inflate the numbers. A shorter session is still recorded, as a **tune**, and that distinction is what separates channels nobody wants from channels that are simply broken.

Some channels look unused but are not, so they are kept out of the never-watched judgment by default: pay-per-view and live-event slots that idle between events, local and over-the-air news, and sports with its off season. A channel whose stream profile is not proxying writes none of the state the collector reads, so it is reported separately as unobservable rather than counted as never watched.

## Safety

- **It never writes to Dispatcharr's database.** That is enforced by a test that reads the syntax tree of every shipped module on every run and fails the build on any write-shaped database call it can prove, on `subprocess` and its relatives, and on any stream probe. The limits of what that test can and cannot prove are documented in the repository.
- **It never contacts your provider.** No stream requests and no probes. A single probe consumes one of your connections and drops whoever is watching.
- **Credentials are redacted.** Provider credentials live inside stream URLs in a typical setup, so every string that can reach a notification or a logged error passes through a redactor first, and the report renders an allowlisted set of fields only.
- **Nothing is served over HTTP.** The report is a file in a folder you already have mounted.
- **If the collector goes blind, the report says so loudly**, rather than quietly reporting that every channel is dead.

## What to expect at first

**Your first month of reports will carry a red "not trustworthy" banner, and that is the plugin working rather than failing.** A dataset younger than the unused threshold cannot honestly call anything unused. There is no way to shorten this by importing history: Dispatcharr does not retain the state Dustarr reads, so a fresh installation genuinely starts at zero.

**Most of a typical lineup is excluded from judgment, and that is the point.** The actionable answer comes from the channels the plugin is willing to judge, not from the whole lineup.

## Optional: emailed reports

Dustarr does not send mail itself. It can hand its report to the [Newsflasharr](https://github.com/PiratesIRC/Dispatcharr_Newsflasharr) plugin, which delivers it. This is off by default, and with Newsflasharr absent or disabled nothing is sent and nothing fails.

## After installing

**Restart the Dispatcharr container.** The web workers reload a plugin when its manifest changes, but the Celery workers that run the scheduled report import plugins only at worker start.

Then press **Validate settings**, which writes nothing and checks the collector, the schedule and whether email could go out.

## Documentation

- [User guide](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/USER-GUIDE.md): every setting, every button, and how to read the report.
- [Troubleshooting](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin/blob/master/docs/troubleshooting.md): arranged by symptom.
- [Source repository](https://github.com/PiratesIRC/Dispatcharr-Dustarr-Plugin)

## Requirements

- Dispatcharr v0.20.0 or newer
- No internet access of any kind

## License

MIT
