"""
Verifies H1/H2/H3 fixes by faithfully REPLAYING each original cumulative
session (steps 1..N, in order, using the exact edit_intent the real Gemini
classifier returned at the time -- recorded in results/itinerary_NN.json)
against the FIXED edit engine. This matters because each probe step's
starting state depends on every edit before it in the same session; a
fresh single-step reproduction (tried first, then discarded) understates
the real repro since it skips that cumulative mutation. No new LLM calls
are made -- the classifier outputs are replayed verbatim from the log.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import copy
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase2", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from itinerary_specs import ITINERARY_SPECS, CITY  # noqa: E402
from poi_search import poi_search_logic  # noqa: E402
from itinerary_builder import itinerary_builder_logic  # noqa: E402
from edit_engine import apply_edit  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
specs_by_id = {s["id"]: s for s in ITINERARY_SPECS}


def build(spec):
    pois = poi_search_logic(CITY, spec["interests"], constraints={"pace": spec["pace"]}, top_n=30)
    return itinerary_builder_logic(pois, days=spec["days"], pace=spec["pace"])


def dup_check(itin):
    counts = {}
    for key in itin:
        if not key.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[key].get(slot, []):
                counts.setdefault(s["name"], set()).add(key)
    return {n: sorted(ks) for n, ks in counts.items() if len(ks) > 1}


def replay_up_to(itin_id, target_probe, verbose=False):
    """Rebuilds the itinerary, then replays every recorded step's exact
    edit_intent (steps that were actually classified as EDIT) in order,
    through the FIXED apply_edit, up to and including target_probe.
    Returns (state, result_of_target_step)."""
    spec = specs_by_id[itin_id]
    state = build(spec)
    with open(os.path.join(RESULTS_DIR, f"itinerary_{itin_id:02d}.json"), encoding="utf-8") as f:
        data = json.load(f)
    target_result = None
    for step in data["steps"]:
        cls = step["classification"]
        if cls.get("intent") != "EDIT" or not cls.get("edit_intent"):
            continue
        result = apply_edit(state, cls["edit_intent"], pace=spec["pace"], city=CITY)
        if result["ok"]:
            state = result["itinerary"]
        if verbose:
            print(f"    replayed step {step['n']:2d} ({step['probe']:28s}) ok={result['ok']} msg={result['message'][:60]!r}")
        if step["probe"] == target_probe:
            target_result = result
            break
    return state, target_result


print("=" * 70)
print("H1 check -- whole-trip duplicate protection on swap_outdoor")
print("(replaying full cumulative session up to step 5 for each)")
print("=" * 70)
h1_itins = [2, 6, 8, 11, 15, 17]
h1_ok = True
for i in h1_itins:
    state, result = replay_up_to(i, "swap_outdoor")
    dups = dup_check(state)
    status = "FAIL (still duplicated)" if dups else "PASS (no duplicate)"
    if dups:
        h1_ok = False
    print(f"  itin{i:02d} ok={result['ok']} msg={result['message'][:65]!r} dups={dups or 'none'} -> {status}")

print()
print("=" * 70)
print("H2 check -- themed add/swap constraints now resolve")
print("(replaying full cumulative session up to each probe)")
print("=" * 70)
h2_probes = ["swap_theme_category", "add_theme_any_day", "add_food_famous"]
h2_total = 0
h2_fail = 0
for probe in h2_probes:
    still_noop = 0
    for i in range(1, 21):
        _, result = replay_up_to(i, probe)
        h2_total += 1
        if "Couldn't find" in result["message"]:
            still_noop += 1
            h2_fail += 1
    print(f"  probe={probe:22s} still no-op: {still_noop}/20")

print()
print("=" * 70)
print("H3 check -- known-absent-place honesty on 'Select Citywalk mall' add")
print("=" * 70)
h3_fixed = 0
for i in range(1, 21):
    _, result = replay_up_to(i, "add_known_absent_place")
    if "don't have a real, mappable record" in result["message"]:
        h3_fixed += 1
print(f"  honest decline now shown: {h3_fixed}/20")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"H1: {'ALL CLEAR -- no duplicates in any of the 6 previously-broken itineraries' if h1_ok else 'STILL BROKEN in at least one itinerary, see above'}")
print(f"H2: {h2_total - h2_fail}/{h2_total} themed add/swap commands now succeed (previously 0/{h2_total})")
print(f"H3: {h3_fixed}/20 known-absent-place adds now correctly declined (previously 0/20)")
