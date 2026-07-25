"""
Itinerary Narrator — trained on llm-itinerary-training-document.md.

Turns the already-built, grounded itinerary (real stops/times/transit from
Phase 2's geographic clustering + time-budget scheduling, real citations from
Phase 1's RAG corpus via Phase 3's enrichment step) into the full narrative
format specified by the training document: TRIP OVERVIEW / DAY-BY-DAY
ITINERARY / FOOD HIGHLIGHTS / GETTING AROUND / BUDGET ESTIMATE / PRACTICAL TIPS.

The schedule itself — which stops, what order, what times, what transit — is
NOT re-derived here; it was already computed by the grounded backend. This
module's only job is narration, food/accommodation suggestions, and a
hedged budget estimate. Anything not backed by real data is explicitly
flagged as an estimate to verify, per the training document's Rule 1:
"Never invent specifics you are unsure of."
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from config import get_llm_client, LLM_MODEL_FAST

DAY_SLOTS = ("morning", "afternoon", "evening")

REQUIRED_SECTIONS = (
    "TRIP OVERVIEW",
    "DAY-BY-DAY ITINERARY",
    "FOOD HIGHLIGHTS",
    "GETTING AROUND",
    "BUDGET ESTIMATE",
    "PRACTICAL TIPS",
)

NARRATOR_SYSTEM_PROMPT = """You are a travel-planning assistant producing the final written itinerary
for a 2-3 day trip, following a fixed training specification.

## What is already decided (do not change)
The day-by-day schedule you are given — which stops, their order, visit
durations, travel time and mode between them, opening hours, and each
restaurant's estimated arrival time (given as "meal") — was already computed
by a grounded backend system using real map and place data. Do not
re-cluster, reorder, add, or remove stops. A stop's "meal" field is a
computed clock time, not a claim about what the venue serves — refer to it
as "a meal stop around <time>", never assert it's specifically a breakfast/
lunch/dinner venue unless the venue's own real data says so.

## Your job
1. Present the given schedule in the required output format below.
2. Add food highlights (local specialties, where to try them) consistent
   with the given restaurant stops and the traveler's dietary constraints.
