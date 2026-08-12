"""
Edit Engine — Phase 4.

Applies a single EditIntent to an itinerary with slot-level precision:
only the identified target_day + target_slot are ever touched. Guards
every edit against overflowing the day's time budget (feasibility) —
if an edit would push a touched day over budget, it is rejected and
the original itinerary is returned unchanged.
"""

import copy
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
PHASE2_DIR = os.path.join(_ROOT, "phase2")
sys.path.insert(0, PHASE2_DIR)

from itinerary_builder import (
    LANDMARK_RELEVANCE_FLOOR,
    MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN,
    PACE_HOURS,
    SLOTS,
    _duplicate_of,
    _format_clock,
    _haversine_km,
    _travel_mode,
    _travel_time_min,
    itinerary_builder_logic,
)
from poi_search import (
    INTEREST_MAP,
    _resolve_interest_key,
    lookup_known_absent_place,
    poi_search_logic,
    search_poi_by_name,
)
from feasibility import check_feasibility, MAX_TRAVEL_LEG_MIN  # noqa: F401  (check_feasibility re-exported for convenience)

DAY_SLOTS = ("morning", "afternoon", "evening")

# Real OSM category values this dataset uses (mirrors phase6/app.py's
# CATEGORY_ICON keys) -- used by _find_stop_by_name's category-word fallback.
_CATEGORY_WORDS = {"monument", "museum", "temple", "mosque", "church", "gurdwara", "park", "market", "restaurant"}

# R-9 (Itinerary-Quality-Review-and-Recommendations.md F-10): the intent
# classifier extracts the user's own free-text phrasing verbatim (its own
# prompt example is "indoors", not "indoor") — poi_search.py's INTEREST_MAP
# does an exact-key lookup, so any spelling not already a key falls through
# to the generic fallback categories, which is how an "indoor" swap request
# ended up pulling in an open-air market. Normalize the common phrasings
# to the two canonical INTEREST_MAP keys before they're used as a search
# interest.
_INDOOR_SYNONYMS = {"indoor", "indoors", "inside", "enclosed"}
_OUTDOOR_SYNONYMS = {"outdoor", "outdoors", "outside", "open-air", "open air"}


def _normalize_constraint(constraint: str) -> str:
    c = (constraint or "").strip().lower()
    if c in _INDOOR_SYNONYMS:
        return "indoor"
    if c in _OUTDOOR_SYNONYMS:
        return "outdoor"
    return constraint


# Round 3 QA (E-4, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): a
# cost/budget-worded constraint ("something free of charge", "a cheap
# option") has no INTEREST_MAP entry and never will (it's a price filter,
# not a category), so it always fell through to the same generic
# "Couldn't find a suitable replacement for that swap" every other
# no-match case uses — reproduced 20/20 in Round 3's QA run. That message
# is honest (nothing was silently substituted) but not specific: it reads
# identically to "I searched and nothing matched," which invites retrying
# the exact same request, when the real issue is "this app can't filter by
# price at all." Detecting the cost language and saying so plainly, same
# spirit as the existing known-absent-place honesty check just above this
# function's callers.
_COST_CONSTRAINT_WORDS = (
    "free", "no cost", "no fee", "cheap", "cheapest", "budget", "inexpensive",
    "low cost", "low-cost", "affordable", "no charge",
)


def _is_cost_constraint(constraint: str) -> bool:
    c = (constraint or "").strip().lower()
    return any(w in c for w in _COST_CONSTRAINT_WORDS)


# LOW-1 (Team Waypoint Voice-First UI review): only ~39 of ~5,076 POIs carry
# a kb_entry_fee at all (most that do are paid, not free), so this is a
# real but PARTIAL signal -- only ever trust an EXPLICIT "Free" tag, never
# assume an untagged POI (the vast majority) is free just because nothing
# says otherwise. Presenting a guess as a fact is exactly what this app's
# "cited, never invented" discipline exists to prevent, so a cost-
# constrained request that finds no explicitly-free candidate still gets
# the honest decline below, same as before this fix -- it just now actually
# succeeds for the real cases the data does cover.
def _is_free_fee(fee) -> bool:
    return isinstance(fee, str) and fee.strip().lower().startswith("free")


# Live-usage report ("swapping a place with another is not working
# properly"): a constraint like "something else"/"another one" carries no
# real category information, so it was being searched for literally --
# poi_search_logic() has no INTEREST_MAP entry for the phrase "something
# else," so every candidate came back fallback-flagged and got filtered
# out, producing the generic "couldn't find a suitable replacement" message
# for what should be an easy, common request ("swap the market on day 1 for
# something else"). These phrases mean "same kind of place, just a
# different one" -- the old stop's own category is the obvious, correct
# search target instead of the literal vague text.
_VAGUE_REPLACEMENT_PHRASES = (
    "something else", "somewhere else", "anything else", "another one",
    "a different one", "something different", "a different option",
    "another option", "other option", "different", "another",
)


def _is_vague_replacement_constraint(constraint: str) -> bool:
    c = (constraint or "").strip().lower()
    return c in _VAGUE_REPLACEMENT_PHRASES


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _all_day_keys(itinerary: dict) -> list[str]:
    return sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1]))


