# AerioTV Presets

Lets a Dispatcharr admin set up a user's AerioTV app before the user signs in: favorite channels,
Live TV group order, hidden groups and categories, and app settings such as theme and mode. The
plugin writes the user's AerioTV Dispatcharr Sync record; their AerioTV devices offer Dispatcharr
Sync on first sign-in and start from that setup.

Use: choose a user, Save, run Load, reload the page, make your choices, then run Preview and Apply
(Fill only adds what the record does not have yet; Replace overwrites what you set).

Collapsible sections need a Dispatcharr build with plugin settings sections (dev branch, November
2026); older 0.33.0 builds show Expand switches instead. The plugin makes no network calls.

Source, docs, and issues: https://github.com/jonzey231/AerioTVPresets
