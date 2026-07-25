"""
Tool 1: POI Search MCP
Loads the Phase 1 POI dataset and returns ranked POIs matching user interests.

Edge cases handled:
  EC-2.1 — niche interests fall back to general POIs with a fallback flag
  EC-2.4 — POIs closed on travel dates are filtered out
  EC-2.5 — warns if daily budget too short for even one stop
"""

import difflib
import json
import math
import os
import re
import unicodedata
from mcp.server.fastmcp import FastMCP
from schemas import POI_SEARCH_INPUT

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

PHASE1_DATA = os.path.join(
    os.path.dirname(__file__), "..", "phase1", "data", "pois.json"
)

# Maps user interest strings → POI categories from the OSM dataset
INTEREST_MAP: dict[str, list[str]] = {
    "food":               ["restaurant", "market"],
    "cuisine":            ["restaurant"],
    "eating":             ["restaurant"],
    # Team Waypoint recheck (2026-07-22): real repro -- "Add a nice place to
    # eat in Day 1" fell through to GENERAL_FALLBACK_CATEGORIES because
    # "eat" (the verb form) had no INTEREST_MAP entry of its own, only
    # "eating" did. Same class of gap H2 already fixed for "temple"/"mosque"
    # etc. -- a common, everyday phrasing that just hadn't been probed yet.
    "eat":                ["restaurant"],
    "dining":             ["restaurant"],
    "culture":            ["museum", "monument", "temple", "mosque", "church", "gurdwara"],
    "history":            ["monument", "museum"],
    "heritage":           ["monument", "museum", "temple", "mosque"],
    "architecture":       ["monument", "museum", "temple", "mosque", "church"],
    "religion":           ["temple", "mosque", "church", "gurdwara"],
    "spirituality":       ["temple", "mosque", "church", "gurdwara"],
    "nature":             ["park"],
    "outdoors":           ["park"],
    "relaxation":         ["park"],
    "shopping":           ["market"],
    "markets":            ["market"],
    "nightlife":          ["market", "restaurant"],
    "photography":        ["monument", "market", "park"],
    "street photography": ["market", "monument"],
    "graffiti":           ["park", "market"],
    "art":                ["museum", "park"],
    "family":             ["park", "museum", "monument"],
    "kids":               ["park", "museum"],
    # R-9 (Itinerary-Quality-Review-and-Recommendations.md F-10): the edit
    # engine passes "indoor"/"outdoor" straight through as a constraint
    # string when the user asks for an indoor/outdoor swap. Before these
    # keys existed, that string had no INTEREST_MAP entry, so it silently
    # fell through to GENERAL_FALLBACK_CATEGORIES — a mix that includes
    # outdoor categories (park, market) — which is exactly how an "indoor"
    # swap request returned Dilli Haat, an open-air craft bazaar. museum is
    # the one category that's unambiguously indoor; park/market/monument
    # are the open-air categories an indoor request should exclude.
    "indoor":             ["museum"],
    "outdoor":            ["park", "market", "monument"],
    # R-16 (Itinerary-Quality-Review-and-Recommendations.md F-11): a swap/add
    # constraint that names a specific category noun ("a temple", "a
    # mosque") used to have no INTEREST_MAP entry of its own — "temple" only
    # existed as an ELEMENT of religion/spirituality/culture/etc.'s mapped
    # list, never as a key — so it fell through to GENERAL_FALLBACK_CATEGORIES
    # and silently returned an unrelated monument/museum/park/market. Real
    # repro: "swap for a temple" returned Humayun's Tomb. These are literally
    # this dataset's own OSM category names, so mapping each singular noun
    # directly to itself (or, for "garden", to its closest real category)
    # closes the whole class of uncovered category-noun constraints, not just
    # this one word — same fix shape as the indoor/outdoor keys above.
    "temple":             ["temple"],
    "mosque":             ["mosque"],
    "church":             ["church"],
    "gurdwara":           ["gurdwara"],
    "monument":           ["monument"],
    "museum":             ["museum"],
    "restaurant":         ["restaurant"],
    "market":             ["market"],
    "garden":             ["park"],
    "park":               ["park"],
}

# R-7 (Itinerary-Quality-Review-and-Recommendations.md F-7): some interests
# above resolve to a real, non-empty category list, so EC-2.1's is_fallback
# flag never fires for them — but the mapped categories don't actually
# represent what the interest asks for. "nightlife" -> market/restaurant is
# the review's example: the dataset has no bars/clubs/late-night-venue
# category at all, so a "nightlife" request silently comes back as a
# daytime mall-and-lunch crawl (everything scheduled 9am-9pm) with no
# indication anything was substituted. Distinct from is_fallback, which
# only catches a totally unmatched interest — this catches a matched-but-
# not-actually-honored one. Keyed by the exact user-facing caveat to show,
# so the honest alternative is defined once, at the source of the gap.
WEAK_COVERAGE_INTERESTS: dict[str, str] = {
    "nightlife": (
        "I don't have verified nightlife venues (bars, clubs, live-music "
        "spots) for New Delhi — here's an evening food-and-markets plan instead."
    ),
}

