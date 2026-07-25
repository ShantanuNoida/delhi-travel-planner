"""
Orchestrates itinerary delivery: itinerary JSON -> .pdf -> email.
Always saves a local copy of the document; email is best-effort and falls
back gracefully (with a clear reason) when SMTP isn't configured.
"""

import os
import re
from datetime import datetime

from pdf_generator import build_itinerary_pdf
from email_sender import send_email_with_attachment

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def deliver_itinerary(
    itinerary: dict,
    ctx: dict,
    email: str,
    citations: list[dict] | None = None,
    narrative: str | None = None,
) -> dict:
    """
    Returns {"emailed": bool, "message": str, "file_path": str, "file_bytes": bytes | None}.
    file_path/file_bytes are set whenever the document was generated (even if
    the email itself couldn't be sent), so the caller can still offer a
    manual download. narrative, if given, is the trained narrator's full
    TRIP OVERVIEW / DAY-BY-DAY / ... Markdown text, rendered as a leading
    section ahead of the precise structured day-by-day breakdown.
    """
    if not is_valid_email(email):
        return {"emailed": False, "message": "That doesn't look like a valid email address.", "file_path": "", "file_bytes": None}

    doc_stream = build_itinerary_pdf(itinerary, ctx, citations, narrative)
    doc_bytes = doc_stream.getvalue()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"delhi_itinerary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    file_path = os.path.join(OUTPUT_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(doc_bytes)

    result = send_email_with_attachment(
        to_email=email,
        subject="Your New Delhi Itinerary",
        body="Attached is your day-wise New Delhi travel itinerary. Enjoy your trip!",
        attachment_bytes=doc_bytes,
        attachment_filename=filename,
    )

    if result["sent"]:
        message = f"Your itinerary has been sent to {email}."
    else:
        # result["reason"] is developer-facing (e.g. "SMTP not configured — set
        # SMTP_HOST..." or a raw smtplib exception) — log it, but never show it
        # to a traveler (QA-4/R-5).
        print(f"  [delivery] email send failed: {result['reason']}")
        message = f"We couldn't email it right now, but your itinerary is saved — download it below ({filename})."

    return {"emailed": result["sent"], "message": message, "file_path": file_path, "file_bytes": doc_bytes}
