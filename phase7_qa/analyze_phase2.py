"""
Team Waypoint -- Itinerary edit commands QA (Phase 2)
Agent 4 (Quality Manager) support script: flattens all 20 Phase 2 result
files into one compact table, and flags candidate loopholes/inaccuracies by
pattern so nothing gets missed by eyeballing 300 rows individually.
"""
import json
import os
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Phrases that indicate the synthesized answer is itself saying "I found
# nothing relevant" even though explain_engine tagged the response
# grounded=True (it had *some* citations attached, just not useful ones).
DENIAL_PHRASES = (
    "do not contain", "does not contain", "no mention of", "not mentioned",
    "does not mention", "not specify", "does not specify", "no information",
    "not contain any information", "cannot answer", "i cannot determine",
    "not provide", "doesn't provide",
)

# Phrases that would indicate the app correctly admitted it has no hotel/
# lodging data instead of fabricating a walking distance or hotel location.
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
    path = os.path.join(RESULTS_DIR, f"phase2_itinerary_{i:02d}.json")
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
            "itin": i,
            "label": spec["label"],
            "n": step["n"],
            "command": step["command"],
            "category": step["category"],
            "probe": step["probe"],
            "target_stop": step.get("target_stop"),
            "intent": cls.get("intent"),
            "answer": answer.get("answer"),
            "grounded": answer.get("grounded"),
            "n_citations": len(answer.get("citations") or []),
            "grounding_pass": grounding.get("pass"),
            "uncited_tips": grounding.get("uncited_tips"),
            "expected": step.get("expected"),
        }
        rows.append(row)

        ans_lower = (row["answer"] or "").lower()

        # --- Pattern flags ---
        if row["intent"] != "EXPLAIN":
            flags.append(("MISCLASSIFIED_NON_EXPLAIN", row))

        if row["grounding_pass"] is False:
            flags.append(("UNCITED_CLAIM", row))

        if row["grounded"] and any(p in ans_lower for p in DENIAL_PHRASES):
            flags.append(("FALSE_GROUNDED_DENIAL_ANSWER", row))

        if row["probe"] == "unanswerable_missing_context":
            if not any(p in ans_lower for p in MISSING_CONTEXT_HONESTY_PHRASES):
                flags.append(("MISSING_CONTEXT_FABRICATED", row))

        if row["probe"] == "why_vague_referent" and "which place" not in ans_lower:
            flags.append(("VAGUE_REFERENT_NOT_CLARIFIED", row))

        # KB data was available on the target stop (real ground truth
        # already sitting in the itinerary object explain() was passed) but
        # the app fell back to an honest-no-source / ungrounded answer
        # instead of ever consulting it -- explain_engine.py never reads
        # kb_entry_fee/kb_best_time_to_visit/kb_suitable_for at all, only
        # does a fresh RAG text search by POI name.
        exp = row["expected"] or {}
        if row["probe"] == "cost_named_stop" and exp.get("kb_entry_fee") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))
        if row["probe"] == "best_time_named_stop" and exp.get("kb_best_time_to_visit") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))
        if row["probe"] == "suitability_elderly" and exp.get("kb_suitable_for") and not row["grounded"]:
            flags.append(("KB_DATA_AVAILABLE_BUT_UNUSED", row))

        # Adjacent-stop travel data was already computed by the builder
        # (travel_time_from_prev_min / travel_mode_from_prev) but explain()
        # never consults it, only RAG-searches free text.
        if row["probe"] == "travel_between_stops" and exp.get("adjacent") and exp.get("travel_mode_from_prev"):
            if not row["grounded"] or any(p in ans_lower for p in DENIAL_PHRASES):
                flags.append(("TRAVEL_DATA_AVAILABLE_BUT_UNUSED", row))

        # Alternatives/expansion answers that name a specific place -- check
        # it's a real POI, not invented. Heuristic: capitalized 2-4 word
        # phrases not equal to the target stop itself.
        if row["category"] in ("alternatives", "expansion") and row["answer"]:
            candidates = re.findall(r"\b(?:[A-Z][a-zA-Z']+(?:\s+(?:[A-Z][a-zA-Z']+|of|the|and))*)\b", row["answer"])
            candidates = [c.strip() for c in candidates if len(c.split()) >= 2 and len(c) > 6]
            unverified = [c for c in candidates if c.lower() not in VALID_POI_NAMES and "delhi" not in c.lower()]
            if unverified:
                flags.append(("POSSIBLE_UNVERIFIED_PLACE_NAME", {**row, "candidates": unverified}))

out = {
    "total_steps": len(rows),
    "flag_counts": {},
    "flags": [{"flag": f, **r} for f, r in flags],
    "rows": rows,
}
for f, _ in flags:
    out["flag_counts"][f] = out["flag_counts"].get(f, 0) + 1

with open(os.path.join(RESULTS_DIR, "_analysis_phase2.json"), "w", encoding="utf-8") as f:
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
print("=== Category distribution ===")
print(Counter(r["category"] for r in rows))
