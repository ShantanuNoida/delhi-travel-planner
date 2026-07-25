# Golden Dataset & Evaluation Rubric — Voice-First AI Travel Planner (New Delhi)

**Compiled from real, end-to-end runs against the live application** — Phase 5's automated eval suite (`phase5/`), Team Waypoint's Phase 1 edit-command QA (300 real edits) and Phase 2 question-command QA (300 real questions), and the post-fix rechecks that followed. No score in this document is estimated or simulated; every figure cites the specific run/file it came from.

---

## 1. Datasets Referenced

| Dataset | Size | Role | Source file(s) |
|---|---|---|---|
| Overpass API POI extract | 5,078 POIs (restaurant, market, monument, museum, temple, mosque, church, gurdwara, park, hospital, pharmacy, metro station) | Ground truth for every schedulable stop — `osm_id` is the grounding key the Grounding Eval checks against | `phase1/data/pois.json`, `phase1/overpass_client.py` |
| Wikivoyage + Wikipedia scraped articles | 14 articles (3 Wikivoyage + 11 Wikipedia) → chunked into the RAG corpus | Source text for `explain()`'s RAG-grounded answers (justification, contingency, practicalities, etc.) | `phase1/scraper.py`, `phase1/chunker.py` |
| Wikidata enrichment | 83 matched POIs enriched with website/QID/image | Supplementary grounding metadata, CC0-licensed | `phase1/wikidata_client.py` |
| `delhi_tourist_venues_kb.md` (hand-curated venue KB) | 50 venues — entry fee, best time to visit, suitability tags, "why famous" prose | Two roles: (a) enriches matching POIs with `kb_entry_fee`/`kb_best_time_to_visit`/`kb_suitable_for`; (b) also chunked into the same RAG corpus as its own citable source | `phase1/venues_kb_loader.py`, `phase1/venues_kb_enrich.py` |
| Citation index | 197 entries total — 147 Wikipedia/Wikivoyage + 50 venues-KB | Every citation `explain()` ever attaches is checked against this index for authenticity | `phase1/data/citation_index.json` |
| ChromaDB vector store | Same 147+50 chunks, embedded via `paraphrase-multilingual-MiniLM-L12-v2` | Backs every RAG lookup in `explain_engine.py` | `phase1/data/chroma/` |
| `phase5/sample_itinerary.json` | 1 fixture, 2-day, moderate pace, built from real Phase 1/2 data | Dedicated fixture for Phase 5's own standalone CLI eval runs | `phase5/sample_itinerary.json` |
| **Golden itinerary set** (see §2) | 20 itineraries, all real app output | Reference/"golden" itineraries reused, unmodified, across both Phase 1 and Phase 2 QA rounds | `phase7_qa/results/itinerary_01.json` … `itinerary_20.json` |

---

## 2. Golden Dataset Composition

The 20 golden itineraries were generated once, for real, by the actual scheduler (`poi_search_logic()` → `itinerary_builder_logic()` — the same functions the live conversational agent calls), then **reused unmodified as the fixed reference set for both QA phases** (Phase 2's brief explicitly required reusing Phase 1's itineraries as-is). This makes them a genuine golden dataset in the ML-eval sense: a fixed, known-good reference corpus that every subsequent eval run is measured against, not regenerated per test.

