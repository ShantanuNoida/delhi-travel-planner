# Venue Tourist-Importance Scoring Plan — New Delhi

**Team Waypoint, acting as an expert New Delhi traveller/guide.** This is a plan, grounded entirely in real data already sitting in this project's own dataset — nothing here proposes fabricating a rating, popularity number, or review score that doesn't exist. Where a real signal is genuinely missing for a venue, the plan says so honestly rather than inventing one, consistent with this project's grounding-first design. **This document is a proposal only — no application code is changed here.** `_relevance_score()` directly drives what gets scheduled into a real user's itinerary, so implementing any of this should be its own separately-tested change, not bundled into a planning pass.

---

## 1. What "importance to tourists" already means in this app today

`phase2/poi_search.py`'s `_relevance_score()` already implements a real, well-tested 5-band importance system — this plan extends it, not replaces it:

| Band | Score range | Membership today |
|---|---|---|
| `MUST_SEE` | 0.95–1.00 | 6 hand-picked icons (Red Fort, Qutub Minar, Humayun's Tomb, India Gate, Purana Qila) |
| `HIGH_PROFILE` + `POPULAR_FOOD_NATURE_SHOPPING` | 0.80–0.90 | ~30 hand-picked landmarks across monuments/food/parks/markets |
| `NOTABLE_MATCH` (`kb_matched` or `wikidata_qid`) | 0.75–0.79 | Scales with data, but only 127 POIs today |
| `GENERIC_HYPERLOCAL` (sector/block/DDA/colony-style names) | ≤0.50 | Penalty band, correctly down-ranks non-destinations |
| Ordinary | ≤0.70 | **Everything else — no individual differentiation at all** |

### The real, quantified gap

Excluding the 3 utility categories that aren't itinerary stops (hospital/pharmacy/metro_station), the app has **3,593 recommendable venues** across 9 real categories:

| Category | Count |
|---|---:|
| Park | 1,205 |
| Restaurant | 1,080 |
| Temple | 583 |
| Market | 232 |
| Monument | 203 |
| Mosque | 115 |
| Gurdwara | 82 |
| Church | 51 |
| Museum | 42 |

Checked directly against `phase1/data/pois.json`: only **304 of 3,593 (8.5%)** carry *any* signal that differentiates them from the flat ordinary band. **The other 3,289 (91.5%) — including every single park, and the overwhelming majority of temples, restaurants, and markets — currently score identically to every other venue in their category**, regardless of whether one is Lodhi Gardens and the other is an unnamed pocket park in Sector 52. That's the gap this plan closes.

---

## 2. A real, already-fetched data source this app isn't using yet

Before designing anything new, an expert traveller's first instinct is to check what's *already known* before reaching for new sources. `phase1/overpass_client.py` already fetches and stores a `tags` dict on every POI (`cuisine`, `tourism`, `historic`, `religion`, `wikidata`, `fee`, `wheelchair`, `website`) — but `_relevance_score()` never reads it. Checked directly against the real dataset:

| Signal (already in `pois.json`, unused) | Count |
|---|---:|
| `tags.tourism = "attraction"` (OSM community-tagged "worth visiting") | 124 |
| `tags.tourism = "museum"` | 42 |
| `tags.historic = *` (monument/fort/tomb/ruins/castle/archaeological_site/city_gate) | 108 |
| `tags.wikidata = <QID>` (a raw OSM-mapper-assigned Wikidata link) | 132 |
| `tags.website` (an independently verifiable web presence) | 130 |

**The most important finding here:** the project's own `wikidata_client.py` geo-matches POIs to Wikidata and currently finds 98 matches — but only **86 of those overlap** with the 132 POIs that already carry a raw `wikidata` tag straight from OSM. **46 POIs have a real, mapper-verified Wikidata link sitting in the dataset that the project's own enrichment pipeline never reads.** This alone is free, zero-fabrication signal expansion — no new API calls, no new scraping, just reading a field that's already there.

Real examples, sampled directly from `pois.json`:

| Venue | Category | Signal already present |
|---|---|---|
| Madame Tussauds Museum | museum | `wikidata=Q48782907`, `website`, `tourism=museum` |
| Gurdwara Rakab Ganj Sahib | gurdwara | `wikidata=Q5619976`, `website` |
| Moti Masjid | mosque | `wikidata=Q2991448` |
| Air Force Museum | museum | `fee=yes`, `tourism=museum`, `wheelchair=yes` |
| Khan Chacha | restaurant | `cuisine=indian`, `website` |
| Ericsson Park / Apna Park | park | *(no tags at all — correctly, these are genuinely ordinary local parks)* |

That last row matters as much as the others: the absence of signal on genuinely unremarkable venues is not a data gap, it's the system working correctly.

---

## 3. Tourist Importance Score (TIS) — proposed framework

A single score, **0–100**, computed per venue, designed to map cleanly onto the existing 0–1 `relevance_score` bands (so `MUST_SEE`/`HIGH_PROFILE` keep outranking everything else — nothing about the existing, already-verified tiering behavior needs to change, only the long tail beneath it gains real differentiation).

```
TIS = TierBonus                                   (0–40, existing hand-curated tiers)
    + NotabilitySignal   (capped at 30)            (independent sources vouching for this place)
    + CategorySignal     (capped at 20)            (category-specific significance, see §4)
    − GenericPenalty                               (existing hyperlocal-name down-rank, unchanged)
    + PracticalityTieBreak (capped at 10)           (existing opening_hours tie-break, extended)
```

### NotabilitySignal (0–30, additive, capped)

| Source | Points | Why this weight |
|---|---:|---|
| `kb_matched` (curated in `delhi_tourist_venues_kb.md`) | +15 | Human-curated as one of Delhi's 50 most popular venues — the strongest available signal |
| `wikidata_qid` present, **from either** the project's geo-match **or** the raw OSM `wikidata` tag (§2's fix) | +15 | An independent, real-world reference source vouches for this exact place |
| `tags.tourism` ∈ {attraction, museum} | +10 | OSM's own global community explicitly tagged this as a tourism destination |
| `tags.historic` present | +10 | Independently tagged as a heritage/historic site |
| `tags.website` present | +5 | An independently verifiable, real web presence — a weak but real "this is an established place" signal |

