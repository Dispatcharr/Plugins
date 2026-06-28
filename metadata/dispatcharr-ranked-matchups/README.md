[Back to All Plugins](../../README.md)

# Ranked Matchups (Top Games)

**Version:** `1.10.0` | **Author:** Jacob-Lasky | **Last Updated:** Jun 28 2026, 18:15 UTC

Cross-sport interestingness curator. Pulls upcoming games per enabled sport, scores them on interestingness, matches to Dispatcharr channels via EPG, and renames+groups them into a Top Matchups channel profile so your guide shows only the games worth watching. Channels are numbered by kickoff time, so the list sorts soonest-first and the guide binds correctly in both the default M3U/EPG output and the Xtream Codes API with no special settings.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Jacob-Lasky/dispatcharr_ranked_matchups)

## Downloads

### Latest Release

- **Download:** [`dispatcharr-ranked-matchups-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.10.0/dispatcharr-ranked-matchups-1.10.0.zip)
- **Built:** Jun 28 2026, 18:15 UTC
- **Source Commit:** [`224a791`](https://github.com/Dispatcharr/Plugins/commit/224a7911f90db6635a3c7831393a4423592d7d57)

**Checksums:**
```
MD5:    4afd6f1e1175ac937d2bfee599bef01d
SHA256: 09165075376f702d854485d2c4f82983803f5e12c1445aa55b995e8b817fc1c9
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.10.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.10.0/dispatcharr-ranked-matchups-1.10.0.zip) | Jun 28 2026, 18:15 UTC | [`224a791`](https://github.com/Dispatcharr/Plugins/commit/224a7911f90db6635a3c7831393a4423592d7d57) | 4afd6f1e1175ac937d2bfee599bef01d | 09165075376f702d854485d2c4f82983803f5e12c1445aa55b995e8b817fc1c9 |
| `1.9.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.9.0/dispatcharr-ranked-matchups-1.9.0.zip) | Jun 22 2026, 17:39 UTC | [`ca8ef52`](https://github.com/Dispatcharr/Plugins/commit/ca8ef525fce703ff246206308442ed9ec141c35e) | 3f3acd3845ad7097d17a3ae4730d9c9e | 6abd8bd267c5258374f5ca0d1c9acbe5be6c7052e38ed4f7fa6123c654fd3aa2 |
| `1.8.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.8.0/dispatcharr-ranked-matchups-1.8.0.zip) | Jun 19 2026, 13:01 UTC | [`625294e`](https://github.com/Dispatcharr/Plugins/commit/625294e082158bfb51aed378dfcb33150595195c) | 9c10952be2c880b6c320dc0339e7d035 | f53459c29a763f7c792b53882c6558b2e5f0d2eaaffdf97ae276461ce6661ed5 |
| `1.7.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.7.2/dispatcharr-ranked-matchups-1.7.2.zip) | Jun 15 2026, 02:12 UTC | [`ed9c641`](https://github.com/Dispatcharr/Plugins/commit/ed9c641f6bc0bf5b70da688a971994d1d6b520e4) | af4b588393cf8510fcf867536422db48 | 9b20f5b02d57faa2d496e42db150d4406d715c9584b40c0ef5c58bae3f1e4d4e |
| `1.7.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.7.0/dispatcharr-ranked-matchups-1.7.0.zip) | Jun 14 2026, 12:29 UTC | - | 71cea724607fa61ed0ad6c4ea9df0e42 | 82b0c5735c28d3cd217747cd973fc6c36d6b9f2dc0cd493d5c434348b8be5eee |
| `1.5.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/dispatcharr-ranked-matchups-1.5.0/dispatcharr-ranked-matchups-1.5.0.zip) | Jun 14 2026, 02:51 UTC | - | 74b5c647079e1947ca49f6fbaca1f039 | 829bcb6964bfb443f982fb816f82240a8c26f6afa08e503011ce3d695732b7a5 |
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
