"""Reconciliation logic: LDAP groups -> Dispatcharr `User` rows.

Two configurable LDAP group DNs map to Dispatcharr's `user_level`
(Admin=10, Streamer=0). Users in neither group are never touched. A
user who drops out of both groups on a later sync gets `is_active=False`
(configurable). XC passwords are generated once on creation and never
silently rotated afterward.
"""

from apps.accounts.models import User

import ldap_client
import mailer
import xc_password


def _resolve_group(conn, settings, group_dn, level):
    is_username = bool(settings.get("ldap_group_member_is_username"))
    raw_members = ldap_client.resolve_group_members(conn, settings, group_dn)
    resolved = []
    stale = 0
    for raw in raw_members:
        rec = (
            ldap_client.fetch_user_by_username(conn, settings, raw)
            if is_username
            else ldap_client.fetch_user_by_dn(conn, raw, settings)
        )
        if rec is None or not rec.get("username"):
            stale += 1
            continue
        resolved.append({**rec, "level": level})
    return resolved, stale


def _build_matched_users(conn, settings, logger):
    admin_records, admin_stale = _resolve_group(
        conn, settings, (settings.get("ldap_admin_group_dn") or "").strip(), 10
    )
    streamer_records, streamer_stale = _resolve_group(
        conn, settings, (settings.get("ldap_streamer_group_dn") or "").strip(), 0
    )

    matched = {}
    for rec in admin_records:
        matched[rec["username"]] = rec
    for rec in streamer_records:
        if rec["username"] in matched:
            logger.warning(
                "LDAP User Sync: %s is a member of both groups, admin takes precedence",
                rec["username"],
            )
            continue
        matched[rec["username"]] = rec

    return matched, admin_stale + streamer_stale


def _apply_create_or_update(username, rec, settings, dry_run, summary):
    exists = User.objects.filter(username=username).exists()

    if dry_run:
        summary["details"].append(
            f"{'would update' if exists else 'would create'} {username} (level={rec['level']})"
        )
        summary["created" if not exists else "updated"] += 1
        return

    user, created = User.objects.get_or_create(username=username)

    if created:
        user.user_level = rec["level"]
        user.email = rec["email"]
        user.first_name = rec["first_name"]
        user.last_name = rec["last_name"]
        user.set_unusable_password()
        secret = xc_password.generate(settings.get("xc_password_length"))
        user.custom_properties = {
            "ldap_synced": True,
            "ldap_dn": rec["dn"],
            "xc_password": secret,
        }
        user.save()
        summary["created"] += 1
        summary["details"].append(f"created {username} (level={rec['level']})")

        if rec["email"]:
            try:
                mailer.send_xc_password_email(settings, rec["email"], username, secret)
            except Exception as exc:  # noqa: BLE001 - report, never crash the sync
                summary["errors"].append(f"email to {username} failed: {exc}")
        else:
            summary["errors"].append(f"{username} has no email attribute - XC password not emailed")
        return

    changed = False
    if user.user_level != rec["level"]:
        user.user_level = rec["level"]
        changed = True
    if rec["email"] and user.email != rec["email"]:
        user.email = rec["email"]
        changed = True
    if rec["first_name"] and user.first_name != rec["first_name"]:
        user.first_name = rec["first_name"]
        changed = True
    if rec["last_name"] and user.last_name != rec["last_name"]:
        user.last_name = rec["last_name"]
        changed = True

    custom_properties = dict(user.custom_properties or {})
    if custom_properties.get("ldap_dn") != rec["dn"]:
        custom_properties["ldap_dn"] = rec["dn"]
        changed = True
    if not custom_properties.get("ldap_synced"):
        custom_properties["ldap_synced"] = True
        changed = True
    if not user.is_active:
        user.is_active = True
        changed = True

    if changed:
        user.custom_properties = custom_properties
        user.save()
        summary["updated"] += 1
        summary["details"].append(f"updated {username} (level={rec['level']})")


def _apply_disable_pass(matched, settings, dry_run, summary):
    if not settings.get("disable_users_removed_from_groups", True):
        return
    ldap_managed = User.objects.filter(custom_properties__ldap_synced=True)
    for user in ldap_managed:
        if user.username in matched or not user.is_active:
            continue
        if dry_run:
            summary["details"].append(f"would disable {user.username}")
            summary["disabled"] += 1
            continue
        user.is_active = False
        user.save(update_fields=["is_active"])
        summary["disabled"] += 1
        summary["details"].append(f"disabled {user.username}")


def run_sync(settings, logger, dry_run=False):
    summary = {
        "created": 0,
        "updated": 0,
        "disabled": 0,
        "skipped_stale": 0,
        "errors": [],
        "details": [],
    }

    conn = ldap_client.connect_service_account(settings)
    try:
        matched, stale = _build_matched_users(conn, settings, logger)
    finally:
        conn.unbind()
    summary["skipped_stale"] = stale

    for username, rec in matched.items():
        try:
            _apply_create_or_update(username, rec, settings, dry_run, summary)
        except Exception as exc:  # noqa: BLE001 - isolate one bad record from the rest
            summary["errors"].append(f"{username}: {exc}")

    _apply_disable_pass(matched, settings, dry_run, summary)

    return summary


def preview_groups(settings, logger):
    """Read-only counts for the 'Test LDAP Connection' action. Writes nothing."""
    conn = ldap_client.connect_service_account(settings)
    try:
        matched, stale = _build_matched_users(conn, settings, logger)
    finally:
        conn.unbind()
    admins = sum(1 for rec in matched.values() if rec["level"] == 10)
    streamers = sum(1 for rec in matched.values() if rec["level"] == 0)
    return {"admins": admins, "streamers": streamers, "skipped_stale": stale}


def reset_xc_password_for_user(settings, username):
    username = (username or "").strip()
    if not username:
        raise ValueError("No username given")
    user = User.objects.get(username=username)
    secret = xc_password.generate(settings.get("xc_password_length"))
    xc_password.write_for_user(user, secret)
    if user.email:
        mailer.send_xc_password_email(settings, user.email, username, secret)
    else:
        raise ValueError(f"{username} has no email address on file - password rotated but not emailed")
    return secret
