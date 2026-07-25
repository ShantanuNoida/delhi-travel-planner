"""
Explanation Engine — Phase 4.

Answers three kinds of grounded questions about the current itinerary:
  "Why did you pick X?"    -> RAG lookup on the named place, LLM-synthesized from real chunks
  "Is this plan doable?"   -> Feasibility check + a supporting RAG citation on Delhi trip pacing
  "What if it rains?"      -> RAG lookup on indoor alternatives / Delhi weather

Every answer is either grounded in retrieved chunks (with citations attached)
or explicitly says it has no verified source — never both hallucinated and cited.
"""

import difflib
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
PHASE1_DIR = os.path.join(_ROOT, "phase1")
sys.path.insert(0, PHASE1_DIR)

from config import get_llm_client, LLM_MODEL_FAST
from feasibility import check_feasibility
from venues_kb_enrich import KB_NAME_OVERRIDES, _normalize_for_match

NO_SOURCE_TEXT = "I don't have a verified source for this — treat it as a general suggestion."

# Vector search always returns its nearest neighbors, even for nonsense queries —
# there's no built-in "no match" case. A cosine-similarity floor separates genuine
# hits (~0.5-0.75 for on-topic queries) from noise (~0.35 for unrelated queries).
RELEVANCE_THRESHOLD = 0.45

FEASIBILITY_KEYWORDS = (
    "doable", "feasible", "realistic", "too much", "fit in a day", "manage", "possible",
    # R-17 (Itinerary-Quality-Review-and-Recommendations.md F-12): real
    # repro — "Is Day 2 too packed?" fell through to the POI/RAG path
    # (nothing above RELEVANCE_THRESHOLD, honest NO_SOURCE) even though
    # check_feasibility() would have produced a real, grounded verdict.
    # "packed"/"rushed"/etc. are common everyday phrasings of the exact
    # same question the original keyword list already handled.
    "packed", "rushed", "cramped", "cramming", "over-scheduled", "over scheduled", "tight", "too much time",
)
WEATHER_KEYWORDS = ("rain", "raining", "weather", "monsoon", "hot", "cold", "storm")
# R-20 (Itinerary-Quality-Review-and-Recommendations.md F-15): real repro —
# "What areas should I avoid at night?" fell below RELEVANCE_THRESHOLD and
# returned NO_SOURCE even though the exact same corpus grounds "Is the metro
# safe at night?" and the agent's own proactive safety query. Routing these
# through a canonical, retrieval-friendly query (below) instead of the raw
# POI-search path fixes the common phrasings without changing the threshold
# itself (which stays a legitimate noise filter for genuinely unrelated
# questions).
SAFETY_KEYWORDS = ("safe", "safety", "avoid", "danger", "dangerous", "crime", "scam", "pickpocket")

# Phase 2 QA (H2, "Itinerary edit commands QA.md"): cost/timing/suitability
# keyword buckets for _explain_poi()'s direct-from-itinerary-data path (see
# _direct_kb_answer below) — the same keyword-bucket pattern already used
# above for FEASIBILITY_KEYWORDS/WEATHER_KEYWORDS/SAFETY_KEYWORDS.
COST_KEYWORDS = ("cost", "price", "fee", "expensive", "cheap", "how much", "ticket")
# User-reported follow-up ("try more probing questions, act as a genuine
# traveller"): real repro -- "Do I need to book tickets in advance for
# Humayun's Tomb?" is a BOOKING/reservation question, but "ticket" alone
# (the only COST_KEYWORDS entry it contains) routed it to the entry-fee
# answer instead -- a real mismatch (not fabricated, just answering a
# different question than the one asked). "ticket" is genuinely ambiguous
# on its own (a cost question -- "how much is a ticket" -- and a booking
# question -- "do I need to book a ticket" -- both contain it), unlike
# every other COST_KEYWORDS entry, which is unambiguous. The other entries
# stay as a direct, unambiguous cost signal; "ticket" alone is only trusted
# as a cost signal when no booking-intent word is also present.
_BOOKING_INTENT_WORDS = ("book", "advance", "reserve", "reservation")


def _is_cost_question(q_lower: str) -> bool:
    if any(kw in q_lower for kw in COST_KEYWORDS if kw != "ticket"):
        return True
    if "ticket" in q_lower:
        return not any(w in q_lower for w in _BOOKING_INTENT_WORDS)
    return False
