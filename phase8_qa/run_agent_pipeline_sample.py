"""
Team Waypoint -- post-round harness broadening (2026-07-25)

Both run_edits.py and run_questions.py call phase4/edit_engine.apply_edit()
and phase4/explain_engine.explain() DIRECTLY -- a deliberate speed/cost
tradeoff (see their own docstrings), but one with a real, demonstrated
blind spot: it skips phase3/agent.py's `_handle_post_build_turn()`
entirely, so nothing in either harness can ever exercise behavior that only
exists at the AGENT layer -- guard-driven EDIT->EXPLAIN reclassification
immediately followed by a real explain() call in the same turn (the exact
sequence that crashed with a raw AttributeError, live, in production, and
that neither harness had any way to catch), the pending-edit yes/no
confirmation flow (M2), or the recently_changed_names transparency note
(L1).

This script closes that gap -- not by replacing the fast direct-call
harnesses (still the right choice for exhaustive day/slot/constraint
coverage), but by running a SMALL, curated sample of commands through the
REAL `TravelAgent.process_turn()` pipeline, on a handful of itineraries,
specifically targeting the cross-cutting agent-layer behaviors the direct
calls structurally cannot reach. Every real crash this round found while
"acting as a genuine traveller" would have been caught by a script shaped
like this one.

Usage: python run_agent_pipeline_sample.py [n_itineraries]  (default 5)
Writes results/agent_pipeline_sample.json and results/_progress_agent_pipeline.log.
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
for sub in ("phase1", "phase2", "phase3", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_ROOT, ".env"))

from agent import TravelAgent, State  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
PROGRESS_LOG = os.path.join(RESULTS_DIR, "_progress_agent_pipeline.log")

CALL_SPACING_SEC = 1.5
GENERIC_FAILURE_TEXT = "Something went wrong on my end"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _stop_names(itinerary: dict, n: int = 3) -> list[str]:
    names = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        for slot in ("morning", "afternoon", "evening"):
            for stop in itinerary[key].get(slot, []):
                if stop.get("name") and stop["name"] not in names:
                    names.append(stop["name"])
    return names[:n]


def _build_commands(itinerary: dict) -> list[dict]:
    """Curated commands specifically targeting agent-layer-only behavior --
    not exhaustive day/slot/constraint coverage (that's what run_edits.py /
    run_questions.py already do well)."""
    names = _stop_names(itinerary, 4)
    a = names[0] if names else "the first stop"
    b = names[1] if len(names) > 1 else a

    return [
        {
            "probe": "guard_reclassify_then_explain",
            "command": f"What are some alternatives to {a} on Day 1?",
            "why": "The H3 guard can reclassify this from EDIT to EXPLAIN mid-turn; agent.py then calls "
                   "explain() on the result in the SAME turn -- the exact sequence that crashed live "
                   "(classify_intent's query=None bug). Neither direct-call harness can ever reach this.",
        },
        {
            "probe": "pending_edit_confirm_flow_preview",
            "command": "Make the whole trip more fun.",
            "why": "M2's pending_edit preview/confirm flow only exists in agent.py -- direct apply_edit() "
                   "calls commit immediately and never exercise the yes/no gate at all.",
        },
        {
            "probe": "pending_edit_confirm_flow_resolve",
            "command": "Yes",
            "why": "Resolves the pending_edit from the previous turn -- only meaningful as a follow-up "
                   "within a real multi-turn agent session, which direct calls have no concept of.",
        },
        {
            "probe": "named_stop_swap_e2e",
            "command": f"Swap {a} for {b}." if a != b else f"Swap {a} for something else.",
            "why": "End-to-end check of the target_stop_name fix through the REAL pipeline (classify_intent "
                   "-> apply_edit -> correctness/feasibility checks -> reply), not just the isolated function.",
        },
        {
            "probe": "remove_then_reference_transparency",
            "command": f"Remove {b} from the itinerary.",
            "why": "Sets up the next probe -- L1's recently_changed_names tracking only exists in agent.py's "
                   "session state, never in a stateless direct apply_edit() call.",
        },
        {
            "probe": "remove_already_changed_transparency",
            "command": f"Remove {b} from the itinerary.",
            "why": "Real repro shape for L1: asking to remove something already changed this session should "
                   "surface a transparent 'you may have already changed this' note, not a bare 'not found.'",
        },
        {
            "probe": "booking_vs_cost_e2e",
            "command": f"Do I need to book tickets in advance for {a}?",
            "why": "End-to-end check of the booking/cost keyword-collision fix through the real pipeline.",
        },
        {
            "probe": "safety_question_e2e",
            "command": "Would this itinerary feel safe and manageable for a solo female traveller?",
            "why": "End-to-end check of the SAFETY_KEYWORDS-before-FEASIBILITY_KEYWORDS routing fix.",
        },
    ]


def run_one(spec_id: int) -> dict:
    base_path = os.path.join(RESULTS_DIR, f"base_itinerary_{spec_id:02d}.json")
    with open(base_path, encoding="utf-8") as f:
        base = json.load(f)
    spec = base["spec"]
    itinerary = copy.deepcopy(base["itinerary"])

    log(f"=== Itinerary {spec_id:02d}: {spec['label']} ({spec['days']}-day, {spec['pace']}) ===")

    agent = TravelAgent(tts=None, log_level="quiet")
    agent.itinerary = itinerary
    agent.ctx.pace = spec["pace"]
    agent.ctx.city = "New Delhi"
    agent.ctx.interests = spec["interests"]
    agent.state = State.PRESENT

    commands = _build_commands(itinerary)
    steps = []
    for cmd in commands:
        log(f"  [{cmd['probe']}] \"{cmd['command']}\"")
        time.sleep(CALL_SPACING_SEC)
        # Calls the real PUBLIC process_turn() -- not _process_turn_inner()
        # directly -- so a genuine, expected openai.RateLimitError (quota
        # exhaustion, an environmental condition agent.py already handles
        # correctly with a friendly "usage limit" reply) doesn't get
        # misreported as a crash. A real unhandled-type bug still surfaces
        # via the GENERIC_FAILURE_TEXT check below, since
        # _handle_turn_failure()'s own catch-all branch returns exactly that
        # text for anything it doesn't recognize -- this harness's crash
        # detection is for bugs process_turn() itself doesn't already know
        # how to handle, not for every possible exception type.
        try:
            reply, _ = agent.process_turn(cmd["command"])
            crashed = False
            tb = None
        except Exception:
            reply = None
            crashed = True
            tb = traceback.format_exc()

        generic_failure = bool(reply) and GENERIC_FAILURE_TEXT in reply
        step = {
            "probe": cmd["probe"], "command": cmd["command"], "why": cmd["why"],
            "reply": reply, "crashed": crashed, "traceback": tb,
            "generic_failure_fallback": generic_failure,
        }
        steps.append(step)
        flag = "CRASH" if crashed else ("GENERIC_FAILURE" if generic_failure else "ok")
        log(f"       -> [{flag}] {(reply or '')[:150]}")
        if crashed:
            log(f"       TRACEBACK:\n{tb}")

    return {"spec": spec, "steps": steps}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    log(f"Team Waypoint -- Agent-pipeline sample run starting ({n} itineraries)")
    results = []
    for spec_id in range(1, n + 1):
        try:
            results.append(run_one(spec_id))
        except Exception:
            log(f"FAILED itinerary {spec_id:02d}:\n{traceback.format_exc()}")

    out_path = os.path.join(RESULTS_DIR, "agent_pipeline_sample.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"Saved -> {out_path}")

    total = sum(len(r["steps"]) for r in results)
    crashes = sum(1 for r in results for s in r["steps"] if s["crashed"])
    generic = sum(1 for r in results for s in r["steps"] if s["generic_failure_fallback"])
    log(f"Run complete. {total} turns, {crashes} crashes, {generic} generic-failure fallbacks.")


if __name__ == "__main__":
    main()
