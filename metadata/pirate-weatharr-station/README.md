[Back to All Plugins](../../README.md)

# PWS - Pirate Weatharr Station

**Version:** `1.0.0` | **Author:** dexdeadly | **Last Updated:** Jul 31 2026, 12:47 UTC

TV-style weather channels powered by the Pirate Weather API. Runs up to three stations, each with its own location and Dispatcharr channel.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/dexdeadly/pirate-weatharr-station/)

## Downloads

### Latest Release

- **Download:** [`pirate-weatharr-station-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.0.0/pirate-weatharr-station-1.0.0.zip)
- **Built:** Jul 31 2026, 12:47 UTC
- **Source Commit:** [`6411b97`](https://github.com/Dispatcharr/Plugins/commit/6411b9759caf40f17bcc38e88e358fc669c71488)

**Checksums:**
```
MD5:    e190adfe0b8739be04fa80291c4dffcc
SHA256: a44cef5f3470854f1b05faaf64c76fecb67df23050ad5439e900f35e07499263
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.0.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.0.0/pirate-weatharr-station-1.0.0.zip) | Jul 31 2026, 12:47 UTC | [`6411b97`](https://github.com/Dispatcharr/Plugins/commit/6411b9759caf40f17bcc38e88e358fc669c71488) | e190adfe0b8739be04fa80291c4dffcc | a44cef5f3470854f1b05faaf64c76fecb67df23050ad5439e900f35e07499263 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/pirate-weatharr-station)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Pirate Weatharr Station

A self-hosted, TV-style weather channel for Dispatcharr. PWS pulls forecast data from the Pirate Weather API, renders it as a looping broadcast, and publishes the result as a channel.

📖 **[Read the full User Guide](https://github.com/dexdeadly/pirate-weatharr-station/README.md)** — setup steps, settings reference, and troubleshooting for every feature below.

## Pages

The channel cycles through eight pages, about 14 seconds each:

| Page | Contents |
|---|---|
| Current Conditions | Oversized temperature, condition icon, high/low, sun times, eight metric tiles |
| 12-Hour Trend | Temperature curve with precipitation-chance and cloud-cover series |
| 7-Day Forecast | Day cards with icons, highs/lows, a shared temperature range bar, plus precipitation, humidity, wind, gusts, cloud cover and UV per day |
| Live Radar | Animated NEXRAD/MRMS radar from NOAA over an OpenStreetMap base, with a dBZ legend and a source credit |
| Regional Conditions | Current temperatures at nearby cities, plotted on a map |
| Forecast Highs | Tomorrow's highs at those same cities |
| Extended Forecast | Narrative panels for today and tomorrow with an eight-value stat grid, feels-like, accumulation, visibility and moon phase |
| Almanac | Sunrise/sunset, dawn/dusk, moon phase, UV, ozone, accumulations, fire index |

## Requirements

- Dispatcharr v0.25.0 or later

## Documentation

Full setup instructions, settings reference, and troubleshooting: [https://github.com/jstevenscl/tickarr/blob/master/docs/USERGUIDE.md](https://github.com/dexdeadly/pirate-weatharr-station/README.md)

## Source

https://github.com/dexdeadly/pirate-weatharr-station
