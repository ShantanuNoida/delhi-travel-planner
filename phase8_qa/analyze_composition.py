"""
Team Waypoint -- post-round harness broadening (2026-07-25)

Agent 1 (Itinerary Generator) built 20 itineraries and they were treated as
trusted, fixed INPUT for Agent 2 (edits) and Agent 3 (questions) to test
against -- nobody on the team ever reviewed whether the itineraries
THEMSELVES were well-composed relative to what the traveler actually asked
for. That blind spot is exactly how the meal-coverage-guarantee bug (every
day 60% restaurants on an architecture-only trip, real repro) went
undetected through three full QA rounds: it's a defect in generation, not
in editing or answering, so it sat entirely outside what either QA agent
was ever asked to check.

This script closes that gap: for each of the 20 built itineraries, checks
whether its actual composition is proportionate to its stated interests --
specifically, whether restaurant-category stops make up a disproportionate
share of a day when food/cuisine/eating was never part of what was asked
for. Uses the exact same signal the real fix in itinerary_builder.py uses
(does the interest-filtered POI pool contain any restaurant at all), not a
separate keyword heuristic, so this check and the app's own behavior can
never quietly drift apart.

Usage: python analyze_composition.py
Reads phase8_qa/results/base_itinerary_01.json .. base_itinerary_20.json
(Agent 1's already-built output). Writes results/_analysis_composition.json.
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "phase2"))
from poi_search import poi_search_logic  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DAY_SLOTS = ("morning", "afternoon", "evening")

# Above this restaurant share of a day's stops, with no food-related
# interest stated, is flagged -- the real repro this catches ran at 60%
# (3 of 5 stops) every day; a couple of built-in meal stops (now capped at
# 1/day by the fix) landing at 20-33% of a typical 3-5 stop day is normal
# and expected, not a defect.
MEAL_OVERFILL_THRESHOLD = 0.40


def _food_interest_stated(interests: list[str]) -> bool:
    """Mirrors itinerary_builder.py's own real signal exactly (does the
    interest-filtered POI pool contain any restaurant), so this check can
    never quietly diverge from what the app itself actually does."""
    pois = poi_search_logic("New Delhi", interests, top_n=30)
    return any(p.get("category") == "restaurant" for p in pois)


def analyze_one(spec_id: int) -> dict | None:
    path = os.path.join(RESULTS_DIR, f"base_itinerary_{spec_id:02d}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    spec = data["spec"]
    itinerary = data["itinerary"]
    food_stated = _food_interest_stated(spec["interests"])

    day_reports = []
    flags = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        day = itinerary[key]
        stops = [s for slot in DAY_SLOTS for s in day.get(slot, [])]
        if not stops:
            continue
        categories: dict[str, int] = {}
        for s in stops:
            cat = s.get("category", "?")
            categories[cat] = categories.get(cat, 0) + 1
        restaurant_share = categories.get("restaurant", 0) / len(stops)
        day_report = {
            "day": key, "total_stops": len(stops), "categories": categories,
            "restaurant_share": round(restaurant_share, 2),
        }
        day_reports.append(day_report)
        if not food_stated and restaurant_share > MEAL_OVERFILL_THRESHOLD:
            flags.append({
                "day": key, "restaurant_count": categories.get("restaurant", 0),
                "total_stops": len(stops), "restaurant_share": round(restaurant_share, 2),
            })

    return {
        "spec_id": spec_id, "label": spec["label"], "interests": spec["interests"],
        "food_interest_stated": food_stated, "days": day_reports, "meal_overfill_flags": flags,
    }


def main():
    results = []
    for spec_id in range(1, 21):
        r = analyze_one(spec_id)
        if r:
            results.append(r)

    total_flags = sum(len(r["meal_overfill_flags"]) for r in results)
    flagged_itineraries = [r for r in results if r["meal_overfill_flags"]]

    out = {"results": results, "total_meal_overfill_flags": total_flags,
           "flagged_itinerary_count": len(flagged_itineraries)}
    out_path = os.path.join(RESULTS_DIR, "_analysis_composition.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Analyzed {len(results)} itineraries.")
    print(f"MEAL_OVERFILL flags: {total_flags} across {len(flagged_itineraries)} itineraries.")
    if flagged_itineraries:
        print("\nFlagged itineraries (no food interest stated, but a day is >"
              f"{int(MEAL_OVERFILL_THRESHOLD*100)}% restaurants):")
        for r in flagged_itineraries:
            print(f"  #{r['spec_id']:02d} {r['label']} (interests={r['interests']})")
            for f in r["meal_overfill_flags"]:
                print(f"    {f['day']}: {f['restaurant_count']}/{f['total_stops']} stops "
                      f"({int(f['restaurant_share']*100)}%) are restaurants")
    else:
        print("No meal-overfill flags -- composition looks proportionate to stated interests.")
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