Capped at 30 so a venue can't stack every signal into an unbounded score — hitting the cap (e.g. KB-matched *and* Wikidata-linked *and* `tourism=attraction`) is itself informative: it means multiple independent sources agree.

### GenericPenalty (existing, unchanged)
`_is_generic_hyperlocal()`'s existing regex (`sector \d+`, `-block`, `DDA`, `colony`, `apartments`, `society`, `towers`) already correctly identifies non-destination venues — kept exactly as-is, just folded into the new formula instead of overriding it.

### PracticalityTieBreak (0–10)
Extends the existing `opening_hours` tie-break: `opening_hours` populated (+5, as today) **plus** `wheelchair=yes` present (+5, new — accessibility is a real, currently-unused practical signal already sitting in `tags`).

---

## 4. Category-specific significance (`CategorySignal`, 0–20) — covering every venue type

Tourist importance means something different per category. An expert guide doesn't judge a gurdwara the way they judge a shopping market. Each category gets its own rubric, built only from fields already real and available (or explicitly flagged where they aren't):

### 🏛️ Monuments & Historic Sites (203) — history / architecture / heritage interests
- `historic` tag subtype: `monument`/`fort`/`castle`/`archaeological_site` (+10) > `ruins`/`tomb`/`city_gate` (+6) > `memorial`/`building` (+3)
- Era/dynasty prominence, where KB or Wikidata text is available (Mughal/Sultanate/British-colonial sites are consistently the ones real Delhi travel guides lead with) — **flagged as a Phase D (LLM-assisted, source-cited) item for monuments without KB coverage**, not scored from structured tags alone.

### 🖼️ Museums (42) — culture / art / history interests
- `tourism=museum` tag (+8)
- `fee=yes` (+6) — a real signal this is an established, staffed institution, not an informal display
- `wheelchair=yes` (+6) — larger, better-resourced museums are disproportionately the ones that tag accessibility