# Live-usage report ("why is a venue included -- give 3-4 lines on its
# importance/popularity"): questions like "why did you pick X" were already
# routed to a real, grounded answer (_explain_poi -> RAG), but the generic
# _synthesize_answer prompt caps every answer at 2-3 sentences regardless of
# question type, and isn't specifically told to focus on importance/fame
# when that's what's being asked. Detected separately from the generic
# _extract_poi_name "pick/choose/include" regex (which only extracts WHICH
# place the question is about) so _direct_kb_answer can answer straight from
# the curated kb_why_famous field (venues_kb_loader.py's "Why It Is Famous"
# section) when present, and _synthesize_answer can be told to write longer,
# importance-focused prose when it isn't.
WHY_INCLUDED_KEYWORDS = (
    "why did you pick", "why did you choose", "why did you select",
    "why did you include", "why is this included", "why is it included",
    "why include", "why was this included", "what's special about",
    "whats special about", "why is this important", "why is it important",
    "why is this popular", "why is it popular", "why is this famous",
    "why is it famous", "importance of", "significance of", "why visit",
)


def _is_why_included_question(q_lower: str) -> bool:
    return any(kw in q_lower for kw in WHY_INCLUDED_KEYWORDS)


BEST_TIME_KEYWORDS = ("best time", "when should", "when to visit", "when to go", "what time", "time of day")
SUITABILITY_KEYWORDS = ("suitable", "suited", "appropriate for", "good for", "elderly", "senior", "kids",
                         "children", "family", "solo travel", "wheelchair", "accessib", "disab")
# Round 3 QA (Q-3, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md" -- carried
# over from Phase 2's TRAVEL_DATA_AVAILABLE_BUT_UNUSED finding): "how do I
# get from X to Y" questions used to always fall through to a generic
# name-only RAG search that had no chance of covering a specific two-stop
# route, even though the itinerary already carries a real, computed
# travel_time_from_prev_min/travel_mode_from_prev for every adjacent pair.
TRAVEL_KEYWORDS = ("how do i get", "how to get", "get from", "get to", "travel from", "travel between")
# Maps a phrase found in the user's question to the substring to look for in
# a stop's kb_suitable_for tags (e.g. "families", "elderly", "solo travellers")
# so a suitability question about a specific audience gets a direct yes/no,
# not just the full tag list (M2).
_AUDIENCE_TAG_ALIASES = (
    (("elderly", "senior"), "elderly"),
    (("kids", "children", "family"), "famil"),
    (("solo",), "solo"),
    (("budget",), "budget"),
    (("couple", "romantic"), "couple"),
    (("photograph",), "photograph"),
    (("spiritual",), "spiritual"),
    # Team Waypoint recheck (2026-07-22): real repro -- "Would Humayun's
    # Tomb work for someone in a wheelchair?" matched SUITABILITY_KEYWORDS
    # (so the direct-answer path fired at all) but had no alias here, so it
    # fell to the generic full-tag-dump branch instead of a direct answer.
    # kb_suitable_for's source data (delhi_tourist_venues_kb.md's "Suitable
    # For" field) never actually carries accessibility info -- that lives in
    # a separate "Tags" field ("wheelchair-accessible") that venues_kb_enrich.py
    # doesn't propagate onto POIs at all -- so this alias will legitimately
    # never match today. That's fine: the honest answer IS "not specifically
    # tagged for that," which is what this alias now correctly produces,
    # instead of the previous non-answering tag dump. Propagating the Tags
    # field itself (so a real "Yes") is a separate, Phase-1-data-pipeline
    # change, out of scope for this recheck.
    (("wheelchair", "accessib", "disab"), "wheelchair"),
)

# R-18 (Itinerary-Quality-Review-and-Recommendations.md F-13): real repro —
# "Why did you pick this place?" (no POI named) had _extract_poi_name
# capture the literal phrase "this place", RAG-search THAT, and synthesize a
# grounded-sounding but generic answer about "this area" that never
# references any actual scheduled stop. These are the phrasings that
# genuinely carry no place information to extract — not a fuzzy-matching
# problem, an honest "I don't know which place you mean" case.
_VAGUE_REFERENTS = {"this place", "that place", "this spot", "that spot", "this", "that", "it", "here"}


