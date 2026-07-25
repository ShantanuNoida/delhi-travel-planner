"""
Sends the itinerary document by email via plain SMTP — the local Python
equivalent of the n8n webhook -> PDF -> email workflow from the architecture
doc. Requires SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env; if unset, callers
should fall back to saving the document locally rather than failing hard.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

PDF_MIME = ("application", "pdf")


def send_email_with_attachment(
    to_email: str,
    subject: str,
    body: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> dict:
    """Returns {"sent": bool, "reason": str}. reason is "" on success."""
    # .strip() on each: a copy-pasted app password picked up a stray
    # leading space in practice (Gmail displays it space-grouped, e.g.
    # "abcd efgh ijkl mnop", and it's easy to grab a leading/trailing space
    # along with it) -- SMTP AUTH takes the credential literally, so an
    # unstripped stray space silently turns a correct password into a
    # wrong one instead of erroring in an obvious way.
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    sender = (os.environ.get("SMTP_FROM") or user).strip()
    port = int((os.environ.get("SMTP_PORT") or "587").strip())

    if not (host and user and password):
        return {"sent": False, "reason": "SMTP not configured — set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    maintype, subtype = PDF_MIME
    msg.add_attachment(attachment_bytes, maintype=maintype, subtype=subtype, filename=attachment_filename)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
        return {"sent": True, "reason": ""}
    except Exception as e:
        return {"sent": False, "reason": str(e)}
