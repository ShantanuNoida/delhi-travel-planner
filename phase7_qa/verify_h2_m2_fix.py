"""
Verifies the H2/M2 fix ("Itinerary edit commands QA.md", Phase 2, Part 6):
cost/best-time/suitability questions about a named, scheduled stop now
answer directly from that stop's own kb_entry_fee/kb_best_time_to_visit/
kb_suitable_for fields (H2) with a real citation, and suitability answers
give a direct yes/no for the audience asked about instead of a scene
description (M2) -- instead of relying on RAG-search luck.

The new code path (_direct_kb_answer) is fully deterministic (no LLM call),
so this replays the REAL saved Phase 2 itineraries end-to-end through the
real explain() function -- no mocking needed, and zero new LLM spend.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase1", "phase2", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from explain_engine import explain  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load_analysis():
    with open(os.path.join(RESULTS_DIR, "_analysis_phase2.json"), encoding="utf-8") as f:
        return json.load(f)


def load_step(itin_id, n):
    with open(os.path.join(RESULTS_DIR, f"phase2_itinerary_{itin_id:02d}.json"), encoding="utf-8") as f:
        full = json.load(f)
    step = next(s for s in full["steps"] if s["n"] == n)
    return full, step


analysis = load_analysis()
kb_unused_rows = [f for f in analysis["flags"] if f["flag"] == "KB_DATA_AVAILABLE_BUT_UNUSED"]
print(f"=== H2: replaying all {len(kb_unused_rows)} real 'KB data available but unused' cases ===")

failures = []
for row in kb_unused_rows:
    full, step = load_step(row["itin"], row["n"])
    result = explain(step["command"], full["itinerary_full"], full["spec"]["pace"])
    exp = row["expected"] or {}
    kb_value = exp.get("kb_entry_fee") or exp.get("kb_best_time_to_visit")
    if kb_value:
        ok = result["grounded"] is True and result["citations"] and kb_value in result["answer"]
    else:
        # suitability_elderly rows store the tag list, not a plain substring
        tags = exp.get("kb_suitable_for") or []
        ok = result["grounded"] is True and result["citations"] and any(t in result["answer"] for t in tags)
    status = "PASS" if ok else "FAIL"
    if not ok:
        failures.append((row["itin"], row["n"], result))
    print(f"  [{status}] itin {row['itin']:02d} q{row['n']:02d} ({row['probe']}) \"{step['command']}\"")
    print(f"           -> grounded={result['grounded']} citations={len(result['citations'])} :: {result['answer'][:140]}")

print()
print(f"{len(kb_unused_rows) - len(failures)}/{len(kb_unused_rows)} previously-missed KB facts now answered directly and correctly.")
assert not failures, f"H2 fix did not correctly surface KB data: {failures}"

print()
print("=" * 70)
print("=== M2: suitability_elderly answers now give a direct yes/no, not a scene description ===")
print("=" * 70)
suit_rows = [r for r in analysis["rows"] if r["probe"] == "suitability_elderly"]
m2_failures = []
for row in suit_rows:
    full, step = load_step(row["itin"], row["n"])
    result = explain(step["command"], full["itinerary_full"], full["spec"]["pace"])
    exp = row["expected"] or {}
    has_kb = bool(exp.get("kb_suitable_for"))
    if has_kb:
        ok = result["answer"].startswith("Yes —") or "isn't specifically tagged" in result["answer"]
    else:
        ok = True  # no KB data on this stop -- unchanged RAG/no-source behavior, not this fix's concern
    status = "PASS" if ok else "FAIL"
    if not ok:
        m2_failures.append((row["itin"], row["n"], result))
    print(f"  [{status}] itin {row['itin']:02d} q{row['n']:02d} has_kb={has_kb} :: {result['answer'][:140]}")

print()
print(f"{len(suit_rows) - len(m2_failures)}/{len(suit_rows)} suitability answers verified.")
assert not m2_failures, f"M2 fix did not produce a direct answer: {m2_failures}"

print()
print("=" * 70)
print("=== Regression: stops WITHOUT kb data must fall through unchanged ===")
print("=" * 70)
from explain_engine import _direct_kb_answer  # noqa: E402

no_kb_rows = [r for r in analysis["rows"]
              if r["probe"] in ("cost_named_stop", "best_time_named_stop", "suitability_elderly")
              and not (r["expected"] or {}).get("kb_entry_fee")
              and not (r["expected"] or {}).get("kb_best_time_to_visit")
              and not (r["expected"] or {}).get("kb_suitable_for")]
reg_failures = []
for row in no_kb_rows[:10]:
    full, step = load_step(row["itin"], row["n"])
    itin = full["itinerary_full"]
    target = row["target_stop"]
    stop = None
    for k in itin:
        if not k.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[k].get(slot, []):
                if s.get("name") == target:
                    stop = s
    ok = stop is not None and _direct_kb_answer(step["command"], stop) is None
    status = "PASS" if ok else "FAIL"
    if not ok:
        reg_failures.append((row["itin"], row["n"]))
    print(f"  [{status}] itin {row['itin']:02d} q{row['n']:02d} ({row['probe']}) -- no KB data, _direct_kb_answer correctly returns None")

print()
print(f"{len(no_kb_rows[:10]) - len(reg_failures)}/{len(no_kb_rows[:10])} no-KB-data stops correctly fall through to the unchanged RAG path.")
assert not reg_failures, f"Fix incorrectly fired with no KB data: {reg_failures}"

print()
print("ALL H2/M2 VERIFICATION CHECKS PASSED.")
