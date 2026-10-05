[Back to All Plugins](../../README.md)

# PWS - Pirate Weatharr Station

**Version:** `1.5.1` | **Author:** dexdeadly | **Last Updated:** Oct 05 2026, 17:40 UTC

TV-style weather channels powered by the Pirate Weather API & NOAA. Runs up to three stations, each with its own location and Dispatcharr channel.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](https://spdx.org/licenses/MIT.html) [![Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/dexdeadly/pirate-weatharr-station/)

## Downloads

### Latest Release

- **Download:** [`pirate-weatharr-station-latest.zip`](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.5.1/pirate-weatharr-station-1.5.1.zip)
- **Built:** Oct 05 2026, 17:41 UTC
- **Source Commit:** [`d70208b`](https://github.com/Dispatcharr/Plugins/commit/d70208b451f884ee294e6e5f03bac70db7dc2add)

**Checksums:**
```
MD5:    1c9caa76ce3024ace09dc188ac8db0a6
SHA256: 11bd6bacf405cbbf1f42afdbe9df6ce3113c1ba1530942d08082bbeac99dd307
```

### All Versions

| Version | Download | Built | Commit | MD5 | SHA256 |
|---------|----------|-------|--------|-----|--------|
| `1.5.1` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.5.1/pirate-weatharr-station-1.5.1.zip) | Oct 05 2026, 17:41 UTC | [`d70208b`](https://github.com/Dispatcharr/Plugins/commit/d70208b451f884ee294e6e5f03bac70db7dc2add) | 1c9caa76ce3024ace09dc188ac8db0a6 | 11bd6bacf405cbbf1f42afdbe9df6ce3113c1ba1530942d08082bbeac99dd307 |
| `1.4.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.4.2/pirate-weatharr-station-1.4.2.zip) | Oct 01 2026, 19:46 UTC | [`3c4dd61`](https://github.com/Dispatcharr/Plugins/commit/3c4dd6126c9c7c2bdc12f8e9c33fd8295b3f1c18) | 1998819e6011a1f35904d41776643097 | 380c998bc0463b317f49f8756579ea41ab1233fbb86e8c15effe1827c60963e0 |
| `1.3.2` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.3.2/pirate-weatharr-station-1.3.2.zip) | Aug 18 2026, 04:54 UTC | [`878b01c`](https://github.com/Dispatcharr/Plugins/commit/878b01c6f9a5f53c8c9c9e1e78994b5d7fc69d07) | 0a2369bfb13318e04ccc14e00e8a605f | 40bc77a571270d47205d4ec5cb74b172352c2465845dfa59e574e1ca26a3165b |
| `1.0.0` | [Download](https://github.com/Dispatcharr/Plugins/releases/download/pirate-weatharr-station-1.0.0/pirate-weatharr-station-1.0.0.zip) | Jul 31 2026, 12:47 UTC | [`6411b97`](https://github.com/Dispatcharr/Plugins/commit/6411b9759caf40f17bcc38e88e358fc669c71488) | e190adfe0b8739be04fa80291c4dffcc | a44cef5f3470854f1b05faaf64c76fecb67df23050ad5439e900f35e07499263 |

---

**Source:** [Browse Plugin](https://github.com/Dispatcharr/Plugins/tree/main/plugins/pirate-weatharr-station)

**Metadata:** [View full manifest](./manifest.json)

---

## Plugin README

# Pirate Weatharr Station

A self-hosted, TV-style weather channel for Dispatcharr. PWS pulls forecast data from the Pirate Weather API, renders it as a looping broadcast, and publishes the result as a channel — up to three stations, each with its own location and channel.

📖 **[Read the full User Guide](https://github.com/dexdeadly/pirate-weatharr-station/blob/main/README.md)** — setup steps, settings reference, and troubleshooting for every feature below.

## Upgrading from 1.4.x or earlier

Versions up to 1.4.2 installed under a folder the plugin browser couldn't match, so **Update** failed with "Plugin 'pws' already exists". From 1.5 on, updates work in place. The one-time move to 1.5:

1. Install/update PWS from the plugin browser — it installs next to the old entry.
2. **Enable** the new entry. Within ~20 seconds it adopts the old one: API key, station settings and existing Weather channels carry over (no duplicates), the old stations stop and the old entry is disabled.
3. Delete the old, now-disabled **PWS** entry.

## Pages

Up to nine pages, 14 seconds each by default; choose which appear, their order and the time per page in settings.

| Page | Contents |
|---|---|
| Current Conditions | Oversized temperature, condition icon, high/low labelled with the period they cover, sun times, eight metric tiles |
| 12-Hour Trend | Temperature curve with precipitation-chance and cloud-cover series |
| 7-Day Forecast | Day cards with icons, highs/lows and per-day precipitation, humidity, wind, gusts, cloud cover and UV |
| Live Radar | Animated NOAA radar (or RainViewer worldwide) over an OpenStreetMap base |
| Regional Conditions | Current temperatures at well-spread nearby cities, plotted on a map |
| Forecast Highs | Today's high at those cities (tomorrow's after 6 pm) |
| Extended Forecast | Narrative panels for today and tomorrow with a stat grid |
| Surf Report | Optional, with a surf spot set: estimated surf and rating, swell, wind, water temperature, tides and a 5-day wave outlook |
| Almanac | Sunrise/sunset, dawn/dusk, moon phase, UV, ozone, accumulations, fire index |

Every page carries a colour-coded alert bar (no alerts / watch-advisory / warning) fed by NWS alerts polled every minute for US locations.

## What's new in 1.5

- Plugin-browser updates work in place (see above)
- Restart action; changed settings apply on Start; stations auto-start after Dispatcharr restarts
- Colour-coded alert bar with minute-fresh NWS alerts, plus an "updated / data delayed" note
- Optional Surf Report page; well-spread map cities that skip the station's own area
- 12/24-hour clock, page selection and order, inHg pressure for Imperial units
- Map-city weather from Open-Meteo, so the maps no longer use Pirate Weather quota
- Station health (last update, errors, quota left) in the plugin status

## Requirements

- Dispatcharr v0.25.0 or later
- A free Pirate Weather API key (pirateweather.net)

## Documentation

Full setup instructions, settings reference and troubleshooting: [User Guide](https://github.com/dexdeadly/pirate-weatharr-station/blob/main/README.md)

## Source

https://github.com/dexdeadly/pirate-weatharr-station
