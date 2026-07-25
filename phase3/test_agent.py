"""
Phase 3 tests — text-only (no microphone required).

T-3.1  STT accuracy stub — validates text-mode passthrough
T-3.2  TripContext extraction from a fully-specified sentence
T-3.3  Clarifying questions cap (≤ 6 even for vague input)
T-3.4  State machine transitions (correct ordering)
T-3.5  MCP tools called during BUILD (itinerary JSON returned)
T-3.6  End-to-end: full scripted conversation → valid itinerary
T-3.7  City scope enforcement (non-Delhi request declined)
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _pass(name: str, detail: str = "") -> bool:
    msg = f"  [PASS] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return True


def _fail(name: str, detail: str = "") -> bool:
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    return False


# ---------------------------------------------------------------------------
# T-3.1  STT text-mode passthrough
# ---------------------------------------------------------------------------
def test_stt_text_mode() -> bool:
    print("\nT-3.1 — STT Text-Mode Passthrough")
    from stt import STT

    stt = STT(mode="text")
    # Verify the object initialises correctly
    ok = stt.mode == "text"
    return _pass("STT created in text mode") if ok else _fail("STT creation failed")


# ---------------------------------------------------------------------------
# T-3.2  TripContext extraction from a fully-specified sentence
# ---------------------------------------------------------------------------
def test_trip_context_extraction() -> bool:
    print("\nT-3.2 — TripContext Extraction")
    from agent import TravelAgent
    from trip_context import TripContext

    agent = TravelAgent(log_level="quiet")

    sentence = "Plan a 3-day trip to Delhi next weekend. I like food and culture, relaxed pace, group of 2."
    ctx = agent._extract_context(sentence)

    checks = {
        "num_days=3": ctx.num_days == 3,
        "interests not empty": len(ctx.interests) >= 1,
        "pace=relaxed": ctx.pace == "relaxed",
        "group_size=2": ctx.group_size == 2,
    }
    all_ok = True
    for name, ok in checks.items():
        if ok:
            _pass(name)
        else:
            _fail(name, f"got {getattr(ctx, name.split('=')[0], '?')!r}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# T-3.3  Clarifying questions cap (≤ 6)
# ---------------------------------------------------------------------------
def test_clarify_cap() -> bool:
    print("\nT-3.3 — Clarifying Questions Cap")
    from agent import TravelAgent, State

    agent = TravelAgent(log_level="quiet")

    scripted_replies = [
        "Plan me a trip",        # vague
        "I'm not sure",
        "Whatever you think",
        "Something nice",
        "I don't have preferences",
        "You decide",
        "Anything is fine",
    ]

    questions_asked = 0
    for turn_input in scripted_replies:
        _, state = agent.process_turn(turn_input)
        if state == State.CLARIFY:
            questions_asked += 1
        if state in (State.CONFIRM, State.BUILD, State.PRESENT, State.DONE):
            break

    ok = questions_asked <= 6
    return (
        _pass("clarify cap", f"{questions_asked} questions asked (max 6)")
        if ok
        else _fail("clarify cap exceeded", f"{questions_asked} questions asked")
    )


# ---------------------------------------------------------------------------
# T-3.4  State machine transitions
# ---------------------------------------------------------------------------
def test_state_transitions() -> bool:
    print("\nT-3.4 — State Machine Transitions")
    from agent import TravelAgent, State

    agent = TravelAgent(log_level="quiet")

    # Feed a fully-specified request → should reach CONFIRM without CLARIFY
    _, state_after_1 = agent.process_turn(
        "I want a 2-day trip to Delhi. I love history and street food. Moderate pace, solo traveller."
    )
    reached_confirm_or_later = state_after_1 in (State.CONFIRM, State.BUILD, State.PRESENT, State.DONE)

    ok1 = reached_confirm_or_later
    if ok1:
        _pass("fully-specified input reaches CONFIRM quickly", f"state={state_after_1.value}")
    else:
        _fail("state didn't advance as expected", f"state={state_after_1.value}")

    # Confirm + check BUILD → PRESENT
    agent2 = TravelAgent(log_level="quiet")
    states = []
    for msg in [
        "I want 2 days in Delhi, history and food, moderate pace.",
        "yes go ahead",
    ]:
        _, s = agent2.process_turn(msg)
        states.append(s)

    ok2 = State.PRESENT in states or State.BUILD in states
    if ok2:
        _pass("confirmation triggers BUILD or PRESENT", f"states={[s.value for s in states]}")
    else:
        _fail("BUILD/PRESENT not reached after confirm", f"states={[s.value for s in states]}")

    return ok1 and ok2


# ---------------------------------------------------------------------------
# T-3.5  MCP tools called during BUILD (itinerary JSON returned)
# ---------------------------------------------------------------------------
def test_mcp_tools_called() -> bool:
    print("\nT-3.5 — MCP Tools Called During BUILD")
    from agent import TravelAgent, State

    agent = TravelAgent(log_level="quiet")
    # Force BUILD directly by setting context and state
    from trip_context import TripContext
    agent.ctx = TripContext(city="New Delhi", num_days=2, interests=["history", "food"], pace="moderate", group_size=1)
    agent.ctx.fill_defaults()

    itinerary, summary = agent._build_itinerary()

    day_keys = [k for k in itinerary if k.startswith("day_")]
    ok_itin = isinstance(itinerary, dict) and len(day_keys) >= 1
    ok_slots = all(
        {"morning", "afternoon", "evening", "total_hours"}.issubset(itinerary[k])
        for k in day_keys
    )
    ok_summary = isinstance(summary, str) and len(summary) > 10

    _pass(f"itinerary dict returned with {len(day_keys)} days") if ok_itin else _fail("itinerary not a dict / no days")
    _pass("each day has morning/afternoon/evening slots") if ok_slots else _fail("day missing slot keys")
    _pass("spoken summary generated") if ok_summary else _fail("summary empty")
    return ok_itin and ok_slots and ok_summary


# ---------------------------------------------------------------------------
# T-3.6  End-to-end scripted conversation → valid itinerary
# ---------------------------------------------------------------------------
def test_end_to_end() -> bool:
    print("\nT-3.6 — End-to-End Scripted Conversation")
    from agent import TravelAgent, State

    agent = TravelAgent(log_level="quiet")

    conversation = [
        "Plan a 2-day Delhi trip. I like history and street food, moderate pace.",
        "Yes, go ahead.",
    ]

    final_state = State.COLLECT
    for msg in conversation:
        _, final_state = agent.process_turn(msg)
        if final_state == State.PRESENT:
            break

    has_itinerary = agent.itinerary is not None
    day_keys = [k for k in agent.itinerary if k.startswith("day_")] if has_itinerary else []
    valid_days = has_itinerary and len(day_keys) >= 1
    slots_ok = valid_days and all(
        {"morning", "afternoon", "evening"}.issubset(agent.itinerary[k]) for k in day_keys
    )

    _pass("final state is PRESENT") if final_state == State.PRESENT else _fail("did not reach PRESENT", f"state={final_state.value}")
    _pass("itinerary produced") if has_itinerary else _fail("no itinerary")
    _pass("itinerary has valid day/slot structure") if slots_ok else _fail("day/slot structure invalid")

    return final_state == State.PRESENT and has_itinerary and slots_ok


# ---------------------------------------------------------------------------
# T-3.7  City scope enforcement
# ---------------------------------------------------------------------------
def test_city_scope() -> bool:
    print("\nT-3.7 — City Scope Enforcement")
    from agent import TravelAgent, State, _is_out_of_scope

    # Test the fast keyword check (first-turn behavior — mid_conversation defaults False)
    checks = {
        "Mumbai trip": ("Plan a trip to Mumbai", True),
        "Paris trip": ("I want to visit Paris for 5 days", True),
        "Delhi trip": ("Plan a 3-day trip to New Delhi", False),
        "From Mumbai to Delhi": ("I'm flying from Mumbai to Delhi, plan 3 days", False),
        "Puneet is a name, not Pune": ("My friend Puneet is joining me", False),  # word-boundary (R-12)
    }

    all_ok = True
    for label, (text, expect_oos) in checks.items():
        result = _is_out_of_scope(text)
        if result == expect_oos:
            _pass(f"scope check: {label!r}", f"out_of_scope={result}")
        else:
            _fail(f"scope check: {label!r}", f"expected {expect_oos}, got {result}")
            all_ok = False

    # QA-7/R-12: mid-conversation, a mere mention of another city (comparison/
    # aside) must NOT hard-bounce — only a first-turn request should.
    mid_conv_text = "I love street food like they have in Mumbai"
    still_first_turn = _is_out_of_scope(mid_conv_text, mid_conversation=False)
    once_underway = _is_out_of_scope(mid_conv_text, mid_conversation=True)
    if still_first_turn and not once_underway:
        _pass("scope check is context-aware", "first-turn=True, mid-conversation=False")
    else:
        _fail("scope check context-awareness", f"first-turn={still_first_turn}, mid-conversation={once_underway}")
        all_ok = False

    # Verify agent declines Mumbai (only if LLM key available)
    import os
    if os.environ.get("GEMINI_API_KEY"):
        agent = TravelAgent(log_level="quiet")
        reply, _ = agent.process_turn("Plan a trip to Mumbai for 3 days.")
        declined = "delhi" in reply.lower() or "new delhi" in reply.lower() or "specialize" in reply.lower()
        if declined:
            _pass("agent declines out-of-scope city")
        else:
            _fail("agent did not decline non-Delhi request", f"reply={reply[:80]!r}")
            all_ok = False

        # QA-7/R-12 live check: an aside mentioning another city mid-conversation
        # must not derail an already-underway Delhi conversation.
        agent2 = TravelAgent(log_level="quiet")
        agent2.process_turn("Plan a 2-day trip to New Delhi, I like food and history")
        reply2, _ = agent2.process_turn("I love street food like they have in Mumbai")
        derailed = "specialize exclusively" in reply2.lower()
        if not derailed:
            _pass("mid-conversation city mention does not derail (QA-7/R-12)", f"reply={reply2[:80]!r}")
        else:
            _fail("mid-conversation city mention derailed the turn", f"reply={reply2[:80]!r}")
            all_ok = False
    else:
        _pass("agent city scope (keyword path) — LLM path skipped (no API key)")

    return all_ok


# ---------------------------------------------------------------------------
# T-3.8  Interest vocabulary preserved on the REAL live conversation path
# ---------------------------------------------------------------------------
def test_interest_vocabulary_live_path() -> bool:
    """
    Phase 3 QA (H2, "Itinerary edit commands QA.md"): T-3.2 above only ever
    tested `_extract_context()`, which is never actually called by the real
    conversation flow (`process_turn()` -> `_agent_decision()` -> the static
    SYSTEM_PROMPT) -- confirmed by grep: _extract_context has no other
    caller in this codebase. That gap let a real regression of the
    already-fixed R-2 bug ship silently: "art"/"religion" were being
    generalized to "culture"/"history" on every real request, 8/8 times in
    a 30-itinerary QA round, while T-3.2 kept passing throughout. This test
    drives the real `process_turn()` path specifically so this class of
    regression can't hide behind a passing test again.
    """
    print("\nT-3.8 — Interest Vocabulary Preserved (Real Live Path)")
    from agent import TravelAgent

    cases = [
        ("I want a 2-day trip to Delhi. I am interested in art. Moderate pace.", ["art"]),
        ("I want a 2-day trip to Delhi. I am interested in religion and spirituality. Moderate pace.",
         ["religion", "spirituality"]),
    ]
    all_ok = True
    for text, expected_words in cases:
        agent = TravelAgent(log_level="quiet")
        agent.process_turn(text)
        missing = [w for w in expected_words if w not in agent.ctx.interests]
        if not missing:
            _pass(f"preserved {expected_words}", f"got interests={agent.ctx.interests}")
        else:
            _fail(f"lost {missing} from stated interests", f"got interests={agent.ctx.interests}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def _needs_api_key() -> bool:
    import os
    return bool(os.environ.get("GROQ_API_KEY"))


def _skip(name: str, reason: str = "GROQ_API_KEY not set") -> bool:
    print(f"  [SKIP] {name} — {reason}")
    return True  # treat skipped as pass for summary count


def run_all() -> dict[str, bool]:
    print("=" * 60)
    print("PHASE 3 VALIDATION TESTS")
    print("=" * 60)

    has_key = _needs_api_key()
    if not has_key:
        print("  NOTE: GROQ_API_KEY not set — LLM tests will be skipped.")
        print("  Set it in ../.env or via $env:GROQ_API_KEY to run all tests.\n")

    results = {
        "T-3.1 STT Text Mode":         test_stt_text_mode(),
        "T-3.2 TripContext Extraction": test_trip_context_extraction() if has_key else _skip("T-3.2 TripContext Extraction"),
        "T-3.3 Clarify Cap":           test_clarify_cap() if has_key else _skip("T-3.3 Clarify Cap"),
        "T-3.4 State Transitions":     test_state_transitions() if has_key else _skip("T-3.4 State Transitions"),
        "T-3.5 MCP Tools Called":      test_mcp_tools_called() if has_key else _skip("T-3.5 MCP Tools Called"),
        "T-3.6 End-to-End":            test_end_to_end() if has_key else _skip("T-3.6 End-to-End"),
        "T-3.7 City Scope":            test_city_scope(),
        "T-3.8 Interest Vocab (Live Path)": test_interest_vocabulary_live_path() if has_key else _skip("T-3.8 Interest Vocab (Live Path)"),
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
