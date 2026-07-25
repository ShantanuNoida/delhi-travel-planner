"""
Feasibility check — used by the Explanation Engine ("Is this plan doable?")
and by the Edit Engine as a guard against overflowing edits.

This is the same core check specified for Phase 5's Eval 1 (Feasibility Check).
It is defined here because Phase 4 needs it before Phase 5 exists; Phase 5 can
import this module directly rather than duplicating the logic.
"""

PACE_HOURS = {"relaxed": 6.0, "moderate": 8.0, "intensive": 10.0}
MAX_TRAVEL_LEG_MIN = 45

# Mirrors phase2/itinerary_builder.py's MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN
# (kept as a duplicated literal, not a cross-phase import, to keep this
# module dependency-free per its own docstring — "Phase 4 needs it before
# Phase 5 exists"). The itinerary builder's breakfast/lunch/dinner coverage
# guarantee (added 2026-07-16) can legitimately push a day up to this many
# minutes over its pace budget to fit a real nearby meal; without this
# allowance, this check would flag the builder's own valid, deliberate
# output as an infeasible day — which post-edit even triggers a rollback in
# agent.py's second safety net, undoing an edit that was actually fine.
MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN = 30


def _day_keys(itinerary: dict) -> list[str]:
    return sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1]))


def check_feasibility(itinerary: dict, pace: str) -> dict:
    """
    Returns {"pass": bool, "issues": [{"day": int, "problem": str, "suggestion": str}]}.
    A day fails if its total_hours exceeds the pace budget, or if any single
    travel leg between stops exceeds MAX_TRAVEL_LEG_MIN.
    """
    budget = PACE_HOURS.get(pace, 8.0)
    issues = []

    for key in _day_keys(itinerary):
        day = itinerary[key]
        day_num = int(key.split("_")[1])
        total = day.get("total_hours", 0)

        if total > budget + (MEAL_BUDGET_OVERRUN_ALLOWANCE_MIN / 60):
            issues.append({
                "day": day_num,
                "problem": f"total time {total}h exceeds the {budget}h {pace} budget",
                "suggestion": "remove a stop or move it to another day",
            })

        for slot in ("morning", "afternoon", "evening"):
            for stop in day.get(slot, []):
                leg = stop.get("travel_time_from_prev_min", 0)
                if leg > MAX_TRAVEL_LEG_MIN:
                    issues.append({
                        "day": day_num,
                        "problem": f"travel to {stop.get('name', '?')} takes {leg} min (> {MAX_TRAVEL_LEG_MIN} min)",
                        "suggestion": "re-cluster stops geographically to cut travel time",
                    })

    return {"pass": len(issues) == 0, "issues": issues}


UNDERFILL_RATIO = 0.6  # a day using less than 60% of its pace budget reads as noticeably light


def check_day_balance(itinerary: dict, pace: str) -> dict:
    """
    Informational-only companion to check_feasibility (UX-14/R-16): flags
    days that are notably under the pace budget or have no evening stop, so
    the UI can say so honestly instead of the narrator's generic "explore
    the streets" filler papering over a genuinely light day.

    Deliberately NOT merged into check_feasibility's pass/issues — that
    function is also used as an edit-guard (rejects/rolls back edits that
    push a day over budget), and "under-filled" is not a failure the way
    "over-packed" is. This never returns pass=False and must not be wired
    into any build/edit-blocking path.
    """
    budget = PACE_HOURS.get(pace, 8.0)
    notes = []
    for key in _day_keys(itinerary):
        day = itinerary[key]
        day_num = int(key.split("_")[1])
        total = day.get("total_hours", 0)
        if total < budget * UNDERFILL_RATIO:
            notes.append({
                "day": day_num,
                "note": f"only {total}h scheduled of your {budget}h {pace} budget — plenty of free time",
            })
        if not day.get("evening"):
            notes.append({
                "day": day_num,
                "note": "no evening stop scheduled — evening left open for flexibility",
            })
    return {"notes": notes}
