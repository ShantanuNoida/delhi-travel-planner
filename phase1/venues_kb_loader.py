"""
Loader for delhi_tourist_venues_kb.md — a hand-curated, structured knowledge
base of the 50 most popular New Delhi/NCR tourist venues (project root).

Unlike Overpass/Wikidata (live APIs) this is a static local file, but it's
treated the same way every other source in this project is: parsed into
records, never fabricated beyond what's written, and every "approx."/
"Verify locally" hedge in the source is preserved rather than smoothed over.

Two outputs, feeding the two places every other source feeds:
  - parse_venues()      -> structured records for POI *enrichment*
                            (phase1/venues_kb_enrich.py), same role Wikidata plays.
  - venues_to_articles() -> scraper.py-shaped article dicts for the *RAG
                            corpus* (chunked/embedded alongside Wikivoyage/
                            Wikipedia), so explain() can cite this source too.

The file has no coordinates for its venues, so it can only enrich POIs that
already exist (real OSM lat/lon) — never used to invent a new schedulable
stop.
"""

import os
import re

KB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "delhi_tourist_venues_kb.md")
SOURCE_NAME = "delhi_tourist_venues_kb"

# KB's 7 broad categories -> compatible OSM categories, for the enrichment
# match gate (phase1/venues_kb_enrich.py). Intentionally coarse — several KB
# venues (zoos, amusement parks, IHC) have no compatible OSM category here
# and simply won't be enrichable, which is correct: better an honest miss
# than a wrong match.
KB_CATEGORY_TO_OSM = {
    "religious": {"temple", "mosque", "church", "gurdwara"},
    "museum": {"museum"},
    "historical": {"monument"},
    "cultural": {"market", "monument", "museum"},
    "food": {"restaurant", "market"},
    "park/garden": {"park"},
    "family/entertainment": {"park", "museum"},
}

_VENUE_HEADER_RE = re.compile(r"^### (\d+)\.\s+(.+?)\s*$", re.MULTILINE)
_FIELD_RE_TEMPLATE = r"^- \*\*{label}:\*\*\s*(.*?)(?=\n- \*\*|\n---|\n## |\Z)"

_DURATION_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(hour|hr|minute|min)s?", re.IGNORECASE)


def _extract_field(block: str, label: str) -> str:
    m = re.search(_FIELD_RE_TEMPLATE.format(label=re.escape(label)), block, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_duration_to_minutes(text: str) -> int | None:
    """
    '3–5 hours' -> 240 (midpoint). Best-effort only: extracts every
    (number, unit) pair found and returns the midpoint of the min/max in
    minutes. Returns None if nothing parseable — callers must not assume
    a value is always available.
    """
    matches = _DURATION_UNIT_RE.findall(text)
    if not matches:
        return None
    minutes = []
    for value, unit in matches:
        mins = float(value) * (60 if unit.lower().startswith(("hour", "hr")) else 1)
        minutes.append(mins)
    return round((min(minutes) + max(minutes)) / 2)


def _primary_category(raw: str) -> str:
    """'Religious (secondary: cultural, family/entertainment)' -> 'religious'."""
    return raw.split("(")[0].strip().lower()


def _split_list(text: str) -> list[str]:
    return [t.strip() for t in text.split(",") if t.strip()]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_venues(path: str = KB_PATH) -> list[dict]:
    """Parses every '### N. Venue Name' entry into a structured record."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        text = f.read()

    headers = list(_VENUE_HEADER_RE.finditer(text))
    venues = []
    for i, m in enumerate(headers):
        number, name = int(m.group(1)), m.group(2).strip()
        block_start = m.end()
        block_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[block_start:block_end]

        category_raw = _extract_field(block, "Category")
        duration_text = _extract_field(block, "Recommended Visit Duration")

        venues.append({
            "number": number,
            "name": name,
            "category_raw": category_raw,
            "category": _primary_category(category_raw),
            "tags": _split_list(_extract_field(block, "Tags")),
            "why_famous": _extract_field(block, "Why It Is Famous"),
            "timings": _extract_field(block, "Timings"),
            "entry_fee": _extract_field(block, "Entry Fee"),
            "visit_duration_text": duration_text,
            "visit_duration_min": _parse_duration_to_minutes(duration_text),
            "best_time_to_visit": _extract_field(block, "Best Time to Visit"),
            "how_to_reach": _extract_field(block, "How to Reach"),
            "suitable_for": _split_list(_extract_field(block, "Suitable For")),
            "nearby_attractions": _extract_field(block, "Nearby Attractions"),
        })
    return venues


def venue_to_article_text(venue: dict) -> str:
    """Reconstructs venue fields into one prose blob, suitable for the same
    sentence-aware chunker used on scraped Wikivoyage/Wikipedia text."""
    parts = [venue["why_famous"]]
    if venue["timings"]:
        parts.append(f"Timings: {venue['timings']}")
    if venue["entry_fee"]:
        parts.append(f"Entry fee: {venue['entry_fee']}")
    if venue["visit_duration_text"]:
        parts.append(f"Recommended visit duration: {venue['visit_duration_text']}")
    if venue["best_time_to_visit"]:
        parts.append(f"Best time to visit: {venue['best_time_to_visit']}")
    how_to_reach = re.sub(r"\s*\n\s*", " ", venue["how_to_reach"])
    how_to_reach = re.sub(r"-\s*\*\*(.*?):\*\*", r"\1:", how_to_reach)  # drop nested "- **Label:**" markdown
    if how_to_reach:
        parts.append(f"How to reach: {how_to_reach}")
    return " ".join(p.strip() for p in parts if p.strip())


def venues_to_articles(venues: list[dict], last_modified: str) -> list[dict]:
    """Converts venues into scraper.py-shaped article dicts for the existing
    chunk() -> embed() RAG pipeline. One article per venue (not per section)
    so citations stay precise to the actual place being explained."""
    return [
        {
            "source": SOURCE_NAME,
            "title": v["name"],
            "url": f"local-kb://{SOURCE_NAME}#{_slug(v['name'])}",
            "text": venue_to_article_text(v),
            "last_modified": last_modified,
        }
        for v in venues
        if v["why_famous"]  # skip anything that failed to parse a body
    ]


def run() -> list[dict]:
    venues = parse_venues()
    print(f"Parsed {len(venues)} venues from {os.path.basename(KB_PATH)}.")
    return venues


if __name__ == "__main__":
    run()
