"""Send the digest email.

Free ways, picked with EMAIL_PROVIDER in .env:
- gmail_api (default): the Gmail API with a one-time browser sign-in
  (scripts/gmail_authorize.py). Works without app passwords.
- gmail: Gmail SMTP with a 16-letter app password (only if your Google
  account offers app passwords). GMAIL_SENDER can be a different Gmail
  account from MY_EMAIL — the digest is sent from GMAIL_SENDER to MY_EMAIL.
- brevo: Brevo's email API — free plan, 300 emails/day.
"""

import base64
import json
import os
import smtplib
from email.message import EmailMessage

import requests

from app.config import ROOT_DIR

SENDER_NAME = "AI News Digest"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_TOKEN_FILE = ROOT_DIR / "credentials" / "gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _build_message(sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{sender}>"
    msg["To"] = recipient
    msg.set_content(text_body)  # plain-text fallback
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_email(subject: str, html_body: str, text_body: str, to: str | None = None) -> None:
    my_email = os.getenv("MY_EMAIL", "").strip()
    if "@" not in my_email:
        raise RuntimeError("MY_EMAIL in .env must be the email address that receives the digest")
    sender = my_email
    recipient = to or my_email

    provider = os.getenv("EMAIL_PROVIDER", "gmail_api").strip().lower()
    senders = {"gmail_api": _send_gmail_api, "gmail": _send_gmail_smtp, "brevo": _send_brevo}
    if provider not in senders:
        raise RuntimeError(f"Unknown EMAIL_PROVIDER '{provider}' (use one of: {', '.join(senders)})")
    senders[provider](sender, recipient, subject, html_body, text_body)


# ---------- Gmail API (OAuth) ----------
def _gmail_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    # GMAIL_TOKEN_JSON lets a server (e.g. GitHub Actions) pass the token as a secret.
    token_json = os.getenv("GMAIL_TOKEN_JSON", "").strip()
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
    elif GMAIL_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), GMAIL_SCOPES)
    else:
        raise RuntimeError("No Gmail token yet — run: uv run python scripts/gmail_authorize.py")

    if not creds.valid:
        creds.refresh(Request())  # uses the saved refresh token; no browser needed
        if not token_json:
            GMAIL_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _send_gmail_api(sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> None:
    creds = _gmail_credentials()
    raw = base64.urlsafe_b64encode(_build_message(sender, recipient, subject, html_body, text_body).as_bytes())
    response = requests.post(
        GMAIL_SEND_URL,
        headers={"Authorization": f"Bearer {creds.token}"},
        json={"raw": raw.decode()},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gmail API rejected the email ({response.status_code}): {response.text[:300]}")


# ---------- Gmail SMTP (app password) ----------
def _send_gmail_smtp(sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> None:
    # The app password belongs to GMAIL_SENDER, which may differ from MY_EMAIL (the recipient).
    sender = os.getenv("GMAIL_SENDER", "").strip() or sender
    # Google shows app passwords as "abcd efgh ijkl mnop"; the spaces aren't part of it.
    password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not password:
        raise RuntimeError("GMAIL_APP_PASSWORD must be set in .env")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(_build_message(sender, recipient, subject, html_body, text_body))


# ---------- Brevo ----------
def _send_brevo(sender: str, recipient: str, subject: str, html_body: str, text_body: str) -> None:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY must be set in .env")
    response = requests.post(
        BREVO_URL,
        headers={"api-key": api_key, "accept": "application/json", "content-type": "application/json"},
        json={
            "sender": {"name": SENDER_NAME, "email": sender},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Brevo rejected the email ({response.status_code}): {response.text[:300]}")
