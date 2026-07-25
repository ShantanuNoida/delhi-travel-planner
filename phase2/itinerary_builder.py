"""
Tool 2: Itinerary Builder MCP
Schedules candidate POIs into a day-wise itinerary with time slots.

Edge cases handled:
  EC-2.2 — strict daily time cap; excess POIs are dropped with a message
  EC-2.3 — geographic clustering keeps nearby POIs on the same day
  EC-2.5 — detects when daily budget is too short for even one stop

Also enforces the "no single travel leg > 45 min" rule from Phase 5's
Feasibility Eval at build time, so an itinerary doesn't need a later edit
just to fix a leg the builder could have avoided in the first place.
"""

import difflib
import json
import os
import re
from mcp.server.fastmcp import FastMCP

# Reused for baseline meal-guarantee candidates (see _load_baseline_restaurants
# below) so a restaurant filled in purely to guarantee meal coverage gets the
# exact same real-duration logic (including any KB-matched duration) as one
# that arrived through the normal interest-driven candidate pool — same
# directory, no import cycle (poi_search.py never imports from this module).
from poi_search import _visit_duration

# High Priority recommendation #5 (AI-Evaluation-Rubric.md, "MCP Usage &
# System Design"): _haversine_km was duplicated verbatim in both this file
# and travel_time.py. Reusing the one in travel_time.py (same directory, no
# import cycle -- travel_time.py has no imports from this module) removes
# that duplication with zero behavior change, since it's a pure geometry
# formula with no dependency on either file's own state.
#
# Deliberately NOT wired further than this: _travel_time_min() below uses
# its own simpler flat-speed-per-leg model, while travel_time.py's
# travel_time_estimator MCP tool uses a mode-aware speed model (walk/auto/
# metro each at a different km/h). _travel_mode()'s own docstring already
# documents that gap as an intentional, previously-made decision -- other
# phases' tests depend on _travel_time_min's exact existing minute values,
# so merging the two speed models would be a real behavior change to
# scheduled itineraries' timing, not a pure refactor. Left as-is.
from travel_time import _haversine_km

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PACE_HOURS = {"relaxed": 6.0, "moderate": 8.0, "intensive": 10.0}

# Time slot definitions (hour of day)
SLOTS = {
    "morning":   (9,  12),   # 9 AM – 12 PM
    "afternoon": (12, 17),   # 12 PM – 5 PM
    "evening":   (17, 21),   # 5 PM – 9 PM
}
SLOT_CAPACITY_MIN = {
    "morning":   180,  # 3 h
    "afternoon": 300,  # 5 h
    "evening":   240,  # 4 h
}

# Categories preferred per slot.
SLOT_PREFERENCE = {
    "morning":   {"monument", "museum", "temple", "mosque", "church", "gurdwara", "restaurant"},
    "afternoon": {"park", "market", "monument", "restaurant"},
    "evening":   {"restaurant", "market"},
}

# R-6 (Itinerary-Quality-Review-and-Recommendations.md F-6): a restaurant
# used to be labeled "breakfast"/"lunch"/"dinner" purely by which slot it
# landed in — e.g. a thali canteen (a lunch/dinner institution) tagged
# "breakfast" just because the scheduler happened to place it in the
# morning slot. That's a menu claim ("this place serves breakfast") this
# app has no real per-venue data to back up. Fixed per the review's own
# suggested alternative: label by the stop's actual computed arrival clock
# time instead — genuinely grounded (derived from real visit-duration/
# travel-time estimates already used for scheduling), asserts nothing about
# what a venue serves, still tells the traveler when they'll be eating.
def _format_clock(total_min: int) -> str:
    total_min %= 24 * 60
    hour, minute = divmod(total_min, 60)
    period = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {period}"

PHASE1_DATA = os.path.join(os.path.dirname(__file__), "..", "phase1", "data", "pois.json")

# Delhi area centroids for geographic zone assignment (EC-2.3)
DELHI_ZONES = {
    "old_delhi":    (28.656, 77.232),
    "central":      (28.630, 77.220),
    "south":        (28.530, 77.220),
    "south_west":   (28.510, 77.080),
    "north":        (28.730, 77.220),
    "east":         (28.640, 77.310),
}

MAX_SAME_DAY_DISTANCE_KM = 15.0
TRAVEL_BUFFER_MIN = 20  # default travel time between stops if estimator not available
MAX_TRAVEL_LEG_MIN = 45  # no single leg between consecutive stops may exceed this

# R-4: relevance_score cutoff (matches poi_search.py's LANDMARK_SCORE_FLOOR)
# used to route landmark-tier POIs ahead of filler POIs within a day, so
# they're scheduled while budget is still fresh rather than dropped for it.
LANDMARK_RELEVANCE_FLOOR = 0.8

