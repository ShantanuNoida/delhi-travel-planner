"""
Team Waypoint -- Itinerary edit commands QA (Phase 1)

Agent 1 (Coordinator) drives this whole script in order:
  Agent 2 (Itinerary Generator)  -> build_itinerary()
  Agent 3 (Edit Command Agent)   -> generate_edit_commands() + apply each via the real app
  [Agent 4 and Agent 5's work happens afterwards, offline, over these logs]

This calls the REAL application code (phase2/itinerary_builder + phase4's
intent_classifier/edit_engine + phase5's eval checks) -- no simulated/mocked
behavior. Each of the 20 itineraries gets a real 15-command editing session,
applied cumulatively (each edit builds on the previous one, like a real user
session), with the real Gemini-backed intent classifier parsing every
command exactly as the live app would.

Usage: python run_qa.py [start_id] [end_id]   (1-based, inclusive; default 1 20)
Writes phase7_qa/results/itinerary_<id>.json per itinerary as it finishes
(so a partial run is never lost), plus results/_progress.log.
"""

import copy
import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase2", "phase4", "phase5"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from itinerary_specs import ITINERARY_SPECS, CITY  # noqa: E402
from edit_commands import generate_edit_commands  # noqa: E402

from poi_search import poi_search_logic  # noqa: E402
from itinerary_builder import itinerary_builder_logic  # noqa: E402
from intent_classifier import classify_intent  # noqa: E402
from edit_engine import apply_edit  # noqa: E402
from feasibility import check_feasibility  # noqa: E402
from edit_correctness import check_edit_correctness  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
PROGRESS_LOG = os.path.join(RESULTS_DIR, "_progress.log")

CALL_SPACING_SEC = 1.5  # gentle pacing between LLM classify_intent calls
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 20


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def classify_with_retry(text: str) -> dict:
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return classify_intent(text)
        except Exception as e:  # noqa: BLE001 -- deliberately broad: this is a QA harness,
            # any classifier failure (rate limit exhausted across all rotated
            # keys, transient network error, etc.) should be retried a few
            # times with backoff rather than aborting the whole run.
            last_exc = e
            log(f"    classify_intent error (attempt {attempt}/{MAX_RETRIES}): {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)
    return {"intent": "ERROR", "edit_intent": None, "query": text, "_error": str(last_exc)}


def summarize_itinerary(itin: dict) -> dict:
    """Compact summary for logging (full itinerary is also saved separately)."""
    out = {}
    for key in sorted((k for k in itin if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        day = itin[key]
        out[key] = {
            "total_hours": day.get("total_hours"),
            "stops": [
                {"slot": slot, "name": s["name"], "category": s.get("category"),
                 "arrival_time": s.get("arrival_time"), "travel_min": s.get("travel_time_from_prev_min")}
                for slot in ("morning", "afternoon", "evening") for s in day.get(slot, [])
            ],
        }
    return out


def build_itinerary(spec: dict) -> dict:
    pois = poi_search_logic(CITY, spec["interests"], constraints={"pace": spec["pace"]}, top_n=30)
    itinerary = itinerary_builder_logic(pois, days=spec["days"], pace=spec["pace"])
    return itinerary


def run_one(spec: dict) -> dict:
    log(f"=== Itinerary {spec['id']:02d}: {spec['label']} ({spec['days']}-day, {spec['pace']}, interests={spec['interests']}) ===")
    itinerary = build_itinerary(spec)
    initial_snapshot = summarize_itinerary(itinerary)
    log(f"  Built: {len(itinerary)} days, " + ", ".join(f"{k}={itinerary[k]['total_hours']}h" for k in sorted(itinerary, key=lambda k: int(k.split('_')[1]))))

    commands = generate_edit_commands(itinerary, spec)

    state = copy.deepcopy(itinerary)
    steps = []
    for cmd in commands:
        log(f"  [{cmd['n']:02d}/15] ({cmd['category']}/{cmd['probe']}) \"{cmd['command']}\"")
        before = copy.deepcopy(state)
        time.sleep(CALL_SPACING_SEC)
        classification = classify_with_retry(cmd["command"])

        step = {
            "n": cmd["n"],
            "command": cmd["command"],
            "category": cmd["category"],
            "probe": cmd["probe"],
            "expected": cmd["expected"],
            "classification": classification,
        }

        if classification.get("intent") == "EDIT" and classification.get("edit_intent"):
            edit_intent = classification["edit_intent"]
            result = apply_edit(state, edit_intent, pace=spec["pace"], city=CITY)
            step["edit_result_ok"] = result["ok"]
            step["edit_result_message"] = result["message"]
            step["changed_days"] = result["changed_days"]
            if result["ok"]:
                state = result["itinerary"]
            correctness = check_edit_correctness(
                before, state, edit_intent.get("target_day", "all"), edit_intent.get("target_slot", "all")
            )
            step["edit_correctness"] = correctness
        else:
            step["edit_result_ok"] = None
            step["edit_result_message"] = f"Not applied -- classified as {classification.get('intent')}, not EDIT."
            step["changed_days"] = []
            step["edit_correctness"] = None

        feasibility = check_feasibility(state, spec["pace"])
        step["feasibility_after"] = feasibility
        step["state_after_snapshot"] = summarize_itinerary(state)

        steps.append(step)
        log(f"       -> intent={classification.get('intent')} edit_type={classification.get('edit_intent', {}).get('edit_type') if classification.get('edit_intent') else None} "
            f"ok={step['edit_result_ok']} feasible={feasibility['pass']} :: {step['edit_result_message'][:100]}")

    result = {
        "spec": spec,
        "initial_itinerary_full": itinerary,
        "initial_itinerary_summary": initial_snapshot,
        "final_itinerary_full": state,
        "final_itinerary_summary": summarize_itinerary(state),
        "steps": steps,
    }
    out_path = os.path.join(RESULTS_DIR, f"itinerary_{spec['id']:02d}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log(f"  Saved -> {out_path}")
    return result


def main():
    start_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end_id = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    log(f"Team Waypoint -- Itinerary edit commands QA run starting (itineraries {start_id}-{end_id})")
    for spec in ITINERARY_SPECS:
        if not (start_id <= spec["id"] <= end_id):
            continue
        out_path = os.path.join(RESULTS_DIR, f"itinerary_{spec['id']:02d}.json")
        if os.path.exists(out_path):
            log(f"Skipping itinerary {spec['id']:02d} (already has a result file)")
            continue
        try:
            run_one(spec)
        except Exception:
            log(f"FAILED itinerary {spec['id']:02d}:\n{traceback.format_exc()}")
    log("Run complete.")


if __name__ == "__main__":
    main()
