# Profilarr

Hybrid ffmpeg + cvlc stream profile. ffmpeg fetches the provider stream directly with a custom user-agent and reconnect handling, and regenerates timestamps (+genpts+igndts, resent PAT/PMT, clamped negative timestamps); cvlc then buffers and delivers that already-clean stream, so downstream players don't freeze on a CDN-hiccup discontinuity.

Full docs, install options, and troubleshooting: https://github.com/Tw1zT3d2four7/Profilarr
