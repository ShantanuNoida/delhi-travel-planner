"""
Intent Classifier — Phase 4.

Classifies a voice command issued after an itinerary already exists into:
  EDIT      — modify the existing itinerary
  EXPLAIN   — ask a question about the plan, a place, feasibility, or weather
  NEW_PLAN  — discard this plan and start a completely new trip

For EDIT commands, also extracts a structured EditIntent.
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from config import get_llm_client, LLM_MODEL_FAST

VALID_INTENTS = {"EDIT", "EXPLAIN", "NEW_PLAN"}
VALID_EDIT_TYPES = {"relax", "swap", "add", "remove", "reduce_travel", "reorder"}
VALID_SLOTS = {"morning", "afternoon", "evening", "all"}

CLASSIFIER_SYSTEM = """Classify the user's voice command about their New Delhi trip itinerary into exactly one of: EDIT, EXPLAIN, NEW_PLAN.

- EDIT: the user wants to change the existing itinerary, e.g. "make Day 2 more relaxed", "swap Day 1 evening for something indoors", "remove the museum on Day 3", "add one famous local food place", "reduce travel time between stops", "swap the order of Day 1's morning and afternoon plans".
- EXPLAIN: the user is asking a question about the plan, a specific place, feasibility, or weather, e.g. "why did you pick Red Fort?", "is this doable?", "what if it rains?".
- NEW_PLAN: the user wants to discard this plan entirely and start planning a different trip from scratch.

For EDIT commands, also extract an edit_intent object:
  target_day   — 1, 2, 3, 4, or "all" (which day the edit applies to; "all" if unspecified or it applies to the whole trip)
  target_slot  — "morning", "afternoon", "evening", or "all"
  edit_type    — one of:
    "relax"         — lighten a day/slot WITHOUT the user naming a specific stop or category to drop; the system picks which one to remove. Use this for vague-quantity phrasing too: "make Day 2 more relaxed", "make Day 1 less packed", "take one thing out of Day 2 evening", "remove something from Day 1", "cut one stop", "lighten up the trip" — none of these name WHAT to drop, only that something generic and unspecified should go.
    "remove"        — drop a SPECIFIC place or category the user names or clearly identifies: "remove the museum on Day 3", "remove Red Fort", "take out the temple visit". Only use "remove" when the constraint you extract would be a real, searchable place name or category (museum, temple, a specific POI) — never a vague placeholder like "one thing", "something", or "a stop", since nothing in the itinerary is ever literally named that and the edit would then fail to find anything to remove.
    "swap"          — replace an EXISTING stop with a DIFFERENT PLACE (a new stop nobody has seen yet fills that slot), e.g. "swap Day 1 evening for something indoors", "swap the museum for a market". Only use "swap" when the request is about WHAT occupies a slot, never about the ORDER stops happen in.
    "reorder"       — change the SEQUENCE/order of stops already on the itinerary, with no new place involved at all — nothing gets replaced or removed, only re-sequenced: "swap the order of Day 1's morning and afternoon plans", "move the museum to the afternoon instead", "put the market before the temple", "do Day 2 in reverse order". The word "swap" alone does NOT mean edit_type="swap" — read for whether a *replacement place* is wanted (→ swap) or the *sequence of existing stops* is wanted (→ reorder).
    "add"           — insert a new stop, e.g. "add one famous local food place"
    "reduce_travel" — re-cluster stops to cut travel time between them
  constraint       — free text describing the change (e.g. "indoors", "food", a specific POI name to remove — leave empty for "relax"/"reorder", since by definition nothing specific was named). For "swap", this is the NEW place/category that should fill the slot.
  target_stop_name — ONLY for "swap" or "remove": the name of the SPECIFIC EXISTING stop already on the itinerary that the user named to be replaced/removed, verbatim as they said it, e.g. "swap Humayun's Tomb for Qutab Minar" -> target_stop_name="Humayun's Tomb", constraint="Qutab Minar"; "I don't like Karim's, replace it with another restaurant" -> target_stop_name="Karim's", constraint="restaurant". Leave as an empty string whenever the user identifies what to change by day/time-of-day instead of by name ("swap Day 1 evening for something indoors" -> target_stop_name="", since no existing stop was named) — target_day/target_slot alone are enough for the app to find it in that case.