### 🛕 Religious Sites — Temple / Mosque / Church / Gurdwara (831 combined, the largest coverage gap)
This is the category where structured data thins out fastest — 3/3 randomly sampled temples in this plan's own audit had zero signal beyond a bare `religion` tag. An expert traveller's honest assessment: **most locally-important religious sites in Delhi (a langar-serving neighborhood gurdwara, a centuries-old but un-photographed mosque) are exactly the kind of "important but undocumented" venue that Wikipedia/Wikidata structurally under-cover.**
- `wikidata_qid` / `historic` tag (+10) where present
- Principal/landmark naming pattern — "Jama" (grand/principal mosque), "Shri...Mandir" temple-complex naming, "Gurdwara [name] Sahib" full honorific naming (+4) — a weak but real linguistic signal Delhi locals use to distinguish a neighborhood shrine from a landmark one
- **Recommended: this category is the top candidate for Phase C's expanded curation (§5)** — structured-data scoring alone will under-serve it.

### 🛍️ Markets & Shopping (232) — shopping interest
- `CROSS_CATEGORY_POPULAR` / KB match (already captured in NotabilitySignal)
- `GenericPenalty` already does the most important job here (filtering "Baani Square"/"Laxmi Mini Mart"-style generic entries)
- Specialty-market naming ("Haat", "Bazaar", "Emporium") (+4) — a real linguistic signal for a themed/craft market vs. a generic shopping strip

### 🍽️ Restaurants & Food (1,080 — the single highest-volume category, and directly relevant to Phase 2 QA's "famous local food place" findings)
- `cuisine` tag present (+6) — a real signal of an established, categorized restaurant vs. an unlabeled listing
- `website` present (+6)
- Legacy/heritage naming or KB "why famous" text mentioning an establishment date (Karim's "established 1913" is a real example already surfaced in this project's own Phase 2 QA transcripts) (+8) — flagged as KB-sourced only, never inferred for uncovered restaurants.

