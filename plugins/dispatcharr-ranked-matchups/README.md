# Ranked Matchups (Top Games)

A cross-sport "interestingness" curator for Dispatcharr. It pulls upcoming games for each sport you enable, scores every matchup on how interesting it is (rankings, standings, rivalries, betting lines, playoff/knockout stakes), matches the worthwhile games against your lineup, and renames + groups them into a dedicated **!Top Matchups** channel group. Your guide ends up showing the games worth watching instead of the full firehose.

## What it does

- Per-sport adapters (college football/basketball, NFL, NBA, MLB, NHL, WNBA, NWSL, MLS, top-flight soccer leagues, internationals/friendlies, World Cup, and more), each toggleable.
- Scores matchups with a transparent model (see `SCORING.md` in the source repo): ranked-vs-ranked, standings importance, rivalries, and betting-line signal where available.
- Matches scored games against your lineup and builds a curated **!Top Matchups** channel group with clean, renamed entries.
- Runs on demand from the plugin UI or on a schedule.

## How games are matched

Three independent paths, all of which can contribute (results merge and stack as
fallback streams):

- **EPG programme title, sub-title or description** inside the game's window.
- **Channel name**, for providers that name the fixture on the channel.
- **Stream name, whether or not that stream is attached to a channel.** This is
  what lets a large M3U produce per-match feeds without curating them into
  channels first, and it is why a matchup channel can pick up feeds you never
  added yourself.

Because that third path sweeps your whole M3U, three settings decide what
happens to feeds you did not curate, and none of them removes a stream unless
you say so: **Preferred languages** (an ordered list like `en` or `de, en`),
**Demote stream groups** (used only as a last resort, still playable), and
**Exclude stream groups** (never attached at all). Streams you have attached to
a channel of your own always sort ahead of ones found only by the sweep.

## Requirements

- Most sources need a free API key (e.g. CollegeFootballData / CollegeBasketballData, Football-Data.org, The Odds API). Each sport's setting documents which key it needs; sports you do not enable need no key.
- Off-season sports simply produce no rows.

## Source, docs, and issues

Full source, scoring methodology, changelog, and issue tracker live in the upstream repository:

https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups

## License

MIT