def _rag_query(text: str, n_results: int = 3) -> list[dict]:
    sys.path.insert(0, PHASE1_DIR)
    from embedder import query as embedder_query
    hits = embedder_query(text, n_results=n_results)
    return [h for h in hits if h.get("score", 0) >= RELEVANCE_THRESHOLD]


def _hits_to_citations(hits: list[dict]) -> list[dict]:
    seen = set()
    citations = []
    for h in hits:
        key = (h.get("article_title"), h.get("source_url"))
        if key in seen or not h.get("source_url"):
            continue
        seen.add(key)
        # "source" (wikivoyage/wikipedia) is real chunk metadata, already present
        # on every hit — surfacing it lets the UI show "Delhi/New Delhi
        # (Wikivoyage)" instead of a bare, low-information "Delhi" (UX-5/R-8).
        citations.append({
            "source_title": h.get("article_title", ""),
            "source_url": h.get("source_url", ""),
            "source": h.get("source", ""),
        })
    return citations


def _synthesize_answer(query: str, hits: list[dict], focus_on_importance: bool = False) -> str | None:
    """Returns None (not a raised exception) on an empty/None completion --
    see L1's fix note on _synthesize_or_no_source below for why.

    focus_on_importance: set for "why did you pick/include this" style
    questions on a stop with no kb_why_famous field to answer from directly
    (_direct_kb_answer) -- the generic 2-3 sentence cap produced answers
    that were accurate but too thin for what was actually asked (a real
    live-usage report). Only changes the length/framing instruction; still
    grounded in ONLY the same provided excerpts as every other answer."""
    length_instruction = (
        "Answer in 3-4 sentences, focusing specifically on this place's historical/cultural "
        "importance and its popularity with visitors — why it's a notable, worthwhile stop, "
        "not just what it is."
        if focus_on_importance else
        "Answer the user's question in 2-3 concise sentences."
    )
    context = "\n\n".join(f"[{h['article_title']}]: {h['text']}" for h in hits)
    client = get_llm_client()
    resp = client.chat.completions.create(
        model=LLM_MODEL_FAST,
        temperature=0,
        messages=[
            {"role": "system", "content": (
                f"{length_instruction} Use ONLY the provided "
                "source excerpts as your factual basis. Do not invent facts that are not present "
                "in the excerpts. State the answer directly and naturally, as you would explain "
                "it to a traveler in person — never mention 'the provided text/excerpts/source' "
                "or otherwise refer to how you were given this information (UX-13/R-15). "
                # R-20 (Itinerary-Quality-Review-and-Recommendations.md F-15):
                # real leaked outputs despite the instruction above — "There
                # is no specific information provided…", "The provided
                # information does not explicitly state…" — the model was
                # narrating its own retrieval process instead of just
                # answering. Naming the exact forbidden phrases plus a
                # concrete instruction for the partial-coverage case (which
                # is when this leak happened) closes it more reliably than
                # the general instruction alone.
                "If the excerpts only partially cover the question, answer with what they DO "
                "support and stop there — do not say phrases like 'there is no specific "
                "information provided', 'the excerpts do not state', or 'not explicitly "
                "mentioned'; just state the relevant facts you do have, naturally."
            )},
            {"role": "user", "content": f"Question: {query}\n\nSource excerpts:\n{context}"},
        ],
    )
    content = resp.choices[0].message.content
    return content.strip() if content else None


def _no_source_response() -> dict:
    return {"answer": NO_SOURCE_TEXT, "citations": [], "grounded": False}


# Phase 2 QA (H1, "Itinerary edit commands QA.md"): _rag_query()'s relevance
# floor only checks topical similarity, not whether a hit actually covers the
# SPECIFIC fact asked. A chunk can clear the floor (e.g. it mentions the POI
# by name) without containing the answer -- and the system prompt above
# correctly tells the model not to invent one, so it honestly declines. That
# honest decline was previously still packaged as {"grounded": True, with
# citations}, since the code only checked "did _rag_query() return any hits"
# and never looked at what the synthesized answer actually said. Real repro:
# 82 of 300 Phase 2 QA questions got a cited, "grounded" answer whose own
# text said things like "the provided sources do not contain any information
# about X." The R-20 system-prompt instruction alone doesn't reliably
# prevent this (that QA run is itself evidence it still happens), so this
# detects the leak in the output and reroutes to the same honest no-source
# shape used when _rag_query() finds nothing at all.
_DENIAL_PHRASES = (
    "do not contain", "does not contain", "doesn't contain",
    "no mention of", "not mentioned", "does not mention", "doesn't mention",
    "not specify", "does not specify", "doesn't specify",
    "no information", "not contain any information",
    "cannot answer", "can't answer", "i cannot determine", "unable to determine",
    "not provide", "doesn't provide", "does not provide",
)


