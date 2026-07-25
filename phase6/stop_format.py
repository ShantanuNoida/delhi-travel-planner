"""Shared stop-detail display formatting — used by app.py and docx_generator.py."""

import re

_DAY_TOKEN_RE = re.compile(r"\b(mo|tu|we|th|fr|sa|su)\b", re.IGNORECASE)
_DAY_CANON = {"mo": "Mo", "tu": "Tu", "we": "We", "th": "Th", "fr": "Fr", "sa": "Sa", "su": "Su"}

# A dotted abbreviation like "A.I.I.M.S." is a single whitespace-split
# "word" with 5+ letters, so it would otherwise pass the length>3 check
# and get capitalize()'d as one unit — mangling it into "A.i.i.m.s.".
_DOTTED_ABBREVIATION_RE = re.compile(r"^([A-Za-z]\.){2,}$")


def format_opening_hours(raw: str) -> str:
    """
    Cosmetic-only cleanup of a raw OSM opening_hours string (QA-9/R-15):
    normalizes day-abbreviation casing ("tu-su" -> "Tu-Su"), spells out the
    "off" keyword, and drops exact duplicate comma-segments. Deliberately
    does NOT try to reconcile genuinely conflicting/overlapping time ranges
    in the source data — doing so would mean asserting hours this app can't
    actually verify, which cuts against its whole grounding-first design. A
    messy-but-accurate string is left messy rather than prettied into
    something possibly wrong.
    """
    if not raw:
        return raw
    segments, seen, deduped = [s.strip() for s in raw.split(",")], set(), []
    for s in segments:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    text = ", ".join(deduped)
    text = _DAY_TOKEN_RE.sub(lambda m: _DAY_CANON[m.group(1).lower()], text)
    return re.sub(r"\boff\b", "closed", text, flags=re.IGNORECASE)


def format_display_name(name: str) -> str:
    """
    R-11 (Itinerary-Quality-Review-and-Recommendations.md): raw OSM names
    surface in ALL CAPS ("HANUMAN MANDIR") or inconsistent case
    ("Archaeological museum") often enough to look unpolished. Fixes
    casing per-word with str.capitalize() rather than str.title() — title()
    mis-capitalizes the letter right after an apostrophe (turns "Mandir's"
    into "Mandir'S"), which would corrupt any name with a possessive.
    Only touches words that are fully UPPER or fully lower to begin with;
    an already-mixed-case word (a real acronym embedded in a phrase, or an
    already-correct "Humayun's") is left untouched on the assumption it's
    already intentional. Short (<=3 letter) ALL-CAPS words are also left
    alone since they're usually a real acronym/code (ESI, ITO, DLF), not a
    data-entry casing slip. Cosmetic-only, used at render time — never
    changes the stored name used for matching/dedup/citations.
    """
    if not name:
        return name
    fixed = []
    for word in name.split(" "):
        letters = [c for c in word if c.isalpha()]
        if not letters:
            fixed.append(word)
            continue
        is_all_upper = all(c.isupper() for c in letters)
        is_all_lower = all(c.islower() for c in letters)
        if not is_all_upper and not is_all_lower:
            fixed.append(word)
        elif is_all_upper and (len(letters) <= 3 or _DOTTED_ABBREVIATION_RE.match(word)):
            fixed.append(word)
        else:
            fixed.append(word.capitalize())
    return " ".join(fixed)
