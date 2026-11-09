[Back to All Plugins](../../README.md)

# AerioTV Presets

**Version:** `0.0.2` | **Author:** jonzey231 | **Last Updated:** Nov 09 2026, 18:40 UTC

Preconfigure a user's AerioTV favorites, group order, hidden groups and categories, and app settings. Their AerioTV devices offer Dispatcharr Sync on first sign-in and start from this setup.

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue?style=flat-square)](https://spdx.org/licenses/AGPL-3.0-or-later.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/jonzey231/AerioTVPresets)

![Dispatcharr min](https://img.shields.io/badge/Dispatcharr_min-0.33.0-brightgreen?style=flat-square)

## Downloads

### Latest Release

- **Download:** [`aeriotv-presets-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/aeriotv-presets-0.0.2/aeriotv-presets-0.0.2.zip)
- **Built:** Nov 09 2026, 18:40 UTC
- **Source Commit:** [`9b465fd`](https://github.com/Dispatcharr/Plugins/commit/9b465fdf9a2166f6659a36c9522a21da0a257378)

**Checksums:**
```
MD5:    b2faf122cff00332c1189a01811eba7f
SHA256: f00e221b0ebe8db0a60c7bb1f96d940e220f0f486f62b61d4da64d50a7e5d898
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
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

Use: choose a user, Save, run Load, reload the page, make your choices, then run Preview and Apply
(Fill only adds what the record does not have yet; Replace overwrites what you set).

Collapsible sections need a Dispatcharr build with plugin settings sections (dev branch, November
2026); older 0.33.0 builds show Expand switches instead. The plugin makes no network calls.

Source, docs, and issues: https://github.com/jonzey231/AerioTVPresets