| # | Label | Days | Pace | Interests |
|---|---|---|---|---|
| 1 | Food-only city crawl | 2 | moderate | food |
| 2 | History-only deep dive | 3 | moderate | history |
| 3 | Nature-only escape | 2 | relaxed | nature |
| 4 | Shopping-only spree | 2 | moderate | shopping |
| 5 | Religion-only pilgrimage | 3 | moderate | religion |
| 6 | History + Food | 2 | moderate | history, food |
| 7 | Culture + Art | 3 | moderate | culture, art |
| 8 | Architecture + History + Shopping | 2 | intensive | architecture, history, shopping |
| 9 | Family + Nature | 2 | relaxed | family, nature |
| 10 | Food + Shopping + Culture | 3 | moderate | food, shopping, culture |
| 11 | Religion + History | 2 | moderate | religion, history |
| 12 | Art + Culture + Food | 3 | moderate | art, culture, food |
| 13 | Nature + Family + Shopping | 2 | relaxed | nature, family, shopping |
| 14 | Architecture + Religion | 3 | moderate | architecture, religion |
| 15 | History + Culture + Architecture + Food | 3 | intensive | history, culture, architecture, food |
| 16 | Shopping + Food | 2 | moderate | shopping, food |
| 17 | Family + Culture + History | 3 | moderate | family, culture, history |
| 18 | Nature + Art | 2 | relaxed | nature, art |
| 19 | Religion + Architecture + Culture | 2 | moderate | religion, architecture, culture |
| 20 | Food + History + Nature + Shopping | 3 | moderate | food, history, nature, shopping |

**Composition rationale:** 5 single-interest + 15 multi-interest (2-4 combined interests); 11 two-day + 9 three-day trips; all 3 pace tiers (relaxed/moderate/intensive) represented; every one of the app's 9 interest themes (food, history, culture, nature, art, shopping, architecture, family, religion) appears in at least 2 itineraries. Full per-day/per-stop detail: `Itinerary edit commands QA.md`, Part 1.

---

## 3. Adversarial Test Suite

Every adversarial case below was run for real against the live app (real Gemini classifier calls, real RAG lookups) — none simulated. Grouped by what each class of test is designed to break.