def _is_denial(answer: str) -> bool:
    lower = answer.lower()
    return any(p in lower for p in _DENIAL_PHRASES)


# Phase 2 QA (M1, "Itinerary edit commands QA.md"): "alternatives"/"nearby"
# answers can accurately, honestly name a real Delhi place (grounded in a
# real citation) that nonetheless isn't in this app's own POI dataset --
# real repro: "Meherchand Market," "Purana Qila / Old Fort," "Lothian
# Cemetery" and others named as alternatives, absent from the 5,078-POI
# dataset. Not a factual error, so the answer's content is never changed --
# only a light, honest caveat is appended, and only when the answer is
# actually recommendation-shaped (gated by RECOMMENDATION_PHRASES) so
# ordinary historical/cultural proper nouns in a justification answer
# ("Emperor Shah Jahan," "the Mughal era") don't spuriously trigger it.
RECOMMENDATION_PHRASES = (
    "you can visit", "you can check out", "you can explore", "you can try",
    "you can find", "you could visit", "you will find", "you'll find",
    "alternative", "instead of", "another option", "other option",
    "nearby", "close by",
)
_PLACE_PHRASE_RE = re.compile(r"\b(?:[A-Z][a-zA-Z']+(?:\s+(?:[A-Z][a-zA-Z']+|of|the|and))*)\b")
# Deliberately does NOT include "old"/"new" -- those are common, genuine
# leading words in real Delhi venue names ("Old Fort," "Old Famous Jalebi
# Wala," "Old Ameer Mithai Wala") and blanket-filtering them silently
# suppressed the caveat on exactly the real repro cases this fix targets.
# The specific "Old/New Delhi" area-name phrases this was meant to catch
# are excluded explicitly instead, below.
_PLACE_PHRASE_LEAD_STOPWORDS = {
    "near", "additionally", "also", "other", "alternatively", "instead",
    "based", "the", "this", "that", "you", "if", "while", "visit", "for",
    "explore", "check", "try", "consider", "i",
}
_PLACE_PHRASE_EXACT_EXCLUSIONS = {
    "old delhi", "new delhi", "north delhi", "south delhi", "east delhi", "west delhi", "central delhi",
}
UNBOOKABLE_CAVEAT = (
    " (Note: I'm not able to confirm this one is in my verified, bookable list of stops "
    "for New Delhi -- let me know if you'd like me to search for something similar I can "
    "actually add to your itinerary.)"
)

_POI_NAMES_CACHE: set[str] | None = None


def _poi_names() -> set[str]:
    global _POI_NAMES_CACHE
    if _POI_NAMES_CACHE is None:
        path = os.path.join(PHASE1_DIR, "data", "pois.json")
        with open(path, encoding="utf-8") as f:
            pois = json.load(f)
        _POI_NAMES_CACHE = {p["name"].lower() for p in pois if p.get("name")}
    return _POI_NAMES_CACHE


def _append_unbookable_caveat(answer: str) -> str:
    if not any(p in answer.lower() for p in RECOMMENDATION_PHRASES):
        return answer
    names = _poi_names()
    for phrase in _PLACE_PHRASE_RE.findall(answer):
        words = phrase.split()
        if len(words) < 2 or len(phrase) <= 6:
            continue
        if words[0].lower() in _PLACE_PHRASE_LEAD_STOPWORDS:
            continue
        phrase_lower = phrase.lower()
        if phrase_lower in _PLACE_PHRASE_EXACT_EXCLUSIONS:
            continue
        if any(phrase_lower in n or n in phrase_lower for n in names):
            continue
        return answer + UNBOOKABLE_CAVEAT
    return answer


