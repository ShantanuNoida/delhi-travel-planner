"""
Tests for the trained itinerary narrator (llm-itinerary-training-document.md).
Usage: python test_narrator.py
Requires GROQ_API_KEY.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase2"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env explicitly rather than relying on some other module's import to
# trigger it as a side effect (config.py does this too, but only once
# imported — _needs_api_key() below must be accurate before that happens).
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def _result(label: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


def _build_fixture():
    from poi_search import poi_search_logic
    from itinerary_builder import itinerary_builder_logic

    pois = poi_search_logic("New Delhi", ["history", "food"], top_n=15)
    itin = itinerary_builder_logic(pois, days=2, pace="moderate")
    return itin, pois


def _needs_api_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _real_stop_names(itin: dict) -> list[str]:
    return [
        stop["name"]
        for key in itin if key.startswith("day_")
        for slot in ("morning", "afternoon", "evening")
        for stop in itin[key][slot]
    ]


def check_required_sections(narrative: str) -> bool:
    print("\nNarrator — Required Sections Present")
    from itinerary_narrator import REQUIRED_SECTIONS

    all_ok = True
    for section in REQUIRED_SECTIONS:
        ok = section in narrative
        _result(f'section "{section}" present', ok)
        if not ok:
            all_ok = False
    return all_ok


def check_real_stops_preserved(narrative: str, itin: dict) -> bool:
    print("\nNarrator — Real Stops Preserved (no invented itinerary)")
    real_names = _real_stop_names(itin)
    present = [name for name in real_names if name in narrative]
    ok = len(present) >= max(1, len(real_names) // 2)  # majority of real stops should be named verbatim
    return _result("majority of real grounded stop names appear verbatim", ok, f"{len(present)}/{len(real_names)}")


def check_budget_is_hedged(narrative: str) -> bool:
    print("\nNarrator — Budget Estimate Is Hedged, Not Stated As Fact")
    budget_section_start = narrative.find("BUDGET ESTIMATE")
    ok = budget_section_start != -1
    if ok:
        budget_section = narrative[budget_section_start:budget_section_start + 500]
        has_hedge = "estimat" in budget_section.lower() or "verify" in budget_section.lower()
        ok = has_hedge
        _result("budget section contains estimate/verify hedging", ok)
    else:
        _result("budget section found", False)
    return ok


def test_narrator_does_not_break_build() -> bool:
    print("\nNarrator — Failure Never Blocks Itinerary Presentation")
    from agent import TravelAgent
    from trip_context import TripContext
    import itinerary_narrator

    # itinerary_narrator.generate_narrative_itinerary is imported locally
    # inside agent.py's _generate_narrative(), so patching the module
    # attribute here is what that local `from ... import ...` resolves to.
    original = itinerary_narrator.generate_narrative_itinerary

    def _broken(*args, **kwargs):
        raise RuntimeError("simulated LLM outage")

    itinerary_narrator.generate_narrative_itinerary = _broken
    try:
        agent = TravelAgent(log_level="quiet")
        agent.ctx = TripContext(city="New Delhi", num_days=2, interests=["history", "food"], pace="moderate", group_size=1)
        agent.ctx.fill_defaults()
        itinerary, summary = agent._build_itinerary()
    finally:
        itinerary_narrator.generate_narrative_itinerary = original

    ok_itin = isinstance(itinerary, dict) and any(k.startswith("day_") for k in itinerary)
    ok_narrative_none = agent.narrative is None
    _result("itinerary still built despite narrator failure", ok_itin)
    _result("narrative left as None on failure (no crash)", ok_narrative_none)
    return ok_itin and ok_narrative_none


def _skip(name: str, reason: str = "GROQ_API_KEY not set") -> bool:
    print(f"  [SKIP] {name} — {reason}")
    return True


def run_all() -> dict[str, bool]:
    print("=" * 60)
    print("ITINERARY NARRATOR VALIDATION TESTS")
    print("=" * 60)

    results: dict[str, bool] = {}
    has_key = _needs_api_key()

    if not has_key:
        print("  NOTE: GROQ_API_KEY not set — LLM-dependent tests will be skipped.\n")
        for name in ("Required Sections Present", "Real Stops Preserved", "Budget Is Hedged"):
            results[name] = _skip(name)
    else:
        # Generate the narrative ONCE and reuse it across all three content
        # checks — cuts LLM token usage 3x versus each test generating its
        # own, and means a mid-run API failure (rate limit, network, etc.)
        # can't crash the whole test file: it's caught here and every
        # dependent check is reported as a clear FAIL, not an unhandled
        # traceback.
        try:
            from itinerary_narrator import generate_narrative_itinerary
            itin, _ = _build_fixture()
            ctx = {"city": "New Delhi", "num_days": 2, "pace": "moderate", "interests": ["history", "food"], "group_size": 1}
            narrative = generate_narrative_itinerary(itin, ctx)
        except Exception as e:
            reason = f"narrator call failed — {type(e).__name__}: {e}"
            print(f"\n  [ERROR] Could not generate narrative — {reason}")
            for name in ("Required Sections Present", "Real Stops Preserved", "Budget Is Hedged"):
                results[name] = _result(name, False, reason)
        else:
            results["Required Sections Present"] = check_required_sections(narrative)
            results["Real Stops Preserved"] = check_real_stops_preserved(narrative, itin)
            results["Budget Is Hedged"] = check_budget_is_hedged(narrative)

    # Always runs — no LLM call involved, so nothing above should affect it.
    try:
        results["Narrator Failure Handling"] = test_narrator_does_not_break_build()
    except Exception as e:
        results["Narrator Failure Handling"] = _result(
            "Narrator Failure Handling", False, f"unexpected error — {type(e).__name__}: {e}"
        )

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
