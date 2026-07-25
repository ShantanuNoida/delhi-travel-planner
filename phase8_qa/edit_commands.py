"""
Team Waypoint -- Round 3 (+ post-round harness broadening, 2026-07-25)
Agent 2 (Edit Command Agent): generates 23 edit commands per itinerary --
the original 15 probe types from Phase 1, 5 from Round 3 (free-of-charge
swap, real-named-place add, reorder request, gibberish input, whole-trip
relax), plus 3 added after live user-reported bugs slipped past this
harness entirely: every original swap/remove probe targeted a stop by
DAY/SLOT POSITION ("Swap the Day 1 evening plan...") or by an exact,
unique NAME ("Remove {removable['name']} from Day N") -- never by naming
BOTH an existing and a new stop together ("Swap Humayun's Tomb for Qutab
Minar"), and never by a bare CATEGORY reference to an existing stop ("the
market", "the restaurant from day 1 evening") -- both extremely natural
real-user phrasings this harness's templates never generated, and both hid
real bugs (wrong-stop swaps; a slot-blind remove) that only real,
naturalistic browser testing surfaced. See
Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md's Addendum 4/7 discussion of
why the original harness missed these.
"""

THEMES = ["food", "history", "culture", "nature", "art", "shopping", "architecture", "family", "religion"]
DAY_SLOTS = ("morning", "afternoon", "evening")

# Real, dataset-backed landmark names (distinct from the KNOWN_ABSENT_POPULAR_PLACES
# traps) used for the new "add a real named place" probe.
REAL_NAMED_PLACES = ["Lodhi Garden", "Humayun's Tomb", "India Gate", "Qutab Minar", "Red Fort"]


def _all_stops(itinerary: dict) -> list[dict]:
    stops = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        day_num = int(key.split("_")[1])
        for slot in DAY_SLOTS:
            for stop in itinerary[key].get(slot, []):
                stops.append({"day": day_num, "slot": slot, "name": stop["name"], "category": stop.get("category", "")})
    return stops


