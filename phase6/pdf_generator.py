"""
Generates a PDF itinerary — the "PDF Generation" deliverable from the
architecture doc, now produced as an actual .pdf (previously .docx, kept
that way originally only because python-docx needed no extra setup on
Windows). reportlab is pure-Python (ships as a plain wheel, no system
libraries like LibreOffice/MS Word needed to render or convert anything),
which matters for running on Streamlit Community Cloud as well as locally
— see requirements.txt's note on avoiding exactly that class of dependency.
"""

import io
import re
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from citation_format import format_citation_label
from stop_format import format_display_name, format_opening_hours

DAY_SLOTS = (("Morning", "morning"), ("Afternoon", "afternoon"), ("Evening", "evening"))

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("ItinTitle", parent=_STYLES["Title"], alignment=TA_CENTER)
_META_STYLE = ParagraphStyle(
    "ItinMeta", parent=_STYLES["Normal"], alignment=TA_CENTER, fontName="Helvetica-Oblique"
)
_ITALIC_STYLE = ParagraphStyle("ItinItalic", parent=_STYLES["Normal"], fontName="Helvetica-Oblique")
_BULLET_STYLE = ParagraphStyle("ItinBullet", parent=_STYLES["Normal"], leftIndent=14, spaceAfter=4)

# reportlab's Standard-14 fonts (Helvetica etc.) only cover roughly the
# WinAnsi/Latin-1 range -- no glyph for the Rupee sign, which real KB entry
# fee text uses (delhi_tourist_venues_kb.md / pois.json both have it in
# ~20-30 places). Without this, the sign silently renders as a black box
# (■) IN THE ACTUAL PDF, not just a console-print artifact. Substituting
# ASCII "Rs. " is simpler and more portable than bundling a Unicode TTF
# font just for one currency symbol.
_UNSUPPORTED_GLYPHS = {"₹": "Rs. "}


def _esc(text: str) -> str:
    """escape(), but first swaps out characters the PDF's font can't
    render. Every raw text fragment in this module should go through this
    instead of calling escape() directly, so the fix applies everywhere
    uniformly rather than needing to be remembered at each call site."""
    for bad, good in _UNSUPPORTED_GLYPHS.items():
        text = text.replace(bad, good)
    return escape(text)


def _bold_markup(text: str) -> str:
    """Escapes `text` for reportlab's mini-markup, then re-applies **bold**
    spans as real <b> tags — same job as docx_generator's per-run bold, just
    expressed as inline markup instead of separate python-docx runs."""
    pos, out = 0, []
    for m in _BOLD_RE.finditer(text):
        if m.start() > pos:
            out.append(_esc(text[pos:m.start()]))
        out.append(f"<b>{_esc(m.group(1))}</b>")
        pos = m.end()
    out.append(_esc(text[pos:]))
    return "".join(out)


def _markdown_line_flowable(line: str):
    """
    Minimal Markdown->PDF-flowable line renderer for the trained narrator's
    output: '#'/'##'/'###' headings, '-'/'*' bullets, '**bold**' spans.
    Anything else becomes a plain paragraph. Not a general Markdown parser
    — just enough for the narrator's fixed output shape (mirrors
    docx_generator._add_markdown_line exactly, one flowable per line).
    """
    stripped = line.strip()
    if not stripped:
        return None

    heading_match = re.match(r"^(#{1,3})\s+(.*)", stripped)
    if heading_match:
        level = min(len(heading_match.group(1)) + 1, 4)  # narrative's "#"/"##" sit below the doc's own Day headings
        return Paragraph(_esc(heading_match.group(2)), _STYLES[f"Heading{level}"])

    is_bullet = stripped.startswith(("- ", "* "))
    text = stripped[2:].strip() if is_bullet else stripped
    markup = _bold_markup(text)
    if is_bullet:
        return Paragraph(f"• {markup}", _BULLET_STYLE)
    return Paragraph(markup, _STYLES["Normal"])


