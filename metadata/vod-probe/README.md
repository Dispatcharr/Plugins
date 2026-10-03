[Back to All Plugins](../../README.md)

# VOD Probe

**Version:** `1.3.2` | **Author:** oxios0x00 | **Last Updated:** Oct 03 2026, 14:30 UTC

Probes the real quality of each VOD relation (movies and every episode of every series version) with ffprobe in a background task and writes it into the relation's custom_properties, so every tool reading Dispatcharr's API can use it. Can also backfill missing tmdb_id/imdb_id from the provider's per-title detail endpoint, merging safely into an existing catalogue entry when one already has the id. Dry run by default.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/oxios0x00/dispatcharr-vod-probe)

## Downloads

### Latest Release

- **Download:** [`vod-probe-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/vod-probe-1.3.2/vod-probe-1.3.2.zip)
- **Built:** Oct 03 2026, 14:31 UTC
- **Source Commit:** [`8041328`](https://github.com/Dispatcharr/Plugins/commit/80413280036aeac2cd4b08c8d358844dae2cbb3e)

**Checksums:**
```
MD5:    2d70ad62b80c25aab64ec259fb008670
SHA256: 538c07074d737f63557b342360ba5496a16fd43b1cac0ad28693b86b7a80702f
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.3.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/vod-probe-1.3.2/vod-probe-1.3.2.zip) | Oct 03 2026, 14:31 UTC | [`8041328`](https://github.com/Dispatcharr/Plugins/commit/80413280036aeac2cd4b08c8d358844dae2cbb3e) | 2d70ad62b80c25aab64ec259fb008670 | 538c07074d737f63557b342360ba5496a16fd43b1cac0ad28693b86b7a80702f |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/vod-probe)

**Metadata:** [View full manifest](./manifest.json)
