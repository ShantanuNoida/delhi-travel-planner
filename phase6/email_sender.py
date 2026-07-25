"""
Sends the itinerary document by email — either via an n8n webhook (the
architecture doc's original webhook -> PDF -> email workflow, now actually
wired up) or plain SMTP as a fallback. delivery.py tries n8n first when
N8N_WEBHOOK_URL is configured, falling back to SMTP if that's unset or the
request fails, so a working SMTP setup is never wasted. Requires either
N8N_WEBHOOK_URL, or SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env; if neither
is configured, callers should fall back to saving the document locally
rather than failing hard.
"""

import base64
import os
import smtplib
import ssl
from email.message import EmailMessage

import requests

PDF_MIME = ("application", "pdf")


def send_email_via_n8n(
    to_email: str,
    subject: str,
    body: str,
    attachment_bytes: bytes,
    attachment_filename: str,
) -> dict:
    """
    Returns {"sent": bool, "reason": str}. reason is "" on success.

    Posts a JSON body (not multipart) -- the deployed workflow's "Convert
    to File" node reads the PDF from a base64 string field
    (body.pdf_base64), not a binary upload; confirmed against the real
    webhook (a multipart attempt failed with "The value in
    'body.pdf_base64' is not set" until the payload was switched to this
    shape). N8N_WEBHOOK_URL should be the Production URL (path
    "/webhook/...", not "/webhook-test/...") so it works whenever called,
    not just once after clicking "Listen for test event" in the editor.
    """
    webhook_url = (os.environ.get("N8N_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        return {"sent": False, "reason": "N8N_WEBHOOK_URL not configured"}

    payload = {
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "filename": attachment_filename,
        "pdf_base64": base64.b64encode(attachment_bytes).decode("ascii"),
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=30)
        if 200 <= resp.status_code < 300:
            return {"sent": True, "reason": ""}
        return {"sent": False, "reason": f"n8n webhook returned {resp.status_code}: {resp.text[:300]}"}
    except Exception as e:
        return {"sent": False, "reason": str(e)}


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
