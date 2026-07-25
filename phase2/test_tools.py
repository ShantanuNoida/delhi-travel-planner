"""
Phase 2 test suite — runs tests T-2.1 through T-2.6.
Tests call business logic functions directly (no MCP protocol overhead).
Usage: python test_tools.py
"""

import sys
import os

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

SAMPLE_POIS = [
    {"osm_id": "1", "name": "Red Fort",         "category": "monument",   "lat": 28.6562, "lon": 77.2410, "visit_duration_min": 90,  "relevance_score": 0.9, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "2", "name": "Jama Masjid",      "category": "mosque",     "lat": 28.6507, "lon": 77.2334, "visit_duration_min": 45,  "relevance_score": 0.8, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "3", "name": "Chandni Chowk",    "category": "market",     "lat": 28.6562, "lon": 77.2300, "visit_duration_min": 90,  "relevance_score": 0.7, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "4", "name": "Karim's",          "category": "restaurant", "lat": 28.6504, "lon": 77.2343, "visit_duration_min": 75,  "relevance_score": 0.6, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "5", "name": "Qutab Minar",      "category": "monument",   "lat": 28.5244, "lon": 77.1855, "visit_duration_min": 90,  "relevance_score": 0.9, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "6", "name": "Humayun's Tomb",   "category": "monument",   "lat": 28.5933, "lon": 77.2507, "visit_duration_min": 90,  "relevance_score": 0.9, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "7", "name": "Lodi Garden",      "category": "park",       "lat": 28.5931, "lon": 77.2197, "visit_duration_min": 60,  "relevance_score": 0.7, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "8", "name": "India Gate",       "category": "monument",   "lat": 28.6129, "lon": 77.2295, "visit_duration_min": 60,  "relevance_score": 0.9, "opening_hours": "unknown", "fallback": False},
    {"osm_id": "9", "name": "National Museum",  "category": "museum",     "lat": 28.6115, "lon": 77.2195, "visit_duration_min": 120, "relevance_score": 0.8, "opening_hours": "Tu-Su 10:00-18:00", "fallback": False},
    {"osm_id":"10", "name": "Lotus Temple",     "category": "temple",     "lat": 28.5535, "lon": 77.2588, "visit_duration_min": 45,  "relevance_score": 0.8, "opening_hours": "unknown", "fallback": False},
]


