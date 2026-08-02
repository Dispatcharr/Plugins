# LDAP User Sync

Syncs Dispatcharr user accounts from any standard LDAP directory (Active
Directory, OpenLDAP, 389 Directory Server, Authentik's LDAP outpost,
etc.) based on group membership.

## What it does

- Binds to your LDAP directory (on a schedule and/or on demand) and reads
  the members of two group DNs you configure: an **Admin** group and a
  **Streamer** group.
- Creates or updates the matching Dispatcharr users, setting `user_level`
  to Admin (`10`) or Streamer (`0`). Users in neither group are never
  created or touched.
- Generates a random **Xtream Codes (XC) API password** for every newly
  created user (the secret your IPTV client apps use — separate from the
  Dispatcharr login password) and emails it via plain SMTP. Existing
  users keep their XC password stable across future syncs; use the
  **Reset XC Password** action to rotate one on demand.
- Disables (`is_active=False`) any previously-synced user who drops out
  of both groups on a later sync (toggle-able).
- Optionally enables true **LDAP pass-through login**, so a user's
  Dispatcharr login password always matches their live LDAP password
  (see below for how this works and its limitations).

## LDAP pass-through login

We cannot read a user's plaintext LDAP password via a service-account
bind — no LDAP server exposes it. So the only way to make a Dispatcharr
login "match LDAP" is live pass-through authentication, not password
mirroring:

- LDAP-managed users get `set_unusable_password()` locally — their local
  Dispatcharr password is deterministically disabled.
- When **Enable LDAP pass-through login** is on, a custom Django
  authentication backend attempts a live SIMPLE bind against your LDAP
  server using the DN captured at the most recent sync and the password
  the user typed in. Django's standard `ModelBackend` is tried first, so
  non-LDAP accounts (e.g. a local break-glass admin) are unaffected.

**Accepted limitations, by design:**
- If your LDAP server is unreachable, LDAP-managed users cannot log in
  until it's back — there's no local fallback for them. To restore local
  login for one user in an emergency, clear their
  `custom_properties["ldap_synced"]`/`["ldap_dn"]` and call
  `set_password()` directly (Django shell / admin).
- Nested/recursive group membership is not expanded — a user must be a
  *direct* member of the configured group DN.
- If you fully uninstall this plugin, restart Dispatcharr afterward.
  Django's authentication backend list isn't designed to be mutated at
  runtime, so an already-running process keeps a reference to the
  now-removed backend module until it restarts (it fails safely, closed,
  in the meantime — it just won't clean itself up without a restart).

## Vendored dependencies

Dispatcharr plugins run inside the app's existing Python environment
with no dependency-installation step, and neither `ldap3` nor
`python-ldap` ships with Dispatcharr. This plugin vendors, unmodified,
as plain Python source under `vendor/`:

- [`ldap3`](https://pypi.org/project/ldap3/) 2.9.1 — LGPL-3.0-only.
  Full license text: `vendor/licenses/ldap3/`.
- [`pyasn1`](https://pypi.org/project/pyasn1/) 0.6.4 — BSD-2-Clause.
  Full license text: `vendor/licenses/pyasn1/LICENSE.rst`.

Both are pure Python with no compiled extensions. They are vendored as
clearly-separable, unmodified source trees with their original license
text preserved, satisfying LGPL's combination terms. This plugin's own
code is MIT-licensed; the vendored libraries keep their original
licenses regardless.

## Settings reference

See the in-app field descriptions (grouped into LDAP Connection, Group →
Role Mapping, User Attribute Mapping, Sync Behavior, Pass-Through Login,
XC Password, and SMTP sections). A couple worth calling out:

- **Group Member Attribute**: `member` works for `groupOfNames`-style
  groups (the common case, including AD and Authentik). Set it to
  `uniqueMember` for `groupOfUniqueNames`, or turn on **Group lists
  usernames, not DNs** and set it to `memberUid` for `posixGroup`-style
  directories.
- **Dry Run Mode**: turn this on for your first sync against a real
  directory — it logs exactly what would be created/updated/disabled
  without writing anything.
