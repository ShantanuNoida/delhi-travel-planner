"""
Enriches the Phase 1 POI dataset with delhi_tourist_venues_kb.md (project
root) — a hand-curated knowledge base of the 50 most popular New Delhi/NCR
tourist venues with real entry fees, recommended visit durations, best
visiting times, and audience notes.

Same enrichment-only contract as wikidata_client.py: only adds fields to
POIs that already exist (real OSM lat/lon); never invents a new schedulable
stop, since the KB itself carries no coordinates.

Matching is fuzzy (unlike Wikidata's exact-name+distance match) because KB
venue names don't always match OSM's exact spelling — e.g. the KB's
"Shankar's International Dolls Museum" vs OSM's "Shanker's International
Doll Museum", the very pair R-11 had to de-duplicate. Two gates, both
required, mirroring R-11's multi-gate design: normalized-name similarity
AND category-family compatibility. Neither alone is safe — name similarity
alone would cross-match unrelated venues that happen to share words (e.g.
"Red Fort" vs some other "Fort"); category alone would match arbitrary
same-category POIs regardless of name.
"""

import difflib
import json
import os
import re

from venues_kb_loader import KB_CATEGORY_TO_OSM, parse_venues

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POIS_PATH = os.path.join(DATA_DIR, "pois.json")

# Empirically calibrated against the real dataset (see venues_kb_enrich
# design notes / QA-6-style verification): below ~0.90, character-similarity
# alone starts confusing genuinely different same-category venues that share
# common words — e.g. "National Museum" vs "National Gandhi Museum" scores
# 0.81, "Agrasen ki Baoli" vs the unrelated "Gandhak Ki Baoli" scores 0.69.
# A missed enrichment costs nothing (that POI just doesn't get bonus KB
# data); a wrong one silently attributes a real entry fee/duration to the
# wrong physical place, which is worse than not enriching it at all — so
# this threshold is deliberately tuned for precision over recall.

# R-5 (Itinerary-Quality-Review-and-Recommendations.md): a handful of real
# matches fail the fuzzy check above not because they're actually ambiguous,
# but because one side's name is a strict superset of the other's (KB's
# full official name vs OSM's short common name, or vice versa) — e.g.
# "Swaminarayan Akshardham Temple" (KB) vs OSM's plain "Akshardham" scores
# only ~0.49, well below threshold, so Akshardham silently fell back to the
# flat "temple" category default (45 min) instead of its real 3-5 hour
# recommended duration — a scheduling-accuracy bug, not a labeling one.
# A generic "is one name contained in the other" heuristic was tried and
# rejected: it also matched generic single words like "Temple"/"Dargah"
# across unrelated venues (any POI literally named "Temple" would match
# every religious KB entry). Each pair below was individually confirmed by
# reading both the KB entry and the real OSM record — not a loosened
# threshold, an explicit verified list, same precision-over-recall
# discipline as NAME_SIMILARITY_THRESHOLD itself.
KB_NAME_OVERRIDES: dict[str, str] = {
    "Akshardham": "Swaminarayan Akshardham Temple",
    "India Gate": "India Gate & Kartavya Path",
    "Jantar Mantar Astronomical Observatory, Delhi": "Jantar Mantar",
    "National Rail Museum of India": "National Rail Museum",
    # R-35 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
    # Popularity Gap", 2026-07-16): same "one side's name is a superset of
    # the other's" pattern as the four above, individually confirmed by
    # reading both sides — "Janpath & Tibetan Market" (KB) is the real
    # informal market strip OSM records as "Janpath New Mini Market";
    # "Paranthe Wali Gali" (KB, the famous paranthe-shop lane) has no single
    # OSM record for the street itself, but one of its actual paranthe shops
    # is in the data under its full registered name.
    "Janpath New Mini Market": "Janpath & Tibetan Market",
    "Pandit Kanhaiya Lal Durga Prashad Dixit Paranthe Wala": "Paranthe Wali Gali",
}
NAME_SIMILARITY_THRESHOLD = 0.90


