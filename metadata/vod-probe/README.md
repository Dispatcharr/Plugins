[Back to All Plugins](../../README.md)

# VOD Probe

**Version:** `1.3.3` | **Author:** oxios0x00 | **Last Updated:** Oct 10 2026, 10:04 UTC

Probes the real quality of each VOD relation (movies and every episode of every series version) with ffprobe in a background task and writes it into the relation's custom_properties, so every tool reading Dispatcharr's API can use it. Can also backfill missing tmdb_id/imdb_id from the provider's per-title detail endpoint, merging safely into an existing catalogue entry when one already has the id. Dry run by default.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/oxios0x00/dispatcharr-vod-probe)

## Downloads

### Latest Release

- **Download:** [`vod-probe-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/vod-probe-1.3.3/vod-probe-1.3.3.zip)
- **Built:** Oct 10 2026, 10:04 UTC
- **Source Commit:** [`b52f675`](https://github.com/Dispatcharr/Plugins/commit/b52f675f54ab92cb0c6312aa53dce7b53d20c5b6)

**Checksums:**
```
MD5:    dd346d3865eae81d45a2c325fbe9479b
SHA256: e2a068cbb7b264e16d5a8925fc2ca7c50fcf18bfc46d61450458c09f14f6ebc5
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.3.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/vod-probe-1.3.3/vod-probe-1.3.3.zip) | Oct 10 2026, 10:04 UTC | [`b52f675`](https://github.com/Dispatcharr/Plugins/commit/b52f675f54ab92cb0c6312aa53dce7b53d20c5b6) | dd346d3865eae81d45a2c325fbe9479b | e2a068cbb7b264e16d5a8925fc2ca7c50fcf18bfc46d61450458c09f14f6ebc5 |
| `1.3.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/vod-probe-1.3.2/vod-probe-1.3.2.zip) | Oct 03 2026, 14:31 UTC | [`8041328`](https://github.com/Dispatcharr/Plugins/commit/80413280036aeac2cd4b08c8d358844dae2cbb3e) | 2d70ad62b80c25aab64ec259fb008670 | 538c07074d737f63557b342360ba5496a16fd43b1cac0ad28693b86b7a80702f |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/vod-probe)

**Metadata:** [View full manifest](./manifest.json)
