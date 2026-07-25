"""
Team Waypoint -- Itinerary edit commands QA (Phase 2)
Agent 3 (Question Command Agent): generates 15 question commands per
itinerary, tailored to that itinerary's actual days/stops/KB data -- covering
Justification, Contingency, Alternatives, Expansion, Practicalities, and
Suitability, per the Phase 2 spec.
"""

DAY_SLOTS = ("morning", "afternoon", "evening")


def _all_stops(itinerary: dict) -> list[dict]:
    stops = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        day_num = int(key.split("_")[1])
        for slot in DAY_SLOTS:
            for stop in itinerary[key].get(slot, []):
                stops.append({"day": day_num, "slot": slot, **stop})
    return stops


def _pick(stops: list[dict], idx: int) -> dict:
    """Cyclic pick so short itineraries (few stops) still get variety."""
    return stops[idx % len(stops)]


def generate_question_commands(itinerary: dict, spec: dict) -> list[dict]:
    """Returns a list of 15 dicts: {n, command, category, probe, target_stop, expected}."""
    days = spec["days"]
    stops = _all_stops(itinerary)
    last_day = days
    mid_day = 2 if days >= 2 else 1

    # Prefer stops that carry real KB data for practicality/suitability
    # questions, so the app has an actual fact to be checked against.
    kb_fee_stops = [s for s in stops if s.get("kb_entry_fee")]
    kb_time_stops = [s for s in stops if s.get("kb_best_time_to_visit")]
    kb_suit_stops = [s for s in stops if s.get("kb_suitable_for")]

    s0, s1, s2 = _pick(stops, 0), _pick(stops, 1), _pick(stops, 2)
    fee_stop = kb_fee_stops[0] if kb_fee_stops else _pick(stops, 3)
    time_stop = kb_time_stops[0] if kb_time_stops else _pick(stops, 4)
    suit_stop = kb_suit_stops[0] if kb_suit_stops else _pick(stops, 5)
    alt_stop = _pick(stops, 6)
    alt_stop2 = _pick(stops, 7)
    travel_a, travel_b = _pick(stops, 8), _pick(stops, 9)

    cmds = []

    # -- Justification (3) --
    cmds.append({
        "command": f"Why did you pick {s0['name']} for Day {s0['day']}?",
        "category": "justification", "probe": "why_named_stop",
        "target_stop": s0["name"],
        "expected": {"note": "Should reference the actual scheduled stop, grounded in real source data or an honest no-source admission -- not a generic answer about 'this area'."},
    })
    cmds.append({
        "command": f"Why is {s1['name']} scheduled in the {s1['slot']} instead of another time of day?",
        "category": "justification", "probe": "why_slot_timing",
        "target_stop": s1["name"],
        "expected": {"note": "Tests whether the app can justify slot placement, or honestly says it doesn't have a specific reason for the exact slot."},
    })
    cmds.append({
        "command": "Why did you pick this place?",
        "category": "justification", "probe": "why_vague_referent",
        "target_stop": None,
        "expected": {"note": "No place named ('this place') -- correct behavior is to ask which place, not guess and hallucinate a generic answer (R-18/F-13 fix from earlier work)."},
    })

    # -- Contingency (2) --
    cmds.append({
        "command": "What if it rains on Day 1?",
        "category": "contingency", "probe": "weather_rain",
        "target_stop": None,
        "expected": {"note": "Should surface indoor-alternative / weather guidance grounded in real source data."},
    })
    cmds.append({
        "command": f"What happens to my plan if {s2['name']} is closed for a public holiday?",
        "category": "contingency", "probe": "closure_holiday",
        "target_stop": s2["name"],
        "expected": {"note": "No dataset field encodes holiday closures -- correct behavior is an honest no-verified-source answer, not a fabricated closure schedule."},
    })

    # -- Alternatives (2) --
    cmds.append({
        "command": f"What are some alternatives to {alt_stop['name']} on Day {alt_stop['day']}?",
        "category": "alternatives", "probe": "alt_for_named_stop",
        "target_stop": alt_stop["name"],
        "expected": {"note": "Any alternative places named in the answer should be real (checkable against the POI dataset), not invented."},
    })
    cmds.append({
        "command": f"If {alt_stop2['name']} turns out to be too crowded, what else could I do instead?",
        "category": "alternatives", "probe": "alt_crowds",
        "target_stop": alt_stop2["name"],
        "expected": {"note": "Crowd-avoidance framing of the same alternatives probe -- checks the app doesn't just pattern-match the word 'alternative'."},
    })

    # -- Expansion (2) --
    cmds.append({
        "command": f"What other activities can I do on Day {mid_day} if I have extra time?",
        "category": "expansion", "probe": "expand_day",
        "target_stop": None,
        "expected": {"note": "Should suggest real, groundable options -- not vague filler."},
    })
    cmds.append({
        "command": f"Is there anything interesting near {s0['name']} that isn't on the itinerary?",
        "category": "expansion", "probe": "expand_near_stop",
        "target_stop": s0["name"],
        "expected": {"note": "Tests location-aware expansion; the dataset has no real geo-proximity RAG lookup, so an honest no-source answer is acceptable -- a fabricated nearby landmark is not."},
    })

    # -- Practicalities (3) --
    cmds.append({
        "command": f"How much does it cost to visit {fee_stop['name']}?",
        "category": "practicalities", "probe": "cost_named_stop",
        "target_stop": fee_stop["name"],
        "expected": {"note": "Checkable fact when the stop carries kb_entry_fee" + (f" (dataset says: {fee_stop.get('kb_entry_fee')!r})" if fee_stop.get("kb_entry_fee") else " (no KB fee on this stop -- honest no-source expected)"),
                     "kb_entry_fee": fee_stop.get("kb_entry_fee")},
    })
    cmds.append({
        "command": f"What's the best time of day to visit {time_stop['name']}?",
        "category": "practicalities", "probe": "best_time_named_stop",
        "target_stop": time_stop["name"],
        "expected": {"note": "Checkable fact when the stop carries kb_best_time_to_visit" + (f" (dataset says: {time_stop.get('kb_best_time_to_visit')!r})" if time_stop.get("kb_best_time_to_visit") else " (no KB field -- honest no-source expected)"),
                     "kb_best_time_to_visit": time_stop.get("kb_best_time_to_visit")},
    })
    cmds.append({
        "command": f"How do I get from {travel_a['name']} to {travel_b['name']}?",
        "category": "practicalities", "probe": "travel_between_stops",
        "target_stop": f"{travel_a['name']} -> {travel_b['name']}",
        "expected": {"note": "Itinerary already computes travel_mode_from_prev/travel_time_from_prev_min between consecutive stops -- answer should be consistent with that data when the two stops are adjacent.",
                     "travel_mode_from_prev": travel_b.get("travel_mode_from_prev"),
                     "travel_time_from_prev_min": travel_b.get("travel_time_from_prev_min"),
                     "adjacent": (travel_a["day"] == travel_b["day"] and travel_a["slot"] == travel_b["slot"])},
    })

    # -- Suitability (2) --
    cmds.append({
        "command": f"Is {suit_stop['name']} suitable for elderly travellers?",
        "category": "suitability", "probe": "suitability_elderly",
        "target_stop": suit_stop["name"],
        "expected": {"note": "Checkable when the stop carries kb_suitable_for" + (f" (dataset says: {suit_stop.get('kb_suitable_for')!r})" if suit_stop.get("kb_suitable_for") else " (no KB field -- honest no-source expected)"),
                     "kb_suitable_for": suit_stop.get("kb_suitable_for")},
    })
    cmds.append({
        "command": "Is this itinerary suitable for a family with young kids?",
        "category": "suitability", "probe": "suitability_family_whole_trip",
        "target_stop": None,
        "expected": {"note": "Whole-trip suitability question, no single named place -- tests whether the app can reason across the itinerary or honestly declines rather than answering about one arbitrary stop."},
    })

    # -- Edge case: unanswerable-with-current-data trap, on a REAL stop (1) --
    # Every question in this set must reference a venue that is actually on
    # the itinerary. This still probes for hallucination -- just via a
    # question the app has no data to answer (no hotel/lodging location is
    # tracked anywhere in the app), rather than by asking about a venue that
    # was never scheduled.
    edge_stop = _pick(stops, 10)
    cmds.append({
        "command": f"Is {edge_stop['name']} within walking distance of my hotel?",
        "category": "edge_case", "probe": "unanswerable_missing_context",
        "target_stop": edge_stop["name"],
        "expected": {"note": "No hotel/lodging location is tracked anywhere in the app -- correct behavior is an honest 'I don't know where you're staying' answer, not a fabricated walking distance or an invented hotel location."},
    })

    assert len(cmds) == 15
    for i, c in enumerate(cmds, start=1):
        c["n"] = i
    return cmds
