[Back to All Plugins](../../README.md)

# Packet Slapper

**Version:** `1.0.3` | **Author:** write-erase | **Last Updated:** Oct 06 2026, 22:16 UTC

Runs scheduled or on-demand Ookla Speedtests through Dispatcharr to measure speed and latency.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/write-erase/packet-slapper)

## Downloads

### Latest Release

- **Download:** [`packet-slapper-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/packet-slapper-1.0.3/packet-slapper-1.0.3.zip)
- **Built:** Oct 06 2026, 22:16 UTC
- **Source Commit:** [`c2d4441`](https://github.com/Dispatcharr/Plugins/commit/c2d44413106619a95d620c87d0067b29109872da)

**Checksums:**
```
MD5:    b5fdaa795b88e3d30ea2c22321925a27
SHA256: de7c7a3a00b951bc5055974a5b002946d5f8e4a8569441cfd1c324f65360679b
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.0.3` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/packet-slapper-1.0.3/packet-slapper-1.0.3.zip) | Oct 06 2026, 22:16 UTC | [`c2d4441`](https://github.com/Dispatcharr/Plugins/commit/c2d44413106619a95d620c87d0067b29109872da) | b5fdaa795b88e3d30ea2c22321925a27 | de7c7a3a00b951bc5055974a5b002946d5f8e4a8569441cfd1c324f65360679b |
| `1.0.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/packet-slapper-1.0.2/packet-slapper-1.0.2.zip) | Oct 06 2026, 21:37 UTC | [`5f3473a`](https://github.com/Dispatcharr/Plugins/commit/5f3473a1592f27f6a5fb6b304d4905267f8a4982) | f3cfc6a72f30892c1a3a8456fe5759fe | 2c5eb3b15eb02f454ed9a83cc44a62e433fde30b3cb42b0d6f8af9aa7a4fd43a |
| `1.0.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/packet-slapper-1.0.1/packet-slapper-1.0.1.zip) | Oct 06 2026, 01:53 UTC | [`d5e6aaa`](https://github.com/Dispatcharr/Plugins/commit/d5e6aaa839dc85dcb5bbd5775c643ca4a26796cd) | 7049184debf26bc2715ac5d9ee4d381f | a6483705d1271626c0a306ff4ee3885a3f1dc32a5b34caef864c86bf3c62affd |
| `1.0.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/packet-slapper-1.0.0/packet-slapper-1.0.0.zip) | Sep 27 2026, 19:22 UTC | [`3cfc312`](https://github.com/Dispatcharr/Plugins/commit/3cfc312abf5b0b52533e0b41165189beae2d072e) | af97ba78f3e7a0df5d2a7b6824342a07 | 6e075bedfcbf06be6c60758f42394a4f771ed8761c4d0a769617c3858b162fb9 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/packet-slapper)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# packet-slapper
Packet Slapper runs an official Ookla speedtest directly from inside Dispatcharr, so it measures whatever network path Dispatcharr itself uses, VPN included, without needing a separate container or docker socket.

Run it on demand or on a schedule. Click Run Now for a one-off test, or turn on the scheduler. Scheduled runs skip themselves automatically if anyone's watching live TV, VOD, or catch-up, since a speedtest eats real bandwidth.

Results show right in Dispatcharr, no external service required. You get download, upload, latency, jitter, packet loss, and which server it hit. Add a Discord webhook if you want, and every result also posts there, either as a plain text message or a colored embed card.

A few extras, too. You can pin tests to one specific Ookla server ID so results stay comparable over time, pick your display timezone from a dropdown, and use Check Active Streams or Scheduler Status any time to see what the plugin is doing right now and when the next run is due.