[Back to All Plugins](../../README.md)

# Profilarr

**Version:** `2.1.6` | **Author:** Tw1zT3d2four7 | **Last Updated:** Sep 24 2026, 04:31 UTC

Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt); cvlc then buffers and delivers the already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tw1zT3d2four7/Profilarr)

## Downloads

### Latest Release

- **Download:** [`profilarr-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.1.6/profilarr-2.1.6.zip)
- **Built:** Sep 24 2026, 04:31 UTC
- **Source Commit:** [`f5a6a0b`](https://github.com/Dispatcharr/Plugins/commit/f5a6a0bd3da24796156d458289cd813bf713e9d6)

**Checksums:**
```
MD5:    49c815b332dd130a87d1cde2736f108b
SHA256: 2b66a3375c45b76c6e13120940709f06d323ece6fba89cbd2ea2c9fcc0fc7407
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `2.1.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.1.6/profilarr-2.1.6.zip) | Sep 24 2026, 04:31 UTC | [`f5a6a0b`](https://github.com/Dispatcharr/Plugins/commit/f5a6a0bd3da24796156d458289cd813bf713e9d6) | 49c815b332dd130a87d1cde2736f108b | 2b66a3375c45b76c6e13120940709f06d323ece6fba89cbd2ea2c9fcc0fc7407 |
| `2.1.5` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.1.5/profilarr-2.1.5.zip) | Sep 23 2026, 23:39 UTC | [`650d0da`](https://github.com/Dispatcharr/Plugins/commit/650d0dac0462d8c3bd389f72e03d7cd6fb0dc5b2) | 079df134c2489d523326c6e616f1bb48 | d2c2eb89004b16398c28c2c01fda6d15c102e36d8882c100675d753bd1f43deb |
| `2.1.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.1.4/profilarr-2.1.4.zip) | Sep 23 2026, 22:58 UTC | [`b29c04d`](https://github.com/Dispatcharr/Plugins/commit/b29c04d58b63488ee1fde980406c5b1963936bb9) | 49d09a161e6b96f5ec94d9f73f67affd | f60ad2f12e17d56a0a611127d64c22eae798f7c655be4cd12c403b94746674d9 |
| `2.0.7` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.0.7/profilarr-2.0.7.zip) | Sep 19 2026, 20:31 UTC | [`0fbd3f6`](https://github.com/Dispatcharr/Plugins/commit/0fbd3f69f9a29bae0ececfb30d1ddb7d28d23686) | b2151d8e5a9133dff124b5bd9aed62de | fe804476610bef25a3f46bfcc826ee8ed7853398b6a440c38f459a3b7a58d5b7 |
| `2.0.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-2.0.4/profilarr-2.0.4.zip) | Sep 19 2026, 16:08 UTC | [`bacf325`](https://github.com/Dispatcharr/Plugins/commit/bacf3254903855e47ebd410e4928e58790172495) | c676915eed54c998e03b2da7776d5d56 | 813c52b14666d325063486307b9bd5ad0bb1f2eb65f990cc1cdf61bebe1bbdac |
| `1.0.9` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.9/profilarr-1.0.9.zip) | Sep 19 2026, 02:23 UTC | [`9fb219b`](https://github.com/Dispatcharr/Plugins/commit/9fb219b368448b715525daef5cd52ff9294a475d) | b07e338e82c5ad9df3d27d9b79857ee3 | 249eadbbe2d5c043cffa3e9789b69680d64ece29c9ab8e6f0325b165220cb808 |
| `1.0.8` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.8/profilarr-1.0.8.zip) | Sep 18 2026, 22:40 UTC | [`7ad6778`](https://github.com/Dispatcharr/Plugins/commit/7ad67786acf81b85282861de47d95cff322853b8) | 37540ab6547672bf7339771a2fae119d | 1a7741faee8e1ba80b41743add89d4b2621e7228c6ffa8d90ec503d421f5e6e3 |
| `1.0.6` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.6/profilarr-1.0.6.zip) | Sep 18 2026, 18:04 UTC | [`dae63ae`](https://github.com/Dispatcharr/Plugins/commit/dae63ae3cfb4cc5bbf057979f1c87e3c759573f1) | ffa42a54a3f82b53ed162ca8563a09f0 | ac07dc3703d34a41348019da96fde800bc98cd4d83a6a592309c0de57505ede2 |
| `1.0.5` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.5/profilarr-1.0.5.zip) | Sep 18 2026, 07:26 UTC | [`1386b91`](https://github.com/Dispatcharr/Plugins/commit/1386b913d17c3a799afbeb114ea2079a1820a24d) | 6ca150e502084512f09a63208f035187 | ade08037667b0da5f1b636bee576999bc028ae5a491b5fb7fc8e5d9d9af2adc0 |
| `1.0.4` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/profilarr-1.0.4/profilarr-1.0.4.zip) | Sep 18 2026, 01:21 UTC | [`0f617df`](https://github.com/Dispatcharr/Plugins/commit/0f617dfa7516a311a24533b7dc961e27f2f46493) | c7be50d6f48321bdb2a8a83f0d5988e2 | 763d129b378e944bbc07f012d327ad3277dcef71b22ae27ec978c3eaa119fa45 |

---

**Maintainers:** Tw1zT3d2four7 | **Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/profilarr)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Profilarr

Hybrid ffmpeg + cvlc stream profiles. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts+discardcorrupt, resent PAT/PMT, clamped negative timestamps); cvlc then buffers and delivers that already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
