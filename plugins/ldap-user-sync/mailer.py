"""Plain-SMTP email delivery for the LDAP User Sync plugin.

Dispatcharr core has no outbound email support of its own (no
``EMAIL_*`` settings, no ``django.core.mail`` usage anywhere in the app),
so this follows the same stdlib ``smtplib``/``ssl``/``email.mime``
pattern already established by the merged ``m3u-expiration-notifier``
plugin, reading every credential from plugin settings (never hardcoded)
and always verifying certificates via ``ssl.create_default_context()``.
The HTML email template below mirrors that plugin's layout/styling
(same brand bar, accent stripe, and detail-row table) for a consistent
look across Dispatcharr plugin notification emails.
"""

import smtplib
import ssl
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as html_escape

LOGO_PATH = "/app/frontend/dist/logo.png"
BRAND_DARK = "#1a1b1e"
ACCENT = "#2f9e44"

_LOGO_CACHE = {"loaded": False, "bytes": None}


def _load_logo_bytes():
    if not _LOGO_CACHE["loaded"]:
        try:
            with open(LOGO_PATH, "rb") as fh:
                _LOGO_CACHE["bytes"] = fh.read()
        except OSError:
            _LOGO_CACHE["bytes"] = None
        _LOGO_CACHE["loaded"] = True
    return _LOGO_CACHE["bytes"]


def resolve_smtp_params(settings):
    host = (settings.get("smtp_host") or "").strip()
    if not host:
        raise ValueError("SMTP host is not configured")
    try:
        port = int(settings.get("smtp_port") or 587)
    except (TypeError, ValueError):
        port = 587
    security = settings.get("smtp_security") or "starttls"
    username = (settings.get("smtp_username") or "").strip()
    password = settings.get("smtp_password") or ""
    from_addr = (settings.get("smtp_from_email") or username or "").strip()
    if not from_addr:
        raise ValueError("No From address available (set SMTP Username or From Address)")
    return {
        "host": host,
        "port": port,
        "security": security,
        "username": username,
        "password": password,
        "from_addr": from_addr,
    }


def _render_email_html(heading, status_label, accent_color, message_html, detail_rows):
    logo_bytes = _load_logo_bytes()
    if logo_bytes:
        brand_html = (
            '<img src="cid:dispatcharr-logo" alt="Dispatcharr" height="28" '
            'style="display:block;border:0;outline:none;text-decoration:none;">'
        )
    else:
        brand_html = (
            '<span style="font-size:18px;font-weight:700;color:#ffffff;'
            'letter-spacing:0.5px;">DISPATCHARR</span>'
        )

    rows_html = "".join(
        f'''<tr>
              <td style="padding:8px 0;border-top:1px solid #e9ecef;color:#868e96;
                         font-size:13px;width:150px;vertical-align:top;">{html_escape(label)}</td>
              <td style="padding:8px 0;border-top:1px solid #e9ecef;color:#1a1b1e;
                         font-size:14px;font-weight:600;vertical-align:top;{extra_style}">{value_html}</td>
            </tr>'''
        for label, value_html, extra_style in detail_rows
    )

    return f'''<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f1f3f5;
               font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color:#f1f3f5;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="600" cellpadding="0" cellspacing="0"
                 style="background-color:#ffffff;border-radius:8px;overflow:hidden;
                        box-shadow:0 1px 3px rgba(0,0,0,0.12);">
            <tr>
              <td style="background-color:{BRAND_DARK};padding:18px 32px;">{brand_html}</td>
            </tr>
            <tr>
              <td style="height:4px;line-height:4px;font-size:0;background-color:{accent_color};">&nbsp;</td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h1 style="margin:0 0 6px 0;font-size:21px;color:#1a1b1e;">{html_escape(heading)}</h1>
                <p style="margin:0 0 20px 0;font-size:12px;font-weight:700;letter-spacing:0.6px;
                          text-transform:uppercase;color:{accent_color};">{html_escape(status_label)}</p>
                <p style="margin:0 0 24px 0;font-size:14px;line-height:1.6;color:#495057;">{message_html}</p>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;background-color:#f8f9fa;border-top:1px solid #e9ecef;">
                <p style="margin:0;font-size:12px;color:#adb5bd;">
                  Sent by the LDAP User Sync plugin for Dispatcharr.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>'''


