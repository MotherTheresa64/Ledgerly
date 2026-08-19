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


def send_verification_email(to_email, verification_url):
    subject = "Verify your Ledgerly email"
    text = (
        "Welcome to Ledgerly. Verify your email address to activate your account:\n\n"
        f"{verification_url}\n\n"
        "This link expires in 24 hours. If you did not create this account, you can ignore this email."
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#162019">
      <h1 style="color:#16a34a">Ledgerly</h1>
      <h2>Verify your email</h2>
      <p>Welcome to Ledgerly. Confirm this email address to activate your account.</p>
      <p style="margin:28px 0"><a href="{verification_url}" style="background:#22c55e;color:#061008;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700">Verify email</a></p>
      <p style="font-size:13px;color:#65736a">This link expires in 24 hours. If you did not create this account, you can ignore this email.</p>
    </div>
    """
    return _send(to_email, subject, html, text)


def send_password_reset_email(to_email, reset_url):
    subject = "Reset your Ledgerly password"
    text = (
        "A password reset was requested for your Ledgerly account. Use this link to choose a new password:\n\n"
        f"{reset_url}\n\n"
        "This link expires in one hour. If you did not request a reset, your password has not been changed."
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#162019">
      <h1 style="color:#16a34a">Ledgerly</h1>
      <h2>Reset your password</h2>
      <p>We received a request to reset the password for your Ledgerly account.</p>
      <p style="margin:28px 0"><a href="{reset_url}" style="background:#22c55e;color:#061008;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:700">Reset password</a></p>
      <p style="font-size:13px;color:#65736a">This link expires in one hour. If you did not request a reset, your password has not been changed.</p>
    </div>
    """
    return _send(to_email, subject, html, text)
