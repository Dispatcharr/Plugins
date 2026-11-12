# UK Sport on TV

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin that keeps a list of which UK channel shows each televised football match, weeks ahead: Sky Sports, TNT Sports, Premier Sports, BBC, ITV, Amazon Prime Video, DAZN and the rest.

Your TV guide usually only reaches a week ahead. This fills the gap, so a player can tell you that a match in three weeks' time is on Sky Sports Football before the guide lists it.

## What it does

- Reads the listings from [live-footballontv.com](https://www.live-footballontv.com/), which allows automated reading in its robots.txt.
- **Adds each match to the guide of the channel showing it**, at the time of the match. For example, Sky Sports Football gets "Hearts v Celtic, Scottish Premiership" at 15:00, weeks ahead of most guides. Any player using your Dispatcharr guide then shows it (TiviMate, Plex, Viewarr…).
  - Channels are matched by name, so "ITV1" matches "ITV1 (London)" and "BBC One" matches "BBC One Wales", but "Premier Sports 1" never matches "Premier Sports 14". The provider's numbered event feeds ("SKY SPORTS+ B 04:") are never used.
  - It only fills gaps. The provider's own programmes are never changed or overlapped.
  - The added entries are marked, cleared and re-added after every EPG refresh. **Remove added matches** takes them all out (also turn off **Add matches to channel guides**, or they come back at the next refresh).
- Keeps the next 30 days of matches (you can change this) in the plugin's settings, as a compact JSON list, for players to read directly.
- Refreshes by itself after each EPG refresh. **Refresh listings now** refreshes by hand, and **Show status** lists the next few matches.
- Never wipes good listings: if the page can't be fetched, or comes back in a layout it doesn't recognise, the previous listings are kept.

## Club channels

Many clubs stream their own matches on a club channel. In Scotland in particular, the home club streams the games UK TV doesn't show, such as the Saturday 3pm kick-offs.

- **Which channels:** any channel named like `SPFL - CELTIC TV`, `SPFL - HEARTS TV` or `SERIE A - MILAN TV`. The league prefixes it recognises are SPFL, EPL, EFL, NIFL, WSL, SWPL, SERIE A, LALIGA, LIGUE 1 and BUNDESLIGA. MUTV and LFC TV are recognised by name.
- **Which games:** each league game that isn't on UK TV goes on the **home** club's channel, if you have that channel. So Kilmarnock v Aberdeen goes on Kilmarnock TV. If the home club has no channel in your lineup, the game isn't added anywhere.
- **Not Premier League games:** Premier League club channels can't show live Premier League games, so those are skipped.
- **Fixtures:** they come from ESPN's public data, a request or two per club every 6 hours.
- **Club channels with no guide** get one of the plugin's own: an EPG source called "UK Sport on TV", which only this plugin writes to.
- **Off switch:** turn off **Club channels** to skip all of this.

Whether a club actually streams a particular game depends on the club and where you are. The entries say "usually".

## Polite to the source

- **One page**, fetched at most every 6 hours per Dispatcharr server, only after one of its own EPG refreshes.
- **"Only if changed"**: each request asks for the page only if it has changed since the last fetch, so the reply is usually an empty "not modified".
- **Backs off when refused**: after a "too many requests" or "unavailable" reply, it waits as long as the site asks (at least an hour) and keeps the current listings meanwhile.
- **Rate-limited button**: Refresh works at most once every 10 minutes.
- **Identifies itself** with a User-Agent that links to this repo.

## Who uses it

[Viewarr](https://github.com/petebutty/viewarr), an Android TV player for Dispatcharr, reads it to show where your teams' games are on (Settings → Sports).

Any other client can read it too, through `GET /api/plugins/plugins/`: the `uk_sport_on_tv` plugin's `settings.listings` field. Plugin settings are only readable by Dispatcharr admin users.

Each match in `listings` is stored as:

```json
[1795964400000, "Hearts", "Celtic", "Scottish Premiership", ["Sky Sports Football"]]
```

The first value is the kick-off time in UTC milliseconds.

## Settings

| Setting | Default | |
| --- | --- | --- |
| Days ahead | 30 | How many days of listings to keep. |
| Add matches to channel guides | On | Puts each match on the channels showing it, where the guide has nothing then. |
| Club channels | On | Adds league games that aren't on UK TV to the home club's channel. |

## Notes

- Football only for now; that's what the source covers.
- The `listings` field also includes the club-channel games, with the club channel as their only channel, for example `[…, "Celtic", "St Mirren", "Scottish Premiership", ["Celtic TV"]]`.
- Only matches shown on UK TV or UK streaming services are listed. A Saturday 3pm Premier League or SPFL kick-off isn't there, because it isn't on UK TV.
- No account or API key is needed. Standard library only.
- After installing or updating, restart Dispatcharr so every worker loads the new version.

## Licence

MIT