def _target_days(itinerary: dict, target_day) -> list[str]:
    if target_day == "all":
        return _all_day_keys(itinerary)
    key = f"day_{target_day}"
    return [key] if key in itinerary else []


def _target_slots(target_slot: str) -> list[str]:
    return list(DAY_SLOTS) if target_slot == "all" else [target_slot]


def _recompute_day_total(day: dict) -> float:
    minutes = 0
    for slot in DAY_SLOTS:
        for stop in day.get(slot, []):
            minutes += stop.get("visit_duration_min", 0) + stop.get("travel_time_from_prev_min", 0)
    return round(minutes / 60, 2)


# MEDIUM-4 (Team Waypoint Voice-First UI review): the single shared
# implementation of "move a stop earlier/later" — previously this only
# existed in phase6/app.py behind the Day view's up/down buttons (UX3-5).
# Relocated here so _apply_reorder() below can call the EXACT same logic
# for a typed/spoken "move X earlier" — a voice-only user (the
# accessibility case the docx explicitly calls out) was otherwise fully
# blocked from reordering, since the buttons are mouse/touch-only.
def recompute_slot_times(day: dict, slot: str) -> None:
    """Recomputes travel_time_from_prev_min / travel_mode_from_prev /
    arrival_time (and the restaurant meal timestamp) for every stop in one
    slot, in its current order -- mirrors itinerary_builder.py's own
    per-stop arrival-time formula (slot start hour + minutes already used in
    that slot + travel to reach this stop) so a manually reordered slot
    shows times consistent with a fresh build, not stale positions with the
    old order's times."""
    stops = day.get(slot, [])
    slot_start_min = SLOTS[slot][0] * 60
    minutes_used = 0
    prev = None
    for stop in stops:
        if prev is not None:
            travel = _travel_time_min(prev, stop)
            road_km = _haversine_km(prev["lat"], prev["lon"], stop["lat"], stop["lon"]) * 1.4
            mode = _travel_mode(road_km)
        else:
            travel, mode = 0, None
        stop["travel_time_from_prev_min"] = travel
        stop["travel_mode_from_prev"] = mode
        arrival_min = slot_start_min + minutes_used + travel
        stop["arrival_time"] = _format_clock(arrival_min)
        if stop.get("category") == "restaurant":
            stop["meal"] = f"meal ~{_format_clock(arrival_min)}"
        minutes_used += stop.get("visit_duration_min", 0) + travel
        prev = stop


def move_stop(itinerary: dict, day_key: str, slot: str, idx: int, direction: int) -> bool:
    """Move a stop one position earlier/later through the day's
    morning->afternoon->evening sequence -- swap within the same slot when
    possible, otherwise move across the slot boundary onto the end/start of
    the adjacent slot. direction: -1 = earlier, +1 = later. Returns True if
    a move actually happened, False when already at the very start/end of
    the day (nowhere to go)."""
    day = itinerary[day_key]
    slot_idx = DAY_SLOTS.index(slot)
    stops = day[slot]
    target_idx = idx + direction

    if 0 <= target_idx < len(stops):
        stops[idx], stops[target_idx] = stops[target_idx], stops[idx]
        recompute_slot_times(day, slot)
        day["total_hours"] = _recompute_day_total(day)
        return True

    neighbor_slot_idx = slot_idx + direction
    if not (0 <= neighbor_slot_idx < len(DAY_SLOTS)):
        return False  # already at the very start/end of the day -- nothing to do
    neighbor_slot = DAY_SLOTS[neighbor_slot_idx]
    stop = stops.pop(idx)
    if direction == -1:
        day[neighbor_slot].append(stop)      # becomes the last stop of the earlier slot
    else:
        day[neighbor_slot].insert(0, stop)   # becomes the first stop of the later slot
    recompute_slot_times(day, slot)
    recompute_slot_times(day, neighbor_slot)
    day["total_hours"] = _recompute_day_total(day)
    return True


def _within_budget(day: dict, pace: str) -> bool:
    # The +0.01h tolerance alone was just float-rounding slack. Widened to
    # also cover itinerary_builder.py's own MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN
    # (breakfast/lunch/dinner coverage guarantee, added 2026-07-16): a day
    # the builder legitimately produced up to 30 minutes over budget to fit
    # a real nearby meal is a day this guard should also consider valid —
    # otherwise reduce_travel (which rebuilds a day from scratch via
    # itinerary_builder_logic) rejects the builder's own valid output,
    # exactly the regression this fix closes.
    return _recompute_day_total(day) <= PACE_HOURS.get(pace, 8.0) + (MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN / 60) + 0.01


def _fail(original_itinerary: dict, message: str) -> dict:
    return {"ok": False, "itinerary": original_itinerary, "message": message, "changed_days": []}


