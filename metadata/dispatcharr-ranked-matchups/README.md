[Back to All Plugins](../../README.md)

# Ranked Matchups (Top Games)

**Version:** `1.4.0` | **Author:** Jacob-Lasky | **Last Updated:** Jun 13 2026, 13:20 UTC

Cross-sport interestingness curator. Pulls upcoming games per enabled sport, scores them on interestingness, matches to Dispatcharr channels via EPG, and renames+groups them into a Top Matchups channel profile so your guide shows only the games worth watching. Channels are numbered by kickoff time, so the list sorts soonest-first and the guide binds correctly in both the default M3U/EPG output and the Xtream Codes API with no special settings.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups)

## Downloads

### Latest Release

- **Download:** [`dispatcharr-ranked-matchups-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.4.0/dispatcharr-ranked-matchups-1.4.0.zip)
- **Built:** Jun 13 2026, 13:21 UTC

**Checksums:**
```
MD5:    45e24aef9b1864f5629f8c8a054ac5e0
SHA256: dcb1e12325d9346a0948b3699f4cb1b9eafd5030c4ebe94a21d9dcd121d5ce8a
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.4.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.4.0/dispatcharr-ranked-matchups-1.4.0.zip) | Jun 13 2026, 13:21 UTC | - | 45e24aef9b1864f5629f8c8a054ac5e0 | dcb1e12325d9346a0948b3699f4cb1b9eafd5030c4ebe94a21d9dcd121d5ce8a |
| `1.2.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.2.0/dispatcharr-ranked-matchups-1.2.0.zip) | Jun 11 2026, 14:01 UTC | - | 8fab111209b40779e2ac0b56152958b0 | 818597f921d7307256cb2eae618c786e490d981a8b555e55d25f40f4a62dc345 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/dispatcharr-ranked-matchups)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Ranked Matchups (Top Games)

A cross-sport "interestingness" curator for Dispatcharr. It pulls upcoming games for each sport you enable, scores every matchup on how interesting it is (rankings, standings, rivalries, betting lines, playoff/knockout stakes), matches the worthwhile games to your existing Dispatcharr channels via EPG, and renames + groups them into a dedicated **Top Matchups** channel profile. Your guide ends up showing the games worth watching instead of the full firehose.

## What it does

- Per-sport adapters (college football/basketball, NFL, NBA, MLB, NHL, WNBA, NWSL, MLS, top-flight soccer leagues, internationals/friendlies, World Cup, and more), each toggleable.
- Scores matchups with a transparent model (see `SCORING.md` in the source repo): ranked-vs-ranked, standings importance, rivalries, and betting-line signal where available.
- Matches scored games to your channels through EPG and builds a curated **Top Matchups** profile with clean, renamed entries.
- Runs on demand from the plugin UI or on a schedule.

## Requirements

- Most sources need a free API key (e.g. CollegeFootballData / CollegeBasketballData, Football-Data.org, The Odds API). Each sport's setting documents which key it needs; sports you do not enable need no key.
- Off-season sports simply produce no rows.

## Source, docs, and issues

Full source, scoring methodology, changelog, and issue tracker live in the upstream repository:

https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups

## License

MIT
