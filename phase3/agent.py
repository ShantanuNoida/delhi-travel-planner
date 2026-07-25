"""
Conversational Voice Agent — Phase 3.

State machine: COLLECT -> CLARIFY -> CONFIRM -> BUILD -> PRESENT
Uses Grok LLM via config.py. Calls Phase 2 MCP tools for itinerary building.
Supports both voice (mic + pyttsx3) and text-only modes.
"""

import copy
import json
import os
import re
import sys
import time
from enum import Enum
from typing import Any

# Allow importing from parent (config.py) and sibling (phase2/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from config import get_llm_client, LLM_MODEL
from trip_context import TripContext

PHASE2_DIR = os.path.join(_ROOT, "phase2")
PHASE4_DIR = os.path.join(_ROOT, "phase4")
PHASE5_DIR = os.path.join(_ROOT, "phase5")

# Phase 3 QA (H2, "Itinerary edit commands QA.md"): the real, live interest
# vocabulary, imported here (not hand-typed into SYSTEM_PROMPT below) so the
# prompt can never silently drift out of sync with poi_search.INTEREST_MAP
# again -- see SYSTEM_PROMPT's own "interests" line for the actual bug this
# fixes.
sys.path.insert(0, PHASE2_DIR)
from poi_search import INTEREST_MAP  # noqa: E402
_LIVE_INTEREST_VOCAB = ", ".join(sorted(INTEREST_MAP.keys()))

EXIT_PHRASES = {
    "quit", "exit", "goodbye", "bye", "done",
    "that's all", "that is all", "no more edits", "nothing else", "no thanks",
}
# R-41 (found 2026-07-17 while live-testing the transcript UI): a plain
# substring check (`phrase in text_lower`) matched "stop" inside ordinary
# words like "stops"/"stopping" — e.g. "Reduce travel time between stops."
# prematurely ended the whole session, since "stop" is a literal substring
# of "stops". Same bug shape _is_out_of_scope() already fixed for city names
# ("Puneet" containing "pune") via word-boundary matching.
#
# Word-boundary matching alone isn't enough for "stop" specifically, though:
# it's also an ordinary noun in this app's own domain ("add another stop",
# "remove this stop") — a bare word-boundary match on "stop" still misfires
# on those. "stop" is kept OUT of the regex-matched set entirely and instead
# only ends the session when it's the user's ENTIRE message (see
# _is_exit_phrase below), never when it's part of a longer sentence.
_EXIT_PHRASE_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in EXIT_PHRASES) + r")\b"
)
_EXIT_ONLY_IF_WHOLE_MESSAGE = {"stop"}


def _is_exit_phrase(text_lower: str) -> bool:
    if text_lower.rstrip(".!? ") in _EXIT_ONLY_IF_WHOLE_MESSAGE:
        return True
    return bool(_EXIT_PHRASE_RE.search(text_lower))

# QA-8/R-13: a build fires several LLM calls back-to-back (decision, safety
# explain, transit explain, narrator) against the same rate-limited bucket.
# A small gap between them spreads the same calls over time instead of
# bursting past a per-minute cap — this adds latency, not calls.
BUILD_LLM_CALL_SPACING_SEC = 2.0


class State(str, Enum):
    COLLECT = "collect"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    BUILD = "build"
    PRESENT = "present"
    DONE = "done"


# ------------------------------------------------------------------ #
# System prompt for the LLM
# ------------------------------------------------------------------ #

SYSTEM_PROMPT = """You are a friendly AI travel planning assistant specializing exclusively in New Delhi, India.
Your job is to collect trip planning details through natural conversation and then build a day-wise itinerary.

## Rules
- Only plan trips to New Delhi / Delhi. If the user asks about another city, politely decline and redirect.
- Ask at most 6 clarifying questions total. After that, use sensible defaults.
- Never hallucinate places or facts. All knowledge comes from real data.
- Keep spoken responses concise (≤ 3 sentences) — the full plan is shown on screen.
- Always confirm the trip details with the user before building the itinerary.

## TripContext Fields
- city (always "New Delhi")
- num_days (integer)
- travel_dates (e.g., "next weekend", "July 5-8")
- interests (list): when what the user says matches or is a close synonym of one of these known
  interest categories, use that EXACT word -- never substitute a broader generalization for it.
  For example, a request for "religion and spirituality" must extract as ["religion", "spirituality"],
  NOT ["culture", "history"]; a request for "art" must extract as ["art"], NOT ["culture"].
  Known categories: __INTEREST_VOCAB__.
  If the user's phrasing doesn't clearly match any of these, use their own words as-is.
- pace ("relaxed" = 6h/day, "moderate" = 8h/day, "intensive" = 10h/day)
- group_size (integer)
- constraints (dict with optional keys: budget_inr, accessibility, dietary)

## Output Format
Always respond with a JSON object in one of these formats:

1. Asking a question:
{"type": "question", "text": "<spoken question>", "context_update": {<any fields extracted so far>}}

2. Ready to confirm:
{"type": "confirm", "text": "<confirmation summary spoken to user>", "trip_context": {<all extracted fields>}}

3. User confirmed — ready to build:
{"type": "build", "trip_context": {<confirmed fields>}}

4. User wants to change something:
{"type": "correction", "text": "<acknowledgement>", "context_update": {<corrected fields>}}

5. Out of scope (non-Delhi city):
{"type": "out_of_scope", "text": "<polite decline>"}

Always output valid JSON. Do not include any text outside the JSON."""