# Round 3 QA (E-1, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): the
# post-edit guard below only ever checked total-hours budget (_within_budget)
# -- never the per-leg travel-time limit check_feasibility() (phase5's own
# feasibility eval) already enforces elsewhere. Real repro, reproduced in
# 13/20 fresh itineraries: "Add one famous local food place to Day 1" always
# added the same real venue ("Local"), 69 minutes of travel from the rest of
# Day 1, well over the 45-minute limit -- apply_edit() still returned
# ok=True with a plain success message, and the break silently persisted
# across every subsequent turn until the user happened to separately ask to
# "reduce travel time." This check closes that gap the same way the
# hour-budget guard already works: reject and roll back to the original
# itinerary, with a specific, honest reason -- never leave a changed day in
# a state check_feasibility() would itself flag as broken.
def _over_long_leg(day: dict) -> str | None:
    for slot in DAY_SLOTS:
        for stop in day.get(slot, []):
            leg = stop.get("travel_time_from_prev_min", 0)
            if leg > MAX_TRAVEL_LEG_MIN:
                return f"{stop.get('name', 'that stop')} would be {leg} min from the previous stop (over the {MAX_TRAVEL_LEG_MIN}-min limit)"
    return None


# --------------------------------------------------------------------------- #
# Per-edit-type handlers — each returns (message, changed_day_keys)
# --------------------------------------------------------------------------- #

def _apply_relax(itin: dict, day_keys: list[str], target_slot: str = "all") -> tuple[str, list[str]]:
    """Drop the least essential stop from each targeted day (or slot, if the
    user named one — e.g. "take one thing out of Day 2 evening") to free up
    time. R-23 (Itinerary-Quality-Review-and-Recommendations.md F-17):
    previously ignored target_slot entirely, always scanning the whole day
    — a vague-quantity relax that named a specific slot could drop a stop
    from a DIFFERENT slot than the one the user actually meant."""
    slots = _target_slots(target_slot)
    changed, dropped_names, underfilled_notes = [], [], []
    for key in day_keys:
        day = itin[key]
        candidates = [(slot, i, stop) for slot in slots for i, stop in enumerate(day[slot])]
        if len(candidates) <= 1:
            # R-41 (Itinerary edit commands QA, finding L2): name the
            # specific day/slot and how many stops are actually there,
            # instead of one flat generic line -- the builder's own
            # evening slots routinely hold just a single meal stop, so
            # this reads as a structural trip characteristic rather than
            # a misunderstood command.
            day_num = key.split("_")[1]
            where = f"Day {day_num}'s {target_slot}" if target_slot != "all" else f"Day {day_num}"
            count = len(candidates)
            noun = "stop" if count == 1 else "stops"
            underfilled_notes.append(f"{where} already has just {count} {noun} — nothing to trim there")
            continue
        slot, idx, stop = min(candidates, key=lambda c: c[2].get("relevance_score", 0.5))
        dropped_names.append(stop["name"])
        del day[slot][idx]
        day["total_hours"] = _recompute_day_total(day)
        changed.append(key)
    if dropped_names:
        return (f"Made it more relaxed — removed {', '.join(dropped_names)} to free up time.", changed)
    if underfilled_notes:
        return ("; ".join(underfilled_notes) + ".", [])
    return ("This day is already light — nothing to remove.", [])


_GENERIC_CATEGORY_FILLER_WORDS = {"a", "an", "the", "spot", "place", "stop", "area", "one"}


def _is_pure_category_phrase(constraint: str, resolved_key: str) -> bool:
    """True when the constraint is basically just the resolved category
    word plus generic filler ("a history spot", "the food") — as opposed to
    a specific proper-noun request that merely happens to CONTAIN a category
    word ("the National Museum" contains "museum" but is clearly a specific
    named place, not a generic museum request; a naive "already resolves to
    a category" check would wrongly skip the name lookup for it too)."""
    words = [w for w in re.findall(r"[a-z]+", (constraint or "").lower()) if w not in _GENERIC_CATEGORY_FILLER_WORDS]
    return not words or words == [resolved_key]


def _named_place_candidates(city: str, constraint: str) -> list[dict]:
    """R-41 (Itinerary edit commands QA, finding M1): try a direct
    named-place lookup before falling back to the category search below --
    but only when the constraint isn't already a pure category/theme phrase
    (see _is_pure_category_phrase). A plain thematic phrase ("food", "a
    history spot") should always go through the normal category search, not
    risk a spurious name-similarity match against some unrelated POI that
    happens to contain that common word in its name.

    Round 3 QA (E-5, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): real
    repro found while investigating -- callers must pass an ALREADY
    _normalize_constraint()-d value here. "indoors"/"outdoors" (the plural
    forms the classifier's own prompt examples happen to use) don't literally
    equal the INTEREST_MAP key "indoor"/"outdoor", so _resolve_interest_key
    used to fail to resolve them, `_is_pure_category_phrase`'s skip-condition
    never fired, and a real named-place search ran for the word "indoors"
    itself -- which fuzzy-matched an unrelated real restaurant ("Noor") by
    name similarity. Callers now normalize once, consistently, before this
    function ever sees the constraint."""
    resolved_key = _resolve_interest_key(constraint or "")
    if resolved_key in INTEREST_MAP and _is_pure_category_phrase(constraint, resolved_key):
        return []
    return search_poi_by_name(city, constraint)


def _all_scheduled_stops(itin: dict) -> list[dict]:
    """Every stop currently scheduled anywhere in the trip, across all days
    -- not just one day. Used to keep swap/add candidates from reintroducing
    a place (by exact id, or by the same near-duplicate-detection
    itinerary_builder.py already uses at build time) that's already sitting
    on a different day. See _apply_swap/_apply_add for why this matters."""
    return [s for key in _all_day_keys(itin) for slot in DAY_SLOTS for s in itin[key][slot]]


