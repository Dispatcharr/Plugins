[Back to All Plugins](../../README.md)

# Profilarr

**Version:** `1.0.2` | **Author:** Tw1zT3d2four7 | **Last Updated:** Sep 16 2026, 22:08 UTC

Hybrid ffmpeg + cvlc stream profile: ffmpeg fetches from the provider and regenerates timestamps, cvlc buffers and delivers the already-clean stream to clear up freezes on discontinuities

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Profilarr)

## Downloads

### Latest Release

- **Download:** [`profilarr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.2/profilarr-1.0.2.zip)
- **Built:** Sep 16 2026, 22:09 UTC
- **Source Commit:** [`641d3f4`](https://github.com/Dispatcharr/Plugins/commit/641d3f4107f8968daf0b6bc8a24dca92a9d064ab)

**Checksums:**
```
MD5:    9392534385fcaa826192805d0c582a7b
SHA256: 73529c7f85b3d9e6447690721060064ab36b692527f12602414d9d5d4ec99d5e
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.0.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.2/profilarr-1.0.2.zip) | Sep 16 2026, 22:09 UTC | [`641d3f4`](https://github.com/Dispatcharr/Plugins/commit/641d3f4107f8968daf0b6bc8a24dca92a9d064ab) | 9392534385fcaa826192805d0c582a7b | 73529c7f85b3d9e6447690721060064ab36b692527f12602414d9d5d4ec99d5e |
| `1.0.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.1/profilarr-1.0.1.zip) | Sep 16 2026, 09:17 UTC | [`52669d8`](https://github.com/Dispatcharr/Plugins/commit/52669d8a2afb5e536025c6db7cb0a77ab2585b2c) | 735a8911c2fe4ac1cc3b554ab2b96b21 | a279a0c86aa4353ef7f919dceace40e8ac42d0bbdd77acf337adf3ff1476ec35 |

---

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/profilarr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Profilarr

Hybrid ffmpeg + cvlc stream profile. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts, resent PAT/PMT, clamped negative timestamps); cvlc then buffers and delivers that already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
