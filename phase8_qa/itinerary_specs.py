"""
Team Waypoint -- Comprehensive QA + UX/UI Benchmark (Round 3)

Agent 1 (Itinerary Generator): builds 20 FRESH random itinerary specs,
independent of the Phase 1/Phase 2 batch (per this round's explicit brief --
"Agent1: Create 20 random itineraries"). Unlike Phase 1's hand-curated
combos, these are drawn with Python's random module (fixed seed for
reproducibility) over the same 9 real INTEREST_MAP themes the app supports.
"""

import random

CITY = "New Delhi"

THEMES = ["food", "history", "culture", "nature", "art", "shopping", "architecture", "family", "religion"]
DAY_CHOICES = [2, 3]
PACE_CHOICES = ["relaxed", "moderate", "intensive"]

_rng = random.Random(88)  # fixed seed: reproducible "random" batch, distinct from Phase 1's curated set

ITINERARY_SPECS = []
_seen_signatures = set()
_id = 1
while len(ITINERARY_SPECS) < 20:
    n_interests = _rng.choice([1, 1, 2, 2, 2, 3, 3, 4])  # weighted toward 1-3, occasional 4
    interests = sorted(_rng.sample(THEMES, n_interests))
    days = _rng.choice(DAY_CHOICES)
    pace = _rng.choice(PACE_CHOICES)
    signature = (tuple(interests), days, pace)
    if signature in _seen_signatures:
        continue  # skip exact dupes so the 20 stay distinct
    _seen_signatures.add(signature)
    label = " + ".join(w.capitalize() for w in interests)
    ITINERARY_SPECS.append({
        "id": _id, "label": label, "interests": interests, "days": days, "pace": pace,
    })
    _id += 1

assert len(ITINERARY_SPECS) == 20