def resolve_stop_reference(itin: dict, name: str, preferred_day_keys: list[str] | None = None) -> dict:
    """Live-usage report ("swapping a place with another is not working
    well"): locate a specific scheduled stop by name, wherever it actually
    sits (day/slot/position) -- so a request like "swap Humayun's Tomb for
    Qutab Minar" can target the real stop instead of guessing by position.
    Exact case-insensitive match wins immediately; a substring match is only
    trusted when it's UNAMBIGUOUS (exactly one candidate).

    Team Waypoint Voice-First UI review (HIGH-2): a genuinely AMBIGUOUS
    match (2+ candidates, no exact hit) used to collapse into the exact same
    "no match" result as zero candidates, so callers had no way to ask the
    user which one they meant -- they either guessed wrong (falling through
    to a broad, wrong-scope edit) or silently declined. This now reports
    ambiguity as its own outcome, with the actual candidate list, so
    apply_edit() can surface it as a real choice instead of losing the
    information here.

    preferred_day_keys: when the caller already knows which day was named
    (target_day != "all"), pass its resolved day_keys here -- used only to
    disambiguate the category-word fallback below when it would otherwise
    be ambiguous across the whole trip; never overrides a real name match.

    Returns one of:
      {"status": "unique", "location": (day_key, slot, idx)}
      {"status": "ambiguous", "candidates": [(day_key, slot, idx), ...]}
      {"status": "none"}
    """
    target = (name or "").strip().lower()
    if not target:
        return {"status": "none"}

    # Real repro ("Replace the restaurant on day 2 evening with a different
    # one" -> target_stop_name="restaurant"): a bare category word is not a
    # specific place name, but the substring check below would still match
    # it against any OTHER stop's name that happens to contain that word --
    # e.g. an OSM record literally named "NATRAJ restaurant". That silently
    # resolved to the wrong stop on a completely different day/slot than the
    # one actually declared, which apply_edit() then applied for real before
    # Phase 5's edit-correctness check caught the drift and rolled back the
    # whole edit -- a confusing failure for what should have been a normal
    # swap. A bare single-word category term must always go through the
    # dedicated category-word resolution below instead of the substring
    # heuristic, which exists for genuine partial *names* ("Humayun's" for
    # "Humayun's Tomb"), not category words.
    bare_words = [w for w in re.findall(r"[a-z]+", target) if w not in ("the", "a", "an")]
    is_bare_category_word = len(bare_words) == 1 and bare_words[0].rstrip("s") in _CATEGORY_WORDS

    exact, partial = [], []
    for key in _all_day_keys(itin):
        for slot in DAY_SLOTS:
            for idx, stop in enumerate(itin[key][slot]):
                stop_name = stop.get("name", "").strip().lower()
                if not stop_name:
                    continue
                if stop_name == target:
                    exact.append((key, slot, idx))
                elif not is_bare_category_word and (target in stop_name or stop_name in target):
                    partial.append((key, slot, idx))
    if exact:
        return {"status": "unique", "location": exact[0]}
    if len(partial) == 1:
        return {"status": "unique", "location": partial[0]}
    if len(partial) > 1:
        return {"status": "ambiguous", "candidates": partial}

    # Live-usage fix: "the market"/"the museum" names a CATEGORY of an
    # existing stop, not its proper name -- real repro: "Instead of the
    # market on day 2, can we do something different?" extracted
    # target_stop_name="the market", which matched nothing by name, fell
    # back to the old broad "all slots" behavior, and swapped an unrelated
    # restaurant instead of the actual market. If stripping leading
    # articles/trailing plurals leaves a real OSM category word, resolve it
    # -- preferring a match within the day the user already named (if any)
    # so "the market on day 1" doesn't go ambiguous just because a different
    # day also has a market; only unambiguous either way, never guessed.
    if is_bare_category_word:
        cat = bare_words[0].rstrip("s")
        all_matches = [
            (key, slot, idx)
            for key in _all_day_keys(itin) for slot in DAY_SLOTS
            for idx, stop in enumerate(itin[key][slot])
            if stop.get("category") == cat
        ]
        candidates = all_matches
        if preferred_day_keys:
            scoped = [m for m in all_matches if m[0] in preferred_day_keys]
            if scoped:
                candidates = scoped
        if len(candidates) == 1:
            return {"status": "unique", "location": candidates[0]}
        if len(candidates) > 1:
            return {"status": "ambiguous", "candidates": candidates}
    return {"status": "none"}


def _find_stop_by_name(itin: dict, name: str, preferred_day_keys: list[str] | None = None) -> tuple[str, str, int] | None:
    """Back-compat wrapper around resolve_stop_reference(): unique match
    only -- both "no match" and "ambiguous" collapse to None here, matching
    every caller's original contract. _apply_swap() is only ever reached via
    apply_edit(), which resolves ambiguity itself before calling it (see
    apply_edit()'s swap branch), so by the time this runs the ambiguous case
    has already been handled one layer up."""
    result = resolve_stop_reference(itin, name, preferred_day_keys)
    return result["location"] if result["status"] == "unique" else None


