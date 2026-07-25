"""
Standalone Eval CLI — Phase 5.

Usage:
  python evals.py --input sample_itinerary.json --pace moderate
  python evals.py --input after.json --before before.json --target-day 1 --target-slot evening
  python evals.py --input sample_itinerary.json --explanations explanations.json

Runs Eval 1 (Feasibility) always. Runs Eval 2 (Edit Correctness) only if
--before is given. Runs Eval 3 (Grounding) always; --explanations is optional.
Results are printed to the terminal and appended to eval_results.log.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase4"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feasibility import check_feasibility  # phase4
from edit_correctness import check_edit_correctness
from grounding import check_grounding

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results.log")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_evals(
    itinerary: dict,
    pace: str = "moderate",
    before: dict | None = None,
    target_day=None,
    target_slot: str | None = None,
    explanations: list[dict] | None = None,
) -> dict:
    results = {"eval_1_feasibility": check_feasibility(itinerary, pace)}

    if before is not None:
        results["eval_2_edit_correctness"] = check_edit_correctness(
            before, itinerary, target_day if target_day is not None else "all",
            target_slot or "all",
        )

    results["eval_3_grounding"] = check_grounding(itinerary, explanations)
    return results


def _format_report(results: dict) -> str:
    lines = []
    for name, result in results.items():
        status = "PASS" if result["pass"] else "FAIL"
        lines.append(f"[{status}] {name}")
        for key, value in result.items():
            if key == "pass":
                continue
            if value:
                lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run Phase 5 evals against an itinerary JSON.")
    parser.add_argument("--input", required=True, help="Path to the (current/after) itinerary JSON")
    parser.add_argument("--pace", default="moderate", choices=["relaxed", "moderate", "intensive"])
    parser.add_argument("--before", help="Path to the pre-edit itinerary JSON (enables Eval 2)")
    parser.add_argument("--target-day", default="all", help='1, 2, 3, 4, or "all" (for Eval 2)')
    parser.add_argument("--target-slot", default="all", choices=["morning", "afternoon", "evening", "all"])
    parser.add_argument("--explanations", help="Path to a JSON list of explanation dicts (for Eval 3)")
    args = parser.parse_args()

    itinerary = _load(args.input)
    before = _load(args.before) if args.before else None
    explanations = _load(args.explanations) if args.explanations else None

    target_day = args.target_day
    if target_day != "all":
        target_day = int(target_day)

    results = run_evals(
        itinerary, pace=args.pace, before=before,
        target_day=target_day, target_slot=args.target_slot,
        explanations=explanations,
    )

    report = _format_report(results)
    print(report)

    overall_pass = all(r["pass"] for r in results.values())
    print(f"\nOVERALL: {'PASS' if overall_pass else 'FAIL'}")

    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n=== {datetime.now(timezone.utc).isoformat()} — input={args.input} ===\n")
        f.write(report + "\n")
        f.write(f"OVERALL: {'PASS' if overall_pass else 'FAIL'}\n")

    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
