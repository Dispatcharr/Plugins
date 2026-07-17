# M3U Expiration Notifier

[![Dispatcharr plugin](https://img.shields.io/badge/Dispatcharr-plugin-8A2BE2)](https://github.com/Dispatcharr/Dispatcharr)
[![GitHub Release](https://img.shields.io/github/v/release/barryanderson/dispatcharr-m3u-expiration-notifier?include_prereleases&logo=github)](https://github.com/barryanderson/dispatcharr-m3u-expiration-notifier/releases)
[![Downloads](https://img.shields.io/github/downloads/barryanderson/dispatcharr-m3u-expiration-notifier/total?color=success&label=Downloads&logo=github)](https://github.com/barryanderson/dispatcharr-m3u-expiration-notifier/releases)
![Top Language](https://img.shields.io/github/languages/top/barryanderson/dispatcharr-m3u-expiration-notifier)
![Licence](https://img.shields.io/github/license/barryanderson/dispatcharr-m3u-expiration-notifier)

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin that watches your M3U/Xtream-Codes account expiration dates and emails you before (and when) they expire.

Dispatcharr tracks expiration on each M3U account's default profile (`M3UAccountProfile.exp_date`), but only ever surfaces it as an in-app notification on a fixed 7-day window. This plugin generalises that into a configurable set of day-before-expiration thresholds, delivered by email, on a schedule you control.

**Compatibility:** tested against Dispatcharr `0.27.2`. It likely works on other recent versions too, but that's the only one verified so far.

## Features

- Configurable check interval (default: every 24 hours), run automatically in the background.
- Configurable warning thresholds in days-before-expiration (default `30,14,7,3,1`), plus an always-on notification the moment an account fully expires.
- Per-profile de-duplication — you're notified once per threshold crossed, not on every check, until the account's expiration date changes (e.g. after a renewal).
- Styled HTML emails (with a plain-text fallback) via your own SMTP server — no third-party mail service, no Dispatcharr credentials required.
- On-demand actions: check now, validate your SMTP connection, send a test email, re-apply the schedule after changing the interval, and reset notification history after changing thresholds.
- SMTP delivery failures on scheduled checks (e.g. bad credentials) raise an in-app Dispatcharr notification, so a misconfiguration doesn't go unnoticed between manual checks.

## Installation

### Option A — from a plugin repository

Add this repo's manifest URL under Dispatcharr's plugin repository settings:

```
https://raw.githubusercontent.com/barryanderson/dispatcharr-m3u-expiration-notifier/master/manifest.json
```

The plugin will then appear in Dispatcharr's **Find Plugins** store, ready to install.

### Option B — manual install

1. Download or clone this repo.
2. Copy `plugin.py` and `plugin.json` into `/data/plugins/m3u_expiration_notifier/` inside your Dispatcharr container.
3. In Dispatcharr's Plugins page, click refresh, then enable **M3U Expiration Notifier**.

## Configuration

| Setting | Description |
| --- | --- |
| Check Interval (hours) | How often the background check runs. Run **Apply Schedule** after changing this. |
| Warn X Days Before Expiration | Comma-separated day thresholds (e.g. `30,14,7,3,1`). An email fires the first time an account is found within one of these windows. |
| Notify Email Address(es) | Comma-separated recipient list. |
| SMTP settings | Host, port, security (STARTTLS/SSL/None), username, password, and optional From address. |

### Actions

- **Check Expirations Now** — runs a check immediately using current settings.
- **Validate SMTP Connection** — connects to your SMTP server and logs in (when a username is set) without sending any email. A quick way to check your settings before running a real test email.
- **Send Test Email** — sends a real test email to your configured recipients, confirming delivery end-to-end (not just that the connection works).
- **Apply Schedule** — applies the new interval immediately after changing it, rather than waiting for the next check.
- **Scheduler Status** — shows when the next check is due.
- **Reset Notification State** — clears per-profile notification history. Use this after changing thresholds if an account isn't getting a new email because a since-removed threshold was already recorded as notified for it.

SMTP settings aren't checked automatically — if a scheduled check can't deliver a notification (e.g. bad credentials), Dispatcharr's in-app notification centre shows a warning until it's fixed.

## How it works

- Expiration data comes from `M3UAccountProfile.exp_date`, filtered to active accounts/profiles with an expiration date set — the same population Dispatcharr's own core expiration check uses.
- A small `state.json` file (kept alongside `plugin.py`) tracks, per profile, the expiration date it last saw and the most urgent threshold already notified for it. If the expiration date changes (e.g. a renewal), tracking resets and the notification cycle starts over.
- Since Dispatcharr's plugin system has no built-in "run every N hours" hook, the plugin runs its own background thread: one Dispatcharr process elects itself the scheduler host (via a lock file next to `plugin.py`) and wakes periodically to run the check directly.

## Licence

[MIT](LICENSE)

---

## AI assistance disclosure

This plugin was built with the assistance of [Claude Code](https://claude.com/claude-code), Anthropic's CLI coding agent. Claude Code was used to help design and implement the plugin's logic, diagnose bugs (including a state-tracking issue that could suppress notifications after a threshold change), and prepare this repository for distribution (manifest, licence, and documentation). All changes were reviewed by a human before release.