# Substituted via .replace() (not .format()) since the prompt above contains
# literal, unescaped JSON braces in its own output-format examples.
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("__INTEREST_VOCAB__", _LIVE_INTEREST_VOCAB)


def _extract_system_prompt(interest_vocab: dict) -> str:
    """
    R-2 (Itinerary-Quality-Review-and-Recommendations.md F-2): without the
    vocabulary list below, extraction silently generalized specific stated
    interests into broader buckets before poi_search.INTEREST_MAP — which
    already has real mappings for them — ever saw the original word. E.g. a
    user asking for "religion and spirituality" got extracted as
    interests=["culture", "history"], even though INTEREST_MAP has
    religion -> temple/mosque/church/gurdwara ready to use; "art" likewise
    collapsed to "culture", losing art -> museum/park. Verified via the
    itinerary quality review across 10 real builds.
    """
    vocab_list = ", ".join(sorted(interest_vocab.keys()))
    return f"""Extract trip planning parameters from the user message.
Return a JSON object with only the fields that are explicitly mentioned or clearly implied.
Fields: city, num_days, travel_dates, interests (list), pace, group_size, constraints (dict).
Return {{}} if nothing extractable. Never guess values not present in the text.

For "interests": when what the user says matches or is a close synonym of one of these known
interest categories, use that EXACT word — never substitute a broader generalization for it.
For example, a request for "religion and spirituality" must extract as
["religion", "spirituality"], NOT ["culture", "history"]; a request for "art" must extract as
["art"], NOT ["culture"]. Known categories: {vocab_list}.
If the user's phrasing doesn't clearly match any of these, use their own words as-is."""


# ------------------------------------------------------------------ #
# Agent class
# ------------------------------------------------------------------ #

