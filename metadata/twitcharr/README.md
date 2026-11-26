[Back to All Plugins](../../README.md)

# Twitcharr

**Version:** `1.3.6` | **Author:** eliasbruno124-dev | **Last Updated:** Nov 26 2026, 13:11 UTC

Twitch live-TV plugin for Dispatcharr with automatic channels, streams, XMLTV guide data and Streamlink playback.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/eliasbruno124-dev/Twitcharr)

## Downloads

### Latest Release

- **Download:** [`twitcharr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.6/twitcharr-1.3.6.zip)
- **Built:** Nov 26 2026, 13:12 UTC
- **Source Commit:** [`ed1acee`](https://github.com/Dispatcharr/Plugins/commit/ed1acee5669ce54d8bfea734a307ee0af393d81d)

**Checksums:**
```
MD5:    04cabc4c67f33b518f31b572c5aa98fa
SHA256: 5da26f8baa49c502701907060ebb1de1c245950f8a1e8c1393d767db07960891
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.3.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.6/twitcharr-1.3.6.zip) | Nov 26 2026, 13:12 UTC | [`ed1acee`](https://github.com/Dispatcharr/Plugins/commit/ed1acee5669ce54d8bfea734a307ee0af393d81d) | 04cabc4c67f33b518f31b572c5aa98fa | 5da26f8baa49c502701907060ebb1de1c245950f8a1e8c1393d767db07960891 |
| `1.3.5` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.5/twitcharr-1.3.5.zip) | Nov 24 2026, 20:04 UTC | [`07dae09`](https://github.com/Dispatcharr/Plugins/commit/07dae09d0aae8529f1c5a8c8da5189d423c950a9) | e0d87f789f9f2f54887c94a5eeca2e07 | e748ee426039df281b080c495bcbf9eef88478f471b6fd2c66198e39eeb0633f |
| `1.3.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.4/twitcharr-1.3.4.zip) | Nov 24 2026, 16:25 UTC | [`65a378b`](https://github.com/Dispatcharr/Plugins/commit/65a378b35ef6b88ff8aaa374a76eb8785025ec07) | 73c81b69764c3c5b75179b9a3ab319f1 | 779821cc94db8cf83fd9736bfafbc431f031f74203322c81bb918f1c66cb68fa |
| `1.3.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.3/twitcharr-1.3.3.zip) | Nov 03 2026, 19:46 UTC | [`dd6e1fa`](https://github.com/Dispatcharr/Plugins/commit/dd6e1fa8b36604c630c2b6afdd6cd349283002ec) | 8c3d32792c0e03a60bb89f1af79f0367 | f3e1074dc88bd077abc088fb588fa8523c9064fdc6651512baea91683f52753a |
| `1.3.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.2/twitcharr-1.3.2.zip) | Jul 13 2026, 02:54 UTC | [`2d65eb1`](https://github.com/Dispatcharr/Plugins/commit/2d65eb13b1ad72210ca517520c9d0608d2dc342b) | fcf4797c127a0eae8914cd83d172f63f | 2e9211be932ed2e92936daa00463c822b5b052b10a257afc81f4ecb2f2da8b2c |
| `1.3.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.1/twitcharr-1.3.1.zip) | Jun 21 2026, 18:14 UTC | [`e7c35b1`](https://github.com/Dispatcharr/Plugins/commit/e7c35b1506985c50d060ff8cb79e0c613129ea84) | 09e3b557f19263ffee7b2add67d36c9b | f8af7cbd7acf5d0c6cbef65d2daab87b3f9059d8716095dfca271cf4efa85998 |
| `1.3.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.3.0/twitcharr-1.3.0.zip) | Jun 15 2026, 14:21 UTC | [`f7bca5e`](https://github.com/Dispatcharr/Plugins/commit/f7bca5e4f5ce34958d6ec2b906e59d2cf81a54b7) | a86bcdb52fc0b178580787c8635d243a | d75a104aa0ec0383999f586c93c60d38f297256543f7a47c0fcddea8b3f8659a |
| `1.2.25` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/twitcharr-1.2.25/twitcharr-1.2.25.zip) | Jun 02 2026, 17:16 UTC | - | 34217d30accf77de447452a19e0b4e94 | e81327c022583e58114d0bf81159f8c41c42e298c8d950eb389362bafa18bbfe |

---

**Maintainers:** eliasbruno124-dev | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/twitcharr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Twitcharr

Twitcharr adds Twitch live streams to Dispatcharr as TV channels. It creates channels, streams, XMLTV guide data, and a StreamProfile from Twitch usernames, URLs, or discovery rules.

The plugin uses anonymous Twitch metadata and does not require a Twitch login, OAuth token, Client ID, Client Secret, or Twitch API key. Playback requires Streamlink in the Dispatcharr container.
