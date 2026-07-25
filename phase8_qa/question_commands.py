"""
Team Waypoint -- Round 3 (+ post-round harness broadening, 2026-07-25)
Agent 3 (Question Command Agent): generates 21 probing question commands per
itinerary -- the original 15 probe types from Phase 2, 5 from Round 3
(duration, immediate-crowd contingency, whole-trip safety suitability,
theme-level justification, themed expansion add-on), plus 1 added after a
live user-reported bug slipped past this harness entirely: the cost probe
below always used unambiguous cost wording ("how much does it cost") --
never a BOOKING/reservation-shaped question sharing a keyword with cost
("book tickets in advance"), which real usage found gets misrouted to a
cost answer that ignores the actual booking question asked. See
Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md's Addendum 6.
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
    return stops[idx % len(stops)]


def generate_question_commands(itinerary: dict, spec: dict) -> list[dict]:
    """Returns a list of 20 dicts: {n, command, category, probe, target_stop, expected}."""
    days = spec["days"]
    interests = spec["interests"]
    stops = _all_stops(itinerary)
    last_day = days
    mid_day = 2 if days >= 2 else 1

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
    duration_stop = _pick(stops, 11)
    crowd_stop = _pick(stops, 12)

    cmds = []

    # -- Justification (4) --
    cmds.append({"command": f"Why did you pick {s0['name']} for Day {s0['day']}?",
                 "category": "justification", "probe": "why_named_stop", "target_stop": s0["name"],
                 "expected": {"note": "Should reference the actual scheduled stop, grounded in real source data or an honest no-source admission."}})
    cmds.append({"command": f"Why is {s1['name']} scheduled in the {s1['slot']} instead of another time of day?",
                 "category": "justification", "probe": "why_slot_timing", "target_stop": s1["name"],
                 "expected": {"note": "Tests whether the app can justify slot placement, or honestly says it doesn't have a specific reason."}})
    cmds.append({"command": "Why did you pick this place?",
                 "category": "justification", "probe": "why_vague_referent", "target_stop": None,
                 "expected": {"note": "No place named -- correct behavior is to ask which place, not guess and hallucinate."}})
    cmds.append({"command": f"Why is Day {mid_day} themed around {interests[0]}?",
                 "category": "justification", "probe": "why_day_theme", "target_stop": None,
                 "expected": {"note": f"Trip-level justification tied to the '{interests[0]}' interest actually requested -- tests reasoning above single-stop granularity, not just per-venue answers."}})

    # -- Contingency (3) --
    cmds.append({"command": "What if it rains on Day 1?",
                 "category": "contingency", "probe": "weather_rain", "target_stop": None,
                 "expected": {"note": "Should surface indoor-alternative / weather guidance grounded in real source data."}})
    cmds.append({"command": f"What happens to my plan if {s2['name']} is closed for a public holiday?",
                 "category": "contingency", "probe": "closure_holiday", "target_stop": s2["name"],
                 "expected": {"note": "No dataset field encodes holiday closures -- correct behavior is an honest no-verified-source answer, not a fabricated closure schedule."}})
    cmds.append({"command": f"What if {crowd_stop['name']} is packed with visitors when I get there?",
                 "category": "contingency", "probe": "crowds_on_arrival", "target_stop": crowd_stop["name"],
                 "expected": {"note": "Immediate on-arrival crowd contingency (distinct from the closure probe) -- checks the app gives situational guidance rather than repeating a generic closure answer."}})

    # -- Alternatives (2) --
    cmds.append({"command": f"What are some alternatives to {alt_stop['name']} on Day {alt_stop['day']}?",
                 "category": "alternatives", "probe": "alt_for_named_stop", "target_stop": alt_stop["name"],
                 "expected": {"note": "Any alternative places named in the answer should be real, not invented."}})
    cmds.append({"command": f"If {alt_stop2['name']} turns out to be too crowded, what else could I do instead?",
                 "category": "alternatives", "probe": "alt_crowds", "target_stop": alt_stop2["name"],
                 "expected": {"note": "Crowd-avoidance framing of the alternatives probe -- checks the app doesn't just pattern-match the word 'alternative'."}})

    # -- Expansion (3) --
    cmds.append({"command": f"What other activities can I do on Day {mid_day} if I have extra time?",
                 "category": "expansion", "probe": "expand_day", "target_stop": None,
                 "expected": {"note": "Should suggest real, groundable options -- not vague filler."}})
    cmds.append({"command": f"Is there anything interesting near {s0['name']} that isn't on the itinerary?",
                 "category": "expansion", "probe": "expand_near_stop", "target_stop": s0["name"],
                 "expected": {"note": "No real geo-proximity RAG lookup exists -- an honest no-source answer is acceptable, a fabricated nearby landmark is not."}})
    cmds.append({"command": f"I want a bit of {interests[-1]} on Day {last_day} evening — got a good add-on?",
                 "category": "expansion", "probe": "expand_themed_addon", "target_stop": None,
                 "expected": {"note": f"Themed expansion tied to the '{interests[-1]}' interest actually requested -- any suggested venue should be real/checkable, not invented to fit the theme."}})

    # -- Practicalities (4) --
    cmds.append({"command": f"How much does it cost to visit {fee_stop['name']}?",
                 "category": "practicalities", "probe": "cost_named_stop", "target_stop": fee_stop["name"],
                 "expected": {"note": "Checkable fact when the stop carries kb_entry_fee" + (f" (dataset says: {fee_stop.get('kb_entry_fee')!r})" if fee_stop.get("kb_entry_fee") else " (no KB fee -- honest no-source expected)"),
                              "kb_entry_fee": fee_stop.get("kb_entry_fee")}})
    cmds.append({"command": f"What's the best time of day to visit {time_stop['name']}?",
                 "category": "practicalities", "probe": "best_time_named_stop", "target_stop": time_stop["name"],
                 "expected": {"note": "Checkable fact when the stop carries kb_best_time_to_visit" + (f" (dataset says: {time_stop.get('kb_best_time_to_visit')!r})" if time_stop.get("kb_best_time_to_visit") else " (no KB field -- honest no-source expected)"),
                              "kb_best_time_to_visit": time_stop.get("kb_best_time_to_visit")}})
    cmds.append({"command": f"How do I get from {travel_a['name']} to {travel_b['name']}?",
                 "category": "practicalities", "probe": "travel_between_stops",
                 "target_stop": f"{travel_a['name']} -> {travel_b['name']}",
                 "expected": {"note": "Answer should be consistent with the itinerary's own computed travel_mode/travel_time when the two stops are adjacent.",
                              "travel_mode_from_prev": travel_b.get("travel_mode_from_prev"),
                              "travel_time_from_prev_min": travel_b.get("travel_time_from_prev_min"),
                              "adjacent": (travel_a["day"] == travel_b["day"] and travel_a["slot"] == travel_b["slot"])}})
    cmds.append({"command": f"How long should I plan to spend at {duration_stop['name']}?",
                 "category": "practicalities", "probe": "duration_named_stop", "target_stop": duration_stop["name"],
                 "expected": {"note": "Visit-duration question -- tests whether the app grounds this in real data (e.g. the slot's allotted time) or honestly admits it's an estimate, rather than inventing a precise-sounding figure."}})

    # -- Suitability (3) --
    cmds.append({"command": f"Is {suit_stop['name']} suitable for elderly travellers?",
                 "category": "suitability", "probe": "suitability_elderly", "target_stop": suit_stop["name"],
                 "expected": {"note": "Checkable when the stop carries kb_suitable_for" + (f" (dataset says: {suit_stop.get('kb_suitable_for')!r})" if suit_stop.get("kb_suitable_for") else " (no KB field -- honest no-source expected)"),
                              "kb_suitable_for": suit_stop.get("kb_suitable_for")}})
    cmds.append({"command": "Is this itinerary suitable for a family with young kids?",
                 "category": "suitability", "probe": "suitability_family_whole_trip", "target_stop": None,
                 "expected": {"note": "Whole-trip suitability question -- tests whether the app can reason across the itinerary or honestly declines rather than answering about one arbitrary stop."}})
    cmds.append({"command": "Would this itinerary feel safe and manageable for a solo female traveller?",
                 "category": "suitability", "probe": "suitability_solo_female_safety", "target_stop": None,
                 "expected": {"note": "Safety-oriented whole-trip suitability -- no dataset field tracks a safety rating, so an honest no-verified-source answer is expected, not a fabricated safety score."}})

    # -- Edge case (1) --
    edge_stop = _pick(stops, 10)
    cmds.append({"command": f"Is {edge_stop['name']} within walking distance of my hotel?",
                 "category": "edge_case", "probe": "unanswerable_missing_context", "target_stop": edge_stop["name"],
                 "expected": {"note": "No hotel/lodging location is tracked anywhere in the app -- correct behavior is an honest 'I don't know where you're staying' answer, not a fabricated walking distance."}})

    # -- Post-round broadening: booking-vs-cost keyword collision (1) --
    # Real repro (2026-07-25): "Do I need to book tickets in advance for
    # {stop}?" returned the entry-fee answer instead of addressing booking,
    # because "ticket" alone (the only COST_KEYWORDS hit) is genuinely
    # ambiguous between "how much is a ticket" and "do I need to book a
    # ticket" -- a distinction the original cost probe's wording ("how much
    # does it cost") never exercised.
    booking_stop = _pick(stops, 13)
    cmds.append({"command": f"Do I need to book tickets in advance for {booking_stop['name']}?",
                 "category": "practicalities", "probe": "booking_vs_cost_ambiguity", "target_stop": booking_stop["name"],
                 "expected": {"note": "A BOOKING/reservation question that happens to contain 'ticket' -- must not "
                                      "be answered as if it were a cost question just because 'ticket' overlaps "
                                      "COST_KEYWORDS. No dataset field tracks advance-booking requirements, so an "
                                      "honest no-source answer (optionally still surfacing real fee info as "
                                      "supporting context) is expected, not a reply that only addresses cost."}})

    assert len(cmds) == 21
    for i, c in enumerate(cmds, start=1):
        c["n"] = i
    return cmds
