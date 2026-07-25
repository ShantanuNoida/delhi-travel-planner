"""
Eval 3: Grounding & Hallucination Check.

For every POI in the itinerary, verifies its osm_id exists in the Phase 1
POI dataset. For every explanation/tip shown to the user, verifies each
citation's source_url exists in the Phase 1 citation index — unless the
explanation explicitly admitted it had no verified source, which is the
correct behavior for ungrounded queries, not a failure.
"""

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POIS_PATH = os.path.join(_ROOT, "phase1", "data", "pois.json")
CITATION_INDEX_PATH = os.path.join(_ROOT, "phase1", "data", "citation_index.json")

NO_SOURCE_TEXT = "I don't have a verified source for this — treat it as a general suggestion."

DAY_SLOTS = ("morning", "afternoon", "evening")


def _load_valid_osm_ids() -> set[str]:
    with open(POIS_PATH, encoding="utf-8") as f:
        pois = json.load(f)
    return {str(p["osm_id"]) for p in pois}


def _load_valid_source_urls() -> set[str]:
    with open(CITATION_INDEX_PATH, encoding="utf-8") as f:
        citation_index = json.load(f)
    return {entry["source_url"] for entry in citation_index.values()}


def check_grounding(itinerary: dict, explanations: list[dict] | None = None) -> dict:
    """
    Returns {"pass": bool, "ungrounded_pois": [names], "uncited_tips": [source_titles or answers]}.

    explanations: optional list of {"answer": str, "citations": [...], "grounded": bool}
    dicts, e.g. output of phase4.explain_engine.explain().
    """
    valid_osm_ids = _load_valid_osm_ids()
    valid_source_urls = _load_valid_source_urls()

    ungrounded_pois = []
    for key in (k for k in itinerary if k.startswith("day_")):
        day = itinerary[key]
        for slot in DAY_SLOTS:
            for stop in day.get(slot, []):
                if str(stop.get("osm_id")) not in valid_osm_ids:
                    ungrounded_pois.append(stop.get("name", "?"))

    uncited_tips = []
    for exp in explanations or []:
        answer = exp.get("answer", "")
        citations = exp.get("citations", [])
        # R-22 (Itinerary-Quality-Review-and-Recommendations.md, live-matrix
        # re-run of F-11..F-16, 2026-07-17): this used to re-derive "honestly
        # admitted no claim" by substring-matching the literal NO_SOURCE_TEXT
        # string — which meant any OTHER legitimate no-citation response
        # (e.g. F-13's "Which place are you asking about?" clarifying
        # question, which correctly makes no factual claim to cite) was
        # wrongly flagged as an uncited assertion. explain_engine.py already
        # computes exactly this signal itself — every honest no-claim path
        # (NO_SOURCE fallback, F-13's clarifying question, and any future
        # one) sets grounded=False deliberately — so trust that field
        # directly instead of re-deriving it from specific wording that
        # can't anticipate future honest-fallback phrasings.
        admitted_no_source = exp.get("grounded") is False or NO_SOURCE_TEXT in answer

        if not citations:
            if not admitted_no_source:
                # Made a claim with nothing behind it and didn't say so — flag it.
                uncited_tips.append(answer[:60] or "(empty explanation)")
            continue

        for c in citations:
            if c.get("source_url") not in valid_source_urls:
                uncited_tips.append(c.get("source_title", "?"))

    return {
        "pass": len(ungrounded_pois) == 0 and len(uncited_tips) == 0,
        "ungrounded_pois": ungrounded_pois,
        "uncited_tips": uncited_tips,
    }