def _synthesize_or_no_source(query: str, hits: list[dict], citations: list[dict], focus_on_importance: bool = False) -> dict:
    """Shared by every RAG-answer call site: synthesize from real hits, but
    downgrade to the standard honest no-source response if the model's own
    answer amounts to "I don't actually know this" (see H1 note above)."""
    answer = _synthesize_answer(query, hits, focus_on_importance=focus_on_importance)
    if answer is None:
        # L1 ("Itinerary edit commands QA.md" Part 6): the LLM occasionally
        # returns an empty/None completion (observed ~1% of real Phase 2 QA
        # calls) -- previously this crashed with an unhandled AttributeError
        # on the .strip() call, silently downgrading a legitimate, answerable
        # question to R-1's generic fallback error one layer up in
        # phase3/agent.py. One retry resolves it in every case observed so
        # far; only fall through to the honest no-source response if the
        # retry also comes back empty.
        answer = _synthesize_answer(query, hits, focus_on_importance=focus_on_importance)
    if not answer or _is_denial(answer):
        return _no_source_response()
    answer = _append_unbookable_caveat(answer)
    return {"answer": answer, "citations": citations, "grounded": True}


def _extract_poi_name(query: str, itinerary: dict | None) -> tuple[str, bool, dict | None]:
    """
    Prefer an exact match against a scheduled stop name; else strip question
    phrasing. Returns (search_phrase, is_vague_referent, matched_stop) —
    is_vague_referent is True only when no real stop was matched AND the
    extracted phrase is itself a bare pronoun/demonstrative ("this place",
    "it", …), not for every non-matching phrase (a general question like
    "how do I get around Delhi?" also doesn't match a stop name, but is a
    legitimate, answerable RAG query in its own right — see F-13's fix note
    in explain()). matched_stop is the real scheduled-stop dict when an exact
    name match was found (so its own kb_*/travel_* fields can be used
    directly — see H2's fix, _direct_kb_answer below), else None.
    """
    q_lower = query.lower()
    if itinerary:
        for key in itinerary:
            if not key.startswith("day_"):
                continue
            for slot in ("morning", "afternoon", "evening"):
                for stop in itinerary[key].get(slot, []):
                    name = stop.get("name", "")
                    if name and name.lower() in q_lower:
                        return name, False, stop
    m = re.search(r"(?:pick|choose|recommend|include|selected|about)\s+(.*?)(?:\?|$)", query, re.IGNORECASE)
    phrase = m.group(1).strip() if m else query
    return phrase, phrase.strip().lower() in _VAGUE_REFERENTS, None


_KB_CITATIONS_CACHE: list[dict] | None = None


def _kb_citations() -> list[dict]:
    """Lazy-cached: citation_index.json entries sourced from
    delhi_tourist_venues_kb.md (already indexed in ChromaDB/the citation
    index by phase1/venues_kb_loader.py -- see H2's fix note)."""
    global _KB_CITATIONS_CACHE
    if _KB_CITATIONS_CACHE is None:
        path = os.path.join(PHASE1_DIR, "data", "citation_index.json")
        with open(path, encoding="utf-8") as f:
            idx = json.load(f)
        _KB_CITATIONS_CACHE = [v for v in idx.values() if v.get("source") == "delhi_tourist_venues_kb"]
    return _KB_CITATIONS_CACHE


def _kb_citation_for(stop_name: str) -> dict | None:
    """Finds the real, already-indexed venues-KB citation for a scheduled
    stop carrying kb_* fields. Reuses the exact override table and
    normalized fuzzy-match venues_kb_enrich.py used to attach those fields
    in the first place, so the citation always points to the correct venue
    even where OSM's name differs from the KB's own name (e.g. "Akshardham"
    vs KB's "Swaminarayan Akshardham Temple")."""
    entries = _kb_citations()
    kb_name = KB_NAME_OVERRIDES.get(stop_name)
    if kb_name:
        match = next((e for e in entries if e.get("article_title") == kb_name), None)
        if match:
            return match
    norm_stop = _normalize_for_match(stop_name)
    best, best_score = None, 0.0
    for e in entries:
        score = difflib.SequenceMatcher(None, norm_stop, _normalize_for_match(e.get("article_title", ""))).ratio()
        if score > best_score:
            best, best_score = e, score
    return best if best_score >= 0.55 else None


