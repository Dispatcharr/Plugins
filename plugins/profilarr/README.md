# Profilarr

Hybrid `cvlc` + `ffmpeg` stream profile. `cvlc` fetches and demuxes the provider stream with a custom user-agent; `ffmpeg` remuxes it and regenerates timestamps (`+genpts+igndts`, resent PAT/PMT, clamped negative timestamps) so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
