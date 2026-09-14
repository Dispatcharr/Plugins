# Gluetun Rotate

A Dispatcharr plugin that moves Gluetun to another VPN server when the IPTV provider refuses
the current exit address.

When Dispatcharr reaches the internet through Gluetun, the provider sees the VPN's address,
not yours. Sometimes Gluetun reconnects onto an address the provider's CDN will not serve:
every channel, on every list, answers HTTP 520 at once, while the same request from home
works. Nothing in Dispatcharr can fix that. The failover walks each chain onto the next
source, which is refused the same way, and the cure used to be restarting Gluetun by hand,
then Dispatcharr so it joins the new network namespace.

Gluetun Rotate notices the refusal and asks Gluetun for another server, without recreating
either container.

## Requirements

- Dispatcharr with the plugin system (the Plugins page), sharing Gluetun's network
  (`network_mode: container:gluetun` or `service:gluetun`)
- At least one active Xtream Codes account in Dispatcharr, which is what the plugin asks
- Gluetun's control server, with a role for this plugin (below)
- A Dispatcharr API key

## Install

Add a role to Gluetun's control server auth file, the one `HTTP_CONTROL_SERVER_AUTH_CONFIG_FILEPATH`
points to, and restart Gluetun once so it reads it, then Dispatcharr:

```toml
[[roles]]
name = "gluetun-rotate"
routes = ["GET /v1/publicip/ip", "GET /v1/vpn/status", "PUT /v1/vpn/status"]
auth = "apikey"
apikey = "a-long-random-key"
```

Then install the plugin from the Plugin Hub, or by unzipping the release into
`/data/plugins/gluetun-rotate` and pressing refresh on the Plugins page. Enable it, fill in
both keys, press **Apply**, and press **Ask** to see what the provider answers right now.

## Settings

| Setting | What it does |
|---|---|
| API key | A Dispatcharr API key of an **admin** user, from Settings → Users. The watcher reads the provider accounts with it, and Dispatcharr leaves the account password out for anyone else, so those accounts would be skipped as unusable |
| Gluetun key | The `apikey` of the role above |
| Gluetun URL | Gluetun's control server as Dispatcharr sees it. The default fits a shared network namespace |

## Actions

| Action | What it does |
|---|---|
| Apply settings | Starts the watcher, or restarts it with the new settings |
| Check status | The current exit address, the last rotation, and the journal |
| Ask the provider | Asks every account now and reports what each answered. Nothing is moved |
| Restart watcher | Starts it again if it is down. Also runs by itself when a channel starts, at most once a minute |
| Stop watcher | Stops it. The tunnel stays on whatever server it is on |

## How it works

Every two minutes the watcher asks each active Xtream Codes account for its
`player_api.php`, with the account's user agent. That request costs no stream connection.

Two rounds in a row in which any account answers between 520 and 527, Cloudflare's errors
for an origin that would not talk to it, count as a refused address. The watcher then stops
the tunnel through `PUT /v1/vpn/status`, starts it again, waits up to ninety seconds for a
different public address, and asks the provider once more. The journal records the old
address, the new one and the answer.

Gluetun picks a server at random among those its filters allow each time the tunnel
starts, which is what makes this work. A filter narrowed to one server leaves nowhere to go.

It holds back when:

- the last rotation was less than ten minutes ago
- three rotations have already happened in the last hour

A rotation that fails still counts toward both, so a control server that keeps refusing is
not asked again every two minutes.

A tunnel that comes back on the same address is recorded as a failed rotation. A rotation
that fails part way can leave the tunnel stopped: the next round finds it stopped and starts
it again. A tunnel stopped by hand is left alone.

## What this does not fix

A provider that is failing on its own. A 403, 507 or 509 means the provider is answering
and saying no, to everyone; a new address would not change that, so those answers never
trigger a rotation. Neither does a timeout: a tunnel that is down is Gluetun's own
healthcheck to restart.

Some edges answer 403 to a few streams right after the exit address changes, while
`player_api.php` still answers 200, so the probe cannot see it. From Dispatcharr 0.31.0, which
writes its log to `/data/logs/dispatcharr.log`, the watcher counts the `HTTP 403` lines there
every round and records them in the journal per channel. It only records them: whether a
rotation would help is for those numbers to show. Check status sums them up; the first
journal entry says whether the log was found.

A rotation drops every connection through the tunnel for a few seconds. When the address
is refused nothing is flowing anyway, which is the only time it happens.

## Development

```
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
pytest && mypy . && ruff check . && python scripts/build_zip.py
```

The same four checks run in CI on every push. Decisions, traps and the release routine are in
[docs/MEMORY.md](https://github.com/PilaScat/gluetun-rotate/blob/master/docs/MEMORY.md).

## License

MIT

The logo is built on Gluetun's own logo, from [qdm12/gluetun](https://github.com/qdm12/gluetun),
Copyright (c) 2018 Quentin McGaw, MIT licence.
