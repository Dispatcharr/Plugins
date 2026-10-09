# Pirate Weatharr Station

A self-hosted, TV-style weather channel for Dispatcharr. PWS pulls forecast data from the Pirate Weather API, renders it as a looping broadcast, and publishes the result as a channel — up to three locations, each on its own channel or sharing one.

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

## What's new in 1.6

- **Shared channels:** each station has a Channel setting (A, B or C). Stations on the same channel share it and take turns — e.g. all three on one channel, or two together and one separate. Default is one channel per station.

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
