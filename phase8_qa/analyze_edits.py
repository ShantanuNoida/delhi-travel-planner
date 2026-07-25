"""
Team Waypoint -- Round 3
Agent 2 support script: flattens all 20 edit result files into one compact
table and flags candidate loopholes/inaccuracies by pattern, extending
Phase 1's analyze.py with checks for this round's 5 new probe types.
"""
import json
import os
from collections import Counter

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
    path = os.path.join(RESULTS_DIR, f"edit_itinerary_{i:02d}.json")
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    spec = data["spec"]
    for step in data["steps"]:
        cls = step["classification"]
        row = {
            "itin": i, "label": spec["label"], "n": step["n"], "command": step["command"],
            "category": step["category"], "probe": step["probe"],
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

        if row["intent"] != "EDIT" and step["probe"] not in ("vague_no_actionable_edit_type", "gibberish_low_signal_input"):
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

        # -- New Round-3 probe checks --
        if step["probe"] == "swap_free_of_charge" and any(m in (row["message"] or "") for m in NOOP_MESSAGES):
            flags.append(("BUDGET_CONSTRAINT_UNSUPPORTED", row))
        if step["probe"] == "reorder_slots_same_day":
            if row["edit_type"] == "swap":
                flags.append(("REORDER_MISCLASSIFIED_AS_SWAP", row))
        if step["probe"] == "relax_whole_trip" and len(row["changed_days"] or []) <= 1 and spec["days"] > 1:
            flags.append(("WHOLE_TRIP_RELAX_ONLY_TOUCHED_ONE_DAY", row))
        if step["probe"] == "gibberish_low_signal_input" and row["ok"] is True:
            flags.append(("GIBBERISH_SILENTLY_APPLIED_NO_CLARIFICATION", row))
        if step["probe"] == "add_real_named_place" and row["ok"] is False and "budget" not in (row["message"] or "").lower():
            flags.append(("REAL_PLACE_ADD_REJECTED_UNCLEAR_REASON", row))

out = {"total_steps": len(rows), "flag_counts": {}, "flags": [{"flag": f, **r} for f, r in flags], "rows": rows}
for f, _ in flags:
    out["flag_counts"][f] = out["flag_counts"].get(f, 0) + 1

with open(os.path.join(RESULTS_DIR, "_analysis_edits.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print("Total steps:", len(rows))
print("Flag counts:", json.dumps(out["flag_counts"], indent=2))
print()
print("=== Intent distribution ===")
print(Counter(r["intent"] for r in rows))
print()
print("=== Edit-type distribution (when EDIT) ===")
print(Counter(r["edit_type"] for r in rows if r["intent"] == "EDIT"))
print()
print("=== By probe: ok distribution ===")
probe_ok = {}
for r in rows:
    probe_ok.setdefault(r["probe"], Counter())[r["ok"]] += 1
for probe, c in sorted(probe_ok.items()):
    print(f"  {probe}: {dict(c)}")