class TravelAgent:
    def __init__(self, tts=None, log_level: str = "normal"):
        self.state = State.COLLECT
        self.ctx = TripContext()
        self.history: list[dict] = []
        self.itinerary: dict | None = None
        self.clarify_count = 0
        self.MAX_CLARIFY = 6
        self._llm_client = None  # lazy init — only created on first LLM call
        self.tts = tts
        self.log_level = log_level
        self.last_citations: list[dict] = []
        self.transit_info: dict | None = None
        self.weather_note: str | None = None
        self.safety_tip: dict | None = None
        self.narrative: str | None = None
        self.narrative_stale = False  # True once an edit changes self.itinerary after the narrative was generated (QA-2/R-3)
        self.enrichment_degraded = False  # True if narrative/safety/transit hit a real error (not just "nothing grounded") — QA-8/R-13
        self.pending_edit: dict | None = None  # R-41 (QA M2): a previewed-but-not-yet-committed trip-wide edit awaiting yes/no
        self.recently_changed_names: list[str] = []  # R-41 (QA L1): names removed/swapped out this session, for a more transparent "couldn't find X" message

    def _get_llm(self):
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def _say(self, text: str) -> None:
        # R-9 (Itinerary-Quality-Review-and-Recommendations.md F-10): a
        # presentation-layer failure here (TTS error, or — before R-14's
        # UTF-8 stdout fix — a console encoding crash on a character like
        # "->") used to be able to propagate up past an already-committed
        # state change (e.g. a successful edit's `self.itinerary =
        # outcome["itinerary"]`), landing in a broader except-block that
        # told the user "something went wrong" while the change had, in
        # fact, already been applied — the plan silently changed under an
        # error message. _say is purely a notification side-channel; its
        # failure must never be mistaken for the operation itself failing,
        # so it can never raise past this method.
        try:
            if self.tts:
                self.tts.speak(text)
            else:
                print(f"\n[Agent]: {text}")
        except Exception:
            try:
                print(f"\n[Agent]: {text}".encode("ascii", errors="replace").decode("ascii"))
            except Exception:
                pass

    def _llm(self, messages: list[dict], system: str = SYSTEM_PROMPT) -> str:
        resp = self._get_llm().chat.completions.create(
            model=LLM_MODEL,
            temperature=0,
            messages=[{"role": "system", "content": system}] + messages,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content

    def _extract_context(self, user_text: str) -> TripContext:
        """Use LLM to parse a free-text string into TripContext fields."""
        sys.path.insert(0, PHASE2_DIR)
        from poi_search import INTEREST_MAP

        raw = self._llm(
            [{"role": "user", "content": user_text}],
            system=_extract_system_prompt(INTEREST_MAP),
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return TripContext()
        return _dict_to_context(data)

    def _agent_decision(self) -> dict:
        """Ask the main LLM what to do next based on conversation history."""
        raw = self._llm(self.history)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"type": "question", "text": "Could you tell me more about your trip plans?"}

    def _apply_context_update(self, update: dict) -> None:
        partial = _dict_to_context(update)
        self.ctx.merge(partial)

    # ------------------------------------------------------------------ #
    # Public API: process one turn
    # ------------------------------------------------------------------ #

    def process_turn(self, user_input: str) -> tuple[str, State]:
        """
        Process one user turn. Returns (agent_response_text, new_state).
        Automatically calls TTS if available. Never raises — LLM/network
        failures (e.g. the LLM provider's daily quota being exhausted) are
        caught and turned into a friendly reply instead of crashing the
        caller (QA-1).
        """
        self.history.append({"role": "user", "content": user_input})

        try:
            return self._process_turn_inner(user_input)
        except Exception as e:
            return self._handle_turn_failure(e)

    def _handle_turn_failure(self, error: Exception) -> tuple[str, State]:
        import openai

        if isinstance(error, openai.RateLimitError):
            reply = "We've hit today's AI usage limit — please try again later. Your itinerary so far is preserved."
        elif isinstance(error, (EnvironmentError, openai.AuthenticationError)):
            reply = "The AI service isn't configured correctly right now. Please check back later."
        elif isinstance(error, openai.APIError):
            reply = "The AI service is having trouble responding right now — please try again in a moment."
        else:
            reply = "Something went wrong on my end — please try again in a moment."
            print(f"  [error] Unexpected error in process_turn: {type(error).__name__}: {error}")

        self._say(reply)
        # Log a synthetic assistant turn so history stays coherent for the next LLM call.
        self.history.append({"role": "assistant", "content": json.dumps({"type": "error", "text": reply})})
        return (reply, self.state)

    def _process_turn_inner(self, user_input: str) -> tuple[str, State]:
        if self.state == State.DONE:
            return ("The itinerary is ready. You can edit it by saying things like "
                    "'Make Day 2 more relaxed' or 'Add a museum on Day 1'.", State.DONE)

        if self.state == State.PRESENT:
            return self._handle_post_build_turn(user_input)

        # City-scope check first — only hard-bounces on the conversation's
        # first turn; once underway, a mention of another city falls through
        # to the LLM instead of derailing the turn (QA-7/R-12).
        if _is_out_of_scope(user_input, mid_conversation=len(self.history) > 1):
            reply = ("I specialize exclusively in New Delhi travel planning. "
                     "I can't help with other cities, but I'd love to plan a Delhi trip for you!")
            self._say(reply)
            self.history.append({"role": "assistant", "content": json.dumps({"type": "out_of_scope", "text": reply})})
            return (reply, self.state)

        decision = self._agent_decision()
        dtype = decision.get("type", "question")

        if self.log_level == "verbose":
            print(f"  [LLM decision] {dtype} | state={self.state.value}")

        reply = decision.get("text", "")

        if dtype == "out_of_scope":
            reply = decision.get("text", "I only plan trips to New Delhi.")
            self._say(reply)

        elif dtype == "question":
            self._apply_context_update(decision.get("context_update", {}))
            self.clarify_count += 1
            # Move to CONFIRM as soon as all *required* fields are known, even if
            # the LLM wants to keep asking about optional ones (dates, group size).
            if self.ctx.is_complete() or self.clarify_count >= self.MAX_CLARIFY:
                self.ctx.fill_defaults()
                reply = (f"I have enough information now. Let me confirm the plan: "
                         f"{self.ctx.summary()}. Shall I go ahead and build your itinerary?")
                self.state = State.CONFIRM
                # Keep the logged decision consistent with what we actually did,
                # so the next LLM call sees a coherent conversation history.
                decision = {"type": "confirm", "text": reply, "trip_context": self.ctx.to_dict()}
            else:
                self.state = State.CLARIFY
            self._say(reply)

        elif dtype == "confirm":
            trip_data = decision.get("trip_context", {})
            self._apply_context_update(trip_data)
            self.ctx.fill_defaults()
            reply = decision.get("text", f"Here's what I have: {self.ctx.summary()}. Does this look right?")
            self.state = State.CONFIRM
            self._say(reply)

        elif dtype == "correction":
            self._apply_context_update(decision.get("context_update", {}))
            self.state = State.CLARIFY
            self.clarify_count += 1
            self._say(reply)

        elif dtype == "build":
            trip_data = decision.get("trip_context", {})
            self._apply_context_update(trip_data)
            self.ctx.fill_defaults()
            build_reply = "Great! Let me search for the best places and put together your itinerary."
            self._say(build_reply)
            self.state = State.BUILD
            itinerary, summary = self._build_itinerary()
            self.itinerary = itinerary
            self.state = State.PRESENT
            self._say(summary)
            reply = build_reply + " " + summary

        self.history.append({"role": "assistant", "content": json.dumps(decision)})
        return (reply, self.state)

    # ------------------------------------------------------------------ #
    # BUILD state
    # ------------------------------------------------------------------ #

    def _build_itinerary(self) -> tuple[dict, str]:
        """Call Phase 2 tools, run Phase 5 evals, and return (itinerary_dict, spoken_summary)."""
        sys.path.insert(0, PHASE2_DIR)
        from poi_search import poi_search_logic, WEAK_COVERAGE_INTERESTS
        from itinerary_builder import itinerary_builder_logic

        self.enrichment_degraded = False  # fresh build — clear any earlier retry's failure

        pois = poi_search_logic(
            city=self.ctx.city,
            interests=self.ctx.interests,
            constraints=self.ctx.constraints or None,
            top_n=20,
        )

        # R-7 (Itinerary-Quality-Review-and-Recommendations.md F-7): flag
        # BEFORE building, from the user's own stated interests — not from
        # is_fallback, which never fires here since these interests DO map
        # to a real category, just not one that honors what was asked for.
        weak_coverage_notes = [
            WEAK_COVERAGE_INTERESTS[i] for i in self.ctx.interests if i in WEAK_COVERAGE_INTERESTS
        ]

        itin_result = itinerary_builder_logic(
            pois=pois,
            days=self.ctx.num_days or 2,
            pace=self.ctx.pace or "moderate",
            daily_hours=float(self.ctx.daily_hours()),
        )

        itin_result, caveat = self._run_post_build_evals(itin_result)
        enrichment_note = self._run_post_build_enrichment()
        time.sleep(BUILD_LLM_CALL_SPACING_SEC)  # QA-8/R-13: space out the narrator call from enrichment's
        self._generate_narrative(itin_result)

        summary = _spoken_summary(itin_result, self.ctx)
        for note in weak_coverage_notes:
            summary += " " + note
        if caveat:
            summary += " " + caveat
        if enrichment_note:
            summary += " " + enrichment_note
        return (itin_result, summary)

    def retry_enrichment(self) -> bool:
        """
        Re-runs enrichment (weather/safety/transit) + the narrator for the
        CURRENT itinerary, without rebuilding it — a cheap, explicit retry
        for when a build's LLM burst got rate-limited (QA-8/R-13). Returns
        True if it's no longer degraded afterward. Never called
        automatically — only in response to a user clicking "retry"; an
        automatic retry loop would multiply calls instead of just
        redistributing them.
        """
        if self.itinerary is None:
            return False
        self.enrichment_degraded = False
        self._run_post_build_enrichment()
        time.sleep(BUILD_LLM_CALL_SPACING_SEC)
        self._generate_narrative(self.itinerary)
        return not self.enrichment_degraded

    def _generate_narrative(self, itinerary: dict) -> None:
        """
        Trained narrator (llm-itinerary-training-document.md): turns the
        already-grounded schedule into the full TRIP OVERVIEW / DAY-BY-DAY /
        FOOD HIGHLIGHTS / GETTING AROUND / BUDGET ESTIMATE / PRACTICAL TIPS
        narrative. Best-effort — never blocks itinerary presentation.
        """
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from itinerary_narrator import generate_narrative_itinerary

            self.narrative = generate_narrative_itinerary(
                itinerary, self.ctx.to_dict(),
                weather_note=self.weather_note,
                safety_tip=self.safety_tip,
                transit_info=self.transit_info,
            )
            self.narrative_stale = False
        except Exception:
            self.narrative = None
            # QA-8/R-13: an actual error (e.g. rate limit), not "nothing to
            # narrate" — surface it in the UI instead of failing silently.
            self.enrichment_degraded = True

    def _run_post_build_enrichment(self) -> str:
        """
        Proactively surfaces a one-line weather/packing note (live Open-Meteo
        forecast) and a cited safety tip (RAG) alongside the built itinerary.
        Both are best-effort and grounded — never fabricated, and never
        allowed to break itinerary presentation if the network/LLM hiccups.
        """
        notes = []

        try:
            sys.path.insert(0, PHASE2_DIR)
            from weather import weather_logic

            dates = _resolve_travel_dates(self.ctx)
            forecast = weather_logic(self.ctx.city, dates)
            if forecast.get("forecast"):
                risky_days = [f for f in forecast["forecast"] if f.get("outdoor_risk")]
                if risky_days:
                    note = (
                        f"Weather heads-up: {len(risky_days)} of your {len(dates)} days may see rain or "
                        "extreme heat — pack accordingly and consider an indoor swap for those days."
                    )
                else:
                    note = "Weather looks clear for your trip — pack light, comfortable walking shoes."
                notes.append(note)
                self.weather_note = note
        except Exception:
            pass  # weather is best-effort and not LLM-driven; never block itinerary presentation on it

        try:
            sys.path.insert(0, PHASE4_DIR)
            from explain_engine import explain

            safety = explain("What areas should I avoid at night in New Delhi?", itinerary=None, pace=self.ctx.pace or "moderate")
            if safety.get("grounded"):
                # UX-13/R-15: softer lead-in than a bare "Safety tip:" label,
                # which read as an alarm right after the excited build summary
                # — still clearly flagged as safety info, just less abrupt.
                notes.append(f"One practical safety note for your trip: {safety['answer']}")
                self.last_citations = safety.get("citations", [])
                self.safety_tip = safety
        except Exception:
            # QA-8/R-13: a real failure (rate limit, network) — distinct from
            # explain() legitimately returning grounded=False, which is
            # correct behavior, not a failure to signal.
            self.enrichment_degraded = True

        time.sleep(BUILD_LLM_CALL_SPACING_SEC)  # QA-8/R-13: space the transit call from the safety call above

        # Getting-around info: shown as a dedicated UI panel (not spoken —
        # would make the voice summary too long), so stored separately.
        try:
            sys.path.insert(0, PHASE4_DIR)
            from explain_engine import explain

            transit = explain(
                "How do I get around Delhi — which transit passes or metro cards are worth buying?",
                itinerary=None, pace=self.ctx.pace or "moderate",
            )
            if transit.get("grounded"):
                self.transit_info = transit
        except Exception:
            self.enrichment_degraded = True

        return " ".join(notes)

    def _run_post_build_evals(self, itinerary: dict) -> tuple[dict, str]:
        """
        Eval 3 (Grounding): auto-corrects by dropping any POI not in the Phase 1 dataset.
        Eval 1 (Feasibility): informational only — surfaced as a spoken caveat, not blocking.
        """
        sys.path.insert(0, PHASE4_DIR)
        sys.path.insert(0, PHASE5_DIR)
        from grounding import check_grounding
        from feasibility import check_feasibility

        grounding_result = check_grounding(itinerary)
        if not grounding_result["pass"]:
            itinerary = _strip_ungrounded_pois(itinerary, grounding_result["ungrounded_pois"])
            if self.log_level == "verbose":
                print(f"  [eval] grounding FAILED, removed: {grounding_result['ungrounded_pois']}")

        feasibility_result = check_feasibility(itinerary, self.ctx.pace or "moderate")
        caveat = ""
        if not feasibility_result["pass"]:
            problems = "; ".join(f"Day {i['day']}: {i['problem']}" for i in feasibility_result["issues"])
            caveat = f"Heads up — {problems}."
            if self.log_level == "verbose":
                print(f"  [eval] feasibility FAILED: {feasibility_result['issues']}")

        return itinerary, caveat

    # ------------------------------------------------------------------ #
    # Post-BUILD turns: EDIT / EXPLAIN / NEW_PLAN (Phase 4)
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self.state = State.COLLECT
        self.ctx = TripContext()
        self.history = []
        self.itinerary = None
        self.clarify_count = 0
        self.last_citations = []
        self.transit_info = None
        self.weather_note = None
        self.safety_tip = None
        self.narrative = None
        self.narrative_stale = False
        self.enrichment_degraded = False
        self.pending_edit = None
        self.recently_changed_names = []

    def _handle_post_build_turn(self, user_input: str) -> tuple[str, State]:
        text_lower = user_input.strip().lower()

        # R-41 (QA M2): resolve a pending, not-yet-committed confirmation
        # before anything else -- it's the most specific context we can be
        # in. Anything other than a clear yes/no drops the pending edit
        # rather than leaving the user stuck waiting on a question they may
        # have moved on from; the turn is then processed normally below.
        if self.pending_edit is not None:
            if _is_affirmative(text_lower):
                self.itinerary = self.pending_edit["preview_itinerary"]
                self.narrative_stale = True
                self.pending_edit = None
                reply = "Done — went ahead with that."
                self._say(reply)
                self.history.append({"role": "assistant", "content": json.dumps(
                    {"type": "edit_result", "ok": True, "text": reply}
                )})
                return (reply, self.state)
            if _is_negative(text_lower):
                self.pending_edit = None
                reply = "No problem, I've left your itinerary as it was."
                self._say(reply)
                self.history.append({"role": "assistant", "content": json.dumps(
                    {"type": "edit_result", "ok": False, "text": reply}
                )})
                return (reply, self.state)
            self.pending_edit = None

        if _is_exit_phrase(text_lower):
            self.state = State.DONE
            reply = "Great, enjoy your trip to Delhi! Your itinerary is saved."
            self._say(reply)
            return (reply, self.state)

        sys.path.insert(0, PHASE4_DIR)
        from intent_classifier import classify_intent
        from edit_engine import apply_edit
        from explain_engine import explain

        result = classify_intent(user_input, itinerary=self.itinerary)
        intent = result["intent"]

        if intent == "NEW_PLAN":
            self.reset()
            reply = "Sure, let's start fresh! Tell me about your next trip."
            self._say(reply)
            return (reply, self.state)

        if intent == "EDIT":
            edit_intent = result.get("edit_intent") or {}

            # R-41 (QA M2): a "relax" scoped to the WHOLE trip with no
            # explicit pacing cue in the user's own words (e.g. "make the
            # whole trip more fun") previously committed immediately,
            # silently dropping a real stop from every day at once. Preview
            # instead of committing when nothing in the text actually
            # signals a broad pacing change.
            if (edit_intent.get("edit_type") == "relax"
                    and edit_intent.get("target_day") == "all"
                    and not _has_explicit_pacing_cue(user_input)):
                outcome = apply_edit(self.itinerary, edit_intent, pace=self.ctx.pace or "moderate", city=self.ctx.city)
                if outcome["ok"] and outcome["changed_days"]:
                    self.pending_edit = {"edit_intent": edit_intent, "preview_itinerary": outcome["itinerary"]}
                    reply = (
                        f"\"{user_input}\" is a bit open-ended, so before I touch every day, here's what I'd do: "
                        f"{outcome['message']} Want me to go ahead? (yes/no)"
                    )
                else:
                    reply = outcome["message"]
                self._say(reply)
                self.history.append({"role": "assistant", "content": json.dumps(
                    {"type": "edit_pending" if self.pending_edit else "edit_result", "ok": outcome["ok"], "text": reply}
                )})
                return (reply, self.state)

            before_itinerary = copy.deepcopy(self.itinerary)
            outcome = apply_edit(self.itinerary, edit_intent, pace=self.ctx.pace or "moderate", city=self.ctx.city)

            if outcome["ok"]:
                sys.path.insert(0, PHASE5_DIR)
                from edit_correctness import check_edit_correctness
                from feasibility import check_feasibility

                correctness = check_edit_correctness(
                    before_itinerary, outcome["itinerary"],
                    edit_intent.get("target_day", "all"), edit_intent.get("target_slot", "all"),
                )
                feasibility = check_feasibility(outcome["itinerary"], self.ctx.pace or "moderate")

                if not correctness["pass"]:
                    reply = (
                        "That edit ended up changing more than intended "
                        f"({', '.join(correctness['drifted_slots'])}), so I've left your itinerary as it was."
                    )
                    if self.log_level == "verbose":
                        print(f"  [eval] edit correctness FAILED, rolled back: {correctness['drifted_slots']}")
                elif not feasibility["pass"]:
                    problems = "; ".join(f"Day {i['day']}: {i['problem']}" for i in feasibility["issues"])
                    reply = f"That edit would make the plan too packed ({problems}), so I've left your itinerary as it was."
                    if self.log_level == "verbose":
                        print(f"  [eval] feasibility FAILED post-edit, rolled back: {feasibility['issues']}")
                else:
                    self.itinerary = outcome["itinerary"]
                    self.narrative_stale = True  # Day tabs now ahead of the "Full Itinerary" overview (QA-2/R-3)
                    reply = outcome["message"]
                    # R-41 (QA L1): a later "remove X" that can't find X gives
                    # an unhelpfully generic message when X was already
                    # changed by an earlier edit THIS session -- remember
                    # what just left the itinerary so that message can say so.
                    if edit_intent.get("edit_type") == "remove" and reply.startswith("Couldn't find anything matching"):
                        constraint_name = (edit_intent.get("constraint") or "").strip().lower()
                        match = next(
                            (n for n in self.recently_changed_names if constraint_name and constraint_name in n.lower()),
                            None,
                        )
                        if match:
                            reply += f" You may have already changed or removed \"{match}\" earlier in this session."
                    else:
                        self.recently_changed_names.extend(_extract_changed_out_names(edit_intent.get("edit_type", ""), reply))
            else:
                reply = outcome["message"]

            self._say(reply)
            self.history.append({"role": "assistant", "content": json.dumps(
                {"type": "edit_result", "ok": outcome["ok"], "text": reply}
            )})
            return (reply, self.state)

        # EXPLAIN
        explanation = explain(result.get("query", user_input), self.itinerary, pace=self.ctx.pace or "moderate")
        reply = explanation["answer"]
        self._say(reply)
        self.last_citations = explanation.get("citations", [])
        self.history.append({"role": "assistant", "content": json.dumps(
            {"type": "explain_result", "text": reply, "citations": self.last_citations}
        )})
        return (reply, self.state)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _resolve_travel_dates(ctx: TripContext) -> list[str]:
    """
    Best-effort ISO date resolution for the weather lookup. TripContext.travel_dates
    is free text (e.g. "next weekend") with no date-parsing infrastructure behind
    it, so: try to find an explicit ISO date in it, else default to a real forecast
    window starting tomorrow — live data for a reasonable window, never fabricated.
    """
    import re
    from datetime import date, timedelta

    num_days = ctx.num_days or 2
    if ctx.travel_dates:
        m = re.search(r"\d{4}-\d{2}-\d{2}", ctx.travel_dates)
        if m:
            try:
                start = date.fromisoformat(m.group(0))
                return [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
            except ValueError:
                pass

    start = date.today() + timedelta(days=1)
    return [(start + timedelta(days=i)).isoformat() for i in range(num_days)]

def _strip_ungrounded_pois(itinerary: dict, names: list[str]) -> dict:
    """Eval 3 auto-correction: remove any stop that failed grounding and recompute totals."""
    names_set = set(names)
    for key in itinerary:
        if not key.startswith("day_"):
            continue
        day = itinerary[key]
        for slot in ("morning", "afternoon", "evening"):
            day[slot] = [s for s in day[slot] if s.get("name") not in names_set]
        minutes = sum(
            s.get("visit_duration_min", 0) + s.get("travel_time_from_prev_min", 0)
            for slot in ("morning", "afternoon", "evening")
            for s in day[slot]
        )
        day["total_hours"] = round(minutes / 60, 2)
    return itinerary


def _dict_to_context(d: dict) -> TripContext:
    ctx = TripContext()
    if "city" in d and d["city"]:
        ctx.city = str(d["city"])
    if "num_days" in d and d["num_days"]:
        try:
            ctx.num_days = int(d["num_days"])
        except (ValueError, TypeError):
            pass
    if "travel_dates" in d:
        ctx.travel_dates = d.get("travel_dates")
    if "interests" in d and isinstance(d["interests"], list):
        ctx.interests = [str(i).lower() for i in d["interests"]]
    if "pace" in d and d["pace"] in ("relaxed", "moderate", "intensive"):
        ctx.pace = d["pace"]
    if "group_size" in d and d["group_size"]:
        try:
            ctx.group_size = int(d["group_size"])
        except (ValueError, TypeError):
            pass
    if "constraints" in d and isinstance(d["constraints"], dict):
        ctx.constraints = d["constraints"]
    return ctx


OTHER_CITIES = [
    "mumbai", "bangalore", "bengaluru", "chennai", "kolkata", "hyderabad",
    "pune", "jaipur", "agra", "goa", "varanasi", "kerala", "rajasthan",
    "london", "paris", "dubai", "new york", "singapore", "bangkok",
]
_OTHER_CITY_RE = re.compile(r"\b(" + "|".join(re.escape(c) for c in OTHER_CITIES) + r")\b")
_DELHI_RE = re.compile(r"\bdelhi\b")


def _is_out_of_scope(text: str, mid_conversation: bool = False) -> bool:
    """
    Quick keyword check for non-Delhi cities before calling LLM.

    Word-boundary matching (not bare substring) avoids false positives like
    "Puneet" containing "pune". Once the conversation is already underway
    (mid_conversation=True — this isn't the user's first turn), a mere
    mention of another city is no longer hard-bounced here: "I love food
    like they have in Mumbai" is a comparison, not a request to switch
    cities, and only the LLM can tell the two apart. The pre-LLM
    short-circuit is kept for the cheap, unambiguous case — a fresh
    first-turn request naming another city outright (QA-7/R-12).
    """
    if mid_conversation:
        return False
    lower = text.lower()
    if _OTHER_CITY_RE.search(lower):
        # But let Delhi-adjacent mentions through (e.g., "from Mumbai to Delhi")
        if not _DELHI_RE.search(lower):
            return True
    return False


# R-41 (Itinerary edit commands QA, finding M2): words/phrases that signal
# the user actually meant a pacing change (as opposed to a generic sentiment
# word like "fun"/"better", which the classifier can still map to "relax"
# but which the user very plausibly did NOT mean as "delete real stops").
_PACING_CUE_WORDS = (
    "relax", "pack", "light", "loosen", "easier", "slower", "slow down",
    "chill", "breathing room", "free time", "too much", "too busy",
    "overloaded", "tone down", "cut down", "trim", "less busy", "less full",
    "declutter",
)


def _has_explicit_pacing_cue(text: str) -> bool:
    lower = text.lower()
    return any(cue in lower for cue in _PACING_CUE_WORDS)


_AFFIRMATIVE_PHRASES = {
    "yes", "yeah", "yep", "yup", "sure", "go ahead", "do it", "please do",
    "ok", "okay", "confirm", "affirmative", "sounds good",
}
_NEGATIVE_PHRASES = {
    "no", "nope", "nah", "don't", "do not", "cancel", "nevermind",
    "never mind", "leave it", "stop",
}


def _is_affirmative(text: str) -> bool:
    lower = text.strip().lower().rstrip(".!")
    return lower in _AFFIRMATIVE_PHRASES or any(lower.startswith(p) for p in _AFFIRMATIVE_PHRASES)


def _is_negative(text: str) -> bool:
    lower = text.strip().lower().rstrip(".!")
    return lower in _NEGATIVE_PHRASES or any(lower.startswith(p) for p in _NEGATIVE_PHRASES)


def _extract_changed_out_names(edit_type: str, message: str) -> list[str]:
    """
    Best-effort parse of edit_engine.py's own fixed message formats to learn
    which real stop name(s) just left the itinerary (QA finding L1) -- used
    only so a later "remove X" that can't find X can say it was likely
    already changed earlier in this session, instead of a bare unexplained
    "couldn't find" message.
    """
    names: list[str] = []
    if edit_type == "remove" and message.startswith("Removed ") and message.endswith(" from the itinerary."):
        names.append(message[len("Removed "):-len(" from the itinerary.")])
    elif edit_type == "relax" and "removed " in message and " to free up time." in message:
        middle = message.split("removed ", 1)[1].rsplit(" to free up time.", 1)[0]
        names.extend(n.strip() for n in middle.split(","))
    elif edit_type == "swap" and message.startswith("Swapped: "):
        body = message[len("Swapped: "):].rstrip(".")
        for pair in body.split("; "):
            if "→" in pair:
                names.append(pair.split("→", 1)[0].strip())
    return [n for n in names if n]


def _day_stops(day: dict) -> list[dict]:
    """Flatten a day's morning/afternoon/evening slots into one ordered stop list."""
    return day.get("morning", []) + day.get("afternoon", []) + day.get("evening", [])


def _spoken_summary(itinerary: dict, ctx: TripContext) -> str:
    day_keys = sorted(
        (k for k in itinerary if k.startswith("day_")),
        key=lambda k: int(k.split("_")[1]),
    )
    day_count = len(day_keys)
    total_stops = sum(len(_day_stops(itinerary[k])) for k in day_keys)

    parts = [
        f"Your {day_count}-day Delhi itinerary is ready with {total_stops} stops in total."
    ]
    for i, key in enumerate(day_keys[:2], 1):
        stops = _day_stops(itinerary[key])
        if stops:
            first = stops[0].get("name", "")
            last = stops[-1].get("name", "") if len(stops) > 1 else ""
            if last:
                parts.append(f"Day {i} starts at {first} and ends at {last}.")
            else:
                parts.append(f"Day {i} features {first}.")

    return " ".join(parts)


# ------------------------------------------------------------------ #
# Convenience: run an interactive session
# ------------------------------------------------------------------ #

def run_session(voice: bool = False) -> None:
    from tts import TTS
    from stt import STT

    tts = TTS(mode="speak" if voice else "print")
    stt = STT(mode="mic" if voice else "text")

    agent = TravelAgent(tts=tts, log_level="normal")

    tts.speak("Welcome! I'm your Delhi travel planning assistant. Tell me about your trip — "
              "where are you coming from, how many days, what you enjoy doing?")

    while agent.state != State.DONE:
        user_input = stt.listen()
        if not user_input:
            tts.speak("I didn't catch that. Could you say it again?")
            continue
        _, new_state = agent.process_turn(user_input)

    if agent.itinerary:
        print("\n[Itinerary JSON]")
        print(json.dumps(agent.itinerary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--voice", action="store_true", help="Enable mic input + TTS output")
    args = p.parse_args()
    run_session(voice=args.voice)
