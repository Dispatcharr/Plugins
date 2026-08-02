# Newsflasharr

Central notification service for Dispatcharr plugins. One plugin owns all
delivery: other plugins drop lightweight events into a file queue, and
Newsflasharr routes them to Discord, a generic webhook, ntfy, Apprise, email,
or a banner drawn over live video. Configured once, in one place, instead of
every plugin re-inventing its own webhook code.

## What it does

- **A calling plugin makes one call and is finished.** That call never blocks
  and never raises, so a caller is unaffected even when Newsflasharr is not
  running.
- **Repeats collapse instead of flooding you.** The same alert arriving over
  and over becomes one message, then a summary when the window closes. An
  alert that gets worse breaks the window and is sent at once, so a warning
  can never swallow the critical that follows it.
- **Quiet hours, an hourly cap and per-channel retry** are configured here
  rather than separately in every plugin.
- **Your provider hostnames are removed from outgoing messages**, using the
  electronic programme guide sources and accounts Dispatcharr already holds.
- **It is read-only on Dispatcharr.** It writes nothing outside its own
  directory, and it never creates or edits an output profile, a channel or a
  stream.

## After installing

**Restart the Dispatcharr container.** This is not optional. The worker that
delivers events starts when the plugin is constructed, and without a restart
the plugin loads and looks healthy while nothing is delivered.

Then enable the plugin, fill in at least one channel, click **Validate
settings**, and click **Send test notification** for each channel you
configured. Saving the settings form on its own arms nothing, because
Dispatcharr gives plugins no hook that runs after a save, and only a real send
proves a channel works.

## Two things to know before relying on it

- **Delivery is at-least-once per channel.** A duplicate is possible after a
  crash. That is a deliberate tradeoff, not a defect.
- **Email is the one channel where a successful send can still be a lie.** A
  mail server accepting a message says nothing about spam filtering. Check the
  inbox and the spam folder before trusting that channel.

## Documentation

Full documentation lives in the plugin's own repository:

- [User guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/USER-GUIDE.md)
  for setting up channels, routing rules, quiet hours, redaction, the
  on-screen banner, and a troubleshooting ladder.
- [Caller API](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/API.md)
  for plugin authors who want to send notifications through it.
- [Developer guide](https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin/blob/main/docs/DEVELOPER-GUIDE.md)
  for working on the plugin itself.

Licensed MIT. Source:
<https://github.com/PiratesIRC/Dispatcharr-Newsflasharr-Plugin>
