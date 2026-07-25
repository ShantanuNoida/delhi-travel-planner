"""
Team Waypoint -- Itinerary edit commands QA (Phase 1)
Agent 4 (Quality Manager) support script: flattens all 20 result files into
one compact table for review, and flags candidate loopholes/inaccuracies by
pattern so nothing gets missed by eyeballing 300 rows individually.
"""
import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

NOOP_MESSAGES = (
    "Couldn't find a suitable replacement",
    "Couldn't find a new place matching",
    "Couldn't find anything matching",
    "already light",
)

rows = []
flags = []

for i in range(1, 21):
    path = os.path.join(RESULTS_DIR, f"itinerary_{i:02d}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    spec = data["spec"]
    for step in data["steps"]:
        cls = step["classification"]
        row = {
            "itin": i,
            "label": spec["label"],
            "n": step["n"],
            "command": step["command"],
            "category": step["category"],
            "probe": step["probe"],
            "intent": cls.get("intent"),
            "edit_type": (cls.get("edit_intent") or {}).get("edit_type"),
            "target_day": (cls.get("edit_intent") or {}).get("target_day"),
            "target_slot": (cls.get("edit_intent") or {}).get("target_slot"),
            "constraint": (cls.get("edit_intent") or {}).get("constraint"),
            "ok": step["edit_result_ok"],
            "message": step["edit_result_message"],
            "changed_days": step["changed_days"],
            "correctness_pass": (step["edit_correctness"] or {}).get("pass") if step["edit_correctness"] else None,
            "drifted_slots": (step["edit_correctness"] or {}).get("drifted_slots") if step["edit_correctness"] else None,
            "feasibility_pass": step["feasibility_after"]["pass"],
            "feasibility_issues": step["feasibility_after"]["issues"],
        }
        rows.append(row)

        # --- Pattern flags ---
        if row["intent"] != "EDIT" and step["probe"] not in ("vague_no_actionable_edit_type",):
            flags.append(("MISCLASSIFIED_NON_EDIT", row))
        if row["ok"] is False and step["probe"] != "invalid_day_reference":
            flags.append(("EDIT_REJECTED", row))
        if row["message"] and any(m in row["message"] for m in NOOP_MESSAGES):
            flags.append(("SILENT_NOOP", row))
        if row["correctness_pass"] is False:
            flags.append(("SCOPE_DRIFT", row))
        if row["feasibility_pass"] is False:
            flags.append(("FEASIBILITY_FAIL_SURVIVED", row))
        if step["probe"] == "swap_known_absent_place" and "don't have a real" not in (row["message"] or ""):
            flags.append(("ABSENT_PLACE_NOT_CAUGHT", row))
        if step["probe"] == "add_known_absent_place" and "don't have a real" not in (row["message"] or ""):
            flags.append(("ABSENT_PLACE_NOT_CAUGHT", row))
        if step["probe"] == "invalid_day_reference" and row["ok"] is not False:
            flags.append(("INVALID_DAY_NOT_REJECTED", row))
        if step["probe"] == "remove_vague_no_referent" and row["edit_type"] == "remove":
            flags.append(("VAGUE_REMOVE_TREATED_LITERALLY", row))

out = {
    "total_steps": len(rows),
    "flag_counts": {},
    "flags": [{"flag": f, **r} for f, r in flags],
    "rows": rows,
}
for f, _ in flags:
    out["flag_counts"][f] = out["flag_counts"].get(f, 0) + 1

with open(os.path.join(RESULTS_DIR, "_analysis.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print("Total steps:", len(rows))
print("Flag counts:", json.dumps(out["flag_counts"], indent=2))
print()
print("=== Intent distribution ===")
from collections import Counter
print(Counter(r["intent"] for r in rows))
print()
print("=== Edit-type distribution (when EDIT) ===")
print(Counter(r["edit_type"] for r in rows if r["intent"] == "EDIT"))
print()
print("=== Message pattern distribution ===")
msg_buckets = Counter()
for r in rows:
    m = r["message"] or ""
    if "Couldn't find a suitable replacement" in m:
        msg_buckets["swap_noop"] += 1
    elif "Couldn't find a new place matching" in m:
        msg_buckets["add_noop"] += 1
    elif "Couldn't find anything matching" in m:
        msg_buckets["remove_noop"] += 1
    elif "already light" in m:
        msg_buckets["relax_noop"] += 1
    elif "doesn't exist in this itinerary" in m:
        msg_buckets["invalid_day"] += 1
    elif "don't have a real, mappable record" in m:
        msg_buckets["known_absent_honest"] += 1
    elif "over the" in m and "budget" in m:
        msg_buckets["budget_rejected"] += 1
    else:
        msg_buckets["other_success"] += 1
print(msg_buckets)
