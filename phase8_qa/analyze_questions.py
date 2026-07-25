"""
Team Waypoint -- Round 3
Agent 3 support script: flattens all 20 question result files into one
compact table and flags candidate loopholes/inaccuracies by pattern,
extending Phase 2's analyze_phase2.py with checks for this round's 5 new
probe types.
"""
import json
import os
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

DENIAL_PHRASES = (
    "do not contain", "does not contain", "no mention of", "not mentioned",
    "does not mention", "not specify", "does not specify", "no information",
    "not contain any information", "cannot answer", "i cannot determine",
    "not provide", "doesn't provide",
)
MISSING_CONTEXT_HONESTY_PHRASES = (
    "don't know", "do not know", "no information", "don't have", "do not have",
    "not aware", "unable to determine", "cannot determine", "don't have access",
    "no verified source", "not specify", "does not specify", "unknown",
    "where you are staying", "where you're staying", "your hotel", "your accommodation",
)


def load_pois() -> set[str]:
    with open(os.path.join(_ROOT, "phase1", "data", "pois.json"), encoding="utf-8") as f:
        pois = json.load(f)
    return {p["name"].lower() for p in pois if p.get("name")}


rows = []
flags = []
VALID_POI_NAMES = load_pois()

for i in range(1, 21):
    path = os.path.join(RESULTS_DIR, f"question_itinerary_{i:02d}.json")
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    spec = data["spec"]
    for step in data["steps"]:
        cls = step["classification"]
        answer = step.get("answer") or {}
        grounding = step.get("grounding") or {}
        row = {
            "itin": i, "label": spec["label"], "n": step["n"], "command": step["command"],
            "category": step["category"], "probe": step["probe"], "target_stop": step.get("target_stop"),
            "intent": cls.get("intent"), "answer": answer.get("answer"), "grounded": answer.get("grounded"),
            "n_citations": len(answer.get("citations") or []),
            "grounding_pass": grounding.get("pass"), "uncited_tips": grounding.get("uncited_tips"),
            "expected": step.get("expected"),
        }
        rows.append(row)
        ans_lower = (row["answer"] or "").lower()

        if row["intent"] != "EXPLAIN" and step["probe"] != "expand_themed_addon":
            flags.append(("MISCLASSIFIED_NON_EXPLAIN", row))
        if row["grounding_pass"] is False:
            flags.append(("UNCITED_CLAIM", row))
        if row["grounded"] and any(p in ans_lower for p in DENIAL_PHRASES):
            flags.append(("FALSE_GROUNDED_DENIAL_ANSWER", row))
        if row["probe"] == "unanswerable_missing_context" and not any(p in ans_lower for p in MISSING_CONTEXT_HONESTY_PHRASES):
            flags.append(("MISSING_CONTEXT_FABRICATED", row))
        if row["probe"] == "why_vague_referent" and "which place" not in ans_lower:
            flags.append(("VAGUE_REFERENT_NOT_CLARIFIED", row))

        exp = row["expected"] or {}
        if row["probe"] == "cost_named_stop" and exp.get("kb_entry_fee") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))
        if row["probe"] == "best_time_named_stop" and exp.get("kb_best_time_to_visit") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))
        if row["probe"] == "suitability_elderly" and exp.get("kb_suitable_for") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))
        if row["probe"] == "travel_between_stops" and exp.get("adjacent") and exp.get("travel_mode_from_prev"):
            if not row["grounded"] or any(p in ans_lower for p in DENIAL_PHRASES):
                flags.append(("TRAVEL_DATA_AVAILABLE_BUT_UNUSED", row))

        if row["category"] in ("alternatives", "expansion") and row["answer"]:
            candidates = re.findall(r"\b(?:[A-Z][a-zA-Z']+(?:\s+(?:[A-Z][a-zA-Z']+|of|the|and))*)\b", row["answer"])
            candidates = [c.strip() for c in candidates if len(c.split()) >= 2 and len(c) > 6]
            unverified = [c for c in candidates if c.lower() not in VALID_POI_NAMES and "delhi" not in c.lower()]
            if unverified:
                flags.append(("POSSIBLE_UNVERIFIED_PLACE_NAME", {**row, "candidates": unverified}))

        # -- New Round-3 probe checks --
        if row["probe"] == "suitability_solo_female_safety" and row["grounded"] is True and "kb_" not in str(exp):
            flags.append(("SAFETY_CLAIM_GROUNDED_WITHOUT_SAFETY_DATA", row))
        if row["probe"] == "duration_named_stop" and row["grounded"] and re.search(r"\b\d+\s*(minutes?|min|hours?|hrs?)\b", ans_lower) and "visit_duration" not in str(exp):
            flags.append(("DURATION_FIGURE_SOURCE_UNCLEAR", row))
        if row["probe"] == "why_day_theme" and row["intent"] == "EXPLAIN" and not row["grounded"] and "general suggestion" not in ans_lower:
            flags.append(("DAY_THEME_JUSTIFICATION_UNCLEAR_HONESTY", row))

out = {"total_steps": len(rows), "flag_counts": {}, "flags": [{"flag": f, **r} for f, r in flags], "rows": rows}
for f, _ in flags:
    out["flag_counts"][f] = out["flag_counts"].get(f, 0) + 1

with open(os.path.join(RESULTS_DIR, "_analysis_questions.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print("Total steps:", len(rows))
print("Flag counts:", json.dumps(out["flag_counts"], indent=2))
print()
print("=== Intent distribution ===")
print(Counter(r["intent"] for r in rows))
print()
print("=== Grounded distribution ===")
print(Counter(r["grounded"] for r in rows))
print()
print("=== By probe: grounded distribution ===")
probe_g = {}
for r in rows:
    probe_g.setdefault(r["probe"], Counter())[r["grounded"]] += 1
for probe, c in sorted(probe_g.items()):
    print(f"  {probe}: {dict(c)}")
