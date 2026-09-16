[Back to All Plugins](../../README.md)

# Profilarr

**Version:** `1.0.1` | **Author:** Tw1zT3d2four7 | **Last Updated:** Sep 16 2026, 09:17 UTC

Hybrid cvlc + ffmpeg stream profile: cvlc pulls from the provider, ffmpeg remuxes and regenerates timestamps to clear up freezes on discontinuities

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Profilarr)

## Downloads

### Latest Release

- **Download:** [`profilarr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.1/profilarr-1.0.1.zip)
- **Built:** Sep 16 2026, 09:17 UTC
- **Source Commit:** [`52669d8`](https://github.com/Dispatcharr/Plugins/commit/52669d8a2afb5e536025c6db7cb0a77ab2585b2c)

**Checksums:**
```
MD5:    735a8911c2fe4ac1cc3b554ab2b96b21
SHA256: a279a0c86aa4353ef7f919dceace40e8ac42d0bbdd77acf337adf3ff1476ec35
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.0.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.1/profilarr-1.0.1.zip) | Sep 16 2026, 09:17 UTC | [`52669d8`](https://github.com/Dispatcharr/Plugins/commit/52669d8a2afb5e536025c6db7cb0a77ab2585b2c) | 735a8911c2fe4ac1cc3b554ab2b96b21 | a279a0c86aa4353ef7f919dceace40e8ac42d0bbdd77acf337adf3ff1476ec35 |

---

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/profilarr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Profilarr

Hybrid `cvlc` + `ffmpeg` stream profile. `cvlc` fetches and demuxes the provider stream with a custom user-agent; `ffmpeg` remuxes it and regenerates timestamps (`+genpts+igndts`, resent PAT/PMT, clamped negative timestamps) so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
