"""
Team Waypoint -- Itinerary edit commands QA (Phase 1)

Defines the 20 itinerary specs Agent 2 builds. Mix of single-interest and
multi-interest trips, 2-day and 3-day, across food/history/culture/nature/
art/shopping/architecture/family/religion.
"""

CITY = "New Delhi"

# Each spec: id, label, interests (as passed to poi_search_logic / used to
# pick INTEREST_MAP keys), days, pace.
ITINERARY_SPECS = [
    # -- Single-interest (5) --
    {"id": 1,  "label": "Food-only city crawl",              "interests": ["food"],                                   "days": 2, "pace": "moderate"},
    {"id": 2,  "label": "History-only deep dive",             "interests": ["history"],                                "days": 3, "pace": "moderate"},
    {"id": 3,  "label": "Nature-only escape",                 "interests": ["nature"],                                 "days": 2, "pace": "relaxed"},
    {"id": 4,  "label": "Shopping-only spree",                "interests": ["shopping"],                               "days": 2, "pace": "moderate"},
    {"id": 5,  "label": "Religion-only pilgrimage",            "interests": ["religion"],                               "days": 3, "pace": "moderate"},

    # -- Multi-interest combos (15) --
    {"id": 6,  "label": "History + Food",                      "interests": ["history", "food"],                        "days": 2, "pace": "moderate"},
    {"id": 7,  "label": "Culture + Art",                        "interests": ["culture", "art"],                         "days": 3, "pace": "moderate"},
    {"id": 8,  "label": "Architecture + History + Shopping",    "interests": ["architecture", "history", "shopping"],    "days": 2, "pace": "intensive"},
    {"id": 9,  "label": "Family + Nature",                      "interests": ["family", "nature"],                       "days": 2, "pace": "relaxed"},
    {"id": 10, "label": "Food + Shopping + Culture",            "interests": ["food", "shopping", "culture"],            "days": 3, "pace": "moderate"},
    {"id": 11, "label": "Religion + History",                   "interests": ["religion", "history"],                    "days": 2, "pace": "moderate"},
    {"id": 12, "label": "Art + Culture + Food",                 "interests": ["art", "culture", "food"],                 "days": 3, "pace": "moderate"},
    {"id": 13, "label": "Nature + Family + Shopping",           "interests": ["nature", "family", "shopping"],           "days": 2, "pace": "relaxed"},
    {"id": 14, "label": "Architecture + Religion",              "interests": ["architecture", "religion"],               "days": 3, "pace": "moderate"},
    {"id": 15, "label": "History + Culture + Architecture + Food", "interests": ["history", "culture", "architecture", "food"], "days": 3, "pace": "intensive"},
    {"id": 16, "label": "Shopping + Food",                      "interests": ["shopping", "food"],                       "days": 2, "pace": "moderate"},
    {"id": 17, "label": "Family + Culture + History",           "interests": ["family", "culture", "history"],           "days": 3, "pace": "moderate"},
    {"id": 18, "label": "Nature + Art",                         "interests": ["nature", "art"],                          "days": 2, "pace": "relaxed"},
    {"id": 19, "label": "Religion + Architecture + Culture",    "interests": ["religion", "architecture", "culture"],    "days": 2, "pace": "moderate"},
    {"id": 20, "label": "Food + History + Nature + Shopping",   "interests": ["food", "history", "nature", "shopping"],  "days": 3, "pace": "moderate"},
]

assert len(ITINERARY_SPECS) == 20
assert sum(1 for s in ITINERARY_SPECS if len(s["interests"]) == 1) == 5
assert sum(1 for s in ITINERARY_SPECS if s["days"] == 2) + sum(1 for s in ITINERARY_SPECS if s["days"] == 3) == 20