def generate_edit_commands(itinerary: dict, spec: dict) -> list[dict]:
    """Returns a list of 20 dicts: {n, command, category, probe, expected}."""
    days = spec["days"]
    interests = spec["interests"]
    absent_themes = [t for t in THEMES if t not in interests] or ["art"]
    stops = _all_stops(itinerary)

    last_day = days
    mid_day = 2 if days >= 2 else 1
    removable = next((s for s in stops if s["day"] != 1), stops[0] if stops else None)
    real_place = next((p for p in REAL_NAMED_PLACES if p not in [s["name"] for s in stops]), REAL_NAMED_PLACES[0])

    # Post-round broadening: distinct picks from `removable`/`real_place`
    # above so the three new probes don't collide with existing ones.
    stop_names = [s["name"] for s in stops]
    named_swap_target = next((s for s in stops if s is not removable), stops[0] if stops else None)
    named_swap_new_place = next(
        (p for p in REAL_NAMED_PLACES if p != real_place and p not in stop_names), REAL_NAMED_PLACES[-1]
    )
    category_ref_stop = stops[-1] if stops else None
    category_slot_stop = next((s for s in stops if s is not named_swap_target and s is not removable), category_ref_stop)

    cmds = []

    # -- Pacing (4) --
    cmds.append({"command": "Make Day 1 more relaxed.", "category": "pacing", "probe": "relax_vague_quantity",
                 "expected": {"edit_type": "relax", "target_day": 1, "target_slot": "all"}})
    cmds.append({"command": f"Day {last_day} feels too packed — take one thing out of the evening.",
                 "category": "pacing", "probe": "relax_specific_slot",
                 "expected": {"edit_type": "relax", "target_day": last_day, "target_slot": "evening"}})
    cmds.append({"command": f"Day {mid_day} is a lot — can you lighten it up somehow?",
                 "category": "pacing", "probe": "relax_vague_phrasing",
                 "expected": {"edit_type": "relax", "target_day": mid_day, "target_slot": "all"}})
    cmds.append({"command": "Make the whole trip more relaxed, please.",
                 "category": "pacing", "probe": "relax_whole_trip",
                 "expected": {"edit_type": "relax", "target_day": "all", "target_slot": "all",
                              "note": "Whole-trip relax (distinct from per-day) -- every day should end up lighter, not just day 1."}})

    # -- Swap (4) --
    cmds.append({"command": "Swap the Day 1 evening plan to something indoors.",
                 "category": "swap", "probe": "swap_indoor",
                 "expected": {"edit_type": "swap", "target_day": 1, "target_slot": "evening", "constraint": "indoor"}})
    cmds.append({"command": f"Swap the Day {last_day} morning plan to something outdoors.",
                 "category": "swap", "probe": "swap_outdoor",
                 "expected": {"edit_type": "swap", "target_day": last_day, "target_slot": "morning", "constraint": "outdoor"}})
    cmds.append({"command": f"Swap Day {mid_day} afternoon for a {absent_themes[0]} spot instead.",
                 "category": "swap", "probe": "swap_theme_category",
                 "expected": {"edit_type": "swap", "target_day": mid_day, "target_slot": "afternoon", "constraint": absent_themes[0]}})
    cmds.append({"command": f"Swap the Day {mid_day} morning stop for something free of charge.",
                 "category": "swap", "probe": "swap_free_of_charge",
                 "expected": {"edit_type": "swap", "target_day": mid_day, "target_slot": "morning", "constraint": "free",
                              "note": "No dataset field tracks a 'free' filter directly -- tests whether the app honestly declines/falls back sensibly rather than silently ignoring the cost constraint."}})

    # -- Add (4) --
    cmds.append({"command": "Add one famous local food place to Day 1.",
                 "category": "add", "probe": "add_food_famous",
                 "expected": {"edit_type": "add", "target_day": 1, "target_slot": "evening", "constraint": "food"}})
    cmds.append({"command": f"Add a {absent_themes[-1]} stop somewhere in the trip.",
                 "category": "add", "probe": "add_theme_any_day",
                 "expected": {"edit_type": "add", "target_day": "all", "target_slot": "evening", "constraint": absent_themes[-1]}})
    cmds.append({"command": f"Add {real_place} to Day {mid_day}.",
                 "category": "add", "probe": "add_real_named_place",
                 "expected": {"edit_type": "add", "target_day": mid_day, "constraint": real_place,
                              "note": f"{real_place} is a REAL dataset landmark not currently on this itinerary -- app should be able to add it (or give a grounded reason it can't, e.g. day full), not hallucinate/decline dishonestly."}})
    cmds.append({"command": "Replace the Day 1 evening stop with Connaught Place.",
                 "category": "swap", "probe": "swap_known_absent_place",
                 "expected": {"edit_type": "swap", "target_day": 1, "target_slot": "evening", "constraint": "Connaught Place",
                              "note": "Connaught Place is a documented KNOWN_ABSENT_POPULAR_PLACES entry -- app should honestly decline, not silently substitute."}})

    # -- Remove (2) --
    if removable:
        cmds.append({"command": f"Remove {removable['name']} from Day {removable['day']}.",
                     "category": "remove", "probe": "remove_real_named_stop",
                     "expected": {"edit_type": "remove", "target_day": removable["day"], "constraint": removable["name"]}})
    else:
        cmds.append({"command": "Remove the museum stop from Day 1.",
                     "category": "remove", "probe": "remove_real_named_stop_fallback",
                     "expected": {"edit_type": "remove", "target_day": 1, "constraint": "museum"}})
    cmds.append({"command": "Remove the boring stop from Day 1.",
                 "category": "remove", "probe": "remove_vague_no_referent",
                 "expected": {"edit_type": "remove or relax (ambiguous)", "target_day": 1,
                              "note": "'boring' names nothing searchable -- correct behavior is an honest 'couldn't find a match', not a hallucinated removal."}})

    # -- Logistics / structural (3) --
    cmds.append({"command": "Reduce travel time between stops.",
                 "category": "logistics", "probe": "reduce_travel_whole_trip",
                 "expected": {"edit_type": "reduce_travel", "target_day": "all"}})
    cmds.append({"command": "Add Select Citywalk mall to Day 1.",
                 "category": "add", "probe": "add_known_absent_place",
                 "expected": {"edit_type": "add", "target_day": 1, "constraint": "Select Citywalk",
                              "note": "Select Citywalk is a documented KNOWN_ABSENT_POPULAR_PLACES entry -- app should honestly decline."}})
    cmds.append({"command": "Swap the order of Day 1's morning and afternoon plans.",
                 "category": "reorder", "probe": "reorder_slots_same_day",
                 "expected": {"edit_type": "unsupported or reorder", "target_day": 1,
                              "note": "No reorder-within-day capability is documented in the edit engine -- correct behavior is an honest 'can't do that yet', not a silent no-op presented as success or a corrupted schedule."}})

    # -- Edge cases (3) --
    cmds.append({"command": f"Make Day {last_day + 2} more relaxed.",
                 "category": "edge_case", "probe": "invalid_day_reference",
                 "expected": {"edit_type": "relax", "target_day": last_day + 2,
                              "note": f"Day {last_day + 2} does not exist in a {days}-day trip -- app should reject cleanly, not crash or silently no-op without explanation."}})
    cmds.append({"command": "Make the whole trip more fun.",
                 "category": "edge_case", "probe": "vague_no_actionable_edit_type",
                 "expected": {"edit_type": "ambiguous", "target_day": "all",
                              "note": "No day/slot/edit-type signal at all -- tests whether the classifier defaults sensibly or misfires."}})
    cmds.append({"command": "asldkjf change something idk maybe swap a thing??",
                 "category": "edge_case", "probe": "gibberish_low_signal_input",
                 "expected": {"edit_type": "unclear", "target_day": "unknown",
                              "note": "Near-gibberish, low-signal phrasing -- app should not crash and should either ask for clarification or make a conservative, clearly-labeled guess rather than silently mutating the itinerary with no explanation."}})

    # -- Post-round broadening: named-stop / category-reference phrasing (3) --
    # Real repro (2026-07-25): "Swap Humayun's Tomb for Qutab Minar" replaced
    # two UNRELATED stops instead of the one actually named, because no
    # probe here had ever tested naming both the old AND new stop together.
    if named_swap_target and named_swap_new_place:
        cmds.append({
            "command": f"Swap {named_swap_target['name']} for {named_swap_new_place}.",
            "category": "swap", "probe": "swap_named_stop_for_named_place",
            "expected": {"edit_type": "swap", "target_stop_name": named_swap_target["name"],
                         "constraint": named_swap_new_place,
                         "note": f"Names BOTH the existing stop to replace ({named_swap_target['name']}) and the "
                                 f"specific new place ({named_swap_new_place}) in one sentence -- the app must "
                                 "resolve target_stop_name to its real day/slot and touch ONLY that stop, not "
                                 "default to a day/slot-position guess that could hit unrelated stops."}
        })

    # Real repro: "Instead of the market on day 2, can we do something
    # different?" swapped THREE unrelated stops across the whole day,
    # because "the market" (a category reference to an existing stop, not
    # its proper name) resolved to nothing and fell back to broad
    # day/slot="all" targeting instead of the one actual market stop.
    if category_ref_stop:
        cmds.append({
            "command": f"Instead of the {category_ref_stop['category']} on Day {category_ref_stop['day']}, "
                       "can we do something different?",
            "category": "swap", "probe": "swap_category_reference",
            "expected": {"edit_type": "swap", "target_day": category_ref_stop["day"],
                         "target_stop_name": f"the {category_ref_stop['category']}",
                         "note": f"'The {category_ref_stop['category']}' names an existing stop by CATEGORY, not "
                                 "proper name -- should resolve to that one specific stop (if it's the only one of "
                                 "that category that day), not cascade into unrelated stops."}
        })

    # Real repro: "Remove the restaurant from day 1 evening" ignored
    # "evening" entirely (target_slot was never even passed to the remove
    # handler), sometimes removed a DIFFERENT same-category stop from
    # another slot, and the resulting scope-drift correctly triggered a
    # rollback -- so a well-specified request silently did nothing.
    if category_slot_stop:
        cmds.append({
            "command": f"Remove the {category_slot_stop['category']} from Day {category_slot_stop['day']} "
                       f"{category_slot_stop['slot']}.",
            "category": "remove", "probe": "remove_category_slot_reference",
            "expected": {"edit_type": "remove", "target_day": category_slot_stop["day"],
                         "target_slot": category_slot_stop["slot"], "constraint": category_slot_stop["category"],
                         "note": "Category + day + SLOT reference -- must remove only a stop actually in that "
                                 "slot, never a same-category stop from a different slot on the same day."}
        })

    assert len(cmds) >= 20
    for i, c in enumerate(cmds, start=1):
        c["n"] = i
    return cmds
