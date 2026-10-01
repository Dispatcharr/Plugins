# Clapparr

**The metadata slate for your DVR.** Writes Kodi/Plex NFO sidecars, posters and episode thumbnails for Dispatcharr recordings, from metadata Dispatcharr already holds — so they present with real titles, summaries and artwork instead of `Episode 08-18`.

## What this is for

- Your DVR recordings show up in Plex/Emby/Jellyfin/Kodi as bare `Episode 08-18` entries with no summary or artwork.
- You want the EPG's title, plot, season/episode and poster attached to each recording, automatically, the moment it finishes.
- Daily bulletins with no episode title in the EPG get a readable air-date title (`Wednesday 19 August 2026`) instead of the show name repeated.

## What it writes

```
<show>/tvshow.nfo                 show metadata
<show>/poster.jpg                 show poster
<show>/<recording>.nfo            episode metadata
<show>/<recording>-thumb.jpg      episode still (optional)
```

Runs automatically on `recording_end` (deferred until the remux completes), plus manual **Generate missing / Regenerate all / Preview** actions.

## Highlights

- **Zero dependencies** — Python stdlib only; thumbnails use the ffmpeg already in the Dispatcharr image, and fail soft without it.
- **Guarded artwork fallback** — when Dispatcharr's exact-title lookup finds no poster, a strict fuzzy TVmaze match steps in (word-prefix only, coverage threshold, ambiguous ties refused, every decision logged).
- **Optional webhook** — notify a scan relay such as [autopulse](https://github.com/dan-online/autopulse) per recording, with path rewriting; credentials never reach the log.
- **Optional Plex artwork refresh** — a library scan re-reads episode NFOs but ignores a changed show poster; with a Plex URL+token set, Clapparr issues the forced per-show refresh itself.
- Sidecars take the ownership of their directory, so a root-running container doesn't litter root-owned files beside your media.

## Plex setup

Set the TV library's agent to **Plex NFO Series** (PMS 1.43.1+ — the NFO agent is available to everyone, no Plex Pass required) and keep *Use local assets* on. **Plex takes the episode index from the filename** — recordings must carry `SxxExx`. If yours land on the date-based fallback template despite the EPG having episode numbers, see [Dispatcharr#1307](https://github.com/Dispatcharr/Dispatcharr/issues/1307). One Plex-side limitation to know: NFO-agent libraries don't support Plex's watch-state/ratings sync.

## Tested on

Developed and tested against **Plex only**. The sidecars are standard Kodi-format NFOs, which Kodi, Jellyfin and Emby also read — and they're generally *more* forgiving of date-named files than Plex — but I haven't run them myself. **Feedback from Kodi/Jellyfin/Emby users is very welcome.**

## A note on this project

Clapparr is a personal project, built to scratch an itch on my own DVR and shared in case it saves someone else the same work. It gets attention when my setup needs it. Issues and PRs are welcome and read — just calibrate expectations accordingly.

## More

- Source, full docs, tests: https://github.com/v8eta/clapparr
- Releases: https://github.com/v8eta/clapparr/releases

MIT licensed. AI tools were used in Clapparr's development; the behaviour described here was verified against a live Dispatcharr + Plex setup before release.