def _render_email_text(heading, status_label, message_text, detail_rows):
    lines = [f"{heading} - {status_label}", ""]
    lines.append(message_text)
    lines.append("")
    for label, value_html, _extra_style in detail_rows:
        lines.append(f"{label}: {value_html}")
    lines.append("")
    lines.append("Sent by the LDAP User Sync plugin for Dispatcharr.")
    return "\n".join(lines)


def build_message(subject, from_addr, recipients, html_body, text_body):
    msg_root = MIMEMultipart("related")
    msg_root["Subject"] = subject
    msg_root["From"] = from_addr
    msg_root["To"] = ", ".join(recipients)

    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(text_body, "plain", "utf-8"))
    msg_alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg_root.attach(msg_alt)

    logo_bytes = _load_logo_bytes()
    if logo_bytes:
        img = MIMEImage(logo_bytes, _subtype="png")
        img.add_header("Content-ID", "<dispatcharr-logo>")
        img.add_header("Content-Disposition", "inline")
        msg_root.attach(img)

    return msg_root


def deliver_message(params, recipients, msg=None):
    """Connect, authenticate, and optionally send `msg`. Pass msg=None to just test the login."""
    if not recipients:
        raise ValueError("No recipient email address given")

    if params["security"] == "ssl":
        server = smtplib.SMTP_SSL(
            params["host"], params["port"], timeout=30, context=ssl.create_default_context()
        )
    else:
        server = smtplib.SMTP(params["host"], params["port"], timeout=30)

    with server:
        if params["security"] == "starttls":
            # Deliberately hard-fails if the server doesn't advertise STARTTLS
            # rather than silently falling back to plaintext - that fallback
            # is exactly the STARTTLS-stripping downgrade an attacker on-path
            # would try to induce. Use "none" explicitly for servers that
            # genuinely never support TLS (e.g. a trusted internal relay).
            server.starttls(context=ssl.create_default_context())
        if params["username"]:
            server.login(params["username"], params["password"])
        if msg is not None:
            server.sendmail(params["from_addr"], recipients, msg.as_string())


def send_xc_password_email(settings, recipient, username, xc_password):
    params = resolve_smtp_params(settings)
    public_url = (settings.get("public_url") or "").strip()

    message_text = "Your Dispatcharr Xtream Codes API password has been set."
    message_html = (
        "Use these credentials in your IPTV client app - this is separate "
        "from your Dispatcharr login password."
    )
    detail_rows = [
        ("Username", html_escape(username), ""),
        (
            "XC Password",
            html_escape(xc_password),
            "font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;",
        ),
    ]

    text_lines = [message_text, "", f"Username: {username}", f"XC Password: {xc_password}"]
    if public_url:
        message_html += f' Point your IPTV client app at <a href="{html_escape(public_url)}" style="color:{ACCENT};">{html_escape(public_url)}</a>.'
        text_lines += ["", f"Point your IPTV client app at: {public_url}"]

    html_body = _render_email_html(
        heading="Your Xtream Codes password is ready",
        status_label="Account Provisioned",
        accent_color=ACCENT,
        message_html=message_html,
        detail_rows=detail_rows,
    )
    text_body = _render_email_text(
        heading="Your Xtream Codes password is ready",
        status_label="Account Provisioned",
        message_text="\n".join(text_lines),
        detail_rows=[],
    )

    msg = build_message(
        subject="[Dispatcharr] Your Xtream Codes API password",
        from_addr=params["from_addr"],
        recipients=[recipient],
        html_body=html_body,
        text_body=text_body,
    )
    deliver_message(params, [recipient], msg)


def send_test_email(settings, recipient):
    params = resolve_smtp_params(settings)
    html_body = _render_email_html(
        heading="Test email",
        status_label="LDAP User Sync",
        accent_color=ACCENT,
        message_html="This is a test email from the LDAP User Sync plugin's SMTP settings. "
        "If you can read this, delivery is working.",
        detail_rows=[],
    )
    text_body = _render_email_text(
        heading="Test email",
        status_label="LDAP User Sync",
        message_text="This is a test email from the LDAP User Sync plugin's SMTP settings.",
        detail_rows=[],
    )
    msg = build_message(
        subject="[Dispatcharr] LDAP User Sync test email",
        from_addr=params["from_addr"],
        recipients=[recipient],
        html_body=html_body,
        text_body=text_body,
    )
    deliver_message(params, [recipient], msg)


def validate_smtp_connection(settings):
    params = resolve_smtp_params(settings)
    deliver_message(params, [params["from_addr"]], msg=None)