def _apply_swap(itin: dict, day_keys: list[str], target_slot: str, constraint: str, city: str,
                 target_stop_name: str = "") -> tuple[str, list[str]]:
    """Replace the targeted stop with a POI matching the constraint --
    either the specific named stop (target_stop_name), or the last stop in
    the targeted slot(s) when no specific stop was named."""
    # R-40 (Itinerary-Coverage-Gap-Analysis.md, 2026-07-16): if the user
    # named a specific place we've verified is genuinely absent from the
    # data, say so honestly right here — before poi_search_logic() gets a
    # chance to silently fall back to an unrelated generic POI (it has no
    # way to know "Connaught Place" was meant as a specific place name
    # rather than an unmatched interest keyword).
    absent_note = lookup_known_absent_place(constraint or "")
    if absent_note:
        return (absent_note, [])

    # Round 3 QA (E-5): normalize ONCE and reuse for both the named-place and
    # category searches below (previously only the category search was
    # normalized -- see _named_place_candidates' own docstring for the real
    # "indoors" -> spurious "Noor" match this caused).
    norm_constraint = _normalize_constraint(constraint)

    # Live-usage fix: when the user named the specific EXISTING stop to
    # replace ("swap Humayun's Tomb for Qutab Minar", "replace Karim's with
    # another restaurant"), resolve its real location instead of trusting
    # target_day/target_slot -- the classifier can only guess those when the
    # old stop was identified by NAME rather than by day/time-of-day, and
    # previously always guessed "all"/"all" in that case. That silently
    # replaced the LAST stop in every slot across the WHOLE TRIP instead of
    # just the one stop actually named -- the real repro that prompted this
    # fix: "Swap Humayun's Tomb for Qutab Minar" left Humayun's Tomb
    # untouched and instead swapped two unrelated stops (Karim's, Khan
    # Market) on the other side of the day. Falls back to the original
    # position-based targeting when the name doesn't resolve (e.g. genuinely
    # not on the itinerary), so this only ever narrows scope, never breaks
    # the existing day/slot-based path.
    target_idx = None
    located = _find_stop_by_name(itin, target_stop_name, preferred_day_keys=day_keys) if target_stop_name else None
    if located:
        day_key, resolved_slot, target_idx = located
        day_keys = [day_key]
        slots = [resolved_slot]
    else:
        slots = _target_slots(target_slot)

    changed, swapped_desc = [], []
    # Round 3 QA (E-5): every one of this round's 11 sampled "couldn't find a
    # suitable replacement" no-ops turned out to share one real cause --  the
    # targeted slot was already empty (an earlier edit in the same session
    # had removed its only stop), so there was never anything to swap OUT,
    # and no candidate search even ran. The old generic message reads as "I
    # searched and found nothing," which is misleading when the real reason
    # is "there's nothing here at all." Tracked separately from a genuine
    # search-came-back-empty case (searched_no_match) so the more specific
    # message is only used when EVERY targeted slot was empty -- a mixed
    # case (one slot empty, another slot genuinely searched and failed)
    # still gets the honest generic message, not a claim that doesn't fully
    # cover what happened.
    empty_slot_notes: list[str] = []
    searched_no_match = False
    for key in day_keys:
        day = itin[key]
        did_swap = False
        for slot in slots:
            if not day[slot]:
                empty_slot_notes.append(f"{key.replace('_', ' ')}'s {slot}")
                continue
            idx = target_idx if target_idx is not None else len(day[slot]) - 1
            old_stop = day[slot][idx]
            # "swap the market for something else" etc.: the old stop's own
            # category IS what "something else" means here -- see
            # _is_vague_replacement_constraint's comment for the real repro.
            # LOW-1: a cost constraint ("something free") gets the same
            # treatment for the same reason -- "free" isn't a real
            # INTEREST_MAP category, so searching on it literally would
            # fall through to the fallback-only path and always come back
            # empty; the old stop's own category is the right thing to
            # search, then filtered for an explicit "Free" tag below.
            # Computed per-slot (not once, up top) since it depends on
            # old_stop, which is only known once we're inside this loop.
            is_cost = _is_cost_constraint(constraint)
            slot_constraint = (
                old_stop.get("category", norm_constraint)
                if (_is_vague_replacement_constraint(constraint) or is_cost)
                else norm_constraint
            )
            # R-41 (finding M1): a specific named place is tried first; the
            # category/interest search only ever fills in behind it.
            named_candidates = _named_place_candidates(city, slot_constraint)
            category_candidates = poi_search_logic(city, [slot_constraint or "indoor"], top_n=10)
            named_ids = {c["osm_id"] for c in named_candidates}
            candidates = named_candidates + [c for c in category_candidates if c["osm_id"] not in named_ids]
            # R-41 (Itinerary edit commands QA, finding H1): dedup against
            # every stop scheduled anywhere in the trip, not just this day
            # — mirrors itinerary_builder.py's whole-trip _duplicate_of
            # tracking (R-3/R-11), which this edit path never inherited.
            # Recomputed on every slot so a swap earlier in this same call
            # is visible to the next one, too. Without this, a themed swap
            # (measured real repro: "swap for something outdoors") can
            # reintroduce a landmark already sitting on a different day —
            # confirmed doing exactly that in 6/7 history-themed itineraries
            # in a real 300-command QA run.
            already_scheduled = _all_scheduled_stops(itin)
            # R-16 (F-11): defense-in-depth beyond the INTEREST_MAP additions
            # above — `fallback=True` means the constraint didn't match ANY
            # real category (poi_search_logic fell all the way through to
            # GENERAL_FALLBACK_CATEGORIES), so this candidate is not actually
            # what was asked for. Skip it rather than silently substituting
            # an unrelated category — surfaces as the honest "couldn't find
            # a suitable replacement" message below instead of a wrong-type
            # swap with no signal anything went wrong.
            valid_candidates = [
                p for p in candidates
                if not p.get("fallback") and _duplicate_of(p, already_scheduled) is None
            ]
            # LOW-1: for a cost constraint, only an explicitly "Free"-tagged
            # candidate counts -- see _is_free_fee's docstring for why an
            # untagged one is never treated as free.
            replacement = (
                next((p for p in valid_candidates if _is_free_fee(p.get("kb_entry_fee"))), None)
                if is_cost else
                (valid_candidates[0] if valid_candidates else None)
            )
            if replacement is None:
                searched_no_match = True
                continue
            new_stop = {**replacement, "travel_time_from_prev_min": old_stop.get("travel_time_from_prev_min", 0)}
            day[slot][idx] = new_stop
            swapped_desc.append(f"{old_stop['name']} → {new_stop['name']}")
            did_swap = True
        if did_swap:
            day["total_hours"] = _recompute_day_total(day)
            changed.append(key)
    if swapped_desc:
        return ("Swapped: " + "; ".join(swapped_desc) + ".", changed)
    if _is_cost_constraint(constraint):
        # LOW-1: no longer a blanket "can't filter by price" -- this DOES
        # check for an explicitly free-tagged option now, it just couldn't
        # find one nearby (only a small slice of the data carries verified
        # pricing at all, so a real "no free option found" is common).
        return ("I couldn't find a nearby option specifically tagged as free of charge — "
                "only a small number of places in my data have verified pricing, so I won't "
                "guess. I can still swap it for a different category if that helps.", [])
    if empty_slot_notes and not searched_no_match:
        where = " and ".join(empty_slot_notes)
        verb = "is" if len(empty_slot_notes) == 1 else "are"
        return (f"{where.capitalize()} {verb} currently empty — there's nothing there to swap. "
                "Want me to add something instead?", [])
    return ("Couldn't find a suitable replacement for that swap.", [])


