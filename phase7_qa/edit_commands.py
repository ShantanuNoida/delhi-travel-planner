"""
Team Waypoint -- Itinerary edit commands QA (Phase 1)
Agent 3 (Edit Command Agent): generates 15 edit commands per itinerary,
tailored to that itinerary's actual day count, stops, and theme.
"""

THEMES = ["food", "history", "culture", "nature", "art", "shopping", "architecture", "family", "religion"]

DAY_SLOTS = ("morning", "afternoon", "evening")


def _all_stops(itinerary: dict) -> list[dict]:
    stops = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        day_num = int(key.split("_")[1])
        for slot in DAY_SLOTS:
            for stop in itinerary[key].get(slot, []):
                stops.append({"day": day_num, "slot": slot, "name": stop["name"], "category": stop.get("category", "")})
    return stops


def generate_edit_commands(itinerary: dict, spec: dict) -> list[dict]:
    """Returns a list of 15 dicts: {n, command, category, probe, expected}."""
    days = spec["days"]
    interests = spec["interests"]
    absent_themes = [t for t in THEMES if t not in interests] or ["art"]
    stops = _all_stops(itinerary)

    last_day = days
    mid_day = 2 if days >= 2 else 1
    # a real stop to remove by name (prefer one not in day 1, for variety)
    removable = next((s for s in stops if s["day"] != 1), stops[0] if stops else None)

    cmds = []

    cmds.append({
        "command": "Make Day 1 more relaxed.",
        "category": "pacing", "probe": "relax_vague_quantity",
        "expected": {"edit_type": "relax", "target_day": 1, "target_slot": "all"},
    })
    cmds.append({
        "command": f"Day {last_day} feels too packed — take one thing out of the evening.",
        "category": "pacing", "probe": "relax_specific_slot",
        "expected": {"edit_type": "relax", "target_day": last_day, "target_slot": "evening"},
    })
    cmds.append({
        "command": f"Day {mid_day} is a lot — can you lighten it up somehow?",
        "category": "pacing", "probe": "relax_vague_phrasing",
        "expected": {"edit_type": "relax", "target_day": mid_day, "target_slot": "all"},
    })

    cmds.append({
        "command": "Swap the Day 1 evening plan to something indoors.",
        "category": "swap", "probe": "swap_indoor",
        "expected": {"edit_type": "swap", "target_day": 1, "target_slot": "evening", "constraint": "indoor"},
    })
    cmds.append({
        "command": f"Swap the Day {last_day} morning plan to something outdoors.",
        "category": "swap", "probe": "swap_outdoor",
        "expected": {"edit_type": "swap", "target_day": last_day, "target_slot": "morning", "constraint": "outdoor"},
    })
    cmds.append({
        "command": f"Swap Day {mid_day} afternoon for a {absent_themes[0]} spot instead.",
        "category": "swap", "probe": "swap_theme_category",
        "expected": {"edit_type": "swap", "target_day": mid_day, "target_slot": "afternoon", "constraint": absent_themes[0]},
    })
    cmds.append({
        "command": "Replace the Day 1 evening stop with Connaught Place.",
        "category": "swap", "probe": "swap_known_absent_place",
        "expected": {"edit_type": "swap", "target_day": 1, "target_slot": "evening", "constraint": "Connaught Place",
                     "note": "Connaught Place is a documented KNOWN_ABSENT_POPULAR_PLACES entry -- app should honestly decline, not silently substitute."},
    })

    cmds.append({
        "command": "Add one famous local food place to Day 1.",
        "category": "add", "probe": "add_food_famous",
        "expected": {"edit_type": "add", "target_day": 1, "target_slot": "evening", "constraint": "food"},
    })
    cmds.append({
        "command": f"Add a {absent_themes[-1]} stop somewhere in the trip.",
        "category": "add", "probe": "add_theme_any_day",
        "expected": {"edit_type": "add", "target_day": "all", "target_slot": "evening", "constraint": absent_themes[-1]},
    })
    cmds.append({
        "command": f"Add Select Citywalk mall to Day {mid_day}.",
        "category": "add", "probe": "add_known_absent_place",
        "expected": {"edit_type": "add", "target_day": mid_day, "constraint": "Select Citywalk",
                     "note": "Select Citywalk is a documented KNOWN_ABSENT_POPULAR_PLACES entry -- app should honestly decline."},
    })

    if removable:
        cmds.append({
            "command": f"Remove {removable['name']} from Day {removable['day']}.",
            "category": "remove", "probe": "remove_real_named_stop",
            "expected": {"edit_type": "remove", "target_day": removable["day"], "constraint": removable["name"]},
        })
    else:
        cmds.append({
            "command": "Remove the museum stop from Day 1.",
            "category": "remove", "probe": "remove_real_named_stop_fallback",
            "expected": {"edit_type": "remove", "target_day": 1, "constraint": "museum"},
        })
    cmds.append({
        "command": "Remove the boring stop from Day 1.",
        "category": "remove", "probe": "remove_vague_no_referent",
        "expected": {"edit_type": "remove or relax (ambiguous)", "target_day": 1,
                     "note": "'boring' names nothing searchable -- correct behavior is an honest 'couldn't find a match' or classification as relax, not a hallucinated removal."},
    })

    cmds.append({
        "command": "Reduce travel time between stops.",
        "category": "logistics", "probe": "reduce_travel_whole_trip",
        "expected": {"edit_type": "reduce_travel", "target_day": "all"},
    })

    cmds.append({
        "command": f"Make Day {last_day + 2} more relaxed.",
        "category": "edge_case", "probe": "invalid_day_reference",
        "expected": {"edit_type": "relax", "target_day": last_day + 2,
                     "note": f"Day {last_day + 2} does not exist in a {days}-day trip -- app should reject cleanly, not crash or silently no-op without explanation."},
    })
    cmds.append({
        "command": "Make the whole trip more fun.",
        "category": "edge_case", "probe": "vague_no_actionable_edit_type",
        "expected": {"edit_type": "ambiguous", "target_day": "all",
                     "note": "No day/slot/edit-type signal at all -- tests whether the classifier defaults sensibly or misfires (e.g. defaulting to 'swap' with an empty/nonsense constraint)."},
    })

    assert len(cmds) == 15
    for i, c in enumerate(cmds, start=1):
        c["n"] = i
    return cmds
