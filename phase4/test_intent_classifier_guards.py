"""
Phase 4 test suite -- classifier collision-guard regression tests.
Usage: python main.py --test   (or: python test_intent_classifier_guards.py)

Covers the H3 (EDIT-vs-EXPLAIN) and NEW_PLAN (NEW_PLAN-vs-EXPLAIN) guard
functions added after Team Waypoint's Phase 2 QA found real venue names
colliding with the classifier's own vocabulary/brand associations
("Make My Lagan" silently misrouted to EDIT, then separately to NEW_PLAN --
see "Itinerary edit commands QA.md"). These guards were, until now, only
exercised indirectly inside the phase7_qa QA harness scripts -- this file
tests them directly so a future prompt/keyword-list edit that silently
reintroduces one of those regressions fails immediately.

No LLM calls -- every function tested here is a pure, deterministic string
check, so this runs instantly and needs no API key.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from intent_classifier import (  # noqa: E402
    _looks_like_a_question,
    _matches_real_stop_name,
    _mentions_real_stop_name,
    _has_restart_signal,
)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def _result(label: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


_SAMPLE_ITINERARY = {
    "day_1": {
        "morning": [{"name": "Make My Lagan"}],
        "afternoon": [{"name": "Karim's"}],
        "evening": [],
    },
    "day_2": {
        "morning": [{"name": "Humayun's Tomb"}],
        "afternoon": [],
        "evening": [],
    },
}


# ---------------------------------------------------------------------------
# T-4.7  H3 guard: _looks_like_a_question
# ---------------------------------------------------------------------------
def test_looks_like_a_question() -> bool:
    print("\nT-4.7 — H3 Guard: _looks_like_a_question")

    cases = [
        ("What are some alternatives to Make My Lagan?", True),
        ("Why did you pick this place?", True),
        ("Is this doable?", True),
        ("Give me some other options besides Lodhi Garden", True),   # imperative info-request (recheck fix)
        ("Show me some alternatives to the museum", True),
        ("Tell me about Make My Lagan alternatives", True),
        ("Make Day 2 more relaxed.", False),                          # genuine EDIT, must NOT look like a question
        ("Add one famous local food place to Day 1.", False),
        ("Swap Day 1 evening for something indoors.", False),
        ("Remove the museum on Day 3.", False),
    ]
    all_ok = True
    for text, expected in cases:
        got = _looks_like_a_question(text)
        ok = got == expected
        all_ok &= ok
        _result(f'"{text}"', ok, f"expected={expected}, got={got}")
    return all_ok


# ---------------------------------------------------------------------------
# T-4.8  H3 guard: _matches_real_stop_name (exact-match only, by design)
# ---------------------------------------------------------------------------
def test_matches_real_stop_name() -> bool:
    print("\nT-4.8 — H3 Guard: _matches_real_stop_name (exact match only)")

    cases = [
        ("Make My Lagan", True),
        ("make my lagan", True),          # case-insensitive
        ("  Karim's  ", True),            # surrounding whitespace tolerated
        ("", False),                      # empty constraint never matches
        ("Some Other Restaurant", False), # not a real stop
        # Deliberately NOT an exact match -- a longer descriptive phrase
        # containing the stop's name must NOT match, since that's the whole
        # point of requiring an exact match (avoid overriding a legitimate
        # edit that happens to mention a stop by name within a longer
        # constraint, e.g. "swap Karim's for something else").
        ("other restaurant options besides Make My Lagan", False),
    ]
    all_ok = True
    for constraint, expected in cases:
        got = _matches_real_stop_name(constraint, _SAMPLE_ITINERARY)
        ok = got == expected
        all_ok &= ok
        _result(f'constraint={constraint!r}', ok, f"expected={expected}, got={got}")
    return all_ok


# ---------------------------------------------------------------------------
# T-4.9  NEW_PLAN guard: _mentions_real_stop_name (substring, by design)
# ---------------------------------------------------------------------------
def test_mentions_real_stop_name() -> bool:
    print("\nT-4.9 — NEW_PLAN Guard: _mentions_real_stop_name (substring match)")

    cases = [
        ("Give me some alternatives besides Make My Lagan", True),
        ("What else could I try instead of Make My Lagan?", True),
        ("Is Humayun's Tomb worth visiting?", True),
        ("I want to plan a completely new trip", False),
        ("Forget everything, let's start over", False),
    ]
    all_ok = True
    for text, expected in cases:
        got = _mentions_real_stop_name(text, _SAMPLE_ITINERARY)
        ok = got == expected
        all_ok &= ok
        _result(f'"{text}"', ok, f"expected={expected}, got={got}")
    return all_ok


# ---------------------------------------------------------------------------
# T-4.10  NEW_PLAN guard: _has_restart_signal
# ---------------------------------------------------------------------------
def test_has_restart_signal() -> bool:
    print("\nT-4.10 — NEW_PLAN Guard: _has_restart_signal")

    cases = [
        ("Actually forget Make My Lagan and everything else, let's start over with a totally different trip to Goa.", True),
        ("I want to start planning a completely new trip.", True),
        ("Scrap this plan and make me a new one.", True),
        ("Give me some alternatives besides Make My Lagan", False),
        ("What are some alternatives to Make My Lagan?", False),
    ]
    all_ok = True
    for text, expected in cases:
        got = _has_restart_signal(text)
        ok = got == expected
        all_ok &= ok
        _result(f'"{text}"', ok, f"expected={expected}, got={got}")
    return all_ok


# ---------------------------------------------------------------------------
# T-4.11  Combined guard behavior on the real repro cases (still no LLM call --
# tests the guard logic exactly as classify_intent() applies it, not the
# classifier itself)
# ---------------------------------------------------------------------------
def test_combined_guard_repros() -> bool:
    print("\nT-4.11 — Combined Guard Logic on Real Repro Cases")

    all_ok = True

    # H3 repro: raw EDIT + question-shaped + exact stop-name constraint -> should override to EXPLAIN.
    text = "What are some alternatives to Make My Lagan?"
    would_override = (
        _looks_like_a_question(text)
        and _matches_real_stop_name("Make My Lagan", _SAMPLE_ITINERARY)
    )
    all_ok &= _result("H3 repro: EDIT would be overridden to EXPLAIN", would_override)

    # NEW_PLAN repro: real stop mentioned, no restart signal -> should override to EXPLAIN.
    text2 = "Give me some alternatives besides Make My Lagan"
    would_override2 = (
        _mentions_real_stop_name(text2, _SAMPLE_ITINERARY)
        and not _has_restart_signal(text2)
    )
    all_ok &= _result("NEW_PLAN repro: NEW_PLAN would be overridden to EXPLAIN", would_override2)

    # Regression: a genuine restart request that also names a stop must NOT be overridden.
    text3 = "Actually forget Make My Lagan and everything else, let's start over with a totally different trip to Goa."
    would_override3 = (
        _mentions_real_stop_name(text3, _SAMPLE_ITINERARY)
        and not _has_restart_signal(text3)
    )
    all_ok &= _result("genuine restart request stays NEW_PLAN (not overridden)", not would_override3)

    return all_ok


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all() -> dict[str, bool]:
    print("=" * 60)
    print("PHASE 4 CLASSIFIER GUARD REGRESSION TESTS (no LLM calls)")
    print("=" * 60)

    results = {
        "T-4.7 _looks_like_a_question":       test_looks_like_a_question(),
        "T-4.8 _matches_real_stop_name":      test_matches_real_stop_name(),
        "T-4.9 _mentions_real_stop_name":     test_mentions_real_stop_name(),
        "T-4.10 _has_restart_signal":         test_has_restart_signal(),
        "T-4.11 Combined Guard Repros":       test_combined_guard_repros(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results.values())
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(results)} tests passed")
    return results


if __name__ == "__main__":
    run_all()