def build_itinerary_pdf(
    itinerary: dict,
    ctx: dict,
    citations: list[dict] | None = None,
    narrative: str | None = None,
) -> io.BytesIO:
    """Returns an in-memory .pdf file as a BytesIO stream."""
    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4)
    story = []

    story.append(Paragraph(_esc("New Delhi Travel Itinerary"), _TITLE_STYLE))

    meta_parts = [f"{ctx.get('num_days', '?')} days", f"{ctx.get('pace', 'moderate')} pace"]
    if ctx.get("interests"):
        meta_parts.append("Interests: " + ", ".join(ctx["interests"]))
    if ctx.get("group_size"):
        meta_parts.append(f"Group size: {ctx['group_size']}")
    story.append(Paragraph(_esc(" | ".join(meta_parts)), _META_STYLE))
    story.append(Spacer(1, 12))

    if narrative:
        for line in narrative.splitlines():
            flowable = _markdown_line_flowable(line)
            if flowable is not None:
                story.append(flowable)
        story.append(PageBreak())
        story.append(Paragraph(_esc("Precise Day-by-Day Schedule"), _STYLES["Heading1"]))
        story.append(Paragraph(
            _esc(
                "The grounded schedule below is the exact source data behind the overview "
                "above — real places, distances, and times from the trip planner's backend."
            ),
            _ITALIC_STYLE,
        ))

    day_keys = sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1]))
    for key in day_keys:
        day = itinerary[key]
        day_num = key.split("_")[1]
        heading_text = f"Day {day_num}"
        if day.get("date"):
            heading_text += f" — {day['date']}"
        story.append(Paragraph(_esc(heading_text), _STYLES["Heading1"]))
        story.append(Paragraph(_esc(f"Total scheduled time: {day.get('total_hours', 0)}h"), _STYLES["Normal"]))

        emergency_bits = []
        if day.get("nearest_hospital"):
            h = day["nearest_hospital"]
            emergency_bits.append(f"Nearest hospital: {format_display_name(h['name'])} ({h['distance_km']} km)")
        if day.get("nearest_pharmacy"):
            p = day["nearest_pharmacy"]
            emergency_bits.append(f"Nearest pharmacy: {format_display_name(p['name'])} ({p['distance_km']} km)")
        if day.get("nearest_metro_station"):
            m = day["nearest_metro_station"]
            emergency_bits.append(f"Nearest metro: {format_display_name(m['name'])} ({m['distance_km']} km)")
        if emergency_bits:
            story.append(Paragraph(_esc(" | ".join(emergency_bits)), _ITALIC_STYLE))

        for slot_label, slot_key in DAY_SLOTS:
            stops = day.get(slot_key, [])
            if not stops:
                continue
            story.append(Paragraph(_esc(slot_label), _STYLES["Heading2"]))
            for stop in stops:
                travel = stop.get("travel_time_from_prev_min", 0)
                mode = stop.get("travel_mode_from_prev")
                meal = stop.get("meal")
                hours = stop.get("opening_hours")
                website = stop.get("website")

                name_suffix = " (hidden gem)" if stop.get("is_hidden_gem") else ""
                category_suffix = f", {meal}" if meal else ""
                bold_part = f"{format_display_name(stop['name'])}{name_suffix} ({stop['category']}{category_suffix})"
                line = f"<b>{_esc(bold_part)}</b>"
                line += _esc(f" — visit ~{stop['visit_duration_min']} min")
                if travel:
                    mode_note = f" by {mode}" if mode else ""
                    line += _esc(f", {travel} min travel{mode_note} from previous stop")
                if hours and hours != "unknown":
                    line += _esc(f" — hours: {format_opening_hours(hours)}")
                if website:
                    line += _esc(f" — {website}")
                story.append(Paragraph(f"• {line}", _BULLET_STYLE))

                entry_fee = stop.get("kb_entry_fee")
                if entry_fee:
                    story.append(Paragraph(_esc(f"Entry fee: {entry_fee}"), _ITALIC_STYLE))

    if citations:
        story.append(Paragraph(_esc("Sources"), _STYLES["Heading1"]))
        for c in citations:
            line = _esc(f"{format_citation_label(c)} — {c.get('source_url', '')}")
            story.append(Paragraph(f"• {line}", _BULLET_STYLE))

    story.append(Paragraph(
        _esc(
            "Map & POI data © OpenStreetMap contributors, ODbL (openstreetmap.org/copyright). "
            "Landmark details enriched from Wikidata (CC0). Travel guidance from Wikivoyage (CC BY-SA 4.0)."
        ),
        _ITALIC_STYLE,
    ))

    doc.build(story)
    stream.seek(0)
    return stream
