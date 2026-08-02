"""Xtream Codes (XC) API password helpers.

The XC password is a secret separate from a user's Dispatcharr login
password, used by IPTV client apps to authenticate against Dispatcharr's
own Xtream-Codes-compatible API. It lives at
``user.custom_properties["xc_password"]`` as a plain string (no separate
model/table exists for it in Dispatcharr core).
"""

import secrets


def generate(length=24):
    length = max(8, int(length or 24))
    return secrets.token_urlsafe(length)[:length]


def write_for_user(user, secret):
    user.custom_properties = {**(user.custom_properties or {}), "xc_password": secret}
    user.save(update_fields=["custom_properties"])
