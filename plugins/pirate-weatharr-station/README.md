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
