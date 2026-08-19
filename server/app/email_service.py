import json
import logging
from urllib import error, request as urlrequest

from flask import current_app

logger = logging.getLogger(__name__)


def email_delivery_configured():
    return bool(current_app.config.get("RESEND_API_KEY") and current_app.config.get("EMAIL_FROM"))


def _send(to_email, subject, html, text):
    api_key = current_app.config.get("RESEND_API_KEY", "")
    sender = current_app.config.get("EMAIL_FROM", "")
    if not api_key or not sender:
        logger.warning("Transactional email is not configured; skipped email to %s", to_email)
        return False

    payload = json.dumps({
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }).encode("utf-8")
    req = urlrequest.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Ledgerly/1.0",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            return 200 <= response.status < 300
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        logger.exception("Unable to send Ledgerly transactional email: %s", exc)
        return False


def email_shell(title, body, action_label, action_url, footer):
    return f"""
    <div style="background:#f4f7fb;padding:32px 16px;font-family:Arial,sans-serif;color:#172033">
      <div style="max-width:560px;margin:auto;background:#ffffff;border:1px solid #d7dee8;border-radius:16px;padding:30px">
        <div style="display:inline-block;background:#2563eb;color:#ffffff;font-size:22px;font-weight:800;border-radius:10px;padding:8px 12px;margin-bottom:20px">L</div>
        <h1 style="font-size:26px;margin:0 0 8px;color:#172033">{title}</h1>
        <div style="font-size:15px;line-height:1.6;color:#526176">{body}</div>
        <p style="margin:28px 0"><a href="{action_url}" style="display:inline-block;background:#2563eb;color:#ffffff;padding:12px 18px;border-radius:9px;text-decoration:none;font-weight:700">{action_label}</a></p>
        <p style="font-size:12px;line-height:1.5;color:#7a8798;margin-top:26px">{footer}</p>
      </div>
    </div>
    """


def send_verification_email(to_email, verification_url):
    subject = "Verify your Ledgerly email"
    text = (
        "Welcome to Ledgerly. Verify your email address to activate your account:\n\n"
        f"{verification_url}\n\n"
        "This link expires in 24 hours. If you did not create this account, you can ignore this email."
    )
    html = email_shell(
        "Verify your email",
        "Welcome to Ledgerly. Confirm this email address to activate your account and start using your personal finance workspace.",
        "Verify email",
        verification_url,
        "This link expires in 24 hours. If you did not create this account, you can ignore this email.",
    )
    return _send(to_email, subject, html, text)


def send_password_reset_email(to_email, reset_url):
    subject = "Reset your Ledgerly password"
    text = (
        "A password reset was requested for your Ledgerly account. Use this link to choose a new password:\n\n"
        f"{reset_url}\n\n"
        "This link expires in one hour. If you did not request a reset, your password has not been changed."
    )
    html = email_shell(
        "Reset your password",
        "We received a request to reset the password for your Ledgerly account. Choose a new password using the secure link below.",
        "Reset password",
        reset_url,
        "This link expires in one hour. If you did not request a reset, your password has not been changed.",
    )
    return _send(to_email, subject, html, text)