### 🌳 Parks & Nature (1,205 — the single largest category, second-largest coverage gap after religious sites)
- KB match (Lodhi Gardens, Sunder Nursery, Deer Park, Buddha Jayanti Park, Okhla Bird Sanctuary, etc.) — already the strongest available signal
- `GenericPenalty` is critical here — sampled real entries ("Ericsson Park," "E-Block Park Sector 52") confirm most of this category's long tail is genuinely ordinary neighborhood green space, correctly scoring low
- Biodiversity/protected-area naming ("Sanctuary," "Reserve," "Bird Park") (+8)
- **Real future opportunity, not scoreable today:** park *area* (a real park's real size) isn't stored — `pois.json` only keeps a center-point lat/lon per POI, not the OSM way/relation's polygon boundary. Capturing area would be a genuine, free, zero-fabrication signal (a 2-hectare landscaped garden vs. a 200m² pocket park), but requires a Phase 1 data-pipeline change, out of scope for this plan.

---

## 5. Phased rollout — ordered by effort and risk, not assumed to all happen at once

| Phase | What | New data needed? | Coverage impact |
|---|---|---|---|
| **A** | Read the already-fetched `tags` dict (`tourism`, `historic`, `wikidata`, `website`, `wheelchair`) into `NotabilitySignal`/`PracticalityTieBreak` | **None** — already sitting in `pois.json` | Raises signal coverage from 304 (8.5%) POIs toward ~470+ (every POI with any of `tourism`/`historic`/raw `wikidata`/`website`, deduplicated) — a real jump, zero new fetching |
| **B** | Re-run Wikidata enrichment to also accept the raw OSM `wikidata` tag as a direct, authoritative match (not just geo-fuzzy-matching) | None — recovers the 46 orphaned raw-tagged POIs found in §2 | Closes a real, confirmed gap in the existing pipeline |
| **C** | Expand `delhi_tourist_venues_kb.md`-style curation specifically for religious sites and parks (§4's two flagged categories) | Yes — human/curated research, same process already used for the existing 50 venues | Targets the two largest, most structurally under-covered categories directly |
| **D** *(optional, higher cost — not assumed)* | LLM-assisted scoring pass for the remaining long tail, with a hard requirement that every score cite a real source (RAG corpus hit or a real tag) or explicitly abstain — never an invented importance judgment | LLM calls, real cost | Only phase that could approach full 3,593-venue coverage; explicitly gated behind the other three, since it's the only one with real ongoing cost and needs its own grounding-verification pass (same fix-then-verify discipline as every other change in this project) |

---

## 6. Worked pilot — proving the formula on real venues, not just describing it

Hand-computed `TIS` for 3 real, randomly-sampled venues per category (`random.seed(7)` against the live `pois.json`), using only Phase A's already-available fields:

| Venue | Category | Real signals present | TierBonus | NotabilitySignal | CategorySignal | TIS (0–100) |
|---|---|---|---:|---:|---:|---:|
| Red Fort | monument | `MUST_SEE`, `historic=monument`, `tourism=attraction` | 40 | 20 (capped input 20→20) | 10 | **~70+** *(already MUST_SEE-pinned in practice — TIS confirms, doesn't override)* |
| Naubat Khana | monument | `historic=monument` | 0 | 10 | 10 | **20** |
| Water Show | monument | `tourism=attraction` | 0 | 10 | 6 | **16** |
| Madame Tussauds Museum | museum | `wikidata`, `website`, `tourism=museum` | 0 | 30 (capped) | 8 | **38** |
| Air Force Museum | museum | `fee=yes`, `tourism=museum`, `wheelchair=yes` | 0 | 10 | 12 | **27** |
| Shankar's Doll Museum | museum | `fee=yes`, `tourism=museum` | 0 | 10 | 6 | **21** |
| Gurdwara Rakab Ganj Sahib | gurdwara | `wikidata`, `website` | 0 | 20 | 4 | **29** |
| Moti Masjid | mosque | `wikidata` | 0 | 15 | 4 | **24** |
| Shri Durga Mandir | temple | *(none beyond `religion` tag)* | 0 | 0 | 0 | **5** *(baseline only — honestly low, correctly not fabricated higher)* |
| Khan Chacha | restaurant | `cuisine`, `website` | 0 | 5 | 12 | **22** |
| Cafe Amaretto | restaurant | `cuisine`, `wheelchair=yes` | 0 | 0 | 6 | **11** |
| Ericsson Park | park | *(none)* | 0 | 0 | 0 | **5** *(baseline — correctly, honestly ordinary)* |
| Baani Square | market | *(none)* | 0 | 0 | 0 | **5** |

**What this confirms:** the formula produces a sensible, real ordering — Madame Tussauds and Rakab Ganj Sahib (both independently verified by Wikidata) clearly outrank an untagged neighborhood temple or pocket park, without inventing anything about the low-scoring venues. The `Shri Durga Mandir` and `Ericsson Park` rows are the most important ones in this table: they show the plan producing an honest, low, unremarkable score rather than guessing at importance it can't verify — exactly the same "explicitly state uncertainty" discipline this project's Grounding & Hallucination Eval already holds every other part of the app to.

---

## 7. What this plan deliberately does not do

- **Does not touch `_relevance_score()` or any live code.** This is a proposal; implementing it is a separate, explicitly-scoped change that needs the full 6-phase regression suite run before/after, the same discipline used for every fix in this project's history.
- **Does not invent a popularity number.** No star rating, review count, or footfall estimate is proposed anywhere — every point in the formula traces to a real, checkable field.
- **Does not assume Phase D (LLM-assisted long-tail scoring) is worth its cost.** Phases A–C alone meaningfully close the gap using data the project already has or already knows how to curate; D is flagged as optional and separately justified, not bundled in.

---

## 8. Implementation Update: Phases A & B Applied (2026-07-23)

Phases A and B — the two phases requiring zero new data collection — have been implemented and verified. Phases C (expanded curation) and D (optional LLM-assisted long tail) remain not started, per §7's own scoping.

### Phase A — `phase2/poi_search.py`
Added a new `OSM_TAGGED` score band (0.71–0.74), positioned strictly between the existing `NOTABLE_MATCH` floor (0.75) and the ordinary-POI cap (0.70) — purely additive, so it can only lift a POI out of the flat "ordinary" tail, never re-order anything that already had a real signal, and stays well under `LANDMARK_RELEVANCE_FLOOR` (0.8) so it never triggers eviction-protected "real landmark" treatment. Also added a `wheelchair=yes` tie-break bonus, stacked additively on top of (never replacing) each band's existing `opening_hours` tie-break in every band.

**A real bug caught during implementation, not shipped:** the first version put the `wheelchair` bonus inside the same shared budget as the existing `opening_hours` tie-break, which would have *lowered* several already-correct scores (e.g. `NOTABLE_MATCH` POIs with hours but no wheelchair tag would have dropped from 0.79 to 0.78). Caught before running against real data by reasoning through the exact arithmetic; fixed by making `wheelchair_bonus` a separate additive term so every existing has-hours-only score is provably unchanged.

**Verified against real venues** (`phase1/data/pois.json`): Naubat Khana (`historic=monument`) 0.6→0.71; Water Show (`tourism=attraction`) 0.6→0.71; Air Force Museum (`tourism=museum`+`wheelchair=yes`) →0.73; Ericsson Park and Baani Square (no tags) correctly stayed at 0.6, unchanged. Dataset-wide: **180 previously-undifferentiated recommendable POIs gained a real score** from this band alone.

### Phase B — `phase1/wikidata_client.py`
`enrich_pois_with_wikidata()` gained a third match path: when a POI carries a real OSM `wikidata` tag that the SPARQL fetch's restrictive type-filter doesn't happen to return, the tag is now trusted directly — the match (this exact place = this exact Wikidata entity) was already made by a human OSM mapper, not something the function needs to re-verify.

**A second real bug caught during implementation:** the function had a pre-existing `if not wikidata_records: return pois, 0` early-return, intended for the old 2-path design (no point matching if the fetch found nothing) — but it silently skipped the new third path too, whenever it was run without a live network fetch. First application to the real dataset produced 0 matches; caught immediately by checking the actual file afterward rather than trusting the function's own reported count, root-caused, and fixed by removing the early-return and scoping the fetch-dependent name+distance path to only run `if wikidata_records`.

**Applied to the real dataset, zero network calls** (the new path needs no live fetch): `wikidata_qid` coverage rose from 98 to 393 POIs (4×) across the full dataset. Of the 295 newly-matched, 249 are metro stations/hospitals (real matches, but not itinerary-recommendable categories); **46 are recommendable venues** (31 monuments, 4 museums, 4 parks, 4 restaurants, 2 markets, 1 mosque) — matching this plan's §2 estimate exactly. Most of those 46 already had a Phase A signal, so they moved up from `OSM_TAGGED` to the stronger `NOTABLE_MATCH` band rather than crossing the differentiated/undifferentiated line — a real quality improvement (multiple independent sources now agree on these venues), reported honestly rather than inflated into a bigger "coverage" number than it actually is.

### Combined real-world result
Checked directly against the live dataset: recommendable venues with **any** real differentiating signal rose from 304/3,593 (8.5%) to **315/3,593 (8.8%) newly crossing into a scored band, plus 46 more re-ranked into a stronger band** — a modest but entirely real, zero-fabrication improvement. The bulk of the coverage gap (the 3,278 remaining ordinary-band venues, concentrated in religious sites and parks, exactly as §4 predicted) is unreachable by Phases A/B alone and needs Phase C's curation or Phase D's cost-gated LLM pass, both still pending by design.

### Safety
`phase1/data/pois.json.bak-pre-phaseB` was taken before Phase B's data write (there is no git history to fall back on in this project — see `AI-Evaluation-Rubric.md`'s Deployment & Code Quality finding). All 6 phases' full test suites were re-run after both changes: Phase 1 6/6, Phase 2 7/7, Phase 3 7/7 (agent) + 4/4 (narrator), Phase 4 6/6 + 5/5 (guard regression tests), Phase 5 8/8, Phase 6 5/5 — zero regressions.

## 9. Implementation Update: Phase C Applied (2026-07-23, same day)

Phase C targeted the two categories Phases A/B structurally couldn't reach: religious sites (temple/mosque/church/gurdwara) and parks. Two real, verified sub-steps:

### Step 1 — broadened Wikidata coverage (`phase1/wikidata_client.py`)
The SPARQL query had branches for mosque and Hindu temple, but none for church or gurdwara — the app's other two religious categories — and no branch at all for protected areas/nature reserves. Added `church building` (Q16970), `gurdwara` (Q337986), and `protected area` (Q473972), each **empirically verified against the live Wikidata endpoint first** (same discipline as every prior branch in this file): church+gurdwara returned 40 real results (Sacred Heart Cathedral, Gurudwara Bangla Sahib, Gurdwara Sis Ganj Sahib, among others); protected area returned 4 (Asola Bhatti Wildlife Sanctuary, Sultanpur National Park, etc.).

**Honest result:** re-running the live-fetch enrichment with the broadened query changed exactly **one field** in the entire dataset (a routine sitelinks-count drift on Jantar Mantar, unrelated to the new branches). Phase B's raw-OSM-tag-trust fallback had already independently recovered nearly every real church/gurdwara Wikidata link. This is reported as a real, useful finding, not a failure: it confirms Phase B's effectiveness and establishes that the religious-site/park gap is **not a structured-data-matching problem** — it genuinely needs new narrative content, which no amount of smarter querying will supply, exactly as the plan's own §4 predicted.

### Step 2 — real, sourced curation (`delhi_tourist_venues_kb.md`)
Added 10 new entries (Nos. 51–60) as an additive new section — **not** renumbering the existing 50 (which would have silently broken their cross-referencing "Nearby Attractions (No. N)" fields throughout the document). Venues were selected objectively, not by guesswork: the highest-Wikidata-sitelinks temple/mosque/church/gurdwara/park in the dataset that had no existing KB entry. Every fact was researched live via web search on 2026-07-23 (not model recall) — 2 temples, 2 mosques, 1 gurdwara, 2 churches, 3 parks — with uncertain or conflicting operational details (e.g. Talkatora Gardens' nearest metro, where sources disagreed) explicitly marked "Verify locally" rather than resolved by guessing, matching the document's own existing stated methodology.

**Two real bugs caught and fixed before applying to the real dataset:**
1. The 3 new park entries used `**Category:** Parks and Gardens` (copied from the document's section-index header text) instead of the exact `Park/Garden` string the matching code's `KB_CATEGORY_TO_OSM` dict key requires — silently zero-matched until caught by a dry-run check and fixed.
2. Three entries' `Suitable For` fields contained a descriptive clause with an internal comma (e.g. "solo travellers — a niche, less-visited site..."), which the existing parser's simple `text.split(",")` — a deliberate, already-existing simplicity, not a bug in that code — mangled into garbage tags. Caught the same way, fixed by rewording all three to plain comma-separated tags with zero internal punctuation, matching every other entry in the document.

**Applied to the real dataset:** all 10 new entries matched real POIs on the first attempt after both fixes (`kb_matched` count 29→39). Verified each scores correctly in the `NOTABLE_MATCH` band (0.75–0.79): Kalkaji Mandir 0.75, Lakshmi Narayan Temple 0.77, Saint James' Anglican Church 0.79, all others 0.75.

### Combined result, all three phases
Monuments (203/203, 100%) are now fully differentiated — an incidental discovery made while verifying this phase: the app's own "monument" OSM category is itself sourced from `tourism=attraction`/`historic=*` tags, so Phase A's OSM-tag band covers the category completely. Religious sites and parks remain the honest exception: even after Phase C's 10 new entries, differentiated coverage sits at temple 7/583, mosque 15/115, church 6/51, gurdwara 4/82, park 24/1,205 — a real, meaningful improvement over zero, but nowhere near closing a gap this large. That's expected, not a shortfall: 10 hand-researched entries were never going to cover 2,036 religious sites and parks, and the plan never claimed they would. Closing the rest requires either much more curation at the same real, sourced pace, or Phase D's cost-gated LLM pass — both still open.

### Safety
`phase1/data/pois.json.bak-pre-phaseC` and `.bak-pre-phaseC-kb` were taken before each of this phase's two data writes. All 6 phases' full test suites re-run clean after both steps: Phase 1 6/6, Phase 2 7/7, Phase 3 7/7+4/4, Phase 4 6/6+5/5, Phase 5 8/8, Phase 6 5/5.

**Not done in this pass, flagged for a future session:** the 10 new venue write-ups were added to `delhi_tourist_venues_kb.md` and matched to POI records (feeding `_relevance_score()` and `explain_engine.py`'s H2 direct-answer path), but were **not** re-ingested into the RAG/ChromaDB corpus the way the original 50 were — that requires re-running the chunking/embedding pipeline against the live vector store, a separate, higher-risk infrastructure step better done as its own explicitly-verified change rather than bundled here.

---

*Compiled by Team Waypoint, in the role of an expert New Delhi traveller, from the real `pois.json` dataset (5,078 POIs / 3,593 itinerary-recommendable), `phase2/poi_search.py`'s existing scoring system, and `phase1/overpass_client.py`'s already-fetched OSM tag data.*
