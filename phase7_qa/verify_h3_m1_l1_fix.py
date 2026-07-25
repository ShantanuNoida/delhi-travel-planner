"""
Verifies the H3, M1, and L1 fixes ("Itinerary edit commands QA.md", Phase 2,
Part 6).

H3 — a real venue's own name ("Make My Lagan") could misroute a question
     into a silent EDIT. Deterministic checks against the pure guard
     functions, plus ONE real end-to-end classify_intent() call against the
     actual recorded repro case (the only real LLM spend in this script).
M1 — "alternatives" answers naming a real-but-unlisted place now get an
     honest caveat appended. Fully deterministic, replays real recorded
     Phase 2 answer text -- no LLM calls.
L1 — _synthesize_answer() returning None (empty completion) no longer
     crashes. Fully deterministic via monkeypatching -- no LLM calls.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase1", "phase2", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

print("=" * 70)
print("H3 -- deterministic guard-function checks (no LLM call)")
print("=" * 70)
from intent_classifier import _looks_like_a_question, _matches_real_stop_name  # noqa: E402

with open(os.path.join(RESULTS_DIR, "phase2_itinerary_13.json"), encoding="utf-8") as f:
    itin13 = json.load(f)["itinerary_full"]

real_command = "What are some alternatives to Make My Lagan on Day 2?"
checks = [
    ("real repro is question-shaped", _looks_like_a_question(real_command) is True),
    ("real repro's constraint matches a real stop", _matches_real_stop_name("Make My Lagan", itin13) is True),
    ("a non-existent name does not match", _matches_real_stop_name("Make My Nonexistent Place", itin13) is False),
    ("a genuine EDIT command is not question-shaped", _looks_like_a_question("Make Day 2 more relaxed.") is False),
    ("empty constraint never matches", _matches_real_stop_name("", itin13) is False),
]
h3_failures = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
assert not h3_failures, f"H3 guard-function checks failed: {h3_failures}"

print()
print("=" * 70)
print("H3 -- ONE real end-to-end classify_intent() call against the actual repro")
print("=" * 70)
from intent_classifier import classify_intent  # noqa: E402

before = classify_intent(real_command)  # no itinerary passed -- reproduces the ORIGINAL bug
print(f"  WITHOUT itinerary guard (reproduces original bug): intent={before['intent']}"
      + (f" edit_type={before['edit_intent'].get('edit_type')}" if before.get("edit_intent") else ""))

after = classify_intent(real_command, itinerary=itin13)
print(f"  WITH itinerary guard (the fix): intent={after['intent']}")
assert after["intent"] == "EXPLAIN", f"H3 fix did not reclassify the real repro case: {after}"
print("  PASS -- real repro now correctly classified EXPLAIN, not EDIT")

print()
print("=" * 70)
print("M1 -- replaying all 22 real recorded 'possible unbookable place' answers (no LLM calls)")
print("=" * 70)
from explain_engine import _append_unbookable_caveat, UNBOOKABLE_CAVEAT  # noqa: E402

with open(os.path.join(RESULTS_DIR, "_analysis_phase2.json"), encoding="utf-8") as f:
    analysis = json.load(f)
m1_rows = [f for f in analysis["flags"] if f["flag"] == "POSSIBLE_UNVERIFIED_PLACE_NAME"]
# These 2 of the 24 RAW analyzer flags are known false positives in the raw
# flag list itself (confirmed during the original Phase 2 write-up's own
# fuzzy-match refinement, "22 of 24 flags survive fuzzy substring check"):
# itin 5 q7's "Swaminarayan Akshardham" genuinely matches the real POI
# "Akshardham" (KB_NAME_OVERRIDES' own mapping), and itin 17 q7's every
# candidate phrase contains a genuinely real POI name as a substring
# ("...Safdarjung's Tomb", "Gandhi Smriti..."). The fix is expected to
# correctly NOT add a caveat to these two -- asserted explicitly below,
# not just skipped.
KNOWN_CORRECT_NON_TRIGGERS = {(5, 7), (17, 7)}
m1_failures = []
for row in m1_rows:
    result = _append_unbookable_caveat(row["answer"])
    fired = result.endswith(UNBOOKABLE_CAVEAT)
    should_fire = (row["itin"], row["n"]) not in KNOWN_CORRECT_NON_TRIGGERS
    ok = fired == should_fire
    if not ok:
        m1_failures.append((row["itin"], row["n"], row["candidates"]))
    tag = "PASS" if ok else "FAIL"
    note = "" if should_fire else " (expected non-trigger: real POI substring)"
    print(f"  [{tag}] itin {row['itin']:02d} q{row['n']:02d} fired={fired}{note} candidates={row['candidates']}")
print()
print(f"{len(m1_rows) - len(m1_failures)}/{len(m1_rows)} matched expected behavior "
      f"({len(m1_rows) - len(KNOWN_CORRECT_NON_TRIGGERS)} should fire, {len(KNOWN_CORRECT_NON_TRIGGERS)} should correctly not).")
assert not m1_failures, f"M1 fix behaved unexpectedly: {m1_failures}"

print()
print("=" * 70)
print("M1 -- false-positive check: substantive grounded answers that DON'T name an unlisted place")
print("=" * 70)
flagged_keys = {(f["itin"], f["n"]) for f in m1_rows}
clean_rows = [r for r in analysis["rows"]
              if r["grounded"] is True and r["category"] in ("justification", "practicalities")
              and (r["itin"], r["n"]) not in flagged_keys][:20]
fp_failures = []
for row in clean_rows:
    result = _append_unbookable_caveat(row["answer"])
    ok = not result.endswith(UNBOOKABLE_CAVEAT)
    if not ok:
        fp_failures.append((row["itin"], row["n"], row["answer"][:100]))
    print(f"  [{'PASS' if ok else 'FAIL'}] itin {row['itin']:02d} q{row['n']:02d} ({row['probe']}) -- caveat NOT appended, as expected")
print()
print(f"{len(clean_rows) - len(fp_failures)}/{len(clean_rows)} clean answers correctly left untouched (no false positives).")
if fp_failures:
    print("  Note: false positives found -- see below")
    for fp in fp_failures:
        print("   ", fp)
assert not fp_failures, f"M1 fix over-triggered on clean answers: {fp_failures}"

print()
print("=" * 70)
print("L1 -- _synthesize_or_no_source() no longer crashes on an empty completion (no LLM calls)")
print("=" * 70)
import explain_engine  # noqa: E402

# Case 1: first call returns None, retry succeeds -- should recover cleanly.
call_count = {"n": 0}
def _flaky_then_ok(query, hits):
    call_count["n"] += 1
    return None if call_count["n"] == 1 else "A real, substantive answer about the place."
explain_engine._synthesize_answer = _flaky_then_ok
result = explain_engine._synthesize_or_no_source("some question", [{"article_title": "x", "text": "y"}], [])
ok1 = result["grounded"] is True and result["answer"] == "A real, substantive answer about the place."
print(f"  [{'PASS' if ok1 else 'FAIL'}] retry recovers from one empty completion -- {result}")
assert ok1, "L1 fix: retry-recovery path did not work"

# Case 2: both calls return None -- should degrade gracefully to no-source, not crash.
explain_engine._synthesize_answer = lambda query, hits: None
result2 = explain_engine._synthesize_or_no_source("some question", [{"article_title": "x", "text": "y"}], [])
ok2 = result2["grounded"] is False and result2["answer"] == explain_engine.NO_SOURCE_TEXT
print(f"  [{'PASS' if ok2 else 'FAIL'}] both attempts empty -> honest no-source, no crash -- {result2}")
assert ok2, "L1 fix: double-empty-completion path did not degrade gracefully"

print()
print("ALL H3/M1/L1 VERIFICATION CHECKS PASSED.")
