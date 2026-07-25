"""
Phase 5 test suite — runs tests T-5.1 through T-5.8.
Usage: python main.py --test   (or: python test_phase5.py)
"""

import copy
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase2"))
sys.path.insert(0, os.path.join(_ROOT, "phase4"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def _result(label: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


def _stop(osm_id, name, category, duration_min, travel_min=0, relevance=0.8):
    return {
        "osm_id": osm_id, "name": name, "category": category,
        "lat": 28.6, "lon": 77.2, "visit_duration_min": duration_min,
        "travel_time_from_prev_min": travel_min, "relevance_score": relevance,
        "opening_hours": "unknown",
    }


# ---------------------------------------------------------------------------
# T-5.1  Feasibility Eval: Passing Plan
# ---------------------------------------------------------------------------
def test_feasibility_pass() -> bool:
    print("\nT-5.1 — Feasibility Eval: Passing Plan")
    from feasibility import check_feasibility

    itinerary = {
        "day_1": {"morning": [_stop("1", "A", "monument", 180)], "afternoon": [], "evening": [], "total_hours": 5.5, "date": ""},
    }
    result = check_feasibility(itinerary, pace="relaxed")
    ok = result["pass"] is True and result["issues"] == []
    return _result("returns pass=True, no issues", ok, str(result))


# ---------------------------------------------------------------------------
# T-5.2  Feasibility Eval: Failing Plan
# ---------------------------------------------------------------------------
def test_feasibility_fail() -> bool:
    print("\nT-5.2 — Feasibility Eval: Failing Plan")
    from feasibility import check_feasibility

    itinerary = {
        "day_1": {"morning": [_stop("1", "A", "monument", 300)], "afternoon": [], "evening": [], "total_hours": 5.0, "date": ""},
        "day_2": {"morning": [_stop("2", "B", "monument", 480)], "afternoon": [], "evening": [], "total_hours": 9.0, "date": ""},
        "day_3": {"morning": [_stop("3", "C", "monument", 300)], "afternoon": [], "evening": [], "total_hours": 5.0, "date": ""},
    }
    result = check_feasibility(itinerary, pace="relaxed")

    fails = result["pass"] is False
    day2_flagged = any(i["day"] == 2 for i in result["issues"])
    day1_day3_clean = not any(i["day"] in (1, 3) for i in result["issues"])

    _result("overall pass=False", fails)
    _result("Day 2 flagged", day2_flagged, str(result["issues"]))
    _result("Day 1 and Day 3 not flagged", day1_day3_clean)
    return fails and day2_flagged and day1_day3_clean


# ---------------------------------------------------------------------------
# T-5.3  Feasibility Eval: Long Travel Leg
# ---------------------------------------------------------------------------
def test_feasibility_long_leg() -> bool:
    print("\nT-5.3 — Feasibility Eval: Long Travel Leg")
    from feasibility import check_feasibility

    itinerary = {
        "day_1": {
            "morning": [_stop("1", "A", "monument", 90), _stop("2", "B", "monument", 90, travel_min=60)],
            "afternoon": [], "evening": [], "total_hours": 4.0, "date": "",
        },
        "day_2": {"morning": [_stop("3", "C", "monument", 90)], "afternoon": [], "evening": [], "total_hours": 1.5, "date": ""},
    }
    result = check_feasibility(itinerary, pace="moderate")

    fails = result["pass"] is False
    leg_flagged = any("B" in i["problem"] for i in result["issues"])
    day2_clean = not any(i["day"] == 2 for i in result["issues"])

    _result("overall pass=False", fails)
    _result("60-min leg to B flagged", leg_flagged, str(result["issues"]))
    _result("Day 2 unaffected", day2_clean)
    return fails and leg_flagged and day2_clean


# ---------------------------------------------------------------------------
# T-5.4  Edit Correctness Eval: Clean Edit
# ---------------------------------------------------------------------------
def test_edit_correctness_clean() -> bool:
    print("\nT-5.4 — Edit Correctness Eval: Clean Edit")
    from edit_correctness import check_edit_correctness

    before = {
        "day_1": {"morning": [_stop("1", "A", "monument", 90)], "afternoon": [], "evening": [_stop("2", "B", "restaurant", 60)], "total_hours": 2.5, "date": ""},
    }
    after = copy.deepcopy(before)
    after["day_1"]["evening"] = [_stop("3", "C", "restaurant", 60)]  # only evening changed

    result = check_edit_correctness(before, after, target_day=1, target_slot="evening")
    ok = result["pass"] is True and result["drifted_slots"] == []
    return _result("returns pass=True, no drift", ok, str(result))


# ---------------------------------------------------------------------------
# T-5.5  Edit Correctness Eval: Drift Detection
# ---------------------------------------------------------------------------
def test_edit_correctness_drift() -> bool:
    print("\nT-5.5 — Edit Correctness Eval: Drift Detection")
    from edit_correctness import check_edit_correctness

    before = {
        "day_1": {"morning": [_stop("1", "A", "monument", 90)], "afternoon": [], "evening": [_stop("2", "B", "restaurant", 60)], "total_hours": 2.5, "date": ""},
        "day_2": {"morning": [_stop("3", "C", "monument", 90)], "afternoon": [], "evening": [], "total_hours": 1.5, "date": ""},
    }
    after = copy.deepcopy(before)
    after["day_1"]["evening"] = [_stop("4", "D", "restaurant", 60)]        # declared target — OK
    after["day_2"]["morning"] = [_stop("5", "E", "monument", 90)]          # undeclared drift

    result = check_edit_correctness(before, after, target_day=1, target_slot="evening")
    ok = result["pass"] is False and result["drifted_slots"] == ["day_2.morning"]
    return _result("detects day_2.morning drift", ok, str(result))


# ---------------------------------------------------------------------------
# T-5.6  Grounding Eval: All POIs Verified
# ---------------------------------------------------------------------------
def test_grounding_pass() -> bool:
    print("\nT-5.6 — Grounding Eval: All POIs Verified")
    from grounding import check_grounding
    from poi_search import poi_search_logic

    real_pois = poi_search_logic("New Delhi", ["history"], top_n=2)
    itinerary = {
        "day_1": {"morning": [{**p, "travel_time_from_prev_min": 0} for p in real_pois], "afternoon": [], "evening": [], "total_hours": 3.0, "date": ""},
    }
    result = check_grounding(itinerary)
    ok = result["pass"] is True and result["ungrounded_pois"] == []
    return _result("all real POIs verified", ok, str(result))


# ---------------------------------------------------------------------------
# T-5.7  Grounding Eval: Unverified POI Detection
# ---------------------------------------------------------------------------
def test_grounding_fail() -> bool:
    print("\nT-5.7 — Grounding Eval: Unverified POI Detection")
    from grounding import check_grounding

    itinerary = {
        "day_1": {"morning": [_stop("fake-osm-id-999999", "Fabricated Palace", "monument", 90)], "afternoon": [], "evening": [], "total_hours": 1.5, "date": ""},
    }
    result = check_grounding(itinerary)
    ok = result["pass"] is False and "Fabricated Palace" in result["ungrounded_pois"]
    return _result("flags fabricated POI, not silently kept", ok, str(result))


# ---------------------------------------------------------------------------
# T-5.8  Eval CLI Runner
# ---------------------------------------------------------------------------
def test_cli_runner() -> bool:
    print("\nT-5.8 — Eval CLI Runner")
    import subprocess

    phase5_dir = os.path.dirname(os.path.abspath(__file__))
    fixture = os.path.join(phase5_dir, "sample_itinerary.json")
    log_path = os.path.join(phase5_dir, "eval_results.log")

    if os.path.exists(log_path):
        size_before = os.path.getsize(log_path)
    else:
        size_before = -1  # doesn't exist yet

    proc = subprocess.run(
        [sys.executable, os.path.join(phase5_dir, "evals.py"), "--input", fixture, "--pace", "moderate"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    completed = proc.returncode in (0, 1)  # both are "ran successfully"; 1 just means an eval failed
    has_output = "OVERALL:" in proc.stdout
    log_written = os.path.exists(log_path) and os.path.getsize(log_path) > max(size_before, 0)

    _result("command completes without crashing", completed, f"returncode={proc.returncode}")
    _result("terminal shows PASS/FAIL summary", has_output)
    _result("log file is written", log_written)
    return completed and has_output and log_written


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all() -> dict[str, bool]:
    print("=" * 60)
    print("PHASE 5 VALIDATION TESTS")
    print("=" * 60)

    results = {
        "T-5.1 Feasibility Pass":        test_feasibility_pass(),
        "T-5.2 Feasibility Fail":        test_feasibility_fail(),
        "T-5.3 Feasibility Long Leg":    test_feasibility_long_leg(),
        "T-5.4 Edit Correctness Clean":  test_edit_correctness_clean(),
        "T-5.5 Edit Correctness Drift":  test_edit_correctness_drift(),
        "T-5.6 Grounding Pass":          test_grounding_pass(),
        "T-5.7 Grounding Fail":          test_grounding_fail(),
        "T-5.8 CLI Runner":              test_cli_runner(),
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