def _result(label: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


# ---------------------------------------------------------------------------
# T-2.1  POI Search: Interest Mapping
# ---------------------------------------------------------------------------
def test_poi_search_interest_mapping():
    print("\nT-2.1 — POI Search: Interest Mapping")
    from poi_search import poi_search_logic

    pois = poi_search_logic("New Delhi", ["food", "culture"])
    has_enough = len(pois) >= 10
    food_cats   = {"restaurant", "market"}
    culture_cats = {"museum", "monument", "temple", "mosque", "church", "gurdwara"}
    all_cats = {p["category"] for p in pois}
    has_food    = bool(all_cats & food_cats)
    has_culture = bool(all_cats & culture_cats)
    has_fields  = all(
        {"osm_id", "name", "category", "lat", "lon", "relevance_score", "visit_duration_min"}.issubset(p)
        for p in pois
    )
    ok = has_enough and has_food and has_culture and has_fields
    _result(f"returns >= 10 POIs", has_enough, f"got {len(pois)}")
    _result("includes food categories",    has_food,    str(all_cats & food_cats))
    _result("includes culture categories", has_culture, str(all_cats & culture_cats))
    _result("all fields present", has_fields)
    return ok


# ---------------------------------------------------------------------------
# T-2.2  POI Search: Niche Interest Fallback
# ---------------------------------------------------------------------------
def test_poi_search_fallback():
    print("\nT-2.2 — POI Search: Niche Interest Fallback (EC-2.1)")
    from poi_search import poi_search_logic

    # R-41: "graffiti art" is no longer a valid niche-fallback example --
    # poi_search.py's _resolve_interest_key() now scans a multi-word phrase
    # for any embedded known INTEREST_MAP word, and both "graffiti" and
    # "art" are themselves real keys, so that phrase now correctly resolves
    # instead of falling back. Use interests with no embedded known word at
    # all, so this test still exercises the genuine EC-2.1 fallback path.
    pois = poi_search_logic("New Delhi", ["skydiving", "underground music"])
    not_empty    = len(pois) > 0
    has_fallback = any(p.get("fallback") is True for p in pois)
    _result("returns POIs (not empty)",    not_empty,    f"got {len(pois)}")
    _result("fallback flag set on results", has_fallback)
    return not_empty and has_fallback


# ---------------------------------------------------------------------------
# T-2.3  Itinerary Builder: Day Structure
# ---------------------------------------------------------------------------
def test_itinerary_day_structure():
    print("\nT-2.3 — Itinerary Builder: Day Structure")
    from itinerary_builder import itinerary_builder_logic

    itin = itinerary_builder_logic(SAMPLE_POIS, days=2, pace="moderate")
    has_two_days = set(itin.keys()) == {"day_1", "day_2"}
    has_slots = all(
        {"morning", "afternoon", "evening", "total_hours"}.issubset(itin[d])
        for d in itin
    )
    within_budget = all(itin[d]["total_hours"] <= 8.5 for d in itin)
    no_empty_fields = all(
        all({"name", "osm_id", "visit_duration_min"}.issubset(stop)
            for slot in ("morning", "afternoon", "evening")
            for stop in itin[d][slot])
        for d in itin
    )
    _result("exactly 2 days in output",      has_two_days)
    _result("each day has 3 time slots",     has_slots)
    _result("no day exceeds 8h (moderate)",  within_budget,
            str({d: itin[d]['total_hours'] for d in itin}))
    _result("all stops have required fields", no_empty_fields)
    return has_two_days and has_slots and within_budget and no_empty_fields


# ---------------------------------------------------------------------------
# T-2.4  Itinerary Builder: Geographic Clustering
# ---------------------------------------------------------------------------
def test_geographic_clustering():
    print("\nT-2.4 — Itinerary Builder: Geographic Clustering (EC-2.3)")
    import math
    from itinerary_builder import itinerary_builder_logic, _haversine_km

    itin = itinerary_builder_logic(SAMPLE_POIS, days=2, pace="moderate")

    max_dist = 0.0
    violations = []
    for day_key, day in itin.items():
        all_stops = (
            day["morning"] + day["afternoon"] + day["evening"]
        )
        for i in range(len(all_stops) - 1):
            a, b = all_stops[i], all_stops[i + 1]
            d = _haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            max_dist = max(max_dist, d)
            if d > 15.0:
                violations.append(f"{a['name']} → {b['name']}: {d:.1f}km")

    ok = len(violations) == 0
    _result(
        "no consecutive stops > 15km apart",
        ok,
        f"max={max_dist:.1f}km" + (f", violations={violations}" if violations else ""),
    )
    return ok


# ---------------------------------------------------------------------------
# T-2.5  Itinerary Builder: Day Overflow Prevention
# ---------------------------------------------------------------------------
def test_day_overflow():
    print("\nT-2.5 — Itinerary Builder: Day Overflow Prevention (EC-2.2)")
    from itinerary_builder import itinerary_builder_logic

    # 20 POIs, 1 day, relaxed (6h cap) — builder must drop to fit
    many_pois = SAMPLE_POIS * 2  # 20 POIs
    itin = itinerary_builder_logic(many_pois, days=1, pace="relaxed")

    total_hours = itin["day_1"]["total_hours"]
    within_cap  = total_hours <= 6.5  # small tolerance for rounding
    _result(
        "total hours ≤ 6h (relaxed cap)",
        within_cap,
        f"got {total_hours}h with {len(many_pois)} input POIs",
    )
    return within_cap


# ---------------------------------------------------------------------------
# T-2.6  MCP Tool Schema Validation
# ---------------------------------------------------------------------------
def test_schema_validation():
    print("\nT-2.6 — MCP Tool Schema Validation")
    from poi_search import poi_search_logic
    from itinerary_builder import itinerary_builder_logic

    # Missing required field: city
    city_error = False
    try:
        poi_search_logic("", ["food"])
    except Exception:
        city_error = True

    # Wrong city
    wrong_city_error = False
    try:
        poi_search_logic("Mumbai", ["food"])
    except ValueError:
        wrong_city_error = True

    # No POIs passed to builder
    no_pois_error = False
    try:
        itinerary_builder_logic([], days=2, pace="moderate")
    except ValueError:
        no_pois_error = True

    # Invalid days
    bad_days_error = False
    try:
        itinerary_builder_logic(SAMPLE_POIS, days=10, pace="moderate")
    except ValueError:
        bad_days_error = True

    _result("empty city raises error",         city_error)
    _result("unsupported city raises ValueError", wrong_city_error)
    _result("empty POI list raises ValueError",   no_pois_error)
    _result("days > 4 raises ValueError",         bad_days_error)
    return city_error and wrong_city_error and no_pois_error and bad_days_error


# ---------------------------------------------------------------------------
# Bonus: Travel Time + Weather sanity checks
# ---------------------------------------------------------------------------
def test_bonus_tools():
    print("\nBonus — Travel Time & Weather Tools")
    from travel_time import travel_time_logic
    from weather import weather_logic

    # Travel time: Red Fort → Qutab Minar (~15km)
    tt = travel_time_logic(28.6562, 77.2410, 28.5244, 77.1855)
    tt_ok = tt["estimated_minutes"] > 0 and tt["mode"] in ("walk", "auto", "metro")
    _result(
        "travel time Red Fort → Qutab Minar",
        tt_ok,
        f"{tt['estimated_minutes']} min via {tt['mode']}, {tt['distance_km']} km",
    )

    # Travel time: very close stops (< 1.5km) → should be walk
    tt_walk = travel_time_logic(28.6562, 77.2410, 28.6507, 77.2334)
    _result(
        "short distance → walk mode",
        tt_walk["mode"] == "walk",
        f"{tt_walk['distance_km']} km → {tt_walk['mode']}",
    )

    # Weather: future date
    from datetime import date, timedelta
    future_date = (date.today() + timedelta(days=3)).isoformat()
    w = weather_logic("New Delhi", [future_date])
    weather_ok = "forecast" in w and "outdoor_risk_flag" in w and "source" in w
    _result("weather tool returns valid structure", weather_ok, str(w.get("source")))

    return tt_ok and weather_ok


# ---------------------------------------------------------------------------
# T-2.7  Cuisine-Aware Restaurant Ranking (Phase 3 QA H1)
# ---------------------------------------------------------------------------
def test_cuisine_matching():
    """
    Phase 3 QA (H1, "Itinerary edit commands QA.md"): constraints["dietary"]
    was captured by the conversational agent but never read anywhere in this
    pipeline -- a real 30-itinerary QA round found 0/228 scheduled
    restaurants verifiably matching the requested cuisine. Also covers a
    real robustness bug caught while verifying the fix: constraints
    ["dietary"] comes back from the LLM extraction as a list on some real
    calls, not always a plain string as the schema comment implies -- this
    used to crash _cuisine_hints() outright.
    """
    print("\nT-2.7 — Cuisine-Aware Restaurant Ranking")
    from poi_search import poi_search_logic

    pois = poi_search_logic("New Delhi", ["food"], constraints={"dietary": "North Indian food"}, top_n=10)
    restaurants = [p for p in pois if p["category"] == "restaurant"]
    has_cuisine_field = any("cuisine" in p for p in restaurants)
    _result("restaurant results carry a real cuisine field when tagged", has_cuisine_field,
            f"{sum('cuisine' in p for p in restaurants)}/{len(restaurants)} have it")

    matched = sum(1 for p in restaurants if "indian" in (p.get("cuisine") or "").lower())
    ok_match = matched >= 1
    _result("at least one confirmed North-Indian-tagged restaurant surfaces", ok_match, f"{matched}/{len(restaurants)}")

    # Robustness: constraints["dietary"] as a list (observed real LLM output
    # shape), not a string, must not crash the search.
    crashed = False
    try:
        pois2 = poi_search_logic("New Delhi", ["food"], constraints={"dietary": ["Thai"]}, top_n=10)
    except Exception as e:  # noqa: BLE001
        crashed = True
        pois2 = []
    _result("list-shaped dietary constraint does not crash", not crashed)
    thai_matched = sum(1 for p in pois2 if p["category"] == "restaurant" and "thai" in (p.get("cuisine") or "").lower())
    _result("list-shaped dietary constraint still finds real matches", thai_matched >= 1, f"{thai_matched} matched")

    # No dietary constraint at all: behavior must be completely unchanged
    # (no crash, no forced cuisine field, purely additive feature).
    pois3 = poi_search_logic("New Delhi", ["food"], constraints={}, top_n=10)
    baseline_ok = len([p for p in pois3 if p["category"] == "restaurant"]) > 0
    _result("no dietary constraint -- unaffected baseline behavior", baseline_ok)

    return has_cuisine_field and ok_match and not crashed and thai_matched >= 1 and baseline_ok


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all():
    print("=" * 60)
    print("PHASE 2 VALIDATION TESTS")
    print("=" * 60)

    results = {
        "T-2.1 POI Search Interest Mapping":     test_poi_search_interest_mapping(),
        "T-2.2 POI Search Niche Fallback":        test_poi_search_fallback(),
        "T-2.3 Itinerary Day Structure":          test_itinerary_day_structure(),
        "T-2.4 Geographic Clustering":            test_geographic_clustering(),
        "T-2.5 Day Overflow Prevention":          test_day_overflow(),
        "T-2.6 Schema Validation":                test_schema_validation(),
        "T-2.7 Cuisine-Aware Ranking":             test_cuisine_matching(),
        "Bonus Travel Time + Weather":            test_bonus_tools(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results.values())
    total  = len(results)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
