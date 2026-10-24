# Channel Name Cleaner

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin that tidies up messy IPTV channel
names — the usual provider soup of `| HD |`, `(1080p)`, `[VIP]`, fancy-unicode `ᴴᴰ`, dangling pipes
and inconsistent spacing — safely, with a dry-run preview, a protect-list, collision handling,
backups and one-click undo.

```text
Rte One +1 | HD |            ->  Rte One +1
Sky Atlantic | FHD |         ->  Sky Atlantic
Sky Cinema Disney | FHD |    ->  Sky Cinema Disney FHD     (kept distinct from the HD/SD variants)
007 ᴴᴰ                       ->  007
BBC One (1080p)              ->  BBC One
| Benefits of a VPN |        ->  Benefits of a VPN
1+1 Спорт                    ->  1+1 Спорт                  (protected - left untouched)
&TV                          ->  &TV                        (protected)
```

## Why

IPTV playlists name the same channel a dozen different ways, and Dispatcharr channel names often
inherit that mess from the source `tvg-name`. This plugin normalises them with conservative,
idempotent rules so your lineup reads cleanly — without hand-editing hundreds of channels or risking
the ones that look like junk but aren't.

## Features

- Dry-run Preview — see every `old -> new` before anything is written, plus a full CSV export.
- Collision-safe. `Channel.name` is unique, so when a clean name would duplicate another, the plugin
  resolves it by strategy (keep a clean quality suffix, append a number, or skip) — it never
  force-overwrites.
- Protect-list for the tricky cases: non-Latin names (Cyrillic/Greek/Arabic/CJK...), `&TV`-style
  names, event/info groups, and your own regex.
- Per-group scope — run it on everything, or just chosen groups.
- Backups and multi-step Undo. Every Apply writes a timestamped backup; Undo Last peels back one
  Apply at a time.
- Fast bulk Apply via `bulk_update` (with a safe per-row fallback).
- Test a Name — try the rules on a single name and see which fired.
- Per-rule and per-group stats in the result summary.
- Optional scheduler to re-clean automatically after an M3U re-sync re-dirties names.
- EPG-safe — Dispatcharr links EPG by ID, not channel name, so renaming does not break guide data.

## Install

From the Dispatcharr store (once listed) — Plugins, Find Plugins, Channel Name Cleaner, Install, then
enable it under My Plugins.

Manual drop-in:

1. Download the latest `channel-name-cleaner.zip` from
   [Releases](https://github.com/noodlemctwoodle/dispatcharr-channel-name-cleaner/releases).
2. Extract it to `.../dispatcharr/data/plugins/channel-name-cleaner/` (so `plugin.py` and
   `plugin.json` sit directly inside that folder).
3. In Dispatcharr, go to Plugins, My Plugins, Reload, then toggle the plugin on.

## Usage

Open the plugin under My Plugins and work top to bottom:

1. Preview — a dry run. Nothing changes; you get a summary plus `last_preview.csv`.
2. Test a Name (optional) — type a name into the Test a Name field and run this to see the result and
   which rules fired. Useful for tuning.
3. Apply — renames the channels Preview would change. A timestamped backup is saved first.
4. Undo Last — restores names from the most recent Apply (run again to peel back earlier ones).
5. Last Results — re-show the last run's summary.

Tip: start with the scope limited to a single group (for example `UK | + 1's`) for a confidence run,
then widen it.

## Settings

| Setting | Default | What it does |
|---|---|---|
| Only These Groups | (all) | Comma-separated group names to include. |
| Ignore These Groups | - | Group names to exclude. |
| Strip pipe-delimited junk and quality tags | on | `Rte One +1 \| HD \|` becomes `Rte One +1`. |
| Strip bracketed quality/junk tags | on | Removes `(1080p)`, `[VIP]` etc. - only when the brackets are entirely junk, so `(Moldova)` survives. |
| Strip fancy-unicode quality marks | on | Removes `ᴴᴰ`, `ᵁᴴᴰ`. |
| Unicode NFKC normalize | off | Folds stylised/full-width characters to plain ASCII. |
| Join Separator | `" "` | How remaining pipe segments rejoin (a space, or e.g. `" - "`). |
| Collapse extra whitespace | on | Collapses multiple spaces and trims. |
| Normalize '+1' spacing | off | `Channel 4+1` becomes `Channel 4 +1` (risky - can mangle `1+1 International`). |
| Title-case names | off | Risky - fights acronyms like BBC/ITV/RTE. |
| On Collision | `suffix` | `suffix` (keep a clean quality tag), `numeric` (`... (2)`), or `skip`. |
| Protected Groups | `Todays Live Events, Info \| Service Status` | Groups never touched. |
| Protect non-Latin names | on | Skip Cyrillic/Greek/Arabic/CJK... names. |
| Protect names starting with `&` | on | Skip `&TV`, `&flix`, ... |
| Custom Protect Regex | - | Any name matching is left untouched. |
| Enable Scheduled Auto-Clean | off | Re-runs Apply on an interval (the plugin must be enabled). |
| Run Every (hours) | 12 | Scheduler interval. |
| Custom Rules (regex) | - | Extra `regex => replacement` lines, applied after the built-ins. |
| Test a Name | - | Input for the Test a Name action. |
| Max Preview Rows Shown | 400 | Examples listed on screen (the full set is always in the CSV). |

## How the cleaning works

Rules run in this order, and only when enabled: strip unicode quality marks, NFKC, strip bracketed
junk, split on `|` and drop empty/quality-only segments, `+1` spacing, custom rules, title-case,
collapse whitespace. A name is skipped entirely if it is in a protected group, contains non-Latin
script, starts with `&`, or matches your protect regex. After cleaning, collisions are resolved by
your chosen strategy so two channels never end up with the same name.

## Safety

- Nothing changes without Apply. Preview and Test are read-only.
- Backups are written to `backups/apply_*.csv` in the plugin folder on every Apply; Undo Last
  restores them (multi-step).
- Collision-safe by design - a clean that would duplicate an existing name is suffixed, numbered, or
  skipped, never forced.
- Rules are idempotent, so re-running (or the scheduler) is harmless.

## License

MIT, noodlemctwoodle
