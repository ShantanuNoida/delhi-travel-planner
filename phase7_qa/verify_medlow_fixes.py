import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import copy
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase2", "phase3", "phase4"):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from poi_search import poi_search_logic, search_poi_by_name  # noqa: E402
from itinerary_builder import itinerary_builder_logic  # noqa: E402
from edit_engine import apply_edit, _named_place_candidates  # noqa: E402

CITY = "New Delhi"


def build_sample():
    pois = poi_search_logic(CITY, ["nature"], constraints={"pace": "relaxed"}, top_n=30)
    return itinerary_builder_logic(pois, days=2, pace="relaxed")


print("=" * 70)
print("M1 check -- name-based lookup for add/swap")
print("=" * 70)
matches = search_poi_by_name(CITY, "Qutub Minar")
print(f"  search_poi_by_name('Qutub Minar') -> {[m['name'] for m in matches]}")
assert matches and "qutub" in matches[0]["name"].lower() or "qutab" in matches[0]["name"].lower(), "expected a Qutub/Qutab Minar match"

# Directly verify the candidate-selection mechanism (M1's actual fix)
# rather than fighting real itineraries' budget guard, which is a separate,
# already-verified-correct mechanism (H1's verification exercised it).
named = _named_place_candidates(CITY, "Akshardham")
print(f"  _named_place_candidates('Akshardham') -> {[c['name'] for c in named]}")
assert named and named[0]["name"].lower() == "akshardham", "expected Akshardham as the top named candidate"
print("  PASS (candidate selection)")

# And a full apply_edit() pass against a minimal, deliberately spacious
# fixture, confirming the named candidate actually gets committed end-to-end.
tiny_itin = {
    "day_1": {"morning": [], "afternoon": [], "evening": [], "total_hours": 0.0},
}
edit_intent = {"target_day": 1, "target_slot": "afternoon", "edit_type": "add", "constraint": "Akshardham"}
result = apply_edit(tiny_itin, edit_intent, pace="intensive", city=CITY)
print(f"  add 'Akshardham' to a spacious empty day -> ok={result['ok']} msg={result['message']!r}")
assert result["ok"] and "Akshardham" in result["message"], "M1 fix did not add the named place end-to-end"
print("  PASS (end-to-end commit)")

print()
print("=" * 70)
print("M2 check -- confirm before trip-wide vague relax")
print("=" * 70)
from agent import TravelAgent, State  # noqa: E402
import intent_classifier  # noqa: E402

agent = TravelAgent(tts=None, log_level="quiet")
agent.itinerary = build_sample()
agent.state = State.PRESENT
agent.ctx.pace = "relaxed"
agent.ctx.city = CITY

before_itin = copy.deepcopy(agent.itinerary)
orig_classify = intent_classifier.classify_intent
intent_classifier.classify_intent = lambda text: {
    "intent": "EDIT", "query": text,
    "edit_intent": {"target_day": "all", "target_slot": "all", "edit_type": "relax", "constraint": ""},
}
reply, state = agent.process_turn("Make the whole trip more fun.")
print(f"  reply: {reply!r}")
assert agent.pending_edit is not None, "expected a pending_edit to be set"
assert agent.itinerary == before_itin, "itinerary must NOT change until confirmed"
assert "?" in reply and "yes/no" in reply.lower()
print("  itinerary unchanged, confirmation requested -- PASS")

reply2, _ = agent.process_turn("yes")
print(f"  after 'yes': {reply2!r}")
assert agent.pending_edit is None
assert agent.itinerary != before_itin, "itinerary should have changed after confirmation"
print("  confirmed edit applied -- PASS")