def _direct_kb_answer(query: str, stop: dict) -> dict | None:
    """
    H2/M2 fix ("Itinerary edit commands QA.md" Part 6): the itinerary's own
    attached ground-truth fields (kb_entry_fee/kb_best_time_to_visit/
    kb_suitable_for -- populated by phase1/venues_kb_enrich.py, present on
    ~24% of scheduled stops) were sitting unused on the exact stop object
    explain() was passed, while cost/best-time/suitability questions fell
    through to a generic RAG text search that often missed them (real repro:
    Sunder Nursery's exact entry fee/best-visit-time/suitability tags all
    returned a flat "no verified source" three separate times, despite the
    fact sitting in memory). Answers directly and confidently from that
    field when it's present and the question's keywords ask for it, instead
    of leaving it to RAG-search luck. Returns None (caller falls back to the
    normal RAG path) when the field the question asks about isn't present on
    this stop -- this only ever ADDS a source of truth, never removes the
    existing RAG fallback for stops without KB data.
    """
    q_lower = query.lower()
    name = stop.get("name", "this place")
    citation = _kb_citation_for(name)
    citations = [{
        "source_title": citation["article_title"],
        "source_url": citation["source_url"],
        "source": citation.get("source", "delhi_tourist_venues_kb"),
    }] if citation else []

    if _is_why_included_question(q_lower) and stop.get("kb_why_famous"):
        # The KB's "Why It Is Famous" prose is already real, curated,
        # multi-sentence writing about the venue's historical/cultural
        # importance and popularity (see delhi_tourist_venues_kb.md) --
        # used verbatim rather than re-synthesized, since it's already
        # accurate ground truth, not a source excerpt that needs an LLM to
        # extract an answer from.
        return {"answer": stop["kb_why_famous"], "citations": citations, "grounded": bool(citation)}

    if _is_cost_question(q_lower) and stop.get("kb_entry_fee"):
        answer = f"{name}'s entry fee: {stop['kb_entry_fee']}"
        return {"answer": answer, "citations": citations, "grounded": bool(citation)}

    if any(kw in q_lower for kw in BEST_TIME_KEYWORDS) and stop.get("kb_best_time_to_visit"):
        answer = f"The best time to visit {name}: {stop['kb_best_time_to_visit']}"
        return {"answer": answer, "citations": citations, "grounded": bool(citation)}

    if any(kw in q_lower for kw in SUITABILITY_KEYWORDS) and stop.get("kb_suitable_for"):
        tags = stop["kb_suitable_for"]
        tags_text = ", ".join(tags)
        matched_tag_key = next((tag_key for kws, tag_key in _AUDIENCE_TAG_ALIASES if any(kw in q_lower for kw in kws)), None)
        if matched_tag_key:
            is_suited = any(matched_tag_key in t.lower() for t in tags)
            if is_suited:
                answer = f"Yes — {name} is tagged as suitable for that: it's marked suitable for {tags_text}."
            else:
                answer = f"{name} isn't specifically tagged for that group. It's tagged as suitable for: {tags_text}."
        else:
            answer = f"{name} is tagged as suitable for: {tags_text}."
        return {"answer": answer, "citations": citations, "grounded": bool(citation)}

    return None


def _direct_travel_answer(query: str, itinerary: dict | None) -> dict | None:
    """
    Round 3 QA (Q-3): answers "how do I get from X to Y" directly from the
    itinerary's own already-computed travel_time_from_prev_min /
    travel_mode_from_prev on the LATER of two adjacent, named stops --
    instead of a generic RAG text search, which has no real chance of
    covering a specific two-venue route and returned an honest-but-useless
    no-source answer 8/400 times in this round's QA run despite the exact
    figure already sitting in memory on the itinerary object explain() was
    passed (same class of gap H2/_direct_kb_answer already closed for
    cost/best-time/suitability). Returns None (falls back to the normal RAG
    path) whenever fewer than two named stops are mentioned, or the two
    mentioned stops aren't actually adjacent in the schedule -- this only
    ever ADDS a source of truth for the specific case it can speak to with
    certainty, never guesses at a route between non-adjacent stops.
    """
    q_lower = query.lower()
    if not (itinerary and any(kw in q_lower for kw in TRAVEL_KEYWORDS)):
        return None

    ordered: list[dict] = []
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        for slot in ("morning", "afternoon", "evening"):
            ordered.extend(itinerary[key].get(slot, []))

    mentioned_ids = {s["osm_id"] for s in ordered if s.get("name") and s["name"].lower() in q_lower}
    if len(mentioned_ids) < 2:
        return None

    for i in range(1, len(ordered)):
        prev_stop, stop = ordered[i - 1], ordered[i]
        if prev_stop["osm_id"] in mentioned_ids and stop["osm_id"] in mentioned_ids:
            travel = stop.get("travel_time_from_prev_min")
            if travel is None:
                return None
            mode = stop.get("travel_mode_from_prev")
            mode_text = {"walk": "on foot", "auto": "by auto-rickshaw", "metro": "by metro"}.get(mode)
            answer = (
                f"From {prev_stop['name']} to {stop['name']}: about {travel} minutes"
                f"{f' {mode_text}' if mode_text else ''}, based on your itinerary's own schedule."
            )
            # No external citation exists for a figure this app computed
            # itself (there's no Wikivoyage/Wikidata source describing this
            # specific route) -- grounded=False here means the same thing
            # it means for _explain_feasibility's no-citation branch: a
            # real, non-invented answer, just not backed by an external
            # source, so the UI's citation-based trust marker correctly
            # doesn't show one.
            return {"answer": answer, "citations": [], "grounded": False}

    return None  # both stops are on the itinerary but not adjacent -- no direct answer to give


