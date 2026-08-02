import logging
import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_VENDOR_DIR = os.path.join(_PLUGIN_DIR, "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

import mailer  # noqa: E402
import scheduler  # noqa: E402
import sync_engine  # noqa: E402
from ldap_client import LDAPConnectionError  # noqa: E402

# All cross-file imports in this plugin are absolute top-level imports (not
# `from . import ...`), relying on the sys.path insertion above. This keeps a
# single canonical module instance per file across the whole plugin — mixing
# absolute and relative imports of the same file would create two separate
# module objects (and, critically, two distinct `LDAPConnectionError` class
# objects that would fail `isinstance`/`except` checks against each other).

LOGGER = logging.getLogger(__name__)

_PLUGIN_KEY = os.path.basename(_PLUGIN_DIR).replace(" ", "_").lower()
_AUTH_BACKEND_PATH = "_ldap_user_sync_durable.LDAPPassthroughBackend"


class Plugin:
    name = "LDAP User Sync"
    version = "1.0.0"
    description = (
        "Syncs Dispatcharr Admin/Streamer accounts from any standard LDAP "
        "directory based on group membership, provisions and emails a "
        "random Xtream Codes API password per user, and optionally enables "
        "live LDAP pass-through login."
    )
    author = "ModdingFriendly"

    fields = [
        {"id": "info_ldap_connection", "type": "info", "label": "LDAP Directory Connection"},
        {
            "id": "ldap_host",
            "type": "string",
            "label": "LDAP Host",
            "default": "",
            "help_text": "Hostname or IP of your LDAP server. Works with any standard LDAP "
            "directory (OpenLDAP, Active Directory, 389 Directory Server, Authentik's LDAP "
            "outpost, etc.) — no vendor-specific assumptions.",
        },
        {
            "id": "ldap_port",
            "type": "number",
            "label": "LDAP Port",
            "default": 389,
            "help_text": "Typically 389 (plain/STARTTLS) or 636 (implicit LDAPS).",
        },
        {
            "id": "ldap_encryption",
            "type": "select",
            "label": "Encryption",
            "default": "starttls",
            "options": [
                {"label": "None (not recommended)", "value": "plain"},
                {"label": "STARTTLS", "value": "starttls"},
                {"label": "LDAPS (implicit TLS)", "value": "ldaps"},
            ],
        },
        {
            "id": "ldap_ca_cert_pem",
            "type": "text",
            "label": "Custom CA Certificate (PEM)",
            "default": "",
            "help_text": "Optional. Paste a PEM-encoded CA certificate if your LDAP server "
            "uses a private/internal CA. Certificate verification is always enforced — use "
            "this instead of disabling it.",
        },
        {
            "id": "ldap_bind_dn",
            "type": "string",
            "label": "Bind DN",
            "default": "",
            "help_text": "Full DN of the service account used to search the directory, e.g. "
            "cn=svc-dispatcharr,ou=service-accounts,dc=example,dc=com.",
        },
        {
            "id": "ldap_bind_password",
            "type": "string",
            "label": "Bind Password",
            "default": "",
            "input_type": "password",
        },
        {
            "id": "ldap_base_dn",
            "type": "string",
            "label": "Base DN",
            "default": "",
            "help_text": "e.g. dc=example,dc=com. Used as the default user search base.",
        },
        {"id": "info_group_mapping", "type": "info", "label": "Group -> Role Mapping"},
        {
            "id": "ldap_admin_group_dn",
            "type": "string",
            "label": "Admin Group DN",
            "default": "",
            "help_text": "Members become Dispatcharr Admins (user_level=10).",
        },
        {
            "id": "ldap_streamer_group_dn",
            "type": "string",
            "label": "Streamer Group DN",
            "default": "",
            "help_text": "Members become Dispatcharr Streamers (user_level=0). Users in "
            "neither group are never created or touched.",
        },
        {
            "id": "ldap_group_member_attribute",
            "type": "string",
            "label": "Group Member Attribute",
            "default": "member",
            "help_text": "Use 'member' (groupOfNames, AD, Authentik) or 'uniqueMember' "
            "(groupOfUniqueNames).",
        },
        {
            "id": "ldap_group_member_is_username",
            "type": "boolean",
            "label": "Group lists usernames, not DNs",
            "default": False,
            "help_text": "Turn ON only for posixGroup-style directories where 'memberUid' "
            "stores raw usernames instead of full DNs (set the attribute above to memberUid).",
        },
        {"id": "info_user_attributes", "type": "info", "label": "User Attribute Mapping"},
        {"id": "ldap_username_attribute", "type": "string", "label": "Username Attribute", "default": "uid"},
        {"id": "ldap_email_attribute", "type": "string", "label": "Email Attribute", "default": "mail"},
        {
            "id": "ldap_first_name_attribute",
            "type": "string",
            "label": "First Name Attribute",
            "default": "givenName",
        },
        {"id": "ldap_last_name_attribute", "type": "string", "label": "Last Name Attribute", "default": "sn"},
        {"id": "info_sync_behavior", "type": "info", "label": "Sync Behavior"},
        {
            "id": "sync_interval_minutes",
            "type": "number",
            "label": "Sync Interval (minutes)",
            "default": 60,
            "help_text": "0 disables the automatic schedule — 'Sync Now' is always available "
            "regardless. Click 'Apply Schedule' after changing this.",
        },
        {
            "id": "disable_users_removed_from_groups",
            "type": "boolean",
            "label": "Disable users removed from groups",
            "default": True,
            "help_text": "When ON, a previously-synced user no longer in either LDAP group "
            "gets is_active=False on the next sync.",
        },
        {
            "id": "dry_run_mode",
            "type": "boolean",
            "label": "Dry Run Mode",
            "default": False,
            "help_text": "Log what would change without writing anything. Recommended the "
            "first time you point this at a real directory.",
        },
        {"id": "info_login_passthrough", "type": "info", "label": "LDAP Pass-Through Login (Advanced)"},
        {
            "id": "enable_ldap_passthrough_login",
            "type": "boolean",
            "label": "Enable LDAP pass-through login",
            "default": False,
            "help_text": "When ON, LDAP-synced users authenticate against a live LDAP bind at "
            "login time instead of a locally stored password, so their Dispatcharr login "
            "always matches their current LDAP password. See the plugin README for the full "
            "design and limitations (e.g. login requires LDAP to be reachable).",
        },
        {"id": "info_xc_password", "type": "info", "label": "Xtream Codes API Password"},
        {
            "id": "xc_password_length",
            "type": "number",
            "label": "XC Password Length",
            "default": 24,
        },
        {
            "id": "public_url",
            "type": "string",
            "label": "Public Dispatcharr/Xtream URL",
            "default": "",
            "help_text": "Optional. Included in the notification email.",
        },
        {
            "id": "reset_xc_password_for_username",
            "type": "string",
            "label": "Username to reset XC password for",
            "default": "",
            "help_text": "Fill this in, then click 'Reset XC Password' below.",
        },
        {"id": "info_smtp", "type": "info", "label": "SMTP Email Delivery"},
        {"id": "smtp_host", "type": "string", "label": "SMTP Host", "default": ""},
        {"id": "smtp_port", "type": "number", "label": "SMTP Port", "default": 587},
        {
            "id": "smtp_security",
            "type": "select",
            "label": "SMTP Security",
            "default": "starttls",
            "help_text": "Use 'None' only for a trusted internal relay with no TLS support "
            "(e.g. one only reachable from inside your own private network).",
            "options": [
                {"label": "STARTTLS", "value": "starttls"},
                {"label": "SSL/TLS", "value": "ssl"},
                {"label": "None (trusted internal relay only)", "value": "none"},
            ],
        },
        {"id": "smtp_username", "type": "string", "label": "SMTP Username", "default": ""},
        {
            "id": "smtp_password",
            "type": "string",
            "label": "SMTP Password",
            "default": "",
            "input_type": "password",
        },
        {
            "id": "smtp_from_email",
            "type": "string",
            "label": "From Address",
            "default": "",
            "help_text": "Optional. Falls back to SMTP Username.",
        },
        {
            "id": "test_email_recipient",
            "type": "string",
            "label": "Test Email Recipient",
            "default": "",
        },
    ]

    actions = [
        {
            "id": "test_ldap_connection",
            "label": "Test LDAP Connection",
            "description": "Bind and resolve both group DNs without changing anything",
            "button_label": "Test LDAP Connection",
            "button_variant": "outline",
            "button_color": "blue",
        },
        {
            "id": "sync_now",
            "label": "Sync Now",
            "description": "Run the full LDAP sync immediately",
            "button_label": "Sync Now",
            "button_variant": "filled",
            "button_color": "blue",
        },
        {
            "id": "test_smtp_connection",
            "label": "Test SMTP Connection",
            "description": "Verify SMTP login without sending a message",
            "button_label": "Test SMTP Connection",
            "button_variant": "outline",
        },
        {
            "id": "send_test_email",
            "label": "Send Test Email",
            "description": "Send a real test email to the address configured above",
            "button_label": "Send Test Email",
            "button_variant": "outline",
        },
        {
            "id": "reset_xc_password_for_username",
            "label": "Reset XC Password",
            "description": "Rotate and email a new Xtream Codes password for the username above",
            "button_label": "Reset XC Password",
            "button_variant": "filled",
            "button_color": "red",
            "confirm": {
                "title": "Reset XC password?",
                "message": "This immediately invalidates the current Xtream Codes password "
                "for this user and emails them a new one. Continue?",
            },
        },
        {
            "id": "apply_schedule",
            "label": "Apply Schedule",
            "description": "Restart the sync countdown using the current interval setting",
            "button_label": "Apply Schedule",
            "button_variant": "outline",
        },
        {
            "id": "scheduler_status",
            "label": "Scheduler Status",
            "description": "Report the next scheduled sync time",
            "button_label": "Scheduler Status",
            "button_variant": "outline",
        },
    ]

    def __init__(self):
        self._register_auth_backend()
        self._scheduler = scheduler.Scheduler(
            get_settings=self._current_settings, run_sync_fn=sync_engine.run_sync, logger=LOGGER
        )
        self._scheduler.start()

    def _register_auth_backend(self):
        from django.conf import settings as dj_settings

        if _AUTH_BACKEND_PATH not in dj_settings.AUTHENTICATION_BACKENDS:
            dj_settings.AUTHENTICATION_BACKENDS = list(dj_settings.AUTHENTICATION_BACKENDS) + [
                _AUTH_BACKEND_PATH
            ]

    def _current_settings(self):
        from apps.plugins.models import PluginConfig

        try:
            settings = dict(PluginConfig.objects.get(key=_PLUGIN_KEY).settings or {})
        except PluginConfig.DoesNotExist:
            settings = {}
        for field in self.fields:
            field_id = field.get("id")
            if field_id and field_id not in settings and "default" in field:
                settings[field_id] = field["default"]
        return settings

    # -- actions -------------------------------------------------------------

    def _test_ldap_connection(self, settings, logger):
        result = sync_engine.preview_groups(settings, logger)
        return {
            "status": "success",
            "message": (
                f"LDAP bind succeeded. {result['admins']} admin(s), "
                f"{result['streamers']} streamer(s) resolved, "
                f"{result['skipped_stale']} stale/unresolvable reference(s) skipped."
            ),
        }

    def _sync_now(self, settings, logger):
        summary = sync_engine.run_sync(settings, logger, dry_run=bool(settings.get("dry_run_mode")))
        lines = [
            f"created={summary['created']} updated={summary['updated']} "
            f"disabled={summary['disabled']} skipped_stale={summary['skipped_stale']}"
        ]
        lines.extend(summary["details"])
        if summary["errors"]:
            lines.append("Errors:")
            lines.extend(summary["errors"])
        return {"status": "success" if not summary["errors"] else "error", "message": "\n".join(lines)}

    def _test_smtp_connection(self, settings, logger):
        mailer.validate_smtp_connection(settings)
        return {"status": "success", "message": "SMTP login succeeded."}

    def _send_test_email(self, settings, logger):
        recipient = (settings.get("test_email_recipient") or "").strip()
        if not recipient:
            return {"status": "error", "message": "Set 'Test Email Recipient' first."}
        mailer.send_test_email(settings, recipient)
        return {"status": "success", "message": f"Test email sent to {recipient}."}

    def _reset_xc_password(self, settings, logger):
        username = (settings.get("reset_xc_password_for_username") or "").strip()
        if not username:
            return {"status": "error", "message": "Set 'Username to reset XC password for' first."}
        sync_engine.reset_xc_password_for_user(settings, username)
        return {"status": "success", "message": f"XC password reset and emailed for {username}."}

    def _apply_schedule(self, settings, logger):
        self._scheduler.request_reload()
        return {"status": "success", "message": "Schedule applied."}

    def _scheduler_status(self, settings, logger):
        import time

        next_run = self._scheduler.next_run_at()
        if not next_run:
            return {"status": "success", "message": "No sync currently scheduled (interval is 0 or none run yet)."}
        seconds = max(0, int(next_run - time.time()))
        return {"status": "success", "message": f"Next sync in ~{seconds} second(s)."}

    _ACTIONS = {
        "test_ldap_connection": _test_ldap_connection,
        "sync_now": _sync_now,
        "test_smtp_connection": _test_smtp_connection,
        "send_test_email": _send_test_email,
        "reset_xc_password_for_username": _reset_xc_password,
        "apply_schedule": _apply_schedule,
        "scheduler_status": _scheduler_status,
    }

    def run(self, action, params, context):
        settings = context.get("settings", {}) or {}
        logger = context.get("logger", LOGGER)
        handler = self._ACTIONS.get(action)
        if handler is None:
            return {"status": "error", "message": f"Unknown action: {action}"}
        try:
            return handler(self, settings, logger)
        except LDAPConnectionError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"LDAP User Sync: action '{action}' failed")
            return {"status": "error", "message": f"Error: {exc}"}

    def stop(self, context):
        self._scheduler.stop()