# negative case: decline
agent2 = TravelAgent(tts=None, log_level="quiet")
agent2.itinerary = build_sample()
agent2.state = State.PRESENT
agent2.ctx.pace = "relaxed"
agent2.ctx.city = CITY
before2 = copy.deepcopy(agent2.itinerary)
agent2.process_turn("Make the whole trip more fun.")
reply3, _ = agent2.process_turn("no")
print(f"  after 'no': {reply3!r}")
assert agent2.pending_edit is None
assert agent2.itinerary == before2, "itinerary must stay unchanged after declining"
print("  declined edit left itinerary unchanged -- PASS")

# regression case: explicit pacing cue on target_day="all" should NOT ask for confirmation
agent3 = TravelAgent(tts=None, log_level="quiet")
agent3.itinerary = build_sample()
agent3.state = State.PRESENT
agent3.ctx.pace = "relaxed"
agent3.ctx.city = CITY
before3 = copy.deepcopy(agent3.itinerary)
intent_classifier.classify_intent = lambda text: {
    "intent": "EDIT", "query": text,
    "edit_intent": {"target_day": "all", "target_slot": "all", "edit_type": "relax", "constraint": ""},
}
reply4, _ = agent3.process_turn("Please relax the whole itinerary, it's too packed.")
print(f"  explicit-cue trip-wide relax reply: {reply4!r}")
assert agent3.pending_edit is None, "an explicit pacing cue should not trigger the confirmation path"
assert agent3.itinerary != before3, "explicit-cue relax should commit immediately, same as before the fix"
print("  explicit pacing cue still auto-commits (no regression) -- PASS")

intent_classifier.classify_intent = orig_classify

print()
print("=" * 70)
print("L1 check -- transparent message for remove-already-changed stop")
print("=" * 70)
agent4 = TravelAgent(tts=None, log_level="quiet")
agent4.itinerary = build_sample()
agent4.state = State.PRESENT
agent4.ctx.pace = "relaxed"
agent4.ctx.city = CITY

first_stop_name = None
for k in ("day_1", "day_2"):
    for slot in ("morning", "afternoon", "evening"):
        if agent4.itinerary[k][slot]:
            first_stop_name = agent4.itinerary[k][slot][0]["name"]
            first_stop_day = int(k.split("_")[1])
            break
    if first_stop_name:
        break
print(f"  will remove: {first_stop_name!r} (day {first_stop_day})")

intent_classifier.classify_intent = lambda text: {
    "intent": "EDIT", "query": text,
    "edit_intent": {"target_day": first_stop_day, "target_slot": "all", "edit_type": "remove", "constraint": first_stop_name},
}
reply5, _ = agent4.process_turn(f"Remove {first_stop_name} from Day {first_stop_day}.")
print(f"  first remove: {reply5!r}")
assert first_stop_name in agent4.recently_changed_names

reply6, _ = agent4.process_turn(f"Remove {first_stop_name} from Day {first_stop_day}.")
print(f"  second remove (already gone): {reply6!r}")
assert "already changed or removed" in reply6
print("  PASS")

intent_classifier.classify_intent = orig_classify

print()
print("=" * 70)
print("L2 check -- clearer message for under-filled slot relax no-op")
print("=" * 70)
itin2 = build_sample()
# find a slot with exactly 1 stop
target = None
for k in ("day_1", "day_2"):
    for slot in ("morning", "afternoon", "evening"):
        if len(itin2[k][slot]) == 1:
            target = (k, slot)
            break
    if target:
        break
assert target, "fixture needs a single-stop slot to test L2"
day_key, slot_name = target
day_num = int(day_key.split("_")[1])
edit_intent = {"target_day": day_num, "target_slot": slot_name, "edit_type": "relax", "constraint": ""}
result = apply_edit(itin2, edit_intent, pace="relaxed", city=CITY)
print(f"  relax Day {day_num}'s {slot_name} (1 stop) -> {result['message']!r}")
assert f"Day {day_num}'s {slot_name}" in result["message"] and "just 1 stop" in result["message"]
print("  PASS")

print()
print("ALL MEDIUM/LOW FIX CHECKS PASSED")