# R-40 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
# Popularity Gap", 2026-07-16): same honesty principle as
# WEAK_COVERAGE_INTERESTS above, but for a SPECIFIC named place rather than
# a whole interest — a user asking by name (via an edit like "add Connaught
# Place") for a real, well-known place this dataset genuinely has no usable
# record of. Each name below was individually confirmed absent (a name
# search against phase1/data/pois.json returns zero schedulable records
# under it) before being listed here — same verify-before-list discipline
# as HIGH_PROFILE/POPULAR_FOOD_NATURE_SHOPPING, just for the negative case.
# Keyed by the SAME _normalize_landmark_name() used for the allowlists, so
# "connaught place", "Connaught Place (Rajiv Chowk)", etc. all match.
# Consumed by phase4/edit_engine.py's _apply_add()/_apply_swap(): checked
# BEFORE running a real search, so a genuinely-absent named request gets
# this honest message instead of poi_search_logic() silently falling back
# to an unrelated generic POI (EC-2.1's fallback has no idea the user asked
# for something specific by name — it just sees an unmatched interest
# string and returns whatever general-category filler is available).
KNOWN_ABSENT_POPULAR_PLACES: dict[str, str] = {
    "connaught place": (
        "I don't have a real, mappable record of Connaught Place in my data "
        "(it's absent from the OpenStreetMap extract this planner uses) — "
        "I can't honestly add it. Khan Market or Janpath are real, verified "
        "alternatives nearby if you'd like one of those instead."
    ),
    "sarojini nagar": (
        "I only have Sarojini Nagar as a metro station in my data, not a "
        "mappable market listing — I can't honestly add \"Sarojini Nagar "
        "Market\" as a stop. Lajpat Nagar Central Market is a real, verified "
        "alternative if you'd like that instead."
    ),
    "ina market": (
        "I don't have a real, mappable record of INA Market in my data — "
        "I can't honestly add it. Dilli Haat (right next to INA) or Lajpat "
        "Nagar Central Market are real, verified alternatives nearby."
    ),
    "select citywalk": (
        "I don't have a real, mappable record of Select Citywalk in my "
        "data — I can't honestly add it. Khan Market is a real, verified "
        "alternative if you're looking for a shopping stop."
    ),
}

# Default visit duration in minutes per category
VISIT_DURATION: dict[str, int] = {
    "monument":  90,
    "museum":    120,
    "restaurant": 75,
    "park":       60,
    "market":     90,
    "temple":     45,
    "mosque":     45,
    "church":     30,
    "gurdwara":   45,
}

# Well-known Delhi POIs that get a relevance boost. This tier is DECISIVE,
# not a nudge — see _relevance_score(). Before that fix, a landmark with no
# OSM opening_hours tag (Red Fort/Qutub Minar/Humayun's Tomb/India Gate/
# Purana Qila all have opening_hours="unknown" in the real dataset) scored
# BELOW a same-category non-icon that merely had hours filled in (Dilli
# Haat, Lotus Temple), so round-robin's per-category slot cap could crowd
# every true icon out of a multi-interest trip — verified: zero icons
# across 10 diverse real builds (Itinerary-Quality-Review-and-
# Recommendations.md, F-1/R-1).
HIGH_PROFILE = {
    "red fort", "qutab minar", "qutub minar", "humayun's tomb",
    "india gate", "lotus temple", "jama masjid", "chandni chowk",
    "connaught place", "national museum", "khan market",
    "hauz khas", "akshardham", "raj ghat", "jantar mantar",
    "safdarjung's tomb", "dilli haat", "purana qila",
}

# R-37 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
# Popularity Gap", 2026-07-16): these four are Delhi's most iconic
# shopping/food destinations, but OSM tags every one of them
# category="monument" (verified against phase1/data/pois.json), so the
# plain category filter in poi_search_logic() excludes them before scoring
# even runs whenever the user specifically asks for "food" or "shopping" —
# they're only ever reachable today via history/heritage/culture interests.
# Rather than re-tag the dataset itself (risking whatever legitimately
# depends on their real "monument" category — history/heritage/architecture
# interests correctly DO want them filed that way), a small, explicit,
# real-data-grounded cross-category admission list: each entry's ordering
# and category set is taken directly from delhi_tourist_venues_kb.md's own
# "Category: X (secondary: Y, Z)" field, not guessed — e.g. Khan Market is
# literally "Cultural (secondary: food, shopping)" in the KB, Chandni Chowk
# Food Street is "Food (secondary: cultural, historical)". Listed
# shopping-primary before food-primary or vice versa to match that.
CROSS_CATEGORY_POPULAR: dict[str, tuple[str, ...]] = {
    "khan market":      ("market", "restaurant"),  # KB: Cultural (secondary: food, shopping)
    "dilli haat":       ("market", "restaurant"),  # KB: Cultural (secondary: food, shopping)
    "connaught place":  ("market", "restaurant"),  # KB: Cultural (secondary: shopping, food)
    "chandni chowk":    ("restaurant", "market"),  # KB: Food (secondary: cultural, historical)
}

# R-36 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
# Popularity Gap", 2026-07-16): HIGH_PROFILE above is monument-centric —
# restaurant/market/park had zero popularity signal at all in the real data
# (measured: 0/1,080 restaurants, 0/232 markets, and only 2/1,205 parks in
# any boosted tier — and those 2 "park" hits are Raj Ghat and Safdarjung's
# Tomb, memorial-monuments dual-tagged park, not real green space). Every
# name below was individually confirmed to exist in phase1/data/pois.json
# under this exact category before being added — same verify-before-list
# discipline as HIGH_PROFILE itself, not a guess. (The old "lodi garden"
# entry above is gone, not just left dead — it never matched the dataset's
# real "Lodhi Gardens" even under the old exact-string check; the correct
# spelling now lives here instead, alongside the normalized matching below
# so a small future spelling/punctuation drift like this can't silently
# break the boost again.)
POPULAR_FOOD_NATURE_SHOPPING = {
    # restaurants
    "karim's", "bukhara", "indian accent",
    # parks/gardens
    "lodhi gardens", "the garden of five senses", "deer park",
    "nehru park", "sunder nursery", "saket district park",
    "buddha jayanti park",
    # markets
    "lajpat nagar central market", "janpath new mini market",
    "janpath old mini market",
}

# Delhi's single most iconic, must-see landmarks — a tier above the general
# HIGH_PROFILE set. Three are UNESCO World Heritage Sites; India Gate is the
# national war memorial. Real-world Delhi travel guidance treats these as
# the non-negotiable core of any history/monument-relevant trip. A single
# flat HIGH_PROFILE tier turned out not to be enough: with every named
# landmark tied at the same score, general-interest entries like Dilli Haat
# (a craft market) or Chandni Chowk (a bazaar) could still out-rank these
# five on nothing but incidental OSM data-completeness or dataset order —
# verified this happening even after making HIGH_PROFILE itself decisive
# (Itinerary-Quality-Review-and-Recommendations.md, F-1/R-1).
MUST_SEE = {
    "red fort", "qutab minar", "qutub minar", "humayun's tomb",
    "india gate", "purana qila",
}