def _apply_add(itin: dict, day_keys: list[str], target_slot: str, constraint: str, city: str, pace: str) -> tuple[str, list[str]]:
    """Insert one new POI into the best-fit day (most remaining budget) without displacing others."""
    # R-40: see the matching comment in _apply_swap() above — same honesty
    # check, before any search runs.
    absent_note = lookup_known_absent_place(constraint or "")
    if absent_note:
        return (absent_note, [])

    budget = PACE_HOURS.get(pace, 8.0)
    best_key = max(day_keys, key=lambda k: budget - itin[k]["total_hours"])
    day = itin[best_key]
    # R-41 (Itinerary edit commands QA, finding H1): dedup against every
    # stop scheduled anywhere in the trip, not just this day — see the
    # matching comment in _apply_swap() above for the real repro this fixes.
    already_scheduled = _all_scheduled_stops(itin)
    # R-41 (finding M1): a specific named place is tried first; the
    # category/interest search only ever fills in behind it.
    # Round 3 QA (E-5): normalize once, reuse for both searches -- see
    # _named_place_candidates' docstring and the matching fix in
    # _apply_swap() above for the real "indoors" -> spurious match this
    # inconsistency caused.
    # LOW-1 (Team Waypoint Voice-First UI review): a cost constraint ("add
    # something free") isn't a real INTEREST_MAP category either -- same
    # reasoning as _apply_swap()'s matching fix, see _is_free_fee's
    # docstring for why only an explicit "Free" tag counts.
    is_cost = _is_cost_constraint(constraint)
    norm_constraint = _normalize_constraint(constraint)
    named_candidates = _named_place_candidates(city, norm_constraint)
    category_candidates = poi_search_logic(city, [norm_constraint or "food"], top_n=10)
    named_ids = {c["osm_id"] for c in named_candidates}
    candidates = named_candidates + [c for c in category_candidates if c["osm_id"] not in named_ids]
    # R-16 (F-11): same fallback filter as _apply_swap() — don't add a POI
    # from an unmatched-category fallback search.
    valid_candidates = [
        p for p in candidates
        if not p.get("fallback") and _duplicate_of(p, already_scheduled) is None
    ]
    new_poi = (
        next((p for p in valid_candidates if _is_free_fee(p.get("kb_entry_fee"))), None)
        if is_cost else
        (valid_candidates[0] if valid_candidates else None)
    )
    if new_poi is None:
        if is_cost:
            return ("I couldn't find a nearby option specifically tagged as free of charge — "
                    "only a small number of places in my data have verified pricing, so I won't "
                    "guess. I can still add a place by category if that helps.", [])
        return ("Couldn't find a new place matching that request.", [])

    slot = target_slot if target_slot in DAY_SLOTS else "evening"
    prev_stops = day[slot]
    travel_min = _travel_time_min(prev_stops[-1], new_poi) if prev_stops else 0
    day[slot].append({**new_poi, "travel_time_from_prev_min": travel_min})
    day["total_hours"] = _recompute_day_total(day)

    # R-19 (Itinerary-Quality-Review-and-Recommendations.md F-14): appending
    # to an already-full day (itinerary_builder fills every day close to its
    # pace budget by design) almost always overflows, which used to make
    # "add X" fail outright with a rejection message that itself promised a
    # replace/move fallback apply_edit never actually performed. Do the
    # replace the message already promises: swap the new stop in for the
    # day's lowest-relevance existing stop (never a real landmark, mirroring
    # the eviction protection used elsewhere) instead of leaving the day
    # over budget for the post-hoc guard in apply_edit() to reject wholesale.
    # When nothing is safely evictable (e.g. the whole day is landmarks),
    # deliberately do NOT invent a new rejection path here — leave the
    # over-budget append as-is and let it fall through to apply_edit()'s own
    # existing budget guard below, exactly as it already did before this
    # fix (ok=False, itinerary rolled back to the untouched original) — that
    # guard is already correct and already tested (T-4.3); this fix only
    # needs to intervene for the cases it can genuinely improve on.
    if day["total_hours"] > budget + 0.01:
        new_stop_id = new_poi["osm_id"]

        def _evictable(scope_slots):
            return [
                (s_name, i, s) for s_name in scope_slots for i, s in enumerate(day[s_name])
                if s["osm_id"] != new_stop_id and s.get("relevance_score", 0) < LANDMARK_RELEVANCE_FLOOR
            ]

        evictable = _evictable([slot]) or _evictable(DAY_SLOTS)
        if not evictable:
            return (f"Added {new_poi['name']} to {best_key.replace('_', ' ')} {slot}.", [best_key])
        evict_slot, evict_idx, evicted = min(evictable, key=lambda c: c[2].get("relevance_score", 0.5))
        del day[evict_slot][evict_idx]
        day["total_hours"] = _recompute_day_total(day)
        return (
            f"{best_key.replace('_', ' ').title()} was full, so I replaced {evicted['name']} with "
            f"{new_poi['name']} in {slot}.",
            [best_key],
        )

    return (f"Added {new_poi['name']} to {best_key.replace('_', ' ')} {slot}.", [best_key])


