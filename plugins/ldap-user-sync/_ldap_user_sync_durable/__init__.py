"""Standalone home for `LDAPPassthroughBackend`, kept out of `plugin.py`.

`apps.plugins.loader.PluginManager._unload_package()` evicts every
`sys.modules` entry under the plugin's synthetic package name whenever
the plugin is disabled or force-reloaded. If this backend lived inside
`plugin.py` itself, Django's `AUTHENTICATION_BACKENDS` would hold a
dotted path that stops resolving the moment that happens, breaking the
very next login attempt that reaches it.

This package is deliberately independent: `plugin.py` inserts the
plugin's own folder (not just `vendor/`) onto `sys.path`, so this module
stays importable via normal filesystem lookup even after a
`sys.modules` eviction — a cache eviction just means Python re-imports a
fresh copy from disk instead of failing. It re-does its own `vendor/`
bootstrap below so it never depends on `plugin.py` having already run in
the current call stack.

The name is deliberately unique/underscore-prefixed to avoid colliding
with other plugins' same-named generic helper modules (several ship
their own `utils.py`/`config.py`) now that this plugin's own folder is
on `sys.path`.
"""

import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VENDOR_DIR = os.path.join(_PLUGIN_DIR, "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from ldap3.core.exceptions import LDAPException  # noqa: E402


def _current_settings():
    """Read the plugin's live persisted settings straight from PluginConfig.

    Deliberately independent of plugin.py's own settings helper for the
    same reload-durability reason described above.
    """
    from apps.plugins.models import PluginConfig

    plugin_key = os.path.basename(_PLUGIN_DIR).replace(" ", "_").lower()
    try:
        return PluginConfig.objects.get(key=plugin_key).settings or {}
    except PluginConfig.DoesNotExist:
        return {}


class LDAPPassthroughBackend:
    """Optional live LDAP bind-as-user authentication, opt-in per settings."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        from apps.accounts.models import User

        try:
            settings = _current_settings()
            if not settings.get("enable_ldap_passthrough_login"):
                return None

            user = User.objects.get(username=username, is_active=True)
            custom_properties = user.custom_properties or {}
            if not custom_properties.get("ldap_synced"):
                return None
            dn = custom_properties.get("ldap_dn")
            if not dn:
                return None

            # Import lazily so a broken vendor/import never breaks the
            # ModelBackend path for every other login attempt.
            from ldap_client import verify_user_credentials  # noqa: PLC0415

            if verify_user_credentials(settings, dn, password):
                return user
            return None
        except User.DoesNotExist:
            return None
        except LDAPException:
            return None
        except Exception:
            # A flaky/down directory or unexpected error must degrade to
            # "this backend says no", never to an unhandled 500 on login.
            return None

    def get_user(self, user_id):
        from apps.accounts.models import User

        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
