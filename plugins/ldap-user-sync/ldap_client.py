"""Generic LDAP directory access for the LDAP User Sync plugin.

Uses the vendored ``ldap3``/``pyasn1`` (see ``vendor/``) since Dispatcharr
plugins run inside the app's existing Python environment with no
dependency-installation step, and neither library ships with Dispatcharr.

Deliberately vendor-agnostic: no assumptions about Active Directory,
OpenLDAP, or any specific product (including Authentik's LDAP outpost,
which this plugin was developed and tested against, but never hardcodes
to).
"""

import os
import re
import ssl
import sys

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_VENDOR_DIR = os.path.join(_PLUGIN_DIR, "vendor")
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)

import ldap3  # noqa: E402
from ldap3 import ALL, BASE, SIMPLE, SUBTREE, Connection, Server, Tls  # noqa: E402
from ldap3.core.exceptions import LDAPException  # noqa: E402

_USERNAME_RE = re.compile(r"[^\w.@+-]")


class LDAPConnectionError(Exception):
    """Raised for any LDAP connect/bind/search failure, wrapping the underlying cause."""


def sanitize_username(raw):
    """Reduce an LDAP attribute value to Django's allowed username charset."""
    value = (raw or "").strip()
    return _USERNAME_RE.sub("_", value)


def _build_server(settings):
    host = (settings.get("ldap_host") or "").strip()
    if not host:
        raise LDAPConnectionError("LDAP host is not configured")
    try:
        port = int(settings.get("ldap_port") or 389)
    except (TypeError, ValueError):
        port = 389
    encryption = settings.get("ldap_encryption") or "starttls"

    tls = None
    if encryption in ("starttls", "ldaps"):
        ca_pem = (settings.get("ldap_ca_cert_pem") or "").strip() or None
        # Deliberately leave `version` unset (None): ldap3's Tls.wrap_socket()
        # only calls Python's own ssl.create_default_context() - which
        # enforces a TLS 1.2+ floor - when version is None. Passing an
        # explicit version (e.g. PROTOCOL_TLS_CLIENT) makes it fall through
        # to a manual SSLContext(self.version) path with no such floor,
        # which is what CodeQL's py/insecure-protocol flags.
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_data=ca_pem,
        )

    return Server(
        host,
        port=port,
        use_ssl=(encryption == "ldaps"),
        tls=tls,
        get_info=ALL,
        connect_timeout=10,
    ), encryption


def connect_service_account(settings):
    """Bind as the configured service account. Raises LDAPConnectionError on any failure."""
    server, encryption = _build_server(settings)
    bind_dn = (settings.get("ldap_bind_dn") or "").strip()
    bind_password = settings.get("ldap_bind_password") or ""

    try:
        conn = Connection(
            server,
            user=bind_dn or None,
            password=bind_password or None,
            authentication=SIMPLE if bind_dn else None,
            auto_bind=False,
            receive_timeout=10,
        )
        if encryption == "starttls":
            if not conn.open() or not conn.start_tls():
                raise LDAPConnectionError(f"STARTTLS negotiation failed: {conn.result}")
        if not conn.bind():
            raise LDAPConnectionError(f"LDAP bind failed: {conn.result}")
    except LDAPException as exc:
        raise LDAPConnectionError(f"LDAP connection error: {exc}") from exc

    return conn


def verify_user_credentials(settings, dn, password):
    """Attempt a SIMPLE bind as `dn`/`password` on a fresh connection. Never raises."""
    if not dn or not password:
        return False
    try:
        server, encryption = _build_server(settings)
        conn = Connection(
            server,
            user=dn,
            password=password,
            authentication=SIMPLE,
            auto_bind=False,
            receive_timeout=10,
        )
        if encryption == "starttls":
            if not conn.open() or not conn.start_tls():
                return False
        return bool(conn.bind())
    except Exception:
        return False


def resolve_group_members(conn, settings, group_dn):
    """Return the raw list of member values (DNs, or usernames) for a group entry."""
    if not group_dn:
        return []
    member_attr = settings.get("ldap_group_member_attribute") or "member"
    ok = conn.search(
        search_base=group_dn,
        search_filter="(objectClass=*)",
        search_scope=BASE,
        attributes=[member_attr],
    )
    if not ok or not conn.entries:
        return []
    entry = conn.entries[0]
    if member_attr not in entry:
        return []
    values = entry[member_attr].values
    return [str(v) for v in values]


def fetch_user_by_dn(conn, dn, settings):
    """Look up a single user entry by DN. Returns a normalized dict or None if stale."""
    attrs = [
        settings.get("ldap_username_attribute") or "uid",
        settings.get("ldap_email_attribute") or "mail",
        settings.get("ldap_first_name_attribute") or "givenName",
        settings.get("ldap_last_name_attribute") or "sn",
    ]
    ok = conn.search(search_base=dn, search_filter="(objectClass=*)", search_scope=BASE, attributes=attrs)
    if not ok or not conn.entries:
        return None
    return _normalize_entry(conn.entries[0], dn, settings)


def fetch_user_by_username(conn, settings, username):
    """Look up a single user entry by username attribute under the base DN."""
    base_dn = (settings.get("ldap_base_dn") or "").strip()
    username_attr = settings.get("ldap_username_attribute") or "uid"
    attrs = [
        username_attr,
        settings.get("ldap_email_attribute") or "mail",
        settings.get("ldap_first_name_attribute") or "givenName",
        settings.get("ldap_last_name_attribute") or "sn",
    ]
    escaped = ldap3.utils.conv.escape_filter_chars(username)
    ok = conn.search(
        search_base=base_dn,
        search_filter=f"({username_attr}={escaped})",
        search_scope=SUBTREE,
        attributes=attrs,
    )
    if not ok or not conn.entries:
        return None
    entry = conn.entries[0]
    return _normalize_entry(entry, str(entry.entry_dn), settings)


def _first(entry, attr):
    if attr not in entry:
        return ""
    values = entry[attr].values
    return str(values[0]) if values else ""


def _normalize_entry(entry, dn, settings):
    return {
        "dn": dn,
        "username": sanitize_username(_first(entry, settings.get("ldap_username_attribute") or "uid")),
        "email": _first(entry, settings.get("ldap_email_attribute") or "mail"),
        "first_name": _first(entry, settings.get("ldap_first_name_attribute") or "givenName"),
        "last_name": _first(entry, settings.get("ldap_last_name_attribute") or "sn"),
    }