# Round 3 QA (E-3, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): a
# request to change the SEQUENCE of stops already on the itinerary ("swap
# the order of Day 1's morning and afternoon plans") used to have no
# edit_type of its own -- the classifier's only "swap" concept meant
# replace-with-a-different-place, so these were misclassified into that
# path 16/20 times (returning the actively misleading "Couldn't find a
# suitable replacement for that swap" -- a message about a completely
# different operation) or misclassified as EXPLAIN entirely the other 4/20.
# intent_classifier.py now recognizes "reorder" as its own edit_type.
#
# MEDIUM-4 (Team Waypoint Voice-First UI review): the single most natural
# phrasing -- "move X earlier/later" -- is now a REAL move, not just an
# honest decline: intent_classifier.py extracts target_stop_name +
# direction for this shape, and this calls the exact same move_stop() the
# Day view's up/down buttons use (UX3-5), so a spoken command and a tapped
# button produce byte-for-byte identical results. Anything this can't
# confidently resolve -- no named stop, no clear direction, or a
# whole-slot-order swap like "swap the order of Day 1's morning and
# afternoon" -- still gets the original honest decline: broadening further
# risks silently moving the wrong stop, worse than an honest "not yet" for
# a feature this low-stakes.
def _apply_reorder(itin: dict, day_keys: list[str], target_stop_name: str = "", direction: str = "") -> tuple[str, list[str]]:
    if target_stop_name and direction in ("earlier", "later"):
        located = _find_stop_by_name(itin, target_stop_name, preferred_day_keys=day_keys)
        if located:
            day_key, slot, idx = located
            moved = move_stop(itin, day_key, slot, idx, -1 if direction == "earlier" else 1)
            if moved:
                return (f"Moved {target_stop_name} {direction}.", [day_key])
            edge = "start" if direction == "earlier" else "end"
            return (f"{target_stop_name} is already at the {edge} of the day — nowhere {direction} to move it.", [])
    return (
        "I can't reorder stops within a day from a typed or spoken command yet — "
        "but you can use the ↑ / ↓ buttons next to each stop in the Day view to move it.",
        [],
    )


