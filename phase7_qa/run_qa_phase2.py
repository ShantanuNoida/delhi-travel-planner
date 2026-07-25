"""
Team Waypoint -- Itinerary edit commands QA (Phase 2)

Agent 1 (Coordinator) drives this whole script in order:
  Agent 2 (Itinerary Generator)  -> NO NEW WORK, loads Phase 1's initial
                                     itineraries from phase7_qa/results/itinerary_NN.json
  Agent 3 (Question Command Agent) -> generate_question_commands() + apply
                                       each via the real app (classify_intent + explain)
  [Agent 4 and Agent 5's work happens afterwards, offline, over these logs]

Calls the REAL application code (phase4/intent_classifier.classify_intent +
phase4/explain_engine.explain, which itself does real RAG lookups against
Phase 1's ChromaDB via phase1/embedder.py, plus real Gemini synthesis calls)
-- no simulated/mocked behavior. Each of the 20 itineraries gets a real
15-question session against the SAME itinerary state Agent 2 built in Phase 1
(no edits applied -- Phase 2 explicitly reuses the as-generated itineraries).

Usage: python run_qa_phase2.py [start_id] [end_id]   (1-based, inclusive; default 1 20)
Writes phase7_qa/results/phase2_itinerary_<id>.json per itinerary as it
finishes (so a partial run is never lost), plus results/_progress_phase2.log.
"""

import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase1", "phase2", "phase4", "phase5"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from itinerary_specs import ITINERARY_SPECS  # noqa: E402
from question_commands import generate_question_commands  # noqa: E402

from intent_classifier import classify_intent  # noqa: E402
from explain_engine import explain  # noqa: E402
from grounding import check_grounding  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
PROGRESS_LOG = os.path.join(RESULTS_DIR, "_progress_phase2.log")

CALL_SPACING_SEC = 1.5  # gentle pacing between real Gemini calls
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 20


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs), None
        except Exception as e:  # noqa: BLE001 -- QA harness: retry any transient
            # classifier/RAG/LLM failure (rate limit exhausted across rotated
            # keys, transient network error) a few times with backoff rather
            # than aborting the whole run.
            last_exc = e
            log(f"    {fn.__name__} error (attempt {attempt}/{MAX_RETRIES}): {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC)
    return None, last_exc


def load_phase1_itinerary(spec_id: int) -> dict:
    path = os.path.join(RESULTS_DIR, f"itinerary_{spec_id:02d}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["initial_itinerary_full"]


def run_one(spec: dict) -> dict:
    log(f"=== Itinerary {spec['id']:02d}: {spec['label']} ({spec['days']}-day, {spec['pace']}) ===")
    itinerary = load_phase1_itinerary(spec["id"])

    questions = generate_question_commands(itinerary, spec)

    steps = []
    for q in questions:
        log(f"  [{q['n']:02d}/15] ({q['category']}/{q['probe']}) \"{q['command']}\"")
        time.sleep(CALL_SPACING_SEC)
        classification, cls_err = _with_retry(classify_intent, q["command"])
        if classification is None:
            classification = {"intent": "ERROR", "edit_intent": None, "query": q["command"], "_error": str(cls_err)}

        step = {
            "n": q["n"],
            "command": q["command"],
            "category": q["category"],
            "probe": q["probe"],
            "target_stop": q["target_stop"],
            "expected": q["expected"],
            "classification": classification,
        }

        if classification.get("intent") == "EXPLAIN":
            time.sleep(CALL_SPACING_SEC)
            query = classification.get("query") or q["command"]
            answer, exp_err = _with_retry(explain, query, itinerary, spec["pace"])
            if answer is None:
                answer = {"answer": f"[HARNESS ERROR: {exp_err}]", "citations": [], "grounded": False}
            step["answer"] = answer
            grounding = check_grounding(itinerary, [answer])
            step["grounding"] = grounding
        else:
            step["answer"] = None
            step["grounding"] = None
            step["_note"] = f"Not routed to explain() -- classified as {classification.get('intent')}, not EXPLAIN."

        steps.append(step)
        ans_preview = (step["answer"]["answer"][:100] if step["answer"] else "(not explained)")
        log(f"       -> intent={classification.get('intent')} grounded={step['answer']['grounded'] if step['answer'] else None} "
            f":: {ans_preview}")

    result = {
        "spec": spec,
        "itinerary_full": itinerary,
        "steps": steps,
    }
    out_path = os.path.join(RESULTS_DIR, f"phase2_itinerary_{spec['id']:02d}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    log(f"  Saved -> {out_path}")
    return result


def main():
    start_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end_id = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    log(f"Team Waypoint -- Itinerary Q&A QA (Phase 2) run starting (itineraries {start_id}-{end_id})")
    for spec in ITINERARY_SPECS:
        if not (start_id <= spec["id"] <= end_id):
            continue
        out_path = os.path.join(RESULTS_DIR, f"phase2_itinerary_{spec['id']:02d}.json")
        if os.path.exists(out_path):
            log(f"Skipping itinerary {spec['id']:02d} (already has a Phase 2 result file)")
            continue
        try:
            run_one(spec)
        except Exception:
            log(f"FAILED itinerary {spec['id']:02d}:\n{traceback.format_exc()}")
    log("Run complete.")


if __name__ == "__main__":
    main()