# R-10 (Itinerary-Quality-Review-and-Recommendations.md F-9): the "market"
# OSM category is a wide mix of genuinely notable heritage bazaars
# (Chandni Chowk, Khari Baoli Spice Market) and ordinary suburban shopping
# malls/retail chains (SAYA Status Mall, D'mart, Croma) — the latter are
# common, well-marketed, and unremarkable to a tourist, the opposite of a
# "hidden gem," yet they scored just as low on relevance_score as a genuine
# find simply for not being a named landmark. Real repro: SAYA Status Mall
# tagged a hidden gem in 3 review scenarios. Excluded by name pattern
# rather than trying to positively assert what IS special (no real data
# exists to back that up) — conservative, name-based, only ever narrows
# eligibility, never invents a "this is special" claim.
GENERIC_VENUE_MARKERS = (
    "mall", "plaza", "mega", "mart", "store", "shopping complex",
    "city center", "city centre",
)


def _is_generic_commercial_venue(poi: dict) -> bool:
    if poi["category"] != "market":
        return False
    name = poi["name"].lower()
    return any(marker in name for marker in GENERIC_VENUE_MARKERS)

# QA-6/R-11: OSM sometimes maps the same real place twice under slightly
# different spellings (e.g. "Shanker's International Doll Museum" and
# "Shankar's Doll Museum" are two separate node records ~20m apart). Neither
# signal alone is safe: name similarity alone would wrongly merge distinct
# nearby POIs that just share words ("Shankar Market" vs "Shankar's Doll
# Museum" scores 0.61); proximity alone would wrongly merge distinct POIs
# that are genuinely co-located (a restaurant next to a monument). Requiring
# same category + tight proximity + high name similarity together is what
# distinguishes "same place, two records" from "two different places".
DUPLICATE_PROXIMITY_KM = 0.15   # ~150m — same building/entrance, not just "nearby"
DUPLICATE_NAME_SIMILARITY = 0.5  # difflib ratio on normalized names, when categories match
# R-3 (Itinerary-Quality-Review-and-Recommendations.md F-3): the dataset
# stores some real places under multiple OSM records/categories — e.g. Jama
# Masjid as both "mosque" and "monument", Safdarjung's Tomb as both "park"
# and "monument" — and requiring same-category let these schedule twice
# (verified: Jama Masjid scheduled 3 times in one real 4-day trip). Dropping
# the category requirement entirely would be unsafe on its own (a
# same-category match plus a merely-nearby, differently-named place could
# false-positive), so cross-category matches require a much higher name
# similarity instead — there's no category match left to lean on as a
# safety net, so name similarity alone has to carry more weight.
DUPLICATE_NAME_SIMILARITY_CROSS_CATEGORY = 0.85


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nearest_zone(lat: float, lon: float) -> str:
    return min(
        DELHI_ZONES,
        key=lambda z: _haversine_km(lat, lon, *DELHI_ZONES[z]),
    )


def _travel_time_min(poi_a: dict, poi_b: dict) -> int:
    """Heuristic travel time between two POIs in Delhi (minutes)."""
    dist = _haversine_km(poi_a["lat"], poi_a["lon"], poi_b["lat"], poi_b["lon"])
    road_dist = dist * 1.4  # road vs straight-line factor for Delhi
    speed_kmh = 15.0        # average Delhi traffic speed
    minutes = int((road_dist / speed_kmh) * 60)
    return max(minutes, 10)  # minimum 10 min


def _travel_mode(road_km: float) -> str:
    """
    Suggested transport mode for a leg, using the same distance thresholds
    as the standalone Travel Time Estimator tool (travel_time.py) — kept as
    a separate helper here rather than changing _travel_time_min's existing
    minute calculation, which other phases' tests already depend on.
    """
    if road_km < 1.5:
        return "walk"
    if road_km < 4.0:
        return "auto"
    return "metro"


_reference_pois_cache: dict[str, list[dict]] | None = None
_REFERENCE_CATEGORIES = ("hospital", "pharmacy", "metro_station")


def _load_reference_pois() -> dict[str, list[dict]]:
    """
    Hospitals, pharmacies, and metro stations from the full POI dataset —
    independent of the caller's interest-filtered `pois` list, since safety
    and transit info should always be available regardless of what the
    traveler is interested in. Metro-station nearest-lookup is a
    distance-based substitute for the OTD Delhi GTFS integration (real
    transit times), which requires portal registration this project can't
    complete automatically — see delhi-additional-data-sources.md.
    """
    global _reference_pois_cache
    if _reference_pois_cache is not None:
        return _reference_pois_cache
    if not os.path.exists(PHASE1_DATA):
        _reference_pois_cache = {cat: [] for cat in _REFERENCE_CATEGORIES}
        return _reference_pois_cache
    with open(PHASE1_DATA, encoding="utf-8") as f:
        all_pois = json.load(f)
    _reference_pois_cache = {
        cat: [p for p in all_pois if p.get("category") == cat]
        for cat in _REFERENCE_CATEGORIES
    }
    return _reference_pois_cache


