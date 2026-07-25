"""
Team Waypoint -- 30 Random Itineraries QA (cuisine + category coverage round).

Agent 2's new job for this round: 30 fresh conversational requests, each
stating a specific real-world cuisine preference (rotated across 12 cuisines
genuinely present in phase1/data/pois.json's real `tags.cuisine` OSM data --
never a cuisine invented for the test) plus 1-2 category interests, phrased
the way a real traveller would say it, not as clean category keywords.
"""

# Real cuisines confirmed present in phase1/data/pois.json's restaurant
# tags.cuisine field (checked directly against the live dataset before
# picking these -- not guessed). Counts as of this QA round: indian=111,
# south_indian=16 (incl. combos), north_indian=10 (incl. combos), chinese=19,
# italian=9, japanese=8, korean=8, bengali=5, thai=5, mexican=3, punjabi=4,
# mughlai=2, continental=2 (deliberately included despite being the
# thinnest-represented real cuisine in the dataset -- a real adversarial
# "can the app be honest when it genuinely can't satisfy this well" case).
CUISINES = [
    "North Indian", "South Indian", "Thai", "Continental", "Chinese",
    "Italian", "Mexican", "Japanese", "Korean", "Bengali", "Punjabi", "Mughlai",
]

CATEGORY_INTERESTS = [
    "history", "culture", "nature", "art", "shopping",
    "architecture", "family", "religion",
]

# (days, pace) combinations cycled across the 30 specs for real variety.
DAY_PACE = [
    (2, "relaxed"), (2, "moderate"), (2, "intensive"),
    (3, "relaxed"), (3, "moderate"), (3, "intensive"),
    (4, "moderate"),
]

# Natural phrasing templates a real traveller might actually use -- varied
# on purpose (not all "I love X food") so extraction is tested against real
# phrasing diversity, not one convenient sentence shape.
CUISINE_PHRASES = [
    "I love {cuisine} food",
    "I'm really craving {cuisine} food on this trip",
    "I'd love to try some {cuisine} cuisine",
    "I'm a big fan of {cuisine} food",
    "{cuisine} food is my favorite, I want to eat a lot of it",
]


def build_specs() -> list[dict]:
    specs = []
    for i in range(30):
        cuisine = CUISINES[i % len(CUISINES)]
        phrase_template = CUISINE_PHRASES[i % len(CUISINE_PHRASES)]
        cuisine_phrase = phrase_template.format(cuisine=cuisine)
        days, pace = DAY_PACE[i % len(DAY_PACE)]
        # 1-2 category interests per spec, rotating so all 8 themes appear
        # roughly evenly across the 30 itineraries.
        cat1 = CATEGORY_INTERESTS[i % len(CATEGORY_INTERESTS)]
        cat2 = CATEGORY_INTERESTS[(i + 3) % len(CATEGORY_INTERESTS)]
        cats = [cat1] if i % 3 == 0 else [cat1, cat2]

        opening = (
            f"I'm planning a {days}-day trip to Delhi, {pace} pace. "
            f"{cuisine_phrase}. I'm also interested in {' and '.join(cats)}."
        )
        specs.append({
            "id": i + 1,
            "days": days,
            "pace": pace,
            "cuisine": cuisine,
            "cuisine_phrase": cuisine_phrase,
            "category_interests": cats,
            "opening_message": opening,
        })
    return specs


ITINERARY_SPECS = build_specs()

if __name__ == "__main__":
    for s in ITINERARY_SPECS:
        print(s["id"], s["opening_message"])