Respond with ONLY a JSON object of the form:
{"intent": "EDIT"|"EXPLAIN"|"NEW_PLAN", "edit_intent": {"target_day":.., "target_slot":.., "edit_type":.., "constraint":.., "target_stop_name":..} or null, "query": "<original text, verbatim, if EXPLAIN>"}
"""


# Phase 2 QA (H3, "Itinerary edit commands QA.md"): real repro — "What are
# some alternatives to Make My Lagan on Day 2?" (Make My Lagan is a real
# scheduled restaurant) was classified EDIT/swap, purely because the
# venue's own proper name starts with "Make", which is also the literal
# first word of this prompt's own EDIT examples ("make Day 2 more
# relaxed"). A misroute here is worse than the classifier's more common
# no-op failures: it can silently mutate the itinerary in response to what
# the user believes is a read-only question. _QUESTION_STARTERS is a
# conservative signal (only fires on genuinely question-shaped text), and
# a genuine collision only overrides EDIT when the extracted constraint is
# an EXACT match for a real scheduled stop's name — never a partial/fuzzy
# match, to avoid ever overriding a legitimate edit that happens to mention
# a stop by name ("swap Karim's for something else").
_QUESTION_STARTERS = ("what", "why", "how", "when", "where", "which", "who",
                      "is ", "are ", "can ", "could ", "should ", "does ", "do ")
# Team Waypoint recheck (2026-07-22): real repro -- "Give me some other
# options besides Lodhi Garden" is semantically an information request (the
# same shape as the original "what are some alternatives to X" repro) but
# is grammatically imperative, not interrogative, and has no "?" -- so it
# didn't start with any word in _QUESTION_STARTERS and the H3 guard never
# fired, letting it through as a silent EDIT/remove. Checked as a substring
# anywhere in the text (not just the leading word), same pattern already
# used for explain_engine.py's RECOMMENDATION_PHRASES.
_INFO_REQUEST_PHRASES = ("give me", "show me", "tell me", "suggest", "recommend",
                          "other option", "another option", "alternatives to",
                          "alternative to", "options besides", "options instead")


def _looks_like_a_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    lower = stripped.lower()
    if lower.startswith(_QUESTION_STARTERS):
        return True
    return any(p in lower for p in _INFO_REQUEST_PHRASES)


def _has_info_request_phrase(text: str) -> bool:
    return any(p in text.lower() for p in _INFO_REQUEST_PHRASES)


def _matches_real_stop_name(constraint: str, itinerary: dict) -> bool:
    constraint_norm = constraint.strip().lower()
    if not constraint_norm:
        return False
    for key in itinerary:
        if not key.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for stop in itinerary[key].get(slot, []):
                if stop.get("name", "").strip().lower() == constraint_norm:
                    return True
    return False


# Investigated 2026-07-22 (per "Itinerary edit commands QA.md"'s Team
# Waypoint Recheck section): real repro -- "Give me some alternatives
# besides Make My Lagan" (Make My Lagan is a real scheduled restaurant)
# classified NEW_PLAN 5/6 times at temperature=0. Isolated via a controlled
# swap: the identical sentence with a fabricated venue name ("Make My
# Feast") never produced NEW_PLAN (0/4, always EDIT) -- so this is specific
# to the literal string "Make My Lagan," not the sentence shape. Working
# theory: "Make My Lagan" ("lagan" = wedding in Hindi/Urdu, i.e. "Make My
# Wedding") closely echoes MakeMyTrip, India's largest travel-booking
# brand -- NEW_PLAN's own definition below is literally "start planning a
# different trip," so the model appears to be pattern-matching the "Make
# My ___" construction against that brand association rather than parsing
# it as a scheduled stop's proper name. Same family of bug as H3 (a real
# venue's name colliding with the classifier's own vocabulary/associations),
# on the EXPLAIN-vs-NEW_PLAN boundary instead of EDIT-vs-EXPLAIN.
#
# Mirrors H3's guard shape: only downgrades when the text actually names a
# real scheduled stop AND carries no genuine restart signal, so an actual
# "start over" request that happens to mention a stop in passing (e.g.
# "forget Make My Lagan and everything else, let's start a totally
# different trip to Goa") is left alone.
_RESTART_SIGNAL_PHRASES = (
    "start over", "start planning", "different trip", "different city",
    "new trip", "new plan", "from scratch", "forget this", "scrap this",
    "cancel this", "plan something else", "somewhere else", "another city",
    "different destination",
)


def _mentions_real_stop_name(text: str, itinerary: dict) -> bool:
    lower = text.lower()
    for key in itinerary:
        if not key.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for stop in itinerary[key].get(slot, []):
                name = stop.get("name", "")
                if name and name.lower() in lower:
                    return True
    return False


def _has_restart_signal(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _RESTART_SIGNAL_PHRASES)


def classify_intent(text: str, itinerary: dict | None = None) -> dict:
    """Classify a post-itinerary command. Returns {"intent", "edit_intent", "query"}.

    itinerary (optional): when given, guards against H3-style misroutes —
    a real venue's name colliding with the classifier's own vocabulary or
    brand associations, on either the EDIT-vs-EXPLAIN boundary
    (_matches_real_stop_name) or the NEW_PLAN-vs-EXPLAIN boundary
    (_mentions_real_stop_name + _has_restart_signal). Omit only when no
    itinerary exists yet (there's nothing to guard against in that case
    anyway)."""
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=LLM_MODEL_FAST,
        temperature=0,
        messages=[
            {"role": "system", "content": CLASSIFIER_SYSTEM},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        data = {}

    intent = data.get("intent", "EXPLAIN")
    if intent not in VALID_INTENTS:
        intent = "EXPLAIN"

    edit_intent = None
    if intent == "EDIT" and isinstance(data.get("edit_intent"), dict):
        edit_intent = _normalize_edit_intent(data["edit_intent"])

        # Round 3 QA (Q-2, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
        # real repro -- "What are some alternatives to Punjab Food on Day
        # 2?" stayed misclassified EDIT even with the H3 guard's exact-match
        # check in place, because the model's own `constraint` extraction
        # sometimes keeps the surrounding phrase ("alternatives to Punjab
        # Food") instead of isolating just the venue name, so
        # _matches_real_stop_name's exact-match-only comparison (T-4.8,
        # deliberately exact -- see its own test for why) never fires. This
        # narrow OR fallback catches that specific case using the ORIGINAL
        # TEXT instead of the (possibly imprecise) extracted constraint --
        # but only when the text ALSO carries one of _INFO_REQUEST_PHRASES'
        # explicit informational-intent phrases ("alternatives to," "give
        # me," "other option," etc.), not merely any question-shaped text.
        # A genuine imperative edit ("swap Karim's for something else")
        # contains none of those phrases, so it's untouched -- this doesn't
        # broaden the guard's trigger surface the way loosening
        # _matches_real_stop_name itself would have.
        if (itinerary is not None and _looks_like_a_question(text)
                and (_matches_real_stop_name(edit_intent["constraint"], itinerary)
                     or (_has_info_request_phrase(text) and _mentions_real_stop_name(text, itinerary)))):
            intent = "EXPLAIN"
            edit_intent = None

    if (intent == "NEW_PLAN" and itinerary is not None
            and _mentions_real_stop_name(text, itinerary)
            and not _has_restart_signal(text)):
        intent = "EXPLAIN"

    # Live-usage report ("app isn't handling edit instructions/questions
    # well"): real crash reproduced -- `data.get("query", text)` only falls
    # back to `text` when the "query" KEY IS ABSENT, not when it's present
    # with value None. The classifier's own prompt tells the model to leave
    # "query" null unless it classified EXPLAIN itself -- so whenever the H3
    # guard above (or Q-2's extension of it) reclassifies EDIT -> EXPLAIN
    # *after* the model already committed to EDIT (and correctly left query
    # null per its own instructions), this returned {"intent": "EXPLAIN",
    # "query": None} -- which crashed explain_engine.py's `query.lower()`
    # with a raw AttributeError, surfacing to the user as the generic
    # "Something went wrong" fallback. `or` (not `.get`'s default) covers
    # both "key absent" and "key present but falsy/None".
    return {
        "intent": intent,
        "edit_intent": edit_intent,
        "query": data.get("query") or text,
    }


def _normalize_edit_intent(raw: dict) -> dict:
    target_day = raw.get("target_day", "all")
    if isinstance(target_day, str) and target_day.isdigit():
        target_day = int(target_day)
    if target_day != "all" and not isinstance(target_day, int):
        target_day = "all"

    target_slot = raw.get("target_slot", "all")
    if target_slot not in VALID_SLOTS:
        target_slot = "all"

    edit_type = raw.get("edit_type", "swap")
    if edit_type not in VALID_EDIT_TYPES:
        edit_type = "swap"

    return {
        "target_day": target_day,
        "target_slot": target_slot,
        "edit_type": edit_type,
        "constraint": str(raw.get("constraint", "") or ""),
        # Live-usage report ("swapping a place with another is not working
        # well"): real repro -- "Swap Humayun's Tomb for Qutab Minar" used to
        # have no way to express WHICH existing stop to replace (only
        # target_day/target_slot, a position, and constraint, the NEW
        # place) -- so it defaulted to target_day="all"/target_slot="all"
        # and _apply_swap blindly replaced the LAST stop in every slot
        # across the whole trip instead of the one actually named. This
        # field lets edit_engine.py resolve the real day/slot by NAME when
        # the user identified the old stop that way, instead of only ever
        # by position.
        "target_stop_name": str(raw.get("target_stop_name", "") or ""),
    }