def _nearest_summary(lat: float, lon: float, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    nearest = min(candidates, key=lambda p: _haversine_km(lat, lon, p["lat"], p["lon"]))
    return {
        "name": nearest["name"],
        "distance_km": round(_haversine_km(lat, lon, nearest["lat"], nearest["lon"]), 2),
    }


# --------------------------------------------------------------------------- #
# Meal coverage guarantee (breakfast/lunch/dinner every day, near the venue)
# --------------------------------------------------------------------------- #

_baseline_restaurants_cache: list[dict] | None = None

# "Near the venue" per the explicit request this guarantees against — not
# just anywhere in Delhi. Tighter than MAX_SAME_DAY_DISTANCE_KM (15.0, the
# same-day zone-clustering cap): a day's OTHER stops are already
# zone-clustered, but a "nearby" meal should read as a short hop from them,
# not merely "technically in the same part of the city."
MEAL_PROXIMITY_CAP_KM = 3.0

# Minutes reserved per not-yet-filled meal slot during the main scheduling
# loop (~75min restaurant visit + a modest nearby-travel allowance) — see
# the reservation logic in the main loop below for why this exists.
MEAL_RESERVE_MIN_PER_SLOT = 90

# A small, bounded amount the meal-coverage guarantee is allowed to push a
# day past its normal budget, once every eviction option (a genuine filler
# stop, never a landmark or another meal) has already been exhausted.
# Observed directly: a real day landed just 5 minutes short of fitting a
# needed dinner with nothing left to evict — treating "guarantee a meal
# every slot" as a marginally harder constraint than the general sight-
# seeing budget (a "moderate" day running 8h25m instead of a strict 8h00m
# to fit a real dinner) is a reasonable trade a traveler would actually
# make, and is bounded so it can never let meals balloon a day arbitrarily.
MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN = 30


def _load_baseline_restaurants() -> list[dict]:
    """
    Restaurant-category POIs from the full dataset, independent of the
    caller's interest-filtered `pois` list — meal coverage should always be
    available regardless of the traveler's stated interests. Without this,
    a history+architecture trip (neither maps to "restaurant" in
    poi_search.py's INTEREST_MAP) has zero restaurant candidates anywhere
    in its input, so the normal scheduling loop can't seat a single meal no
    matter how the rest of the logic works — confirmed empirically: a real
    2-day history+architecture build scheduled 0 restaurants across both
    days before this fix.

    Shaped into the same schedulable stop-dict fields poi_search_logic()
    produces, using the identical duration logic (_visit_duration, real
    KB-matched duration where one exists) so a baseline-filled meal is
    scheduled exactly as accurately as an interest-driven one — just with a
    flat, unranked relevance_score, since it was never scored against any
    stated interest.
    """
    global _baseline_restaurants_cache
    if _baseline_restaurants_cache is not None:
        return _baseline_restaurants_cache
    if not os.path.exists(PHASE1_DATA):
        _baseline_restaurants_cache = []
        return _baseline_restaurants_cache
    with open(PHASE1_DATA, encoding="utf-8") as f:
        all_pois = json.load(f)
    _baseline_restaurants_cache = [
        {
            "osm_id": p["osm_id"],
            "name": p["name"],
            "category": "restaurant",
            "lat": p["lat"],
            "lon": p["lon"],
            "opening_hours": p.get("opening_hours", "unknown"),
            "visit_duration_min": _visit_duration(p),
            "relevance_score": 0.5,
            "fallback": False,
        }
        for p in all_pois
        if p.get("category") == "restaurant"
    ]
    return _baseline_restaurants_cache


def _nearest_unused_restaurant(
    slots: dict[str, list[dict]],
    all_scheduled_stops: list[dict],
) -> dict | None:
    """
    Closest not-yet-scheduled restaurant to a day's other stops, for the
    meal-coverage guarantee below. Returns None — rather than fabricating a
    "nearby" match — when nothing real is within MEAL_PROXIMITY_CAP_KM or
    the day has no other stops yet to measure distance from; staying honest
    about a genuine coverage gap instead of suggesting a restaurant that
    isn't actually convenient to the day's plan.
    """
    reference_stops = [s for stops in slots.values() for s in stops]
    if not reference_stops:
        return None
    centroid_lat = sum(s["lat"] for s in reference_stops) / len(reference_stops)
    centroid_lon = sum(s["lon"] for s in reference_stops) / len(reference_stops)

    # R-21 (Itinerary-Quality-Review-and-Recommendations.md F-16): the
    # same-name-restaurant check now lives centrally in `_duplicate_of`
    # itself (extended 2026-07-17 after live-matrix re-testing showed the
    # bug persisting via the MAIN scheduling loop too, not just meal-fill —
    # see that function's own comment for the full "Karim's" measurement),
    # so the call below already covers it — no separate check needed here.
    best, best_dist = None, None
    for cand in _load_baseline_restaurants():
        if _duplicate_of(cand, all_scheduled_stops) is not None:
            continue
        dist = _haversine_km(centroid_lat, centroid_lon, cand["lat"], cand["lon"])
        if dist > MEAL_PROXIMITY_CAP_KM:
            continue
        if best is None or dist < best_dist:
            best, best_dist = cand, dist
    return best


def _fill_missing_meal_slots(
    slots: dict[str, list[dict]],
    slot_load: dict[str, int],
    day_total_min: int,
    all_scheduled_stops: list[dict],
    restaurant_slots_used: set[str],
    budget_min: int,
    max_meals: int = 3,
) -> tuple[int, list[str]]:
    """
    Post-processing guarantee pass, run once per day after the normal
    interest-driven scheduling loop: fills any meal slot still without a
    restaurant, using the nearest real, not-yet-scheduled restaurant to
    that day's other stops. Never overrides a restaurant the interest-
    driven pass already chose (only touches slots absent from
    restaurant_slots_used) and never fabricates a suggestion — a slot with
    no real nearby candidate is left unfilled rather than forced.

    If adding the guaranteed meal would push the day over budget, evicts
    the single lowest-relevance stop already in that slot to make room —
    the same swap-to-guarantee pattern R-1 already established for landmark
    representation — but a stop is only evictable if it's genuine filler
    (relevance_score below LANDMARK_RELEVANCE_FLOOR): a meal guarantee must
    never come at the cost of R-1's landmark guarantee, so a slot holding
    only protected landmarks has nothing safe to evict and that slot's meal
    is left unfilled rather than bumping something more important. Mutates
    `slots`/`slot_load`/`all_scheduled_stops`/`restaurant_slots_used` in
    place; returns the updated day_total_min
    (immutable) plus a list of human-readable notes for logging.
    """
    filled_notes: list[str] = []
    # User-reported ("too many restaurants... even when not explicitly
    # called for"): when max_meals < 3 (no food interest stated -- see the
    # caller's own comment), prioritize afternoon (lunch) as the single
    # most realistic guaranteed meal break during sightseeing. Breakfast is
    # commonly eaten at the hotel and dinner is often handled independently
    # after the day's stops end; skipping lunch entirely on a full
    # sightseeing day is the scenario most likely to actually inconvenience
    # a traveler, so it's the one slot still worth guaranteeing.
    slot_priority = ("morning", "afternoon", "evening") if max_meals >= 3 else ("afternoon", "evening", "morning")
    for slot in slot_priority:
        if len(restaurant_slots_used) >= max_meals:
            break
        if slot in restaurant_slots_used:
            continue
        candidate = _nearest_unused_restaurant(slots, all_scheduled_stops)
        if candidate is None:
            continue

        duration = candidate["visit_duration_min"]
        prev_stops = slots[slot]
        travel_min = _travel_time_min(prev_stops[-1], candidate) if prev_stops else 0
        if travel_min > MAX_TRAVEL_LEG_MIN:
            continue  # not actually a short hop in travel-time terms either

        if day_total_min + duration + travel_min > budget_min:
            # Search the WHOLE day, not just this slot, for a genuine
            # filler stop to evict — day_total_min is a whole-day budget
            # constraint, so a too-tight *target* slot (e.g. currently
            # empty, nothing local to free up — the exact case that first
            # exposed this: an empty evening slot 5 minutes short of
            # budget, with the only landmarks to evict sitting in morning/
            # afternoon) can still be resolved by freeing budget from
            # filler elsewhere in the day. Still never evicts a landmark
            # (R-1's guarantee) — only genuine filler is fair game. Also
            # never evicts a restaurant: a baseline-filled meal scores
            # 0.5 (below LANDMARK_RELEVANCE_FLOOR), so without this
            # exclusion an earlier slot's just-guaranteed meal is "genuine
            # filler" by that same test — evicting it to fund a later
            # slot's meal is a net-zero shuffle, not a real fix, and was
            # observed doing exactly that (a morning meal got evicted to
            # fund evening's, leaving morning newly empty).
            evict_slot, evict_idx, evict_score = None, None, None
            for s_name, s_stops in slots.items():
                for i, s in enumerate(s_stops):
                    if s.get("category") == "restaurant":
                        continue
                    score = s.get("relevance_score", 0.5)
                    if score < LANDMARK_RELEVANCE_FLOOR and (evict_score is None or score < evict_score):
                        evict_slot, evict_idx, evict_score = s_name, i, score
            if evict_slot is not None:
                evicted = slots[evict_slot].pop(evict_idx)
                evicted_cost = evicted["visit_duration_min"] + evicted.get("travel_time_from_prev_min", 0)
                slot_load[evict_slot] = slot_load.get(evict_slot, 0) - evicted_cost
                day_total_min -= evicted_cost
                if evicted in all_scheduled_stops:
                    all_scheduled_stops.remove(evicted)
                # `prev_stops` is a reference into `slots[slot]` — if
                # evict_slot == slot this already reflects the eviction;
                # if not, travel_min for the target slot is unaffected, but
                # recomputing unconditionally is cheap and always correct.
                travel_min = _travel_time_min(prev_stops[-1], candidate) if prev_stops else 0

        if day_total_min + duration + travel_min > budget_min + MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN:
            continue  # still doesn't fit even after eviction + the small overrun allowance — stay honest, skip

        mode = None
        if prev_stops:
            road_km = _haversine_km(prev_stops[-1]["lat"], prev_stops[-1]["lon"], candidate["lat"], candidate["lon"]) * 1.4
            mode = _travel_mode(road_km)
        arrival_min = SLOTS[slot][0] * 60 + slot_load.get(slot, 0) + travel_min
        stop = {
            **candidate,
            "travel_time_from_prev_min": travel_min,
            "travel_mode_from_prev": mode,
            "arrival_time": _format_clock(arrival_min),
            "meal": f"meal ~{_format_clock(arrival_min)}",
        }
        slots[slot].append(stop)
        all_scheduled_stops.append(stop)
        slot_load[slot] = slot_load.get(slot, 0) + duration + travel_min
        day_total_min += duration + travel_min
        restaurant_slots_used.add(slot)
        filled_notes.append(f"{candidate['name']} ({slot})")
    return day_total_min, filled_notes


def _normalize_for_dedup(name: str) -> str:
    """Lowercase, strip possessives/punctuation, collapse whitespace — for
    fuzzy duplicate comparison only (not a display name)."""
    name = name.lower()
    name = re.sub(r"['’]s\b", "", name)  # possessive: "shanker's" -> "shanker"
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _duplicate_of(poi: dict, scheduled_stops: list[dict]) -> dict | None:
    """
    Returns the already-scheduled stop this POI is a likely duplicate of, or
    None. Checks proximity + name similarity regardless of category (R-3) —
    same category alone was too narrow a gate (see DUPLICATE_NAME_SIMILARITY
    comment) — and callers now pass every stop scheduled so far across the
    WHOLE trip, not just the current day (R-3), since the dataset's
    duplicate-record problem isn't confined to a single day. See QA-6/R-11.
    """
    norm = _normalize_for_dedup(poi["name"])
    for stop in scheduled_stops:
        # R-21, extended (Itinerary-Quality-Review-and-Recommendations.md
        # F-16, live-matrix re-verification, 2026-07-17): a real chain
        # restaurant ("Karim's" has 7 OSM records genuinely 3.7-27km apart,
        # measured — real different branches, not mistagged duplicates) can
        # get independently picked on two different days once R-36 gave it
        # landmark-tier priority for ANY day's food-related interest, not
        # just meal-fill — the original fix only covered meal-fill's own
        # restaurant selection. Proximity correctly leaves distant branches
        # as different *places*; repeating the same restaurant *brand*
        # across one trip is still undesirable regardless of which branch.
        # Scoped to restaurant-category only — a "Central Market" appearing
        # in genuinely different, distant neighborhoods is a different,
        # legitimate case than a repeated chain brand.
        if poi["category"] == "restaurant" and stop.get("category") == "restaurant" and _normalize_for_dedup(stop["name"]) == norm:
            return stop
        if _haversine_km(stop["lat"], stop["lon"], poi["lat"], poi["lon"]) > DUPLICATE_PROXIMITY_KM:
            continue
        similarity = difflib.SequenceMatcher(None, norm, _normalize_for_dedup(stop["name"])).ratio()
        threshold = (
            DUPLICATE_NAME_SIMILARITY if stop["category"] == poi["category"]
            else DUPLICATE_NAME_SIMILARITY_CROSS_CATEGORY
        )
        if similarity >= threshold:
            return stop
    return None


def _candidate_slots(poi: dict, slot_load: dict[str, int]) -> list[str]:
    """
    Ranks time slots for a POI by capacity fit: preferred-category slots (or
    any slot under half capacity) first, then any other slot with room.
    Does not check travel-leg length or daily budget — the caller tries each
    candidate in order and skips ones that would violate those.
    """
    duration = poi["visit_duration_min"]
    pass1 = []
    for slot in ("morning", "afternoon", "evening"):
        preferred = poi["category"] in SLOT_PREFERENCE[slot]
        cap = SLOT_CAPACITY_MIN[slot]
        used = slot_load.get(slot, 0)
        if used + duration <= cap and (preferred or used < cap // 2):
            pass1.append(slot)
    pass2 = [
        slot for slot in ("morning", "afternoon", "evening")
        if slot not in pass1 and slot_load.get(slot, 0) + duration <= SLOT_CAPACITY_MIN[slot]
    ]
    return pass1 + pass2


def _cluster_pois_into_days(pois: list[dict], days: int) -> list[list[dict]]:
    """
    EC-2.3: Group POIs by geographic zone, then assign entire zone-groups to
    days. All POIs from the same zone go to the same day, keeping
    consecutive stops close.

    R-4 (Itinerary-Quality-Review-and-Recommendations.md F-5): zones used to
    be assigned to days by round-robin *zone order* alone, ignoring how much
    is actually in each zone — a zone with 2 matching POIs got its own day
    exactly like a zone with 15, so a real 4-day trip could land a 1.25h day
    next to a 7h one purely because the sparse zone's "turn" came up.
    Switched to greedy load-balancing: sort zones by total estimated visit
    time (largest first) and assign each *whole* zone to whichever day
    currently has the least scheduled so far. This is the standard greedy
    heuristic for balanced number-partitioning — not optimal, but reliably
    much closer to even than round-robin-by-order, while still keeping
    every zone's POIs together on one day (the original EC-2.3 intent).
    """
    by_zone: dict[str, list[dict]] = {z: [] for z in DELHI_ZONES}
    for poi in pois:
        zone = _nearest_zone(poi["lat"], poi["lon"])
        by_zone[zone].append(poi)

    zone_order = sorted(
        (z for z in DELHI_ZONES if by_zone[z]),
        key=lambda z: sum(p["visit_duration_min"] for p in by_zone[z]),
        reverse=True,
    )

    buckets: list[list[dict]] = [[] for _ in range(days)]
    day_load_min = [0] * days
    for zone in zone_order:
        target_day = min(range(days), key=lambda d: day_load_min[d])
        buckets[target_day].extend(by_zone[zone])
        day_load_min[target_day] += sum(p["visit_duration_min"] for p in by_zone[zone])

    return buckets


def _nn_route(items: list[dict], start_point: dict | None = None) -> list[dict]:
    """Greedy nearest-neighbor walk over items. If start_point is given, the
    walk's adjacency starts from it (start_point itself is not included in
    the returned route); otherwise the walk starts from items[0]."""
    if not items:
        return []
    remaining = items[:]
    if start_point is None:
        route = [remaining.pop(0)]
    else:
        route = []
    last = route[-1] if route else start_point
    while remaining:
        nxt = min(remaining, key=lambda p: _haversine_km(last["lat"], last["lon"], p["lat"], p["lon"]))
        remaining.remove(nxt)
        route.append(nxt)
        last = nxt
    return route


def _order_by_nearest_neighbor(bucket: list[dict]) -> list[dict]:
    """
    R-4: orders a day's candidate POIs into a sensible walking/driving route
    instead of leaving them in whatever order they arrived in —
    round-robin-by-category interleaving from poi_search.py has no
    geographic awareness, so an unordered bucket could route a day across
    the city and back (e.g. Old Delhi -> south Delhi -> Old Delhi again)
    even though every stop is nominally in the same zone-assigned day. This
    only reorders candidates BEFORE scheduling; the existing
    per-slot/budget/max-leg logic below fills slots strictly in this order
    and drops whatever doesn't fit once the day's budget is used up.

    That last part is why a plain single nearest-neighbor walk is unsafe: a
    day's bucket routinely holds more total visit-duration than the daily
    budget allows (that's normal — not every candidate is meant to survive),
    so SOMETHING gets dropped regardless of order. A pure distance walk can
    place a MUST_SEE landmark after several long filler stops purely because
    it happened to be geographically adjacent to them, and it then gets
    dropped for budget — silently undoing R-1's landmark guarantee (observed:
    India Gate and Jama Masjid dropped from a scenario that had 5/5 icons
    before this reordering existed). To keep the guarantee, landmark-tier
    POIs (relevance_score >= LANDMARK_RELEVANCE_FLOOR, i.e. R-1's
    MUST_SEE/HIGH_PROFILE tiers) are routed as a group FIRST — so they're
    processed while the day's budget is still fresh — then filler POIs are
    walked nearest-neighbor starting from wherever the landmark route ended.
    Both legs are still geographically coherent internally; only the
    landmarks-before-filler ordering is not purely distance-driven.
    """
    if len(bucket) <= 2:
        return bucket
    landmarks = [p for p in bucket if p.get("relevance_score", 0) >= LANDMARK_RELEVANCE_FLOOR]
    filler = [p for p in bucket if p.get("relevance_score", 0) < LANDMARK_RELEVANCE_FLOOR]
    landmark_route = _nn_route(landmarks)
    filler_route = _nn_route(filler, start_point=landmark_route[-1] if landmark_route else None)
    return landmark_route + filler_route


# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------

def itinerary_builder_logic(
    pois: list[dict],
    days: int,
    pace: str = "moderate",
    daily_hours: float | None = None,
    travel_dates: list[str] | None = None,
) -> dict:
    """Core itinerary building logic — callable directly for testing."""
    if not pois:
        raise ValueError("No POIs provided. Run POI Search first.")
    if days < 1 or days > 4:
        raise ValueError("Trip must be between 1 and 4 days.")

    budget_hours = daily_hours if daily_hours is not None else PACE_HOURS.get(pace, 8.0)
    budget_min = int(budget_hours * 60)
    travel_dates = travel_dates or []

    # User-reported ("the application fills in too many restaurants and food
    # options, even when not explicitly called for"): real repro -- an
    # "architecture"-only trip (no food/cuisine/eating interest stated at
    # all) still got 3 restaurants out of 5 stops EVERY day (60%), because
    # the meal-coverage guarantee below always targeted all 3 meal slots
    # regardless of what the traveler actually asked for, and the main
    # loop's reservation logic (below) pre-emptively set aside up to half
    # the day's budget for those meals before a single interest-driven stop
    # was even considered. `pois` is already the caller's INTEREST-FILTERED
    # pool (poi_search.py's INTEREST_MAP only maps "restaurant" from food/
    # cuisine/eating/dining-family interest words) -- so if it contains ANY
    # restaurant, food was genuinely part of what was asked for (keep full
    # 3-meal coverage); if it contains none, the guarantee is scaled down to
    # a single meal per day -- enough that a trip is never completely
    # unfed (the original, still-valid concern this guarantee exists for),
    # without turning an architecture trip into a food tour.
    max_guaranteed_meals = 3 if any(p.get("category") == "restaurant" for p in pois) else 1

    # EC-2.5: check if budget allows even one stop
    min_duration = min(p["visit_duration_min"] for p in pois)
    if min_duration + TRAVEL_BUFFER_MIN > budget_min:
        raise ValueError(
            f"Daily budget ({budget_hours}h) is too short for even one stop "
            f"(min visit {min_duration}min + travel {TRAVEL_BUFFER_MIN}min). "
            "Please extend available hours or reduce pace."
        )

    # Geographic clustering into days (EC-2.3)
    day_buckets = _cluster_pois_into_days(pois, days)

    itinerary: dict = {}
    # R-3: tracks every stop scheduled across the WHOLE trip so far, not
    # just the current day — the dataset's duplicate-record problem (e.g.
    # Jama Masjid as both "mosque" and "monument") isn't confined to one
    # day; a real 4-day trip scheduled it 3 times, once on each of 3
    # different days, which a per-day-only check could never catch.
    all_scheduled_stops: list[dict] = []

    for day_idx, raw_bucket in enumerate(day_buckets):
        day_key = f"day_{day_idx + 1}"
        date_str = travel_dates[day_idx] if day_idx < len(travel_dates) else ""
        # R-4: route-order the day's candidates so the greedy slot-assignment
        # below naturally visits nearby stops back-to-back instead of
        # whatever order round-robin category interleaving happened to
        # leave them in (which had no geographic awareness and could route
        # a day across the city and back).
        bucket = _order_by_nearest_neighbor(raw_bucket)

        slots: dict[str, list[dict]] = {"morning": [], "afternoon": [], "evening": []}
        slot_load: dict[str, int] = {"morning": 0, "afternoon": 0, "evening": 0}
        day_total_min = 0
        dropped: list[str] = []
        duplicates_skipped: list[str] = []
        # R-6 (Itinerary-Quality-Review-and-Recommendations.md F-6): without
        # this, a food-heavy day could pile several restaurants into one
        # slot (observed: 2 tagged "breakfast", 3 tagged "lunch" the same
        # morning/afternoon) since slot capacity is time-based, not a stop-
        # type count. Capping one restaurant per slot forces at most 3/day
        # and, since each slot still has room left over, the scheduler
        # naturally fills that remaining capacity with non-food candidates
        # from the same bucket — threading markets/monuments between meals
        # instead of stacking sit-down stops back-to-back.
        restaurant_slots_used: set[str] = set()

        for poi in bucket:
            duplicate = _duplicate_of(poi, all_scheduled_stops)
            if duplicate is not None:
                # QA-6/R-11 + R-3: same real place already scheduled earlier
                # in this trip (any day) under a different spelling or OSM
                # category — skip rather than schedule it twice. Not counted
                # as "dropped" (that's a budget message) since this doesn't
                # cost any budget; the next bucket POI naturally backfills
                # the slot that would otherwise have gone here.
                # Plain ASCII only — this string can flow into a plain print()
                # (e.g. via agent._say() when TTS is off), and Windows' default
                # console codepage can't encode "≈", which crashed a real build
                # during R-14 testing.
                duplicates_skipped.append(f'"{poi["name"]}" (matches "{duplicate["name"]}")')
                continue

            duration = poi["visit_duration_min"]
            is_restaurant = poi["category"] == "restaurant"
            # Meal-coverage guarantee, part 1: reserve room for a nearby
            # meal in each not-yet-filled slot *during* this loop, not just
            # in the post-processing guarantee pass below. Without this, a
            # landmark-heavy day can (and did, confirmed by direct testing —
            # a real history+architecture day spent 438 of its 480-minute
            # budget on 4 landmarks before the guarantee pass ever got a
            # turn) consume the entire budget before meals get any chance
            # at all, and the guarantee pass can't fix that afterward
            # without evicting something — which R-1's landmark protection
            # correctly refuses to do. Only applies to non-restaurant
            # candidates, and only reserves for slots still genuinely
            # empty of a meal, shrinking automatically as real meals (from
            # this loop or the guarantee pass) fill in — never blocks a
            # restaurant that's part of the interest-driven pool itself.
            # Scaled by max_guaranteed_meals (see its own comment near the
            # top of this function) so a no-food-interest trip doesn't
            # reserve room for meals the guarantee pass was never going to
            # add in the first place.
            empty_meal_slots = max(0, max_guaranteed_meals - len(restaurant_slots_used))
            effective_budget_min = budget_min if is_restaurant else max(
                budget_min - empty_meal_slots * MEAL_RESERVE_MIN_PER_SLOT,
                budget_min // 2,  # never reserve away more than half the day
            )

            chosen_slot = None
            chosen_travel = 0
            chosen_mode = "walk"
            for slot in _candidate_slots(poi, slot_load):
                if poi["category"] == "restaurant" and slot in restaurant_slots_used:
                    continue  # R-6: this slot's one meal is already taken — try another slot
                prev_stops = slots[slot]
                travel_min = _travel_time_min(prev_stops[-1], poi) if prev_stops else 0

                if travel_min > MAX_TRAVEL_LEG_MIN:
                    continue  # this leg alone is too long — try another slot instead
                if day_total_min + duration + travel_min > effective_budget_min:
                    continue  # EC-2.2: would overflow the day (or the meal reservation)

                chosen_slot = slot
                chosen_travel = travel_min
                if prev_stops:
                    road_km = _haversine_km(prev_stops[-1]["lat"], prev_stops[-1]["lon"], poi["lat"], poi["lon"]) * 1.4
                    chosen_mode = _travel_mode(road_km)
                break

            if chosen_slot is None:
                dropped.append(poi["name"])
                continue

            stop = {
                **poi,
                "travel_time_from_prev_min": chosen_travel,
                "travel_mode_from_prev": chosen_mode if slots[chosen_slot] else None,
            }
            # R-25 (Itinerary-Quality-Review... round 4 UX benchmark, UX-22):
            # a real per-stop clock time, not just a duration — same
            # computation R-6 already used for the restaurant-only "meal"
            # timestamp (slot start hour + minutes already used in that slot
            # + travel to reach this stop), now stored for every stop so the
            # UI can render an actual timeline instead of a duration list.
            arrival_min = SLOTS[chosen_slot][0] * 60 + slot_load.get(chosen_slot, 0) + chosen_travel
            stop["arrival_time"] = _format_clock(arrival_min)
            if poi["category"] == "restaurant":
                stop["meal"] = f"meal ~{_format_clock(arrival_min)}"
                restaurant_slots_used.add(chosen_slot)

            slots[chosen_slot].append(stop)
            all_scheduled_stops.append(stop)  # R-3: whole-trip dedup tracking
            slot_load[chosen_slot] = slot_load.get(chosen_slot, 0) + duration + chosen_travel
            day_total_min += duration + chosen_travel

        if dropped:
            print(
                f"  [day {day_idx+1}] Dropped {len(dropped)} POIs to stay within "
                f"{budget_hours}h budget: {', '.join(dropped[:3])}"
                + (" ..." if len(dropped) > 3 else "")
            )
        if duplicates_skipped:
            print(
                f"  [day {day_idx+1}] Skipped {len(duplicates_skipped)} duplicate POI(s): "
                f"{', '.join(duplicates_skipped[:3])}"
                + (" ..." if len(duplicates_skipped) > 3 else "")
            )

        # Meal coverage guarantee (breakfast/lunch/dinner every day, near the
        # day's other stops): the loop above only ever seats a restaurant if
        # one was already in `bucket` — which only happens when the
        # traveler's stated interests map to the restaurant category at all
        # (poi_search.py's INTEREST_MAP). A history+architecture trip has
        # zero restaurant candidates in its input, so without this pass a
        # whole day (or trip) could go completely unfed regardless of pace/
        # budget. Runs after, not instead of, the interest-driven loop —
        # never overrides a restaurant that loop already picked.
        day_total_min, meal_fill_notes = _fill_missing_meal_slots(
            slots, slot_load, day_total_min, all_scheduled_stops, restaurant_slots_used, budget_min,
            max_guaranteed_meals,
        )
        if meal_fill_notes:
            print(f"  [day {day_idx+1}] Added nearby meal option(s): {', '.join(meal_fill_notes)}")

        all_day_stops = slots["morning"] + slots["afternoon"] + slots["evening"]

        # Hidden gem: the lowest-relevance stop still scheduled today — a real,
        # already-computed signal (HIGH_PROFILE landmarks score higher), not a
        # fabricated "offbeat" attribute. Only meaningful with >= 2 stops.
        # R-10: excludes generic commercial venues (malls, retail chains) —
        # low relevance_score there just means "not a landmark," not "an
        # authentic off-the-beaten-path find."
        gem_candidates = [s for s in all_day_stops if not _is_generic_commercial_venue(s)]
        if len(gem_candidates) >= 2:
            gem = min(gem_candidates, key=lambda s: s.get("relevance_score", 0.5))
            gem["is_hidden_gem"] = True

        nearest_hospital = nearest_pharmacy = nearest_metro = None
        if all_day_stops:
            centroid_lat = sum(s["lat"] for s in all_day_stops) / len(all_day_stops)
            centroid_lon = sum(s["lon"] for s in all_day_stops) / len(all_day_stops)
            reference = _load_reference_pois()
            nearest_hospital = _nearest_summary(centroid_lat, centroid_lon, reference["hospital"])
            nearest_pharmacy = _nearest_summary(centroid_lat, centroid_lon, reference["pharmacy"])
            nearest_metro = _nearest_summary(centroid_lat, centroid_lon, reference["metro_station"])

        itinerary[day_key] = {
            "morning":            slots["morning"],
            "afternoon":          slots["afternoon"],
            "evening":            slots["evening"],
            "total_hours":        round(day_total_min / 60, 2),
            "date":               date_str,
            "nearest_hospital":   nearest_hospital,
            "nearest_pharmacy":   nearest_pharmacy,
            "nearest_metro_station": nearest_metro,
        }

    return itinerary


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("itinerary-builder")


@mcp.tool()
def itinerary_builder(
    pois: list[dict],
    days: int,
    pace: str = "moderate",
    daily_hours: float | None = None,
    travel_dates: list[str] | None = None,
) -> dict:
    """
    Build a day-wise itinerary from candidate POIs.
    Assigns POIs to Morning / Afternoon / Evening slots,
    respects daily time budget, and clusters by geography.
    """
    return itinerary_builder_logic(pois, days, pace, daily_hours, travel_dates)


if __name__ == "__main__":
    mcp.run()