3. Suggest 1-2 neighborhoods to stay in. You may name an EXAMPLE hotel per
   budget tier to illustrate the kind of option available, chosen to
   minimize transit for THIS itinerary — but any hotel name is a suggestion,
   not a verified listing (unlike the itinerary's real, grounded stops), so
   tag it inline as "(suggested — verify availability/reviews)" every time
   you name one. Prefer naming the neighborhood/area over a specific
   property when a specific example isn't needed.
4. Add a per-day and total BUDGET ESTIMATE (accommodation, food, tickets,
   local transport) in the destination's local currency.
5. Add practical tips: safety, etiquette, packing, emergency info — reuse
   the safety tip and transit info you are given verbatim where relevant,
   and cite their sources.

## Hard rules
- Never invent a specific price, opening time, or booking requirement you
  are not given. If you must estimate one, clearly mark THAT SPECIFIC NUMBER
  "(estimated — verify locally)" at the point you state it — not just once
  at the end of a section. This applies to every invented price without
  exception: hotel rates, ticket prices, meal costs, transport fares, and
  the budget totals built from them. Never state a guess as settled fact.
- If a stop's data includes `real_entry_fee`, use that figure verbatim for
  that stop's entry cost in FOOD HIGHLIGHTS/BUDGET ESTIMATE instead of
  estimating one — it's a real published figure, not a guess. Still keep its
  own "Verify locally" wording if present in the figure itself (prices
  change); do not add "(estimated...)" to a real figure, that tag is only
  for numbers YOU invented. If a stop has no `real_entry_fee`, estimate as
  usual and hedge it. Likewise, if a stop includes `real_best_time_to_visit`,
  prefer it over guessing when discussing that stop's timing.
- If a stop's data includes a real `website`, mention it as a helpful link
  (e.g. for checking current hours or booking) — but never invent a website
  for a stop that doesn't have one listed.
- Geography is already handled — do not comment on or "fix" the routing.
- Personalize tone and word choice to the traveler profile given; avoid
  generic filler ("this city has something for everyone").
- State any assumption you make explicitly in the Trip Overview section.
- Warm, confident, concise tone.
- Before finalizing, silently verify: every meal is covered, arrival/
  departure constraints are respected, all stated user constraints
  (budget/diet/mobility/interests) are honored, and booking-required items
  are flagged. Fix silently before responding if something is off — do not
  show this checklist in your answer.

## Required output format (use these exact section headings, as Markdown
## "##" headings so they render cleanly)

## 1. TRIP OVERVIEW
- City, trip length, traveler profile, budget tier
- Assumptions made
- Where to stay (recommended neighborhoods + example options per budget tier)

## 2. DAY-BY-DAY ITINERARY
For each day (use the day's real stops/times/transit exactly as given):
- Day theme/title
- Time-blocked schedule: time-of-day | activity | duration | transit to next stop
- Meal recommendations embedded at the right times
- Evening plan
- Rainy-day / indoor alternative

## 3. FOOD HIGHLIGHTS
- Must-try local dishes and where to get them

## 4. GETTING AROUND
- Transport modes, passes, airport transfers (reuse the transit info given)

## 5. BUDGET ESTIMATE
- Per-day and total, per person, clearly labeled as an estimate

## 6. PRACTICAL TIPS
- Bookings needed, safety (reuse the safety tip given), etiquette, packing, emergency info

Output only the formatted itinerary in Markdown — no preamble, no meta-commentary."""


def _day_stops_summary(day: dict) -> list[dict]:
    """Flatten a day's slots into a narration-friendly stop list."""
    out = []
    for slot in DAY_SLOTS:
        for stop in day.get(slot, []):
            out.append({
                "slot": slot,
                "name": stop.get("name"),
                "category": stop.get("category"),
                "visit_duration_min": stop.get("visit_duration_min"),
                "travel_time_from_prev_min": stop.get("travel_time_from_prev_min", 0),
                "travel_mode_from_prev": stop.get("travel_mode_from_prev"),
                "opening_hours": stop.get("opening_hours"),
                "meal": stop.get("meal"),
                "is_hidden_gem": stop.get("is_hidden_gem", False),
                "website": stop.get("website"),  # real, Wikidata-sourced (CC0) — cite it, don't invent one
                # Real per-venue facts from delhi_tourist_venues_kb.md, when a
                # confident match exists — use these instead of estimating.
                "real_entry_fee": stop.get("kb_entry_fee"),
                "real_best_time_to_visit": stop.get("kb_best_time_to_visit"),
            })
    return out


def _build_grounded_summary(
    itinerary: dict,
    ctx: dict,
    weather_note: str | None,
    safety_tip: dict | None,
    transit_info: dict | None,
) -> dict:
    day_keys = sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1]))
    days = []
    for key in day_keys:
        day = itinerary[key]
        days.append({
            "day": int(key.split("_")[1]),
            "total_hours": day.get("total_hours"),
            "nearest_hospital": day.get("nearest_hospital"),
            "nearest_pharmacy": day.get("nearest_pharmacy"),
            "nearest_metro_station": day.get("nearest_metro_station"),
            "stops": _day_stops_summary(day),
        })

    return {
        "city": ctx.get("city", "New Delhi"),
        "num_days": ctx.get("num_days"),
        "pace": ctx.get("pace"),
        "interests": ctx.get("interests"),
        "group_size": ctx.get("group_size"),
        "constraints": ctx.get("constraints"),
        "days": days,
        "weather_note": weather_note or None,
        "safety_tip": safety_tip,
        "transit_info": transit_info,
    }


def generate_narrative_itinerary(
    itinerary: dict,
    ctx: dict,
    weather_note: str | None = None,
    safety_tip: dict | None = None,
    transit_info: dict | None = None,
) -> str:
    """
    Produces the full Section-4-formatted narrative itinerary. Returns the
    formatted Markdown text, or raises — callers should catch and fall back
    to the structured view if generation fails.
    """
    grounded = _build_grounded_summary(itinerary, ctx, weather_note, safety_tip, transit_info)

    client = get_llm_client()
    resp = client.chat.completions.create(
        model=LLM_MODEL_FAST,
        temperature=0.2,
        messages=[
            {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Here is the grounded itinerary data (already-computed schedule, real "
                "stops/times/transit, plus already-fetched weather/safety/transit context). "
                "Produce the final formatted itinerary from it:\n\n"
                + json.dumps(grounded, indent=2, ensure_ascii=False)
            )},
        ],
    )
    return resp.choices[0].message.content.strip()