def _normalize_for_match(name: str) -> str:
    name = name.lower()
    name = re.sub(r"['’]s\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _candidate_names(venue_name: str) -> list[str]:
    """
    Many KB venue names carry a '(Alternate Name)' or ', Location' suffix
    that dilutes straight string similarity even for an exact real match
    — e.g. "Red Fort (Lal Qila)" vs OSM's plain "Red Fort" scores only
    0.64 on the full string, but 1.00 on the pre-parenthesis core. Try the
    full name, the part before the first '(' or ',', and any parenthetical
    content (sometimes THAT is the name OSM actually uses, e.g. ISKCON's
    "(Sri Sri Radha Parthasarathi Mandir)") — take whichever scores best.
    """
    names = [venue_name]
    core = re.split(r"[(,]", venue_name)[0].strip()
    if core and core != venue_name:
        names.append(core)
    for m in re.finditer(r"\(([^)]+)\)", venue_name):
        inner = re.split(r"[,;]", m.group(1))[0].strip()
        if inner:
            names.append(inner)
    return names


def _best_match(venue: dict, pois: list[dict]) -> dict | None:
    compatible_categories = KB_CATEGORY_TO_OSM.get(venue["category"], set())
    if not compatible_categories:
        return None
    candidates = [p for p in pois if p["category"] in compatible_categories]
    if not candidates:
        return None

    for poi_name, kb_name in KB_NAME_OVERRIDES.items():
        if venue["name"] == kb_name:
            override = next((p for p in candidates if p["name"] == poi_name), None)
            if override is not None:
                return override

    venue_norms = [_normalize_for_match(n) for n in _candidate_names(venue["name"])]
    best, best_score = None, 0.0
    for poi in candidates:
        poi_norm = _normalize_for_match(poi["name"])
        score = max(difflib.SequenceMatcher(None, vn, poi_norm).ratio() for vn in venue_norms)
        if score > best_score:
            best, best_score = poi, score
    return best if best_score >= NAME_SIMILARITY_THRESHOLD else None


def enrich_pois_with_venues_kb(pois: list[dict], venues: list[dict] | None = None) -> tuple[list[dict], int]:
    """
    Adds kb_entry_fee/kb_visit_duration_min/kb_best_time_to_visit/
    kb_suitable_for/kb_why_famous to POIs with a confident fuzzy-name +
    category match. Returns (enriched_pois, match_count). Never removes or
    invents a POI — the KB has no coordinates, so it can only enrich what
    OSM already found.
    """
    if venues is None:
        venues = parse_venues()
    if not venues:
        return pois, 0

    match_count = 0
    for venue in venues:
        match = _best_match(venue, pois)
        if match is None:
            continue
        if venue["entry_fee"]:
            match["kb_entry_fee"] = venue["entry_fee"]
        if venue["visit_duration_min"]:
            match["kb_visit_duration_min"] = venue["visit_duration_min"]
        if venue["best_time_to_visit"]:
            match["kb_best_time_to_visit"] = venue["best_time_to_visit"]
        if venue["suitable_for"]:
            match["kb_suitable_for"] = venue["suitable_for"]
        # Live-usage report ("why is this venue included" should give a
        # 3-4 line importance/popularity answer): the KB's own "Why It Is
        # Famous" prose was already parsed (venues_kb_loader.py) and chunked
        # into the RAG corpus, but never attached directly to the matching
        # POI record the way kb_entry_fee etc. are -- so a "why" question
        # depended on RAG retrieval luck instead of this reliable, already-
        # curated ground truth. Mirrors the existing kb_* fields exactly.
        if venue["why_famous"]:
            match["kb_why_famous"] = venue["why_famous"]
        match["kb_matched"] = True
        match_count += 1

    return pois, match_count


def run() -> list[dict]:
    """Loads pois.json, enriches in place, and saves it back."""
    if not os.path.exists(POIS_PATH):
        print(f"  [warn] {POIS_PATH} not found — run Overpass fetch first.")
        return []

    with open(POIS_PATH, encoding="utf-8") as f:
        pois = json.load(f)

    venues = parse_venues()
    print(f"Loaded {len(venues)} venues from delhi_tourist_venues_kb.md.")

    pois, match_count = enrich_pois_with_venues_kb(pois, venues)
    print(f"  Matched {match_count}/{len(venues)} KB venues to existing POIs "
          f"(entry fee/visit duration/best time where available).")

    with open(POIS_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"  Saved enriched dataset -> {POIS_PATH}")
    return pois


if __name__ == "__main__":
    run()
