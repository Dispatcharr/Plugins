[Back to All Plugins](../../README.md)

# AerioTV Presets

**Version:** `0.0.8` | **Author:** jonzey231 | **Last Updated:** Nov 13 2026, 20:03 UTC

Preconfigure a user's AerioTV favorites, group order, hidden groups, and settings. Their AerioTV devices offer Dispatcharr Sync on first launch and start from this setup. Requires AerioTV 1.8.45 or newer on Apple devices and AerioTV for Android 0.5.14 or newer.

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue?style=flat-square)](https://spdx.org/licenses/AGPL-3.0-or-later.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jonzey231/AerioTVPresets)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-0.33.0-brightgreen?style=flat-square)

## Downloads

### Latest Release

- **Download:** [`aeriotv-presets-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.8/aeriotv-presets-0.0.8.zip)
- **Built:** Nov 13 2026, 20:03 UTC
- **Source Commit:** [`221dcd5`](https://github.com/Dispatcharr/Plugins/commit/221dcd559adc08adc8019630368a45cbcbfdf7e4)

**Checksums:**
```
MD5:    08c02498e3a0293d33907bfa5f67cca7
SHA256: 46648c2c3e299762431e416c3afd6a61b8c1818609efee09c752a30799508601
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `0.0.8` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.8/aeriotv-presets-0.0.8.zip) | Nov 13 2026, 20:03 UTC | [`221dcd5`](https://github.com/Dispatcharr/Plugins/commit/221dcd559adc08adc8019630368a45cbcbfdf7e4) | 08c02498e3a0293d33907bfa5f67cca7 | 46648c2c3e299762431e416c3afd6a61b8c1818609efee09c752a30799508601 |
| `0.0.7` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.7/aeriotv-presets-0.0.7.zip) | Nov 09 2026, 21:15 UTC | [`87c45ef`](https://github.com/Dispatcharr/Plugins/commit/87c45efdc70a7dad3de92882de8afaf876b4cf5b) | 9c4016ad744f1ae726b138f4f20bc18b | 38aada8e834ceb21b1b99ad3239ccca71852ea11679046a0e5d5cbd093b4bffe |
| `0.0.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.6/aeriotv-presets-0.0.6.zip) | Nov 09 2026, 19:14 UTC | [`c902725`](https://github.com/Dispatcharr/Plugins/commit/c902725c303267207d1b44a3a97b5b2e12773237) | de359cb4d59e6c6e6fafdd2683ca2878 | c7688e78601ea4b2281bb2ab6a63ee103e887daa6704718b782f00135d377dfc |
| `0.0.5` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.5/aeriotv-presets-0.0.5.zip) | Nov 09 2026, 19:05 UTC | [`2cb8b42`](https://github.com/Dispatcharr/Plugins/commit/2cb8b422d685c6aa87a7ec985432b945d0906705) | 5c9f0ad2eadf80bcfade59620e4c7685 | a02431ac212ad0a14d94018247833068c0a2d787237947f056960a03440f0327 |
| `0.0.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.4/aeriotv-presets-0.0.4.zip) | Nov 09 2026, 18:55 UTC | [`d8da598`](https://github.com/Dispatcharr/Plugins/commit/d8da598a5da09939e403f1f842784366aba84dd7) | d1e6f172a134a771e9d094b6be07d399 | df299edd2316b52ce2e6f8ef43832b976b0854e8a926b8c033b8a5b5cb025d1f |
| `0.0.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.3/aeriotv-presets-0.0.3.zip) | Nov 09 2026, 18:50 UTC | [`6dc6153`](https://github.com/Dispatcharr/Plugins/commit/6dc615387ce76f32d2f30d0fcf6bfb3a5df4063f) | bb66aaecaf2fc492c7012e10b1b7923e | 9617cf1349ae52c11f3eda7ef8cbb46e75789755756f36c9b436d13c0d506fe6 |
| `0.0.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.2/aeriotv-presets-0.0.2.zip) | Nov 09 2026, 18:40 UTC | [`9b465fd`](https://github.com/Dispatcharr/Plugins/commit/9b465fdf9a2166f6659a36c9522a21da0a257378) | b2faf122cff00332c1189a01811eba7f | f00e221b0ebe8db0a60c7bb1f96d940e220f0f486f62b61d4da64d50a7e5d898 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/aeriotv-presets)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# AerioTV Presets

Lets a Dispatcharr admin set up a user's AerioTV app before the user signs in: favorite channels,
Live TV group order, hidden groups and categories, and app settings such as theme and mode. The
plugin writes the user's AerioTV Dispatcharr Sync record; their AerioTV devices offer Dispatcharr
Sync on first sign-in and start from that setup.

Use: choose a user, Save, run Refresh Lists, reload the page, make your choices, then run Preview and Apply
(Fill only adds what the record does not have yet; Replace overwrites what you set).

Collapsible sections need a Dispatcharr build with plugin settings sections (dev branch, November
2026); older 0.33.0 builds show Expand switches instead. The plugin makes no network calls.

Requires AerioTV 1.8.45 or newer on iPhone, iPad, and Apple TV, or AerioTV for Android 0.5.14 or
newer on phones, tablets, and Android TV.

Source, docs, and issues: https://github.com/jonzey231/AerioTVPresets
