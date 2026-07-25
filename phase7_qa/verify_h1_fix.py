"""
Verifies the H1 fix ("Itinerary edit commands QA.md", Phase 2, Part 6):
answers were tagged grounded=True with citations attached even when the
synthesized answer itself was an honest "I don't have this information"
denial.

No new LLM calls: monkeypatches explain_engine._synthesize_answer to return
the EXACT real answer text recorded during the Phase 2 QA run (both the 82
denial cases the fix targets, and a sample of genuine substantive answers,
to confirm no regression), then checks the real explain() function's output
against the fixed post-processing logic.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase1", "phase2", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

import explain_engine  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def load_analysis():
    with open(os.path.join(RESULTS_DIR, "_analysis_phase2.json"), encoding="utf-8") as f:
        return json.load(f)


def load_itinerary(itin_id):
    with open(os.path.join(RESULTS_DIR, f"phase2_itinerary_{itin_id:02d}.json"), encoding="utf-8") as f:
        return json.load(f)["itinerary_full"]


analysis = load_analysis()
denial_rows = [f for f in analysis["flags"] if f["flag"] == "FALSE_GROUNDED_DENIAL_ANSWER"]
print(f"Replaying all {len(denial_rows)} real recorded denial-but-grounded cases from the Phase 2 run...")

failures = []
for row in denial_rows:
    itin = load_itinerary(row["itin"])
    recorded_data = load_itinerary_step = None
    # Pull the exact step (command, target_stop) to rebuild the real call.
    with open(os.path.join(RESULTS_DIR, f"phase2_itinerary_{row['itin']:02d}.json"), encoding="utf-8") as f:
        full = json.load(f)
    step = next(s for s in full["steps"] if s["n"] == row["n"])
    recorded_answer_text = row["answer"]

    # Monkeypatch _synthesize_answer to return the exact real denial text
    # that was actually produced for this question, so we're testing the
    # fixed post-processing logic against real observed model output, not a
    # synthetic stand-in.
    explain_engine._synthesize_answer = lambda query, hits, _t=recorded_answer_text: _t

    result = explain_engine.explain(step["command"], itin, full["spec"]["pace"])

    ok = result["grounded"] is False and result["answer"] == explain_engine.NO_SOURCE_TEXT and result["citations"] == []
    status = "PASS" if ok else "FAIL"
    if not ok:
        failures.append((row["itin"], row["n"], result))
    print(f"  [{status}] itin {row['itin']:02d} q{row['n']:02d} ({row['probe']}): "
          f"grounded={result['grounded']} citations={len(result['citations'])} "
          f":: was {recorded_answer_text[:70]!r}")

print()
print(f"{len(denial_rows) - len(failures)}/{len(denial_rows)} denial cases now correctly downgraded to grounded=False, no citations.")
assert not failures, f"H1 fix did not correctly downgrade: {failures}"

print()
print("=" * 70)
print("Regression check: genuine substantive grounded answers must stay grounded=True")
print("=" * 70)

all_rows = analysis["rows"]
substantive = [r for r in all_rows if r["grounded"] is True and r["category"] in ("justification", "practicalities", "alternatives", "expansion")
               and not any(f["itin"] == r["itin"] and f["n"] == r["n"] for f in denial_rows)]
sample = substantive[:15]
reg_failures = []
for row in sample:
    with open(os.path.join(RESULTS_DIR, f"phase2_itinerary_{row['itin']:02d}.json"), encoding="utf-8") as f:
        full = json.load(f)
    step = next(s for s in full["steps"] if s["n"] == row["n"])
    itin = load_itinerary(row["itin"])
    recorded_answer_text = row["answer"]

    explain_engine._synthesize_answer = lambda query, hits, _t=recorded_answer_text: _t
    result = explain_engine.explain(step["command"], itin, full["spec"]["pace"])

    ok = result["grounded"] is True and result["answer"] == recorded_answer_text
    status = "PASS" if ok else "FAIL"
    if not ok:
        reg_failures.append((row["itin"], row["n"], result))
    print(f"  [{status}] itin {row['itin']:02d} q{row['n']:02d} ({row['probe']}): grounded={result['grounded']} "
          f":: {recorded_answer_text[:70]!r}")

print()
print(f"{len(sample) - len(reg_failures)}/{len(sample)} genuine substantive answers correctly still grounded=True (no regression).")
assert not reg_failures, f"H1 fix over-triggered on genuine answers: {reg_failures}"

print()
print("ALL H1 VERIFICATION CHECKS PASSED.")
