[Back to All Plugins](../../README.md)

# Profilarr

**Version:** `1.0.8` | **Author:** Tw1zT3d2four7 | **Last Updated:** Sep 18 2026, 22:39 UTC

Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt); cvlc then buffers and delivers the already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Profilarr)

## Downloads

### Latest Release

- **Download:** [`profilarr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.8/profilarr-1.0.8.zip)
- **Built:** Sep 18 2026, 22:40 UTC
- **Source Commit:** [`7ad6778`](https://github.com/Dispatcharr/Plugins/commit/7ad67786acf81b85282861de47d95cff322853b8)

**Checksums:**
```
MD5:    37540ab6547672bf7339771a2fae119d
SHA256: 1a7741faee8e1ba80b41743add89d4b2621e7228c6ffa8d90ec503d421f5e6e3
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.0.8` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.8/profilarr-1.0.8.zip) | Sep 18 2026, 22:40 UTC | [`7ad6778`](https://github.com/Dispatcharr/Plugins/commit/7ad67786acf81b85282861de47d95cff322853b8) | 37540ab6547672bf7339771a2fae119d | 1a7741faee8e1ba80b41743add89d4b2621e7228c6ffa8d90ec503d421f5e6e3 |
| `1.0.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.6/profilarr-1.0.6.zip) | Sep 18 2026, 18:04 UTC | [`dae63ae`](https://github.com/Dispatcharr/Plugins/commit/dae63ae3cfb4cc5bbf057979f1c87e3c759573f1) | ffa42a54a3f82b53ed162ca8563a09f0 | ac07dc3703d34a41348019da96fde800bc98cd4d83a6a592309c0de57505ede2 |
| `1.0.5` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.5/profilarr-1.0.5.zip) | Sep 18 2026, 07:26 UTC | [`1386b91`](https://github.com/Dispatcharr/Plugins/commit/1386b913d17c3a799afbeb114ea2079a1820a24d) | 6ca150e502084512f09a63208f035187 | ade08037667b0da5f1b636bee576999bc028ae5a491b5fb7fc8e5d9d9af2adc0 |
| `1.0.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.4/profilarr-1.0.4.zip) | Sep 18 2026, 01:21 UTC | [`0f617df`](https://github.com/Dispatcharr/Plugins/commit/0f617dfa7516a311a24533b7dc961e27f2f46493) | c7be50d6f48321bdb2a8a83f0d5988e2 | 763d129b378e944bbc07f012d327ad3277dcef71b22ae27ec978c3eaa119fa45 |
| `1.0.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.3/profilarr-1.0.3.zip) | Sep 17 2026, 19:29 UTC | [`cf00c95`](https://github.com/Dispatcharr/Plugins/commit/cf00c95ed204b3819961bbd8f2bd867f020dc2ce) | 868a7ff9757771e38261bc5aa9a13ab6 | c643e324a44e193589b922d8e9f081424571a101d403d4be66001de3dcceeff9 |
| `1.0.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.2/profilarr-1.0.2.zip) | Sep 16 2026, 22:09 UTC | [`641d3f4`](https://github.com/Dispatcharr/Plugins/commit/641d3f4107f8968daf0b6bc8a24dca92a9d064ab) | 9392534385fcaa826192805d0c582a7b | 73529c7f85b3d9e6447690721060064ab36b692527f12602414d9d5d4ec99d5e |
| `1.0.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.1/profilarr-1.0.1.zip) | Sep 16 2026, 09:17 UTC | [`52669d8`](https://github.com/Dispatcharr/Plugins/commit/52669d8a2afb5e536025c6db7cb0a77ab2585b2c) | 735a8911c2fe4ac1cc3b554ab2b96b21 | a279a0c86aa4353ef7f919dceace40e8ac42d0bbdd77acf337adf3ff1476ec35 |

---

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/profilarr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Profilarr

Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt, resent PAT/PMT, clamped negative timestamps); cvlc then buffers and delivers that already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