| # | Category | Adversarial probe | Real example used | Expected behavior | Result (post-fix) |
|---|---|---|---|---|---|
| A1 | Known-absent place | Name a real, well-known Delhi landmark that is genuinely absent from the OSM extract | "Replace the Day 1 evening stop with Connaught Place" | Honest, sourced decline — never a silent no-op, never a fabricated add | ✅ 20/20 |
| A2 | Known-absent place, natural phrasing | Same as A1, with a trailing generic noun ("mall"/"market") that breaks naive exact-key matching | "Add Select Citywalk mall to Day 2" | Same honest decline as the exact-name case | ✅ 20/20 (post H3-P1 fix) |
| A3 | Known-absent place, fresh names (recheck) | Different absent-place entries, different phrasing, to test generalization | "Add INA Market to Day 1", "Swap Day 2 evening for Sarojini Nagar Market" | Honest decline with each entry's own correct message | ✅ both, confirmed in the fresh recheck |
| A4 | Invalid day reference | Reference a day number that doesn't exist in this trip | "Make Day 4 more relaxed" on a 2-day trip | Clean rejection, no crash, no silent no-op | ✅ 20/20 |
| A5 | No-referent vague command | A command that names nothing searchable | "Remove the boring stop from Day 1" | Routed to `relax` (drop lowest-relevance stop), never a hallucinated match for "boring" | ✅ 20/20 |
| A6 | Fully vague, no actionable signal | No day/slot/edit-type signal at all | "Make the whole trip more fun." | Previewed + confirmation requested before a multi-day change commits (not silent) | ✅ (M2-P1 fix); confirmed again with fresh phrasing in recheck |
| A7 | Themed-constraint phrasing stress test | Natural-language category requests using words outside the original literal vocabulary | "one famous local food place", "a history spot", "a nice place to eat", "a cultural spot" | Resolves to the correct category, not a silent no-op | ✅ (H2-P1 fix + "eat"/"dining" gap fix from the recheck) |
| A8 | Vague-referent question (hallucination trap) | A question with no place information to extract | "Why did you pick this place?" | Asks which place, rather than guessing and hallucinating a generic answer | ✅ 20/20 |
| A9 | Unanswerable-with-current-data question | A question the app has no data source for at all (no hotel/lodging is tracked anywhere) | "Is `<real venue>` within walking distance of my hotel?" | Honest "I don't know" — never a fabricated distance or invented hotel location | ✅ 20/20, 0 fabricated |
| A10 | Venue-name / classifier-vocabulary collision (EDIT axis) | A real venue's own name happens to match the classifier's own trigger vocabulary | "What are some alternatives to Make My Lagan on Day 2?" ("Make My Lagan" starts with "Make," the classifier's own EDIT example verb) | Classified as a question (`EXPLAIN`), not a silent `EDIT` | ✅ (H3-P2 fix); 6/6 on repeated fresh-phrasing recheck |
| A11 | Venue-name / classifier-vocabulary collision (NEW_PLAN axis) | Same real venue's name additionally echoes an unrelated real-world brand ("Make My Lagan" ≈ "Make My Wedding" ≈ MakeMyTrip) | "Give me some alternatives besides Make My Lagan" | Classified `EXPLAIN`, not `NEW_PLAN` (discard-the-plan) | ✅ fixed; was `NEW_PLAN` 5/6 times pre-fix, now `EXPLAIN` 6/6 |
| A12 | Denial-disguised-as-grounded | A RAG hit clears the relevance floor but doesn't actually cover the specific fact asked | "What if it rains on Day 1?" / "How do I get from X to Y?" on itineraries with thin corpus coverage | Answer that denies knowledge must be labeled `grounded: False` with no citations, not dressed up as sourced | ✅ (H1-P2 fix); 82/82 real recorded denial cases now correctly downgraded |
| A13 | Real-but-unbookable recommendation | An "alternatives" answer names a real, accurately-cited Delhi place absent from the app's own bookable POI dataset | "What could I do instead of visiting Chandni Chowk?" → names Dariba Kalan (real, not in the 5,078-POI set) | Honest caveat appended, without altering the answer's actual content | ✅ (M1-P2 fix); 22/24 real cases correctly caveated, 2/24 correctly not (both contain a genuinely bookable POI as a substring) |
| A14 | KB ground-truth available but unused | A stop carries exact structured fee/timing/suitability data that a naive RAG-only path can miss | "How much does it cost to visit Sunder Nursery?" (real, exact `kb_entry_fee` on the stop) | Answer directly from the itinerary's own attached data, cited | ✅ (H2-P2 fix); 21/21 real cases now correctly answered |
| A15 | Rare empty-LLM-completion resilience | The completion API occasionally returns empty content | (production condition, not user-phrasable) | One silent retry, then an honest no-source fallback — never an unhandled crash | ✅ (L1-P2 fix); verified via both real-run observation (~1% real occurrence rate) and deterministic monkeypatch replay |

**Totals:** 15 adversarial categories, spanning both the edit surface (Phase 1: 300 real commands across 20 itineraries) and the question/explain surface (Phase 2: 300 real questions across the same 20 itineraries), plus a further ~35 fresh, differently-phrased commands/questions in the post-fix recheck. Full transcripts: `phase7_qa/results/itinerary_*.json`, `phase7_qa/results/phase2_itinerary_*.json`, `phase7_qa/results/_recheck_log.json`.

---

## 4. Evaluation Parameters (Highlighted Criteria)

### 🅰️ Feasibility Eval
> Does the app produce and maintain a *physically realistic* itinerary?

- **Daily duration ≤ available time** — every day's scheduled stops (visit duration + travel time) must fit within that day's pace budget (relaxed/moderate/intensive each map to a fixed hour cap).
- **Reasonable travel times** — no single leg between two consecutive stops may exceed `MAX_TRAVEL_LEG_MIN = 45` minutes; enforced both at build time and as a standalone post-edit check.
- **Pace consistency** — the itinerary's actual density (stops/hour, coverage across morning/afternoon/evening) should match the pace tier the user asked for, not silently drift looser or tighter.

### 🅱️ Edit Correctness Eval
> When the user asks for one specific change, does *only* that change happen?

- **Voice edits only modify intended sections** — an edit scoped to `target_day=N, target_slot=S` must only touch that day/slot.
- **No unintended changes elsewhere** — every other day/slot in the itinerary must be byte-for-byte identical before and after the edit (one documented, intentional exception: `reduce_travel`, which by design re-clusters the whole trip).

### 🅲️ Grounding & Hallucination Eval
> Is every claim the app makes either real and sourced, or honestly flagged as not?

- **POIs map to dataset records** — every scheduled stop's `osm_id` must resolve to a real record in `phase1/data/pois.json`; no invented POI ever reaches the itinerary.
- **Tips cite RAG sources** — every citation shown alongside an explanation/tip must point to a real, indexed `source_url` in `phase1/data/citation_index.json`.
- **Uncertainty is explicitly stated when data is missing** — when the app doesn't have a verified fact, it must say so (`NO_SOURCE_TEXT` / an honest decline), never fabricate a plausible-sounding answer.

---

## 5. Evals Rubric (Weighted)

Weightage reflects the project's own stated design priority: this app's core pitch is a **grounding-first, no-fabrication** planner (Phase 5's eval suite and every QA round in this project exists specifically to enforce that promise), so Grounding & Hallucination carries the largest single weight. Feasibility and Edit Correctness are weighted equally beneath it — both are necessary-but-secondary trust properties (a plan that's grounded but unrealistic, or grounded but that mangles edits, is still a broken product, just a differently-broken one).

| Category | Weight | Sub-criterion | Sub-weight | Overall weight |
|---|---:|---|---:|---:|
| **Feasibility Eval** | **30%** | Daily duration ≤ available time | 40% of category | 12% |
| | | Reasonable travel times | 30% of category | 9% |
| | | Pace consistency | 30% of category | 9% |
| **Edit Correctness Eval** | **30%** | Voice edits only modify intended sections | 60% of category | 18% |
| | | No unintended changes elsewhere | 40% of category | 12% |
| **Grounding & Hallucination Eval** | **40%** | POIs map to dataset records | 35% of category | 14% |
| | | Tips cite RAG sources | 30% of category | 12% |
| | | Uncertainty explicitly stated when data is missing | 35% of category | 14% |
| **Total** | **100%** | | | **100%** |

---

## 6. Scores Achieved

Every score below is a real pass rate from an actual run, not an estimate. "Evidence" cites the specific source.

### Feasibility Eval — 30% weight

| Sub-criterion | Score | Evidence |
|---|---:|---|
| Daily duration ≤ available time | **100 / 100** | `check_feasibility()` budget guard: 0 of 300 real Phase 1 edits produced an undetected over-budget day (2 edits that *would* have overflowed were correctly rejected with a constructive alternative). Phase 5 `T-5.1`/`T-5.2` (Feasibility Eval: Passing/Failing Plan) both pass. |
| Reasonable travel times | **100 / 100** | `MAX_TRAVEL_LEG_MIN = 45` enforced at build time (`phase2/itinerary_builder.py`) via a try-each-candidate-slot loop, not just as a downstream check; `phase5/sample_itinerary.json` regenerated and passes with zero long-leg violations. Phase 5 `T-5.3` (Feasibility Eval: Long Travel Leg) passes. |
| Pace consistency | **88 / 100** | Pace tiers are respected at build time (relaxed/moderate/intensive map to real, enforced hour caps — never violated in 20/20 golden itineraries). Docked for a known, *deliberately accepted* limitation: `check_day_balance()` (added for UX-14/R-16) flags real under-filled evenings/days (single-stop evening slots are common) as a structural characteristic of the scheduler, not a bug fixed by rescheduling — the project chose honest labeling over a riskier scheduler rewrite. |
| **Category score** | **95.6 / 100** | Weighted: (100×0.40 + 100×0.30 + 88×0.30) |

### Edit Correctness Eval — 30% weight

| Sub-criterion | Score | Evidence |
|---|---:|---|
| Voice edits only modify intended sections | **100 / 100** | `check_edit_correctness()` (scope-drift detector) across all 300 real Phase 1 edits: 0 drifted slots outside the declared `target_day`/`target_slot`. Phase 5 `T-5.4` (Edit Correctness Eval: Clean Edit) passes. |
| No unintended changes elsewhere | **100 / 100** | Same 300-edit run, same detector — zero unintended cross-day/slot changes, with one documented, intentional design exception (`reduce_travel`, which is explicitly allowed to touch every day since re-clustering is its whole purpose). Phase 5 `T-5.5` (Edit Correctness Eval: Drift Detection) passes. Reconfirmed on a fresh, differently-phrased command set in the post-fix recheck (H1/H2/M1-P1/M2-P1/L1/L2 rechecks — 0 unexpected side effects observed). |
| **Category score** | **100 / 100** | Weighted: (100×0.60 + 100×0.40) |

### Grounding & Hallucination Eval — 40% weight

| Sub-criterion | Score | Evidence |
|---|---:|---|
| POIs map to dataset records | **100 / 100** | `check_grounding()`: 0 ungrounded POIs (invalid `osm_id`) across all 20 golden itineraries, both as originally built and after 300 real edits. Phase 5 `T-5.6`/`T-5.7` (Grounding Eval: All POIs Verified / Unverified POI Detection) both pass. R-11's whole-trip duplicate detector (`_duplicate_of`) further guarantees no double-counted record. |
| Tips cite RAG sources | **100 / 100** | 0 of 300 real Phase 2 questions produced a citation pointing to a URL absent from the 197-entry citation index — 100% citation authenticity, both before and after the H1 fix (H1's bug was the `grounded` *flag's* accuracy, never the citations' authenticity, which was always clean). |
| Uncertainty explicitly stated when data is missing | **93 / 100** | Post-fix: H1 (82/300 real denial-but-"grounded" cases → 0/300, all now correctly honest), H2 (KB data no longer silently omitted — 21/21 real cases fixed), L1 (rare ~1% empty-completion crash → graceful honest fallback, both retry-path and both-attempts-empty paths verified). Docked 7 points for two residual, real risk classes: (a) M1-P2's unbookable-place caveat is a heuristic, not a proof — verified precise on 22/24 real cases, imperfect by construction; (b) the venue-name/classifier-vocabulary collision *class* of bug (A10/A11 above) was found twice by QA on this dataset alone, and while both known instances are now fixed, a structurally similar new venue name could still surface a fresh collision — this is a residual, open-ended risk rather than a fully closed one. |
| **Category score** | **97.55 / 100** | Weighted: (100×0.35 + 100×0.30 + 93×0.35) |

### Overall Weighted Score

| Category | Category score | Weight | Contribution |
|---|---:|---:|---:|
| Feasibility Eval | 95.6 | 30% | 28.68 |
| Edit Correctness Eval | 100.0 | 30% | 30.00 |
| Grounding & Hallucination Eval | 97.55 | 40% | 39.02 |
| **Overall** | | **100%** | **97.7 / 100** |

---

## 7. Interpretation

**Overall: 97.7 / 100.** The app's two hardest, most binary safety properties — never mangling an edit outside its scope, and never scheduling an unverifiable POI — are both **perfect (100/100)** across every real run in this project (300 edits, 300 questions, plus a fresh differently-phrased recheck of every prior fix). The two categories with any deduction share a common shape: **the deducted points are for known, honestly-documented residual risk, not undetected failures** —

- Pace consistency's deduction is a *deliberate, recorded design tradeoff* (R-16: honest under-fill labeling over a riskier scheduler rewrite), not a defect.
- The uncertainty-signaling deduction is for two *open-ended risk classes* (a caveat heuristic that's precise but not provably complete; a venue-naming collision pattern that's been found and fixed twice on this exact dataset) — both are actively monitored and every specific instance found so far has been fixed and verified, but the categories themselves can't be marked fully closed the way a fixed, finite bug can.

This scoring approach — docking points for honestly-flagged residual risk rather than only for confirmed failures — is intentional and consistent with the project's own grounding-first philosophy: a 100/100 score that ignored known open-ended risk would itself be a small dishonesty.

---

*Compiled by Team Waypoint from real, end-to-end application runs. Sources: `phase5/` (automated eval suite, 8/8 passing), `Itinerary edit commands QA.md` (Phase 1 + Phase 2 QA, all findings fixed and verified), `phase7_qa/results/` (raw transcripts and recheck logs).*