def _list_itinerary_stop_names(itinerary: dict | None, limit: int = 6) -> list[str]:
    names: list[str] = []
    if not itinerary:
        return names
    for key in sorted((k for k in itinerary if k.startswith("day_")), key=lambda k: int(k.split("_")[1])):
        for slot in ("morning", "afternoon", "evening"):
            for stop in itinerary[key].get(slot, []):
                if stop.get("name") and stop["name"] not in names:
                    names.append(stop["name"])
    return names[:limit]


def _explain_poi(query: str, itinerary: dict | None) -> dict:
    poi_name, is_vague, matched_stop = _extract_poi_name(query, itinerary)
    if is_vague:
        # R-18 (F-13): a genuinely referent-less question ("why did you
        # pick THIS PLACE?") has no place information to RAG-search at all
        # — searching the literal pronoun phrase used to retrieve loosely-
        # related chunks and synthesize a plausible-sounding but generic
        # answer about "this area" that never engaged with any real
        # scheduled stop. Ask which place instead of guessing.
        stop_names = _list_itinerary_stop_names(itinerary)
        if stop_names:
            listed = ", ".join(stop_names)
            answer = f"Which place are you asking about? Your itinerary includes: {listed}."
        else:
            answer = "Which place are you asking about? I don't see a built itinerary to reference yet."
        return {"answer": answer, "citations": [], "grounded": False}
    if matched_stop is not None:
        direct = _direct_kb_answer(query, matched_stop)
        if direct is not None:
            return direct
    hits = _rag_query(poi_name, n_results=3)
    if not hits:
        return _no_source_response()
    return _synthesize_or_no_source(
        query, hits, _hits_to_citations(hits[:2]),
        focus_on_importance=_is_why_included_question(query.lower()),
    )


def _explain_safety(query: str) -> dict:
    # R-20 (F-15): route through a canonical, retrieval-friendly safety
    # query instead of the raw POI-search path — see SAFETY_KEYWORDS' own
    # comment for the real repro this fixes ("what areas should I avoid at
    # night?" falling below threshold while "is the metro safe at night?"
    # doesn't, on the exact same corpus). Still answers the user's actual
    # question via _synthesize_answer(query, hits); only the retrieval
    # query text is expanded, not the answer.
    hits = _rag_query("New Delhi safety areas to avoid at night petty crime scams tourist safety tips", n_results=3)
    if not hits:
        return _no_source_response()
    return _synthesize_or_no_source(query, hits, _hits_to_citations(hits))


def _explain_feasibility(itinerary: dict | None, pace: str) -> dict:
    if not itinerary:
        return _no_source_response()

    result = check_feasibility(itinerary, pace)
    if result["pass"]:
        answer = f"Yes, this plan looks doable — every day fits within the {pace} pace budget."
    else:
        problems = "; ".join(f"Day {i['day']}: {i['problem']}" for i in result["issues"])
        answer = f"This plan may be tight — {problems}."

    hits = _rag_query("recommended pace and how many days to see New Delhi sightseeing", n_results=2)
    citations = _hits_to_citations(hits)
    if not citations:
        return {"answer": answer + " " + NO_SOURCE_TEXT, "citations": [], "grounded": False}
    return {"answer": answer, "citations": citations, "grounded": True}


