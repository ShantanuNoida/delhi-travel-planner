"""
Eval 2: Edit Correctness Check.

Diffs an itinerary before/after a voice edit and verifies the change was
confined to the declared target_day + target_slot. Any change outside that
scope is "drift" and should trigger a rollback by the caller.
"""

import json

DAY_SLOTS = ("morning", "afternoon", "evening")


def _all_day_keys(itinerary: dict) -> set[str]:
    return {k for k in itinerary if k.startswith("day_")}


def _slot_equal(before_slot: list[dict], after_slot: list[dict]) -> bool:
    return json.dumps(before_slot, sort_keys=True) == json.dumps(after_slot, sort_keys=True)


def check_edit_correctness(before: dict, after: dict, target_day, target_slot: str) -> dict:
    """
    Returns {"pass": bool, "drifted_slots": ["day_2.morning", ...]}.
    target_day: int (1-based) or "all". target_slot: "morning"/"afternoon"/"evening"/"all".
    """
    allowed_days = _all_day_keys(before) if target_day == "all" else {f"day_{target_day}"}
    allowed_slots = set(DAY_SLOTS) if target_slot == "all" else {target_slot}

    drifted = []
    all_days = _all_day_keys(before) | _all_day_keys(after)

    for day_key in sorted(all_days, key=lambda k: int(k.split("_")[1])):
        before_day = before.get(day_key, {})
        after_day = after.get(day_key, {})

        if day_key not in before or day_key not in after:
            # A day was added/removed entirely — only acceptable for "all"-scoped edits
            # (e.g. reduce_travel rebuilding the day set).
            if day_key not in allowed_days:
                drifted.append(f"{day_key}.*")
            continue

        for slot in DAY_SLOTS:
            if not _slot_equal(before_day.get(slot, []), after_day.get(slot, [])):
                if day_key not in allowed_days or slot not in allowed_slots:
                    drifted.append(f"{day_key}.{slot}")

    return {"pass": len(drifted) == 0, "drifted_slots": drifted}