# Four clean, non-overlapping score bands — MUST_SEE always outranks
# HIGH_PROFILE(+POPULAR_FOOD_NATURE_SHOPPING), which always outranks a
# KB-matched POI, which always outranks an ordinary POI. An opening_hours
# tag only breaks ties WITHIN a band; it can never let a lower band outrank
# a higher one, which was the actual bug (icons with opening_hours="unknown"
# losing to same-tier or lower-tier POIs that merely had the tag filled in).
MUST_SEE_SCORE_FLOOR = 0.95
LANDMARK_SCORE_FLOOR = 0.8
LANDMARK_SCORE_CAP = 0.9
# R-35/R-38 (Itinerary-Coverage-Gap-Analysis.md, 2026-07-16): a new band for
# POIs with a REAL, verifiable-but-not-hand-curated notability signal —
# either a matched delhi_tourist_venues_kb.md entry (R-35;
# phase1/venues_kb_enrich.py sets kb_matched=True) or a confidently-matched
# Wikidata article (R-38; phase1/wikidata_client.py sets wikidata_qid,
# extended to also query park/garden/marketplace/bazaar types — previously
# only landmarks/monuments were queried at all) — but aren't also on the
# hand-picked POPULAR_FOOD_NATURE_SHOPPING/HIGH_PROFILE allowlist above.
# Deliberately kept BELOW LANDMARK_SCORE_FLOOR (0.8), not merged into it:
# itinerary_builder.py treats relevance_score >= 0.8 as eviction-protected
# and routes it first as a "real landmark" — appropriate for the small,
# individually-verified allowlist above, but this band exists precisely to
# scale beyond hand-curation to every future KB/Wikidata match, most of
# which won't get that same individual scrutiny. "Near the landmark band"
# (as scoped) rather than inside it. Both signals share one band rather
# than getting a fifth: KB-match and Wikidata-article are the same
# *strength* of claim — "a real, independent, non-fabricated source
# vouches for this place" — just from two different sources.
NOTABLE_MATCH_SCORE_FLOOR = 0.75
NOTABLE_MATCH_SCORE_CAP = 0.79
# Venue-Tourist-Importance-Scoring-Plan.md, Phase A: phase1/overpass_client.py
# already fetches and stores tourism=attraction/museum and historic=* OSM
# tags on every POI (delhi-additional-data-sources.md), but _relevance_score()
# never read them until now -- verified against the real dataset, 8.5% of the
# 3,593 itinerary-recommendable POIs had ANY differentiating signal at all,
# with every park and the vast majority of temples/restaurants/markets
# scoring identically in the flat band below. This is a real, independent,
# community-verified signal (a real person tagged this specific place as a
# tourist attraction or historic site in OpenStreetMap) -- weaker than a
# hand-curated KB match or a confirmed Wikidata article (still handled by
# NOTABLE_MATCH above), but a real signal all the same, so it gets its own
# band strictly BELOW NOTABLE_MATCH_SCORE_FLOOR (0.75) and ABOVE
# NON_LANDMARK_SCORE_CAP (0.7) -- purely additive: it can only lift a POI
# that was previously in the flat, undifferentiated "ordinary" tail, and it
# stays well under LANDMARK_RELEVANCE_FLOOR (0.8, itinerary_builder.py /
# edit_engine.py), so it never becomes eviction-protected the way a real
# hand-curated landmark is.
OSM_TAGGED_SCORE_FLOOR = 0.71
OSM_TAGGED_SCORE_CAP = 0.74
NON_LANDMARK_SCORE_CAP = 0.7

# How many top-ranked landmarks per matched category are guaranteed a slot
# in the final candidate pool, even if round-robin's even per-category split
# would otherwise crowd one out (e.g. many HIGH_PROFILE monuments competing
# for a handful of monument-category round-robin slots once several
# interests are combined). Bounded so a landmark-heavy category can't
# swallow the whole top_n and starve the user's other stated interests.
# 6 covers all 5 real "monument"-category MUST_SEE records in the current
# dataset (confirmed against phase1/data/pois.json) with one slot to spare,
# while still leaving the rest of a 20-POI pool for other HIGH_PROFILE
# entries and the user's other stated interests.
GUARANTEED_LANDMARKS_PER_CATEGORY = 6

GENERAL_FALLBACK_CATEGORIES = ["monument", "museum", "park", "market"]

# Pace → available hours per day
PACE_HOURS = {"relaxed": 6.0, "moderate": 8.0, "intensive": 10.0}


# Live-usage report ("swapping a place with another is not working well"):
# real repro found while investigating -- two genuine OSM records in this
# dataset carry non-place-name "names" (a park literally named "ME   ♡𓆝",
# decorative symbols + an Egyptian hieroglyph -- an upstream OSM tagging
# artifact, not a scraping bug), and got surfaced as real swap/add
# recommendations, directly undermining the app's "cited, never invented"
# credibility. Filters at the single load-time choke point every search
# path (poi_search_logic, search_poi_by_name, the itinerary builder's own
# candidate pool) shares, so the fix applies everywhere uniformly.
# Deliberately conservative: rejects a name only when it contains an
# astral-plane character (code point >= 0x10000 -- emoji, hieroglyphs, and
# other decorative symbol blocks all live there; every script actually used
# for real Delhi place names -- Latin, Devanagari, Perso-Arabic -- is
# entirely within the Basic Multilingual Plane) or has fewer than 3 real
# letters once whitespace and Symbol-category characters are stripped out.
# Never rejects a name merely for using a non-Latin script.
def _is_presentable_name(name: str) -> bool:
    if not name:
        return False
    if any(ord(c) >= 0x10000 for c in name):
        return False
    real_chars = [c for c in name if not c.isspace() and unicodedata.category(c) != "So"]
    return len(real_chars) >= 3


def _load_pois() -> list[dict]:
    if not os.path.exists(PHASE1_DATA):
        raise FileNotFoundError(
            f"POI dataset not found at {PHASE1_DATA}. Run Phase 1 first."
        )
    with open(PHASE1_DATA, encoding="utf-8") as f:
        all_pois = json.load(f)
    return [p for p in all_pois if _is_presentable_name(p.get("name", ""))]


