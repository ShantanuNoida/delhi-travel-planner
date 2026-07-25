"""
Team Waypoint -- 30 Random Itineraries QA (cuisine + category coverage round).

Agent 1 (Coordinator) drives this whole script:
  Agent 2 (Itinerary Generator) -> cuisine_specs.ITINERARY_SPECS + real
                                    TravelAgent conversational sessions
  Agent 4's evaluation happens inline as each build completes: real
  check_feasibility + check_grounding (reused, not reimplemented, from
  phase4/phase5) plus two NEW checks specific to this round -- cuisine
  accuracy (do the actual restaurant stops match the requested cuisine?)
  and category coverage (does every requested non-food interest actually
  get a real stop?).

Drives the REAL conversational agent end-to-end (phase3/agent.py's
TravelAgent, text mode, real Gemini calls for interest extraction) exactly
as a real user would type -- not a direct poi_search_logic() call -- so this
tests the full real pipeline including whether cuisine specificity survives
LLM-based interest extraction at all.

Usage: python run_qa_cuisine.py [start_id] [end_id]   (1-based, inclusive; default 1 30)
Writes phase7_qa/results/cuisine_itinerary_<id>.json per itinerary as it
finishes, plus results/_progress_cuisine.log.
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
for sub in ("phase1", "phase2", "phase3", "phase4", "phase5"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from cuisine_specs import ITINERARY_SPECS  # noqa: E402
from agent import TravelAgent, State  # noqa: E402
from feasibility import check_feasibility  # noqa: E402
from grounding import check_grounding  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
PROGRESS_LOG = os.path.join(RESULTS_DIR, "_progress_cuisine.log")

CALL_SPACING_SEC = 1.5
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 20


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            last_exc = e
            log(f"    retry {attempt}/{MAX_RETRIES} after {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)
    raise last_exc


_CUISINE_TAG_HINTS = {
    "North Indian": ("north_indian", "punjabi", "indian"),
    "South Indian": ("south_indian",),
    "Thai": ("thai",),
    "Continental": ("continental", "international"),
    "Chinese": ("chinese",),
    "Italian": ("italian", "pizza"),
    "Mexican": ("mexican", "tex-mex"),
    "Japanese": ("japanese",),
    "Korean": ("korean",),
    "Bengali": ("bengali",),
    "Punjabi": ("punjabi", "north_indian"),
    "Mughlai": ("mughlai", "indian"),
}


def _restaurant_stops(itin: dict) -> list[dict]:
    stops = []
    for k in itin:
        if not k.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[k].get(slot, []):
                if s.get("category") == "restaurant":
                    stops.append(s)
    return stops


def _stop_names(itin: dict) -> list[str]:
    names = []
    for k in itin:
        if not k.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[k].get(slot, []):
                names.append(s["name"])
    return names


def check_cuisine_accuracy(itin: dict, requested_cuisine: str) -> dict:
    """Real check: for every scheduled restaurant, does its real tags.cuisine
    value match (or plausibly relate to) the requested cuisine? No fabricated
    ground truth -- this reads the same real OSM tags already in pois.json."""
    restaurants = _restaurant_stops(itin)
    hints = _CUISINE_TAG_HINTS.get(requested_cuisine, ())
    matched, unmatched, no_cuisine_tag = [], [], []
    for r in restaurants:
        tag = (r.get("tags") or {}).get("cuisine") or r.get("cuisine")
        if not tag:
            no_cuisine_tag.append(r["name"])
            continue
        tag_lower = str(tag).lower()
        if any(h in tag_lower for h in hints):
            matched.append(r["name"])
        else:
            unmatched.append((r["name"], tag))
    return {
        "total_restaurants": len(restaurants),
        "matched_cuisine": matched,
        "unmatched_cuisine": unmatched,
        "no_cuisine_tag": no_cuisine_tag,
    }


def check_category_coverage(itin: dict, requested_categories: list[str]) -> dict:
    """Real check: for each requested non-food category interest, does the
    itinerary contain at least one real stop from a category that interest
    maps to (reusing poi_search.INTEREST_MAP, not a separate guess)?"""
    from poi_search import INTEREST_MAP, _resolve_interest_key

    present_categories = set()
    for k in itin:
        if not k.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[k].get(slot, []):
                present_categories.add(s.get("category"))

    covered, missing = [], []
    for interest in requested_categories:
        mapped = INTEREST_MAP.get(_resolve_interest_key(interest), [])
        if any(c in present_categories for c in mapped):
            covered.append(interest)
        else:
            missing.append(interest)
    return {"covered": covered, "missing": missing}


def run_one(spec: dict) -> dict:
    log(f"=== Itinerary {spec['id']:02d}: {spec['cuisine']} + {spec['category_interests']} "
        f"({spec['days']}-day, {spec['pace']}) ===")
    log(f"  opening: \"{spec['opening_message']}\"")

    agent = TravelAgent(tts=None, log_level="quiet")
    time.sleep(CALL_SPACING_SEC)
    reply1, state1 = with_retry(agent.process_turn, spec["opening_message"])
    log(f"  -> state={state1.value} reply=\"{reply1[:150]}\"")

    reply2, state2 = None, state1
    if state1 not in (State.PRESENT, State.DONE):
        time.sleep(CALL_SPACING_SEC)
        reply2, state2 = with_retry(agent.process_turn, "Yes, go ahead.")
        log(f"  -> state={state2.value} reply=\"{(reply2 or '')[:150]}\"")

    result = {
        "spec": spec,
        "final_state": state2.value if state2 else state1.value,
        "extracted_interests": list(agent.ctx.interests),
        "extracted_constraints": dict(agent.ctx.constraints or {}),
        "num_days_extracted": agent.ctx.num_days,
        "pace_extracted": agent.ctx.pace,
        "itinerary": agent.itinerary,
    }

    if agent.itinerary:
        result["feasibility"] = check_feasibility(agent.itinerary, agent.ctx.pace or spec["pace"])
        result["grounding"] = check_grounding(agent.itinerary)
        result["cuisine_accuracy"] = check_cuisine_accuracy(agent.itinerary, spec["cuisine"])
        result["category_coverage"] = check_category_coverage(agent.itinerary, spec["category_interests"])
        stops = _stop_names(agent.itinerary)
        log(f"  built: {len(stops)} stops, feasibility_pass={result['feasibility']['pass']}, "
            f"grounding_pass={result['grounding']['pass']}, "
            f"cuisine_matched={len(result['cuisine_accuracy']['matched_cuisine'])}/{result['cuisine_accuracy']['total_restaurants']}, "
            f"category_missing={result['category_coverage']['missing']}")
    else:
        result["feasibility"] = None
        result["grounding"] = None
        result["cuisine_accuracy"] = None
        result["category_coverage"] = None
        log(f"  NO ITINERARY BUILT -- final_state={result['final_state']}")

    out_path = os.path.join(RESULTS_DIR, f"cuisine_itinerary_{spec['id']:02d}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    log(f"  Saved -> {out_path}")
    return result


def main():
    start_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end_id = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    log(f"Team Waypoint -- 30 Random Itineraries QA (cuisine round) starting ({start_id}-{end_id})")
    for spec in ITINERARY_SPECS:
        if not (start_id <= spec["id"] <= end_id):
            continue
        out_path = os.path.join(RESULTS_DIR, f"cuisine_itinerary_{spec['id']:02d}.json")
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