# User-reported follow-up ("Fix the weather retrieval gap if possible"):
# investigated the actual indexed corpus directly (embedder.query, several
# phrasings, up to 8 results) -- Wikivoyage's Delhi article only has a
# purely DESCRIPTIVE Climate section (season timing, temperature, fog), no
# "what to do if it rains" advisory content at all, in this corpus. No
# retrieval-query tuning can synthesize an answer to a question the source
# material never addresses -- that's not a routing bug, it's a genuine
# corpus gap, and forcing a confident-sounding answer over it would mean
# inventing content, which this app's whole design exists to prevent.
# Mirrors _explain_feasibility's existing pattern instead: answer directly
# from data the itinerary object already has (each stop's real category),
# then optionally strengthen with a general-climate citation when one
# exists -- never blocked by the RAG search having nothing actionable.
_OUTDOOR_WEATHER_CATEGORIES = {"park", "monument", "market"}


def _explain_weather(query: str, itinerary: dict | None = None) -> dict:
    day_match = re.search(r"day\s*(\d+)", query, re.IGNORECASE)
    if day_match and itinerary:
        day_key = f"day_{day_match.group(1)}"
        if day_key in itinerary:
            outdoor, indoor = [], []
            for slot in ("morning", "afternoon", "evening"):
                for stop in itinerary[day_key].get(slot, []):
                    name = stop.get("name", "?")
                    bucket = outdoor if stop.get("category") in _OUTDOOR_WEATHER_CATEGORIES else indoor
                    bucket.append(name)

            if outdoor:
                answer = (
                    f"Day {day_match.group(1)} has {len(outdoor)} open-air stop"
                    f"{'s' if len(outdoor) != 1 else ''} rain would affect most: {', '.join(outdoor)}."
                    + (f" The rest ({', '.join(indoor)}) are indoors or covered either way." if indoor else "")
                )
            else:
                answer = (
                    f"Good news — every stop on Day {day_match.group(1)} "
                    f"({', '.join(indoor)}) is indoors or covered, so rain shouldn't disrupt your plan."
                )

            hits = _rag_query("New Delhi weather rain monsoon climate season", n_results=2)
            citations = _hits_to_citations(hits)
            if citations:
                return {"answer": answer, "citations": citations, "grounded": True}
            return {"answer": answer, "citations": [], "grounded": False}

    hits = _rag_query("New Delhi weather rain monsoon indoor attractions alternatives", n_results=2)
    if not hits:
        return _no_source_response()
    return _synthesize_or_no_source(query, hits, _hits_to_citations(hits))


def explain(query: str, itinerary: dict | None, pace: str = "moderate") -> dict:
    """
    Answer a grounded question about the itinerary.
    Returns {"answer": str, "citations": [{"source_title", "source_url"}], "grounded": bool}.
    """
    q_lower = query.lower()
    # Round 3 QA (Q-1, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): real
    # repro — "Would this itinerary feel safe and manageable for a solo
    # female traveller?" contains "manage" (a FEASIBILITY_KEYWORDS entry) as
    # a substring of "manageable", so with FEASIBILITY_KEYWORDS checked
    # first this always won and returned a pace-budget answer ("every day
    # fits within the moderate pace budget") marked grounded=True for a
    # question that was actually about personal safety — the one failure
    # mode this app's whole "cited, never invented" design is meant to
    # prevent, confirmed reproducing in 20/20 sampled itineraries. Safety is
    # checked first: it's the more specific, unambiguous signal ("safe" only
    # ever means personal safety) versus "manage"/"too much"/etc., which are
    # generic enough to appear inside unrelated words. No FEASIBILITY_KEYWORDS
    # entry is a substring of any SAFETY_KEYWORDS entry or vice versa, so this
    # reordering only changes routing for genuinely safety-worded questions —
    # a pure feasibility question ("is this doable?") never touches
    # SAFETY_KEYWORDS and is unaffected.
    if any(kw in q_lower for kw in SAFETY_KEYWORDS):
        return _explain_safety(query)
    if any(kw in q_lower for kw in FEASIBILITY_KEYWORDS):
        return _explain_feasibility(itinerary, pace)
    if any(kw in q_lower for kw in WEATHER_KEYWORDS):
        return _explain_weather(query, itinerary)
    direct_travel = _direct_travel_answer(query, itinerary)
    if direct_travel is not None:
        return direct_travel
    return _explain_poi(query, itinerary)
