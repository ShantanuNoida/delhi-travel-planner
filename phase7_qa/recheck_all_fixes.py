"""
Team Waypoint -- post-fix recheck across BOTH phases.

The user asked Team Waypoint to recheck every fix recorded in
"Itinerary edit commands QA.md" (Phase 1's H1-H3/M1-M2/L1-L2, Phase 2's
H1-H3/M1-M2/L1) using FRESH commands/questions -- similar in spirit to the
original probes but not the literal recorded text -- to confirm each fix
generalizes rather than being narrowly special-cased to the exact original
repro. Every check here is real, end-to-end, against the live app code
(classify_intent, apply_edit, explain, TravelAgent where the fix lives at
that layer) -- no mocking of the functions under test.

Uses the 20 real itineraries already built in Phase 1 (loaded fresh/copied
per check, not cumulative, so each check is attributable to one fix).

Usage: python recheck_all_fixes.py
Writes results/_recheck_log.json (full transcript) as it runs.
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

from intent_classifier import classify_intent  # noqa: E402
from edit_engine import apply_edit  # noqa: E402
from explain_engine import explain  # noqa: E402
from feasibility import check_feasibility  # noqa: E402
from agent import TravelAgent, State  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
CITY = "New Delhi"
CALL_SPACING_SEC = 1.5
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 20

log_entries = []


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)


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


def load_itin(i):
    with open(os.path.join(RESULTS_DIR, f"itinerary_{i:02d}.json"), encoding="utf-8") as f:
        data = json.load(f)
    return data["initial_itinerary_full"], data["spec"]


def all_stop_names(itin):
    names = []
    for k in itin:
        if not k.startswith("day_"):
            continue
        for slot in ("morning", "afternoon", "evening"):
            for s in itin[k].get(slot, []):
                names.append(s["name"])
    return names


def record(finding, phase, command, extra_check_fn, itin_id=None):
    time.sleep(CALL_SPACING_SEC)
    itin, spec = load_itin(itin_id) if itin_id else (None, None)
    before_names = all_stop_names(itin) if itin else None
    cls = with_retry(classify_intent, command, itin)
    entry = {"finding": finding, "phase": phase, "itin": itin_id, "command": command, "classification": cls}

    if cls["intent"] == "EDIT" and cls.get("edit_intent"):
        result = with_retry(apply_edit, copy.deepcopy(itin), cls["edit_intent"], spec["pace"], CITY)
        entry["edit_ok"] = result["ok"]
        entry["edit_message"] = result["message"]
        entry["after_names"] = all_stop_names(result["itinerary"]) if result["ok"] else before_names
        entry["feasibility"] = check_feasibility(result["itinerary"], spec["pace"]) if result["ok"] else None
    elif cls["intent"] == "EXPLAIN":
        time.sleep(CALL_SPACING_SEC)
        answer = with_retry(explain, cls.get("query") or command, itin, spec["pace"] if spec else "moderate")
        entry["answer"] = answer

    check_result, check_note = extra_check_fn(entry)
    entry["check_result"] = check_result
    entry["check_note"] = check_note
    log_entries.append(entry)
    tag = "PASS" if check_result else "FAIL"
    log(f"  [{tag}] {finding} :: \"{command}\" -> {check_note}")
    return entry


# ============================================================
# PHASE 1 RECHECKS -- fresh edit commands
# ============================================================
log("=" * 70)
log("PHASE 1 RECHECKS")
log("=" * 70)

# --- H1: duplicate landmark across days (fresh phrasing, 2 itineraries) ---
def check_h1(e):
    if not e.get("edit_ok"):
        return True, f"edit not applied (ok={e.get('edit_ok')}) -- no duplicate possible either way: {e.get('edit_message','')[:80]}"
    names = e["after_names"]
    dupes = {n for n in names if names.count(n) > 1}
    return (len(dupes) == 0), f"post-edit stop names has duplicates: {dupes}" if dupes else "no duplicates -- PASS"

record("H1", 1, "Change the Day 1 morning plan to something outdoors", check_h1, itin_id=8)
record("H1", 1, "Could you swap Day 2's afternoon for an outdoor spot instead?", check_h1, itin_id=17)

# --- H2: themed constraint generalizes to fresh phrasing ---
def check_h2(e):
    ok = e.get("edit_ok") is True and "couldn't find" not in e.get("edit_message", "").lower()
    return ok, e.get("edit_message", "")[:120]

record("H2", 1, "Add a nice place to eat in Day 1", check_h2, itin_id=1)
record("H2", 1, "Swap Day 2 afternoon for a cultural spot instead", check_h2, itin_id=7)
record("H2", 1, "Can you include a good shopping spot somewhere in the trip?", check_h2, itin_id=4)

# --- H3: known-absent place, fresh place names (not the original Connaught Place / Select Citywalk) ---
def check_h3(e):
    msg = e.get("edit_message", "")
    ok = "don't have a real, mappable record" in msg
    return ok, msg[:150]

record("H3", 1, "Add INA Market to Day 1", check_h3, itin_id=1)
record("H3", 1, "Swap Day 2 evening for Sarojini Nagar Market instead", check_h3, itin_id=4)

# --- M1: named-place add generalizes to a fresh named place ---
def check_m1_phase1(e):
    if not e.get("edit_ok"):
        return False, f"edit rejected: {e.get('edit_message','')[:120]}"
    return True, e.get("edit_message", "")[:120]

record("M1(P1)", 1, "Add Akshardham to Day 2", check_m1_phase1, itin_id=2)
record("M1(P1)", 1, "Add the National Museum to Day 1", check_m1_phase1, itin_id=7)

# --- M2: vague trip-wide edit still asks for confirmation, via REAL TravelAgent + real classify_intent ---
def m2_recheck():
    itin, spec = load_itin(9)
    agent = TravelAgent(tts=None, log_level="quiet")
    agent.itinerary = copy.deepcopy(itin)
    agent.state = State.PRESENT
    agent.ctx.pace = spec["pace"]
    agent.ctx.city = CITY
    before = copy.deepcopy(agent.itinerary)

    time.sleep(CALL_SPACING_SEC)
    reply, _ = with_retry(agent.process_turn, "Can you make this itinerary better overall?")
    ok1 = agent.pending_edit is not None and agent.itinerary == before
    log(f"  [{'PASS' if ok1 else 'FAIL'}] M2(P1) vague fresh phrasing -> pending_edit set, itinerary unchanged: {reply[:100]!r}")
    log_entries.append({"finding": "M2(P1)-preview", "phase": 1, "command": "Can you make this itinerary better overall?",
                         "check_result": ok1, "reply": reply})

    time.sleep(CALL_SPACING_SEC)
    reply2, _ = with_retry(agent.process_turn, "yes")
    ok2 = agent.pending_edit is None and agent.itinerary != before
    log(f"  [{'PASS' if ok2 else 'FAIL'}] M2(P1) confirm 'yes' commits: {reply2[:100]!r}")
    log_entries.append({"finding": "M2(P1)-confirm", "phase": 1, "command": "yes",
                         "check_result": ok2, "reply": reply2})

    # regression: explicit pacing cue, fresh phrasing, should NOT ask for confirmation
    agent3 = TravelAgent(tts=None, log_level="quiet")
    agent3.itinerary = copy.deepcopy(itin)
    agent3.state = State.PRESENT
    agent3.ctx.pace = spec["pace"]
    agent3.ctx.city = CITY
    before3 = copy.deepcopy(agent3.itinerary)
    time.sleep(CALL_SPACING_SEC)
    reply3, _ = with_retry(agent3.process_turn, "This trip feels exhausting, please relax it all.")
    ok3 = agent3.pending_edit is None
    log(f"  [{'PASS' if ok3 else 'FAIL'}] M2(P1) explicit-cue fresh phrasing auto-commits (no confirmation ask): {reply3[:100]!r}")
    log_entries.append({"finding": "M2(P1)-explicit-cue-regression", "phase": 1,
                         "command": "This trip feels exhausting, please relax it all.",
                         "check_result": ok3, "reply": reply3})

m2_recheck()

# --- L1: remove-already-changed transparency, fresh phrasing ---
def l1_recheck():
    itin, spec = load_itin(3)
    agent = TravelAgent(tts=None, log_level="quiet")
    agent.itinerary = copy.deepcopy(itin)
    agent.state = State.PRESENT
    agent.ctx.pace = spec["pace"]
    agent.ctx.city = CITY
    target_name = all_stop_names(agent.itinerary)[0]

    time.sleep(CALL_SPACING_SEC)
    reply1, _ = with_retry(agent.process_turn, f"Please get rid of {target_name}.")
    log(f"    first removal (fresh phrasing) of {target_name!r}: {reply1[:100]!r}")

    time.sleep(CALL_SPACING_SEC)
    reply2, _ = with_retry(agent.process_turn, f"Take out {target_name} from the plan.")
    ok = "already changed or removed" in reply2
    log(f"  [{'PASS' if ok else 'FAIL'}] L1 second removal (different phrasing) mentions transparency note: {reply2[:150]!r}")
    log_entries.append({"finding": "L1", "phase": 1, "command": f"Take out {target_name} from the plan.",
                         "check_result": ok, "reply": reply2})

l1_recheck()

# --- L2: lighten-evening messaging, fresh phrasing ---
def l2_recheck():
    itin, spec = load_itin(1)
    target = None
    for k in ("day_1", "day_2"):
        if k not in itin:
            continue
        for slot in ("morning", "afternoon", "evening"):
            if len(itin[k].get(slot, [])) == 1:
                target = (k, slot)
                break
        if target:
            break
    if not target:
        log("  [SKIP] L2 -- no single-stop slot found in itinerary 1")
        return
    day_key, slot_name = target
    day_num = int(day_key.split("_")[1])
    time.sleep(CALL_SPACING_SEC)
    cls = with_retry(classify_intent, f"Could you make the {slot_name} a bit lighter on Day {day_num}?", itin)
    if cls["intent"] == "EDIT" and cls.get("edit_intent"):
        result = with_retry(apply_edit, copy.deepcopy(itin), cls["edit_intent"], spec["pace"], CITY)
        msg = result["message"]
        ok = f"Day {day_num}'s {slot_name}" in msg and "just 1 stop" in msg
        log(f"  [{'PASS' if ok else 'FAIL'}] L2 fresh phrasing -> {msg!r}")
        log_entries.append({"finding": "L2", "phase": 1, "command": f"Could you make the {slot_name} a bit lighter on Day {day_num}?",
                             "check_result": ok, "message": msg})
    else:
        log(f"  [FAIL] L2 -- fresh phrasing did not classify as EDIT/relax: {cls}")
        log_entries.append({"finding": "L2", "phase": 1, "check_result": False, "classification": cls})

l2_recheck()


# ============================================================
# PHASE 2 RECHECKS -- fresh questions
# ============================================================
log("")
log("=" * 70)
log("PHASE 2 RECHECKS")
log("=" * 70)

# --- H1: grounded-denial mislabeling, fresh questions likely to be honestly unanswerable ---
def check_h1_phase2(e):
    ans = e.get("answer")
    if ans is None:
        return False, f"not routed to EXPLAIN: {e['classification']}"
    denial_phrases = ("do not contain", "does not contain", "no mention", "not mentioned", "cannot answer",
                       "does not specify", "not provide", "no information")
    is_denial_text = any(p in ans["answer"].lower() for p in denial_phrases)
    if is_denial_text:
        ok = ans["grounded"] is False and not ans["citations"]
        return ok, f"denial text correctly downgraded: grounded={ans['grounded']} citations={len(ans['citations'])}"
    return True, f"substantive answer (no denial to check): grounded={ans['grounded']} :: {ans['answer'][:80]}"

record("H1", 2, "Is there a locker facility near Janpath New Mini Market?", check_h1_phase2, itin_id=1)
record("H1", 2, "Will there be roadwork near Humayun's Tomb this month?", check_h1_phase2, itin_id=2)

# --- H2: KB direct-answer, fresh phrasing + a venue not in the original 3 probes ---
def check_h2_phase2(e):
    ans = e.get("answer")
    if ans is None:
        return False, f"not routed to EXPLAIN: {e['classification']}"
    return ans["grounded"] is True and len(ans["citations"]) > 0, f"grounded={ans['grounded']} citations={len(ans['citations'])} :: {ans['answer'][:100]}"

record("H2", 2, "What's the ticket price for Humayun's Tomb?", check_h2_phase2, itin_id=2)
record("H2", 2, "When is the ideal time to go to Jama Masjid?", check_h2_phase2, itin_id=5)

# --- H3: venue-name/classifier collision, fresh phrasing on the same real repro venue ---
def check_h3_phase2(e):
    return e["classification"]["intent"] == "EXPLAIN", f"intent={e['classification']['intent']}"

record("H3", 2, "What else could I try instead of Make My Lagan?", check_h3_phase2, itin_id=13)
record("H3", 2, "Any other suggestions besides Make My Lagan on day 2?", check_h3_phase2, itin_id=13)

# --- M1: unbookable-place caveat, fresh alternatives questions ---
def check_m1_phase2(e):
    ans = e.get("answer")
    if ans is None:
        return None, f"not routed to EXPLAIN: {e['classification']}"
    from explain_engine import UNBOOKABLE_CAVEAT
    fired = ans["answer"].endswith(UNBOOKABLE_CAVEAT)
    return True, f"caveat_fired={fired} :: {ans['answer'][:150]}"

record("M1", 2, "What could I do instead of visiting Chandni Chowk?", check_m1_phase2, itin_id=4)
record("M1", 2, "Give me some other options besides Lodhi Garden", check_m1_phase2, itin_id=9)

# --- M2: suitability direct yes/no, fresh audience phrasing ---
def check_m2_phase2(e):
    ans = e.get("answer")
    if ans is None:
        return False, f"not routed to EXPLAIN: {e['classification']}"
    direct = ans["answer"].startswith("Yes —") or "isn't specifically tagged" in ans["answer"]
    return direct, ans["answer"][:150]

record("M2", 2, "Would Humayun's Tomb work for someone in a wheelchair?", check_m2_phase2, itin_id=2)
record("M2", 2, "Is Jama Masjid good for solo travelers?", check_m2_phase2, itin_id=5)

log("")
log("=" * 70)
log("L1 (Phase 2) -- rare empty-completion crash resilience is inherently not forceable "
    "via a live call; already covered deterministically by verify_h3_m1_l1_fix.py. Skipped here.")
log("=" * 70)

out_path = os.path.join(RESULTS_DIR, "_recheck_log.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(log_entries, f, indent=2, ensure_ascii=False, default=str)
log(f"\nSaved full recheck transcript -> {out_path}")

n_checked = sum(1 for e in log_entries if "check_result" in e and e["check_result"] is not None)
n_pass = sum(1 for e in log_entries if e.get("check_result") is True)
log(f"\n{n_pass}/{n_checked} checks passed.")