# R-41 (Itinerary edit commands QA, finding H2, 2026-07-17): the edit
# engine passes the intent classifier's extracted constraint through close
# to verbatim (the classifier's own prompt examples are noun phrases like
# "one famous local food place"), so a themed add/swap constraint routinely
# arrives as "history spot", "religion stop", "famous local food place"
# rather than a bare INTEREST_MAP key. An exact-key lookup alone sent every
# one of these to GENERAL_FALLBACK_CATEGORIES (is_fallback=True), which the
# edit engine's own anti-hallucination guard then filters out entirely --
# measured in a real 300-command QA run: 100% (60/60) of "add" edits and
# 100% (20/20) of themed "swap" edits silently failed this way. Falls back
# to scanning the phrase's individual words for a known INTEREST_MAP key
# (almost every real key is a single word) before giving up on it --
# same fix shape as edit_engine.py's indoor/outdoor synonym normalization,
# generalized past that one pair.
def _resolve_interest_key(interest: str) -> str:
    key = interest.lower().strip()
    if key in INTEREST_MAP:
        return key
    for word in re.findall(r"[a-z]+", key):
        if word in INTEREST_MAP:
            return word
    return key


def _resolve_categories(interests: list[str]) -> tuple[set[str], bool]:
    """
    Returns (matched_categories, is_fallback).
    is_fallback=True when no interest maps to a known category (EC-2.1).
    """
    cats: set[str] = set()
    for interest in interests:
        mapped = INTEREST_MAP.get(_resolve_interest_key(interest), [])
        cats.update(mapped)
    if not cats:
        return set(GENERAL_FALLBACK_CATEGORIES), True
    return cats, False


def _category_weights(interests: list[str], matched_cats: set[str]) -> dict[str, float]:
    """
    R-8 (Itinerary-Quality-Review-and-Recommendations.md F-8): how central
    each matched category is to what the user actually asked for. A category
    that's one of only two mapped for a focused interest ("history" ->
    monument, museum) is far more central than one that's a minor entry
    among six for a broad interest ("culture" -> museum/monument/temple/
    mosque/church/gurdwara) — flat equal-share round-robin treated both the
    same, which is how an obscure 30-min church ended up with the same slot
    allocation as monument even on trips where "culture" was only one of
    several stated interests (real repro: LDS Church/St Mary's/St Thomas
    Orthodox recurring across a family/nature/culture trip and an art trip).
    Each interest distributes 1.0 "vote" across the categories it maps to;
    a category's weight is the sum of votes it receives. Falls back to equal
    weight across matched_cats if no interest contributes anything (EC-2.1
    fallback path, or an interest whose exact mapping isn't found) — never
    zero out a category that's actually a real candidate.
    """
    weights: dict[str, float] = {cat: 0.0 for cat in matched_cats}
    for interest in interests:
        mapped = INTEREST_MAP.get(_resolve_interest_key(interest), [])
        mapped = [c for c in mapped if c in matched_cats]
        if not mapped:
            continue
        share = 1.0 / len(mapped)
        for cat in mapped:
            weights[cat] += share
    if not any(weights.values()):
        return {cat: 1.0 for cat in matched_cats}
    return weights


def _day_of_week(date_str: str) -> str:
    """Return weekday name for an ISO date string."""
    from datetime import date
    d = date.fromisoformat(date_str)
    return d.strftime("%A")


def _is_open(poi: dict, travel_dates: list[str]) -> bool:
    """
    EC-2.4: Filter POIs closed on the user's travel days.
    Opening hours format from OSM is freeform; we do a best-effort parse.
    If hours are 'unknown', we include the POI with a flag.
    """
    hours = poi.get("opening_hours", "unknown")
    if hours == "unknown" or not travel_dates:
        return True

    hours_lower = hours.lower()
    for date_str in travel_dates:
        day = _day_of_week(date_str).lower()[:2]  # "mo", "tu", "we", ...
        # Check for explicit "off" or "closed" day patterns
        if f"{day} off" in hours_lower or f"closed {day}" in hours_lower:
            return False
        # Check for "Mo-Fr" range exclusions — skip if the day falls on weekend-only schedule
        if "mo-fr" in hours_lower and day in ("sa", "su"):
            return False
    return True