def _apply_remove(itin: dict, day_keys: list[str], constraint: str, target_slot: str = "all") -> tuple[str, list[str]]:
    """Remove the first stop whose name or category matches the constraint,
    within the targeted slot(s) only."""
    # Live-usage report ("app isn't handling edit instructions well"): real
    # repro -- "Remove the restaurant from day 1 evening" ignored the
    # "evening" part entirely (target_slot was never a parameter here at
    # all), removed a DIFFERENT restaurant from an earlier slot in day 1,
    # got correctly caught as scope drift by check_edit_correctness one
    # layer up in agent.py, and the whole edit was rolled back -- so a
    # perfectly well-specified request silently did nothing. Restricting
    # the search to the targeted slot(s), the same way every other edit
    # type already does, fixes it at the source instead of relying on the
    # rollback safety net to mask it.
    target = (constraint or "").strip().lower()
    slots = _target_slots(target_slot)
    for key in day_keys:
        day = itin[key]
        for slot in slots:
            for i, stop in enumerate(day[slot]):
                if target and (target in stop.get("name", "").lower() or target == stop.get("category", "").lower()):
                    removed_name = stop["name"]
                    del day[slot][i]
                    day["total_hours"] = _recompute_day_total(day)
                    return (f"Removed {removed_name} from the itinerary.", [key])
    return (f"Couldn't find anything matching '{constraint}' to remove.", [])


def _apply_reduce_travel(itin: dict, city: str, pace: str) -> tuple[str, list[str]]:
    """Re-cluster every currently-scheduled stop geographically across the same number of days."""
    all_pois = [
        {k: v for k, v in stop.items() if k != "travel_time_from_prev_min"}
        for key in _all_day_keys(itin)
        for slot in DAY_SLOTS
        for stop in itin[key][slot]
    ]
    if not all_pois:
        return ("No stops to re-cluster.", [])

    days = len(_all_day_keys(itin))
    rebuilt = itinerary_builder_logic(all_pois, days=days, pace=pace)
    for key in _all_day_keys(itin):
        del itin[key]
    itin.update(rebuilt)
    return ("Re-clustered your stops to minimize travel time between them.", _all_day_keys(itin))


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def apply_edit(itinerary: dict, edit_intent: dict, pace: str = "moderate", city: str = "New Delhi") -> dict:
    """
    Apply a single EditIntent to the itinerary.
    Returns {"ok": bool, "itinerary": dict, "message": str, "changed_days": [str]}.
    On failure (unknown day, or a feasibility violation) the ORIGINAL itinerary
    is returned unchanged.
    """
    new_itin = copy.deepcopy(itinerary)
    target_day = edit_intent.get("target_day", "all")
    target_slot = edit_intent.get("target_slot", "all")
    edit_type = edit_intent.get("edit_type", "swap")
    constraint = edit_intent.get("constraint", "")

    day_keys = _target_days(new_itin, target_day)
    if not day_keys:
        return _fail(itinerary, f"Day {target_day} doesn't exist in this itinerary.")

    if edit_type == "relax":
        message, changed_days = _apply_relax(new_itin, day_keys, target_slot)
    elif edit_type == "swap":
        target_stop_name = edit_intent.get("target_stop_name", "")
        # Team Waypoint Voice-First UI review (HIGH-2): when the named
        # target resolves to 2+ real candidates ("swap the temple" with two
        # temples on the trip), don't guess and don't silently fall through
        # to the old broad day/slot-based path -- surface the real
        # candidates so the caller (agent.py) can ask the user which one
        # they meant, docx's "show tappable choices instead of guessing"
        # principle. Checked here, before _apply_swap(), so the ambiguous
        # case never reaches its (unrelated) internal name lookup at all.
        if target_stop_name:
            ref = resolve_stop_reference(new_itin, target_stop_name, preferred_day_keys=day_keys)
            if ref["status"] == "ambiguous":
                candidates = [
                    {
                        "day_key": key, "slot": slot, "idx": idx,
                        "name": new_itin[key][slot][idx]["name"],
                        "category": new_itin[key][slot][idx].get("category", ""),
                    }
                    for (key, slot, idx) in ref["candidates"][:4]  # cap at 4 tappable choices
                ]
                return {
                    "ok": False, "itinerary": itinerary,
                    "message": f"I found {len(candidates)} stops matching \"{target_stop_name}\" — which one did you mean?",
                    "changed_days": [], "needs_choice": True, "candidates": candidates,
                }
        message, changed_days = _apply_swap(new_itin, day_keys, target_slot, constraint, city, target_stop_name)
    elif edit_type == "add":
        message, changed_days = _apply_add(new_itin, day_keys, target_slot, constraint, city, pace)
    elif edit_type == "remove":
        message, changed_days = _apply_remove(new_itin, day_keys, constraint, target_slot)
    elif edit_type == "reduce_travel":
        message, changed_days = _apply_reduce_travel(new_itin, city, pace)
    elif edit_type == "reorder":
        message, changed_days = _apply_reorder(
            new_itin, day_keys, edit_intent.get("target_stop_name", ""), edit_intent.get("direction", ""),
        )
    else:
        return _fail(itinerary, f"Unknown edit type '{edit_type}'.")

    for key in changed_days:
        if not _within_budget(new_itin[key], pace):
            budget = PACE_HOURS.get(pace, 8.0)
            return _fail(
                itinerary,
                f"That would push {key.replace('_', ' ')} over the {budget}h budget. "
                "I can replace an existing stop instead, or move this to another day — want me to do that?",
            )
        long_leg = _over_long_leg(new_itin[key])
        if long_leg is not None:
            return _fail(
                itinerary,
                f"That would leave {key.replace('_', ' ')} with a long gap: {long_leg}. "
                "I can pick a closer option instead, or move this to another day — want me to do that?",
            )

    return {"ok": True, "itinerary": new_itin, "message": message, "changed_days": changed_days}
