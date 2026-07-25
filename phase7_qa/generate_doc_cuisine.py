"""
Team Waypoint -- 30 Random Itineraries QA (cuisine round), Agent 5 support:
renders the per-itinerary summary table from the real run's JSON logs.
"""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load(i):
    with open(os.path.join(RESULTS_DIR, f"cuisine_itinerary_{i:02d}.json"), encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return str(s).replace("|", "\\|")


out = ["| # | Requested (days/pace) | Cuisine requested | Categories requested | Extracted interests | Stops | Cuisine matched | Category gap | Feas. | Ground. |",
       "|---|---|---|---|---|---|---|---|---|---|"]
for i in range(1, 31):
    d = load(i)
    s = d["spec"]
    itin = d["itinerary"]
    n_stops = sum(len(itin[k][slot]) for k in itin if k.startswith("day_") for slot in ("morning", "afternoon", "evening")) if itin else 0
    ca = d["cuisine_accuracy"] or {}
    cc = d["category_coverage"] or {}
    cuisine_str = f"{len(ca.get('matched_cuisine', []))}/{ca.get('total_restaurants', 0)}"
    gap = ", ".join(cc.get("missing", [])) or "—"
    feas = "PASS" if d["feasibility"] and d["feasibility"]["pass"] else "FAIL"
    ground = "PASS" if d["grounding"] and d["grounding"]["pass"] else "FAIL"
    out.append(f"| {i} | {s['days']}d/{s['pace']} | {esc(s['cuisine'])} | {esc(', '.join(s['category_interests']))} | "
               f"{esc(', '.join(d['extracted_interests']))} | {n_stops} | {cuisine_str} | {esc(gap)} | {feas} | {ground} |")

with open(os.path.join(RESULTS_DIR, "_cuisine_table.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("wrote _cuisine_table.md")
