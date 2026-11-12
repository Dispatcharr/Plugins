# UK Sport on TV

A [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr) plugin that keeps a list of which UK channel shows each televised football match, weeks ahead: Sky Sports, TNT Sports, Premier Sports, BBC, ITV, Amazon Prime Video, DAZN and the rest.

Your TV guide usually only reaches a week ahead. This fills the gap, so a player can tell you that a match in three weeks' time is on Sky Sports Football before the guide lists it.

## What it does

- Reads the listings from [live-footballontv.com](https://www.live-footballontv.com/), which allows automated reading in its robots.txt. One page is fetched, at most every 6 hours.
- Keeps the next 30 days of matches (you can change this) in the plugin's settings, as a compact JSON list: kick-off time, home team, away team, competition and channels.
- Refreshes by itself after each EPG refresh, and you can refresh by hand with **Refresh listings now**. **Show status** lists the next few matches.
- Never wipes good listings: if the page can't be fetched, or comes back in a layout it doesn't recognise, the previous listings are kept.

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

## Notes

- Football only for now; that's what the source covers.
- Only matches shown on UK TV or UK streaming services are listed. A Saturday 3pm Premier League or SPFL kick-off isn't there, because it isn't on UK TV.
- No account or API key is needed.

## Licence

MIT
