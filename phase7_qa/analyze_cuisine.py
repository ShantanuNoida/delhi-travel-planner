"""
Team Waypoint -- 30 Random Itineraries QA (cuisine round) -- Agent 4 analysis.
"""
import json
import os
from collections import Counter

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

rows = []
for i in range(1, 31):
    path = os.path.join(RESULTS_DIR, f"cuisine_itinerary_{i:02d}.json")
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    rows.append(d)

print(f"Total itineraries analyzed: {len(rows)}")
print()

built = [r for r in rows if r["itinerary"] is not None]
print(f"Successfully built: {len(built)}/{len(rows)}")
print()

feas_pass = sum(1 for r in built if r["feasibility"]["pass"])
ground_pass = sum(1 for r in built if r["grounding"]["pass"])
print(f"Feasibility Eval pass: {feas_pass}/{len(built)}")
print(f"Grounding Eval pass: {ground_pass}/{len(built)}")
print()

total_restaurants = sum(r["cuisine_accuracy"]["total_restaurants"] for r in built)
total_matched = sum(len(r["cuisine_accuracy"]["matched_cuisine"]) for r in built)
total_unmatched = sum(len(r["cuisine_accuracy"]["unmatched_cuisine"]) for r in built)
total_no_tag = sum(len(r["cuisine_accuracy"]["no_cuisine_tag"]) for r in built)
itins_with_zero_match = sum(1 for r in built if r["cuisine_accuracy"]["total_restaurants"] > 0 and len(r["cuisine_accuracy"]["matched_cuisine"]) == 0)

print("=== Cuisine Accuracy ===")
print(f"Total restaurant stops across all 30 itineraries: {total_restaurants}")
print(f"  Matched the requested cuisine (real tag confirms it): {total_matched} ({total_matched/total_restaurants:.1%})")
print(f"  Wrong cuisine (real tag present, doesn't match): {total_unmatched} ({total_unmatched/total_restaurants:.1%})")
print(f"  No cuisine tag at all (can't verify either way): {total_no_tag} ({total_no_tag/total_restaurants:.1%})")
print(f"Itineraries with ZERO cuisine-matched restaurants: {itins_with_zero_match}/{len(built)}")
print()

print("=== Where cuisine preference actually landed after extraction ===")
in_constraints_dietary = sum(1 for r in rows if r["extracted_constraints"].get("dietary"))
in_interests = 0
for r in rows:
    cuisine_word = r["spec"]["cuisine"].lower().split()[0]  # e.g. "north" from "North Indian"
    if any(cuisine_word in i.lower() for i in r["extracted_interests"]):
        in_interests += 1
print(f"Captured in constraints.dietary: {in_constraints_dietary}/{len(rows)}")
print(f"Cuisine word appears literally in extracted_interests: {in_interests}/{len(rows)}")
print(f"extracted_interests always generalized to bare 'food': {sum(1 for r in rows if 'food' in r['extracted_interests'])}/{len(rows)}")
print()

print("=== Category Coverage ===")
all_missing = Counter()
itins_with_gap = 0
for r in built:
    missing = r["category_coverage"]["missing"]
    if missing:
        itins_with_gap += 1
        for m in missing:
            all_missing[m] += 1
print(f"Itineraries with at least one requested category not represented: {itins_with_gap}/{len(built)}")
print(f"Missing-category breakdown: {dict(all_missing)}")
print()

# Per-cuisine breakdown
print("=== Per-cuisine breakdown (match rate) ===")
by_cuisine = {}
for r in built:
    c = r["spec"]["cuisine"]
    by_cuisine.setdefault(c, {"total": 0, "matched": 0})
    by_cuisine[c]["total"] += r["cuisine_accuracy"]["total_restaurants"]
    by_cuisine[c]["matched"] += len(r["cuisine_accuracy"]["matched_cuisine"])
for c, v in by_cuisine.items():
    rate = v["matched"] / v["total"] if v["total"] else 0
    print(f"  {c:15s}: {v['matched']}/{v['total']} ({rate:.0%})")

# Save aggregate for the doc
out = {
    "total": len(rows),
    "built": len(built),
    "feasibility_pass": feas_pass,
    "grounding_pass": ground_pass,
    "total_restaurants": total_restaurants,
    "total_matched": total_matched,
    "total_unmatched": total_unmatched,
    "total_no_tag": total_no_tag,
    "itins_with_zero_match": itins_with_zero_match,
    "in_constraints_dietary": in_constraints_dietary,
    "in_interests": in_interests,
    "itins_with_category_gap": itins_with_gap,
    "missing_category_breakdown": dict(all_missing),
    "by_cuisine": by_cuisine,
}
with open(os.path.join(RESULTS_DIR, "_analysis_cuisine.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