def _normalize_landmark_name(name: str) -> str:
    """
    R-36 (Itinerary-Coverage-Gap-Analysis.md QA-20, 2026-07-16): the old
    check was exact-lowercase `in` membership with zero normalization — the
    allowlist's "lodi garden" never matched the dataset's real "Lodhi
    Gardens" for exactly this reason, so even Delhi's most famous park never
    got its boost. Strips possessives and non-alphanumerics so matching
    survives that kind of trivial spelling/punctuation drift instead of
    silently missing (this is not fuzzy matching — it's normalization; a
    genuinely different name still won't match).
    """
    name = name.lower().strip()
    name = re.sub(r"['’]s\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


# R-41 (Itinerary edit commands QA, finding H3, 2026-07-17): the honesty
# check below (KNOWN_ABSENT_POPULAR_PLACES) requires an exact match after
# _normalize_landmark_name(), which strips punctuation/possessives but not
# generic trailing venue words -- "Select Citywalk mall" never matched the
# dict's "select citywalk" key for exactly that reason, so all 20 "add"
# requests for it fell through to the generic, unexplained "couldn't find"
# message instead of the intended honest, sourced decline (the equivalent
# "swap ... with Connaught Place" phrasing worked 20/20 times because
# "Connaught Place" needed no stripping). Stripping the same generic
# suffixes from BOTH the query and the dict's own keys keeps every existing
# match intact (e.g. "ina market" -> "ina", consistently on both sides)
# while letting natural phrasing variants still resolve to the same entry.
_ABSENT_PLACE_GENERIC_SUFFIXES = {"mall", "market", "place", "plaza", "complex", "center", "centre"}


def _strip_generic_suffix_words(name: str) -> str:
    words = name.split()
    while len(words) > 1 and words[-1] in _ABSENT_PLACE_GENERIC_SUFFIXES:
        words.pop()
    return " ".join(words)


def _normalize_for_absent_match(name: str) -> str:
    return _strip_generic_suffix_words(_normalize_landmark_name(name))


_ABSENT_PLACES_BY_NORMALIZED_KEY = {
    _normalize_for_absent_match(k): v for k, v in KNOWN_ABSENT_POPULAR_PLACES.items()
}


def lookup_known_absent_place(name: str) -> str | None:
    """Honesty-check lookup for the edit engine, used before adding/swapping
    in a named place -- see KNOWN_ABSENT_POPULAR_PLACES above. Normalizes
    trailing generic venue words so natural phrasing variants still match
    (see the comment above _ABSENT_PLACE_GENERIC_SUFFIXES)."""
    return _ABSENT_PLACES_BY_NORMALIZED_KEY.get(_normalize_for_absent_match(name or ""))


_MUST_SEE_NORMALIZED = {_normalize_landmark_name(n) for n in MUST_SEE}
_LANDMARK_NAMES_NORMALIZED = {
    _normalize_landmark_name(n) for n in (HIGH_PROFILE | POPULAR_FOOD_NATURE_SHOPPING)
}


def _is_must_see(poi: dict) -> bool:
    return _normalize_landmark_name(poi["name"]) in _MUST_SEE_NORMALIZED


def _is_landmark(poi: dict) -> bool:
    """True for MUST_SEE too — it's a subset of HIGH_PROFILE. Used where
    callers just need "is this a named landmark at all" (e.g. deciding
    what's safe to swap out in the R-1 guarantee pass). Since R-36, also
    true for the hand-curated POPULAR_FOOD_NATURE_SHOPPING names — the same
    "definitely worth featuring" tier, just for restaurant/market/park
    instead of monuments."""
    return _normalize_landmark_name(poi["name"]) in _LANDMARK_NAMES_NORMALIZED


# R-39 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
# Popularity Gap", 2026-07-16): measured, systemic OSM data-quality issues
# with no existing filter — see that doc section for the measurement.
#
# (a) A record tagged category="park" whose name has no park/garden/ground
# word anywhere at all (the measured "Kotak Mahindra Bank" case — a literal
# bank with zero park-related wording) is an outright mistagging bug, not
# just noise, so it's hard-filtered out of candidates entirely rather than
# merely down-ranked. Deliberately narrow: a name like "Bank Enclave Park"
# or "Park behind V3S Mall" DOES contain a real park/garden/ground word, so
# it's a genuine (if small, hyperlocal) park named after a nearby landmark,
# not a mistagged bank/mall itself — that case is handled by (b) below
# instead (down-ranked, not dropped, since it IS a real park).
_PARK_WORD_RE = re.compile(r"\b(park|garden|ground|playground)s?\b", re.IGNORECASE)
_NON_PLACE_NAME_RE = re.compile(r"\b(bank|apartments?|towers?|society)\b", re.IGNORECASE)


def _is_mistagged_non_park(poi: dict) -> bool:
    if poi["category"] != "park":
        return False
    return bool(_NON_PLACE_NAME_RE.search(poi["name"])) and not _PARK_WORD_RE.search(poi["name"])


# (b) Generic hyperlocal market/park names (a "Sector 41 C-Block Market",
# "Pocket A2 colony small park", or a small park named only after its own
# apartment complex/housing society — e.g. "Rail Vihar Society Park",
# "Malibu Town Tower 3-4 Park" — tell a visitor nothing) are real places and
# stay legitimate last-resort candidates if nothing more notable exists in
# that category — down-ranked in _relevance_score() below, not dropped.
# Deliberately checked only in the LOWEST score band there, so it can never
# override a POI that already earned a MUST_SEE/landmark/KB-matched boost.
_GENERIC_HYPERLOCAL_NAME_RE = re.compile(
    r"(\bsector\s*\d+\b|\b[a-z]-?block\b|\bdda\b|\bpocket\s*[a-z0-9]?\b"
    r"|\bsociety\b|\bapartments?\b|\btowers?\b|\bcolony\b)",
    re.IGNORECASE,
)
GENERIC_HYPERLOCAL_SCORE_CAP = 0.5


def _is_generic_hyperlocal(poi: dict) -> bool:
    return poi["category"] in ("market", "park") and bool(_GENERIC_HYPERLOCAL_NAME_RE.search(poi["name"]))


# Venue-Tourist-Importance-Scoring-Plan.md, Phase A: a real, independently
# community-tagged OSM signal -- tourism=attraction/museum, or any historic=*
# subtype (monument/fort/tomb/ruins/castle/archaeological_site/city_gate/...)
# -- that isn't already covered by a hand-curated KB match or a confirmed
# Wikidata article (NOTABLE_MATCH above already handles those, and is
# deliberately checked first so this never downgrades a POI that already
# qualified for the stronger band).
def _has_osm_tourism_or_historic_tag(poi: dict) -> bool:
    tags = poi.get("tags") or {}
    return tags.get("tourism") in ("attraction", "museum") or bool(tags.get("historic"))


def _relevance_score(poi: dict, matched_cats: set[str]) -> float:
    if poi["category"] not in matched_cats:
        return 0.0
    has_hours = poi.get("opening_hours", "unknown") != "unknown"
    # Venue-Tourist-Importance-Scoring-Plan.md, Phase A: wheelchair=yes is a
    # real, previously-unread OSM tag -- a small tie-break bonus stacked ON
    # TOP of (never replacing) each band's existing has_hours tie-break, so
    # every band's previous has_hours-only score is completely unchanged;
    # this can only ever raise a score, never lower one.
    wheelchair_bonus = 0.02 if (poi.get("tags") or {}).get("wheelchair") == "yes" else 0.0
    # Six clean, non-overlapping bands (R-1, extended by R-35/R-36/R-38/R-39,
    # and the OSM_TAGGED band above) — see MUST_SEE/HIGH_PROFILE/
    # POPULAR_FOOD_NATURE_SHOPPING/NOTABLE_MATCH/OSM_TAGGED/GENERIC_HYPERLOCAL
    # comments above. An opening_hours/wheelchair tag only breaks ties WITHIN
    # a band; it can never let a lower band outrank a higher one.
    if _is_must_see(poi):
        return MUST_SEE_SCORE_FLOOR + (0.05 if has_hours else 0.0)
    if _is_landmark(poi):
        return round(min(LANDMARK_SCORE_FLOOR + (0.1 if has_hours else 0.0) + wheelchair_bonus, LANDMARK_SCORE_CAP), 3)
    if poi.get("kb_matched") or poi.get("wikidata_qid"):
        return round(min(NOTABLE_MATCH_SCORE_FLOOR + (0.05 if has_hours else 0.0) + wheelchair_bonus, NOTABLE_MATCH_SCORE_CAP), 3)
    if _has_osm_tourism_or_historic_tag(poi):
        return round(min(OSM_TAGGED_SCORE_FLOOR + (0.02 if has_hours else 0.0) + wheelchair_bonus, OSM_TAGGED_SCORE_CAP), 3)
    if _is_generic_hyperlocal(poi):
        return round(min(0.4 + (0.1 if has_hours else 0.0), GENERIC_HYPERLOCAL_SCORE_CAP), 3)
    return round(min(0.6 + (0.1 if has_hours else 0.0) + wheelchair_bonus, NON_LANDMARK_SCORE_CAP), 3)


# Phase 3 QA (H1, "Itinerary edit commands QA.md"): TripContext.constraints
# ["dietary"] was captured correctly by the conversational agent (confirmed:
# e.g. {"dietary": "North Indian food"}) but nothing in this pipeline ever
# read it -- a real 30-itinerary QA round found 0 of 228 scheduled restaurant
# stops verifiably matching the requested cuisine, across 12 real cuisines.
# Maps a free-text dietary phrase to the real tags.cuisine substrings it
# should match, checked against phase1/data/pois.json's actual OSM cuisine
# values (never invented) -- see venues_kb_enrich.py-style "verify against
# the real dataset before adding" discipline applied here too.
_CUISINE_HINT_MAP: dict[str, tuple[str, ...]] = {
    "north indian": ("north_indian", "punjabi", "indian"),
    "south indian": ("south_indian",),
    "continental":  ("continental", "international"),
    "chinese":      ("chinese",),
    "italian":      ("italian", "pizza"),
    "mexican":      ("mexican", "tex-mex"),
    "japanese":     ("japanese",),
    "korean":       ("korean",),
    "bengali":      ("bengali",),
    "punjabi":      ("punjabi", "north_indian"),
    "mughlai":      ("mughlai", "indian"),
    "thai":         ("thai",),
    "american":     ("american",),
    "regional":     ("regional",),
    "asian":        ("asian",),
    # Generic "indian" is checked last (as a fallback substring, not a key
    # collision) since "north indian"/"south indian"/"punjabi"/"mughlai" all
    # also legitimately contain or relate to it -- see _cuisine_hints below.
    "indian":       ("indian",),
}


def _cuisine_hints(dietary) -> tuple[str, ...]:
    # Defensive: constraints["dietary"] is LLM-extracted free text and has
    # been observed coming back as a list (e.g. ["Thai"]) as well as a plain
    # string, depending on how the model phrases its own JSON output for a
    # given turn -- never assume the schema-documented type held. Join any
    # non-string value into one string rather than letting .lower() crash a
    # real itinerary build over what should be a purely additive feature.
    if not isinstance(dietary, str):
        dietary = " ".join(str(d) for d in dietary) if isinstance(dietary, (list, tuple)) else str(dietary)
    dietary_lower = dietary.lower()
    for key, hints in _CUISINE_HINT_MAP.items():
        if key in dietary_lower:
            return hints
    return ()


# Large enough that a confirmed cuisine match on a restaurant the user
# explicitly asked for outranks even an untagged HIGH_PROFILE/
# POPULAR_FOOD_NATURE_SHOPPING restaurant (relevance up to LANDMARK_SCORE_CAP
# 0.9) -- an explicit, stated preference is a stronger signal than generic
# fame the app can't actually verify applies to what was asked. Restaurants
# are never MUST_SEE (that tier is monument-only), so this can't overshoot
# into unintended territory.
CUISINE_MATCH_BOOST = 0.25


def _cuisine_boost(poi: dict, dietary: str | None) -> float:
    if not dietary or poi.get("category") != "restaurant":
        return 0.0
    tag = str((poi.get("tags") or {}).get("cuisine") or "").lower()
    if not tag:
        return 0.0
    hints = _cuisine_hints(dietary)
    return CUISINE_MATCH_BOOST if any(h in tag for h in hints) else 0.0


def _visit_duration(poi: dict) -> int:
    """
    Prefers delhi_tourist_venues_kb.md's real per-venue "Recommended Visit
    Duration" (e.g. Akshardham's 3-5h vs a small temple's 45min) over the
    flat per-category default, which otherwise gives every museum/monument
    the same duration regardless of actual size — a real scheduling
    accuracy improvement for the ~23 well-known venues confidently matched.
    """
    return poi.get("kb_visit_duration_min") or VISIT_DURATION.get(poi["category"], 60)


def poi_search_logic(
    city: str,
    interests: list[str],
    constraints: dict | None = None,
    top_n: int = 20,
) -> list[dict]:
    """Core POI search logic — callable directly for testing."""
    if city.lower() not in ("new delhi", "delhi"):
        raise ValueError(f"City '{city}' is not supported. Only 'New Delhi' is available.")

    constraints = constraints or {}
    travel_dates = constraints.get("travel_dates", [])
    pace = constraints.get("pace", "moderate")
    daily_hours = PACE_HOURS.get(pace, 8.0)

    all_pois = _load_pois()
    matched_cats, is_fallback = _resolve_categories(interests)

    # Filter: category match + open on travel dates
    candidates = [
        p for p in all_pois
        if p["category"] in matched_cats and _is_open(p, travel_dates)
    ]

    # R-37 (Itinerary-Coverage-Gap-Analysis.md, 2026-07-16): admit
    # CROSS_CATEGORY_POPULAR venues (Khan Market, Dilli Haat, Chandni Chowk,
    # Connaught Place) that OSM tags "monument" but a "food"/"shopping"
    # interest should still be able to reach — see that dict's own comment.
    # A shallow copy with `category` overridden to whichever admitted
    # category matches this search, so the original record (and its real
    # "monument" category, still correct for history/heritage searches) is
    # never mutated. Skipped if the POI's real category already matched
    # normally, so it's never entered twice.
    candidate_ids = {p["osm_id"] for p in candidates}
    for p in all_pois:
        if p["osm_id"] in candidate_ids or not _is_open(p, travel_dates):
            continue
        granted = CROSS_CATEGORY_POPULAR.get(_normalize_landmark_name(p["name"]))
        if not granted:
            continue
        admitted_cat = next((c for c in granted if c in matched_cats), None)
        if admitted_cat is None:
            continue
        candidates.append({**p, "category": admitted_cat})
        candidate_ids.add(p["osm_id"])

    # EC-2.1: if still empty after filtering, use general fallback
    if not candidates:
        candidates = [
            p for p in all_pois
            if p["category"] in GENERAL_FALLBACK_CATEGORIES and _is_open(p, travel_dates)
        ]
        is_fallback = True

    # R-39: drop outright mistagged non-places (see _is_mistagged_non_park's
    # own comment) from every path above in one place, rather than repeating
    # the check at each candidate source.
    candidates = [p for p in candidates if not _is_mistagged_non_park(p)]

    # Score and sort. H1 fix: fold in a cuisine-match boost when the user
    # stated a dietary/cuisine preference (constraints["dietary"]) -- purely
    # additive on top of the existing relevance score, only ever applies to
    # restaurant candidates whose real tags.cuisine value actually matches,
    # so it can only ever help a confirmed match rank higher, never demote
    # or exclude anyone.
    dietary = constraints.get("dietary")
    scored = sorted(
        candidates,
        key=lambda p: _relevance_score(p, matched_cats) + _cuisine_boost(p, dietary),
        reverse=True,
    )

    # Deduplicate by osm_id, AND by (category, normalized name) — R-39:
    # measured real duplicate/near-duplicate OSM records under the exact
    # same name (Pizza Hut x36, Karim's x4, Dilli Haat x4) that would
    # otherwise occupy multiple round-robin/top_n slots as if they were
    # different places. `scored` is already sorted by relevance descending,
    # so the first occurrence kept per name is always the highest-scoring
    # (or tied-and-first-in-dataset) one. A rare, disclosed tradeoff: two
    # genuinely different real places that happen to share a common generic
    # name (e.g. two unrelated "Central Market"s) would also collapse to
    # one — accepted, since the measured alternative (no dedup at all,
    # verified: Pizza Hut alone could occupy 4 of a 15-candidate list) is
    # the worse problem this fixes.
    seen_ids = set()
    seen_names = set()
    unique = []
    for p in scored:
        name_key = (p["category"], _normalize_landmark_name(p["name"]))
        if p["osm_id"] in seen_ids or name_key in seen_names:
            continue
        seen_ids.add(p["osm_id"])
        seen_names.add(name_key)
        unique.append(p)

    # Round-robin across matched categories rather than a flat top-N score
    # cut. A flat cut lets one category — usually one with many
    # HIGH_PROFILE-boosted entries — crowd out every other matched interest
    # once the dataset has enough candidates (e.g. "food"+"culture" losing
    # all food-category results once culture-site coverage grew). Each
    # per-category bucket is still relevance-sorted, so the highest-scoring
    # POI within each category is still taken first.
    #
    # R-8: plain round-robin gave every matched category an EQUAL turn
    # regardless of how central it actually is to what was asked — weighted
    # instead, using _category_weights() (see its docstring). This is the
    # standard weighted-round-robin "highest credit first" scheduling
    # algorithm: every category's credit grows each round by its weight;
    # whichever has the most credit spends a turn and pays it down. Over
    # many rounds this converges to proportional-by-weight allocation while
    # still interleaving categories every round (not blocks) — round-robin
    # is still exactly what happens among equally-weighted categories
    # (credits stay tied), so diversity/fairness is preserved as a
    # tie-breaker, just no longer the primary allocator.
    by_category: dict[str, list[dict]] = {}
    for p in unique:
        by_category.setdefault(p["category"], []).append(p)

    weights = _category_weights(interests, set(by_category))

    top: list[dict] = []
    cursor = {cat: 0 for cat in by_category}
    credit = {cat: 0.0 for cat in by_category}
    while len(top) < top_n and any(cursor[cat] < len(pois_) for cat, pois_ in by_category.items()):
        eligible = [cat for cat in by_category if cursor[cat] < len(by_category[cat])]
        if not eligible:
            break
        for cat in eligible:
            credit[cat] += weights.get(cat, 1.0)
        # Paying down by the sum of currently-eligible weights (not a fixed
        # constant) is what makes this converge to proportional allocation
        # — recomputed each round so it adapts as categories get exhausted,
        # rather than let a low-weight category start dominating once the
        # heavier ones it used to compete against run out of candidates.
        total_weight = sum(weights.get(cat, 1.0) for cat in eligible)
        chosen_cat = max(eligible, key=lambda c: credit[c])
        top.append(by_category[chosen_cat][cursor[chosen_cat]])
        cursor[chosen_cat] += 1
        credit[chosen_cat] -= total_weight

    # R-1: guarantee representation for top landmarks per matched category.
    # The scoring fix above already sorts landmarks first within their own
    # category, but round-robin's even per-category split can still crowd
    # every true icon out of a multi-interest trip — a category can hold
    # more HIGH_PROFILE entries than the round-robin slots it gets once
    # several interests are combined (verified: zero icons across 10
    # diverse real builds before this fix). Swap in by replacing the
    # lowest-scoring non-landmark already selected — never grows top_n,
    # never invents a stop.
    top_ids = {p["osm_id"] for p in top}
    # Skip a landmark whose NAME (not just osm_id) is already present in
    # `top` — the dataset stores some real places under multiple OSM
    # records/categories (e.g. Jama Masjid as both "mosque" and "monument";
    # see Itinerary-Quality-Review-and-Recommendations.md F-3/R-3), and
    # reserving the same landmark twice would waste a guaranteed slot
    # instead of surfacing a genuinely different icon.
    top_names = {p["name"].lower() for p in top}
    guaranteed: list[dict] = []
    for cat in matched_cats:
        for p in by_category.get(cat, [])[:GUARANTEED_LANDMARKS_PER_CATEGORY]:
            if not _is_landmark(p):
                continue
            if p["osm_id"] in top_ids or p["name"].lower() in top_names:
                continue
            guaranteed.append(p)
            top_ids.add(p["osm_id"])
            top_names.add(p["name"].lower())

    for p in guaranteed:
        if len(top) < top_n:
            top.append(p)
            continue
        swap_idx = min(
            (i for i, t in enumerate(top) if not _is_landmark(t)),
            key=lambda i: _relevance_score(top[i], matched_cats),
            default=None,
        )
        if swap_idx is not None:
            top[swap_idx] = p

    # EC-2.5: warn if even the shortest visit exceeds daily budget
    min_visit = min((_visit_duration(p) for p in top), default=60)
    if min_visit / 60 > daily_hours:
        print(
            f"[warn] Daily budget ({daily_hours}h) is too short for even one stop "
            f"(min visit ~{min_visit}min). Consider extending available hours."
        )

    return [
        {
            "osm_id":           p["osm_id"],
            "name":             p["name"],
            "category":         p["category"],
            "lat":              p["lat"],
            "lon":              p["lon"],
            "opening_hours":    p.get("opening_hours", "unknown"),
            "visit_duration_min": _visit_duration(p),
            "relevance_score":  _relevance_score(p, matched_cats),
            "fallback":         is_fallback,
            # Wikidata enrichment (CC0), when a confident match exists — real
            # official site / canonical identifier, never fabricated.
            **({"website": p["website"]} if p.get("website") else {}),
            **({"wikidata_qid": p["wikidata_qid"]} if p.get("wikidata_qid") else {}),
            # R-22 (Itinerary-Quality-Review... round 4 UX benchmark, QA-17):
            # wikidata_client.py already fetches a real Commons photo (P18)
            # for every confidently-matched landmark and writes it onto the
            # POI record — this allowlist just never re-exported it, so the
            # photo silently died here, one stage before the itinerary, and
            # the UI never had a chance to render it.
            **({"image": p["image"]} if p.get("image") else {}),
            # delhi_tourist_venues_kb.md enrichment, when a confident match
            # exists — real entry fee/best-time/audience notes, never fabricated.
            **({"kb_entry_fee": p["kb_entry_fee"]} if p.get("kb_entry_fee") else {}),
            **({"kb_best_time_to_visit": p["kb_best_time_to_visit"]} if p.get("kb_best_time_to_visit") else {}),
            **({"kb_suitable_for": p["kb_suitable_for"]} if p.get("kb_suitable_for") else {}),
            # Phase 3 QA (H1, "Itinerary edit commands QA.md"): real OSM
            # cuisine tag, when present -- previously silently dropped here,
            # so even a correctly cuisine-matched restaurant (see
            # _cuisine_boost above) had no way to be verified or displayed
            # downstream once it reached the itinerary.
            **({"cuisine": p["tags"]["cuisine"]} if p.get("tags", {}).get("cuisine") else {}),
        }
        for p in top
    ]


# R-41 (Itinerary edit commands QA, finding M1, 2026-07-17): _apply_add()/
# _apply_swap() in phase4/edit_engine.py previously only ever treated the
# edit's constraint as a category/interest string fed into
# poi_search_logic() above -- there was no path to add/swap in a SPECIFIC
# real named place ("add the National Museum") except by coincidence (the
# exact phrase happening to also be a literal INTEREST_MAP key). This is a
# direct name-based lookup, tried first by the edit engine before it falls
# back to the category search. High similarity threshold (0.72) plus a
# forced-match on a clean substring keeps this from matching on noisy short
# constraints -- callers are expected to skip calling this at all when the
# constraint already resolves to a real INTEREST_MAP category (see
# edit_engine.py), so it's only reached for genuine proper-noun requests.
NAME_MATCH_SIMILARITY_THRESHOLD = 0.72


def search_poi_by_name(city: str, name: str, top_n: int = 3) -> list[dict]:
    """Direct name-based POI lookup -- returns POIs shaped like
    poi_search_logic()'s output, best match first, or [] if nothing is a
    confident match."""
    if city.lower() not in ("new delhi", "delhi"):
        return []
    query = _normalize_landmark_name(name or "")
    if not query:
        return []

    all_pois = _load_pois()
    scored = []
    for p in all_pois:
        cand = _normalize_landmark_name(p["name"])
        if not cand:
            continue
        similarity = difflib.SequenceMatcher(None, query, cand).ratio()
        if query in cand or cand in query:
            similarity = max(similarity, 0.9)
        if similarity >= NAME_MATCH_SIMILARITY_THRESHOLD:
            scored.append((similarity, p))
    scored.sort(key=lambda t: t[0], reverse=True)

    # Same dedup discipline as poi_search_logic() above (osm_id + normalized
    # category/name), so a place with several near-duplicate OSM records
    # doesn't occupy more than one slot in the result.
    seen_ids, seen_names, out = set(), set(), []
    for _, p in scored:
        name_key = (p["category"], _normalize_landmark_name(p["name"]))
        if p["osm_id"] in seen_ids or name_key in seen_names:
            continue
        seen_ids.add(p["osm_id"])
        seen_names.add(name_key)
        out.append({
            "osm_id": p["osm_id"],
            "name": p["name"],
            "category": p["category"],
            "lat": p["lat"],
            "lon": p["lon"],
            "opening_hours": p.get("opening_hours", "unknown"),
            "visit_duration_min": _visit_duration(p),
            "relevance_score": _relevance_score(p, {p["category"]}),
            "fallback": False,
        })
        if len(out) >= top_n:
            break
    return out


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("poi-search")


@mcp.tool()
def poi_search(
    city: str,
    interests: list[str],
    constraints: dict | None = None,
    top_n: int = 20,
) -> list[dict]:
    """
    Search for Points of Interest in New Delhi matching user interests.
    Returns ranked POIs with metadata including visit duration and relevance score.
    """
    return poi_search_logic(city, interests, constraints, top_n)


if __name__ == "__main__":
    mcp.run()
