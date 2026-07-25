# AI Evaluation Rubric — Voice-First AI Travel Planner (New Delhi)

Scored against the 6-category rubric provided, using real evidence from the codebase, test suites, and Team Waypoint's QA rounds (`Itinerary edit commands QA.md`). Every score below cites the specific file, test, or run it's based on — including honest, low scores where the project made a deliberate scope tradeoff or where a real gap was found. A rubric that only ever scores high isn't a credible rubric.

---

## Rubric & Weights

| Category | Weight |
|---|---:|
| Voice UX & Intent Handling | 25% |
| MCP Usage & System Design | 20% |
| Grounding & RAG Quality | 15% |
| AI Evals & Iteration Depth | 20% |
| Workflow Automation | 10% |
| Deployment & Code Quality | 10% |
| **Total** | **100%** |

---

## Golden Dataset

The evidence cited throughout this rubric — "20 golden itineraries," "300 real edit commands," "197-entry citation index," and similar — draws on one fixed, real reference dataset, generated once by the actual app and reused unmodified across every QA round since.

### Underlying data sources

| Dataset | Size | Role | Source file(s) |
|---|---|---|---|
| Overpass API POI extract | 5,078 POIs (restaurant, market, monument, museum, temple, mosque, church, gurdwara, park, hospital, pharmacy, metro station) | Ground truth for every schedulable stop — `osm_id` is the grounding key the Grounding Eval checks against | `phase1/data/pois.json`, `phase1/overpass_client.py` |
| Wikivoyage + Wikipedia scraped articles | 14 articles (3 Wikivoyage + 11 Wikipedia) → chunked into the RAG corpus | Source text for `explain()`'s RAG-grounded answers | `phase1/scraper.py`, `phase1/chunker.py` |
| Wikidata enrichment | 83 matched POIs enriched with website/QID/image | Supplementary grounding metadata, CC0-licensed | `phase1/wikidata_client.py` |
| `delhi_tourist_venues_kb.md` (hand-curated venue KB) | 50 venues — entry fee, best time to visit, suitability tags, "why famous" prose | Enriches matching POIs with `kb_*` fields, and is itself chunked into the same RAG corpus as a citable source | `phase1/venues_kb_loader.py`, `phase1/venues_kb_enrich.py` |
| Citation index | 197 entries — 147 Wikipedia/Wikivoyage + 50 venues-KB | Every citation `explain()` attaches is checked against this index for authenticity | `phase1/data/citation_index.json` |
| ChromaDB vector store | Same 147+50 chunks, embedded via `paraphrase-multilingual-MiniLM-L12-v2` | Backs every RAG lookup in `explain_engine.py` | `phase1/data/chroma/` |
| Golden itinerary set | 20 itineraries, all real app output | Fixed reference set reused unmodified across both QA phases | `phase7_qa/results/itinerary_01.json` … `itinerary_20.json` |

### Golden itinerary composition

Generated once by the real scheduler (`poi_search_logic()` → `itinerary_builder_logic()` — the same functions the live agent calls), then reused unmodified as the fixed reference set for every subsequent QA round.

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

**Composition rationale:** 5 single-interest + 15 multi-interest (2-4 combined interests); 11 two-day + 9 three-day trips; all 3 pace tiers (relaxed/moderate/intensive) represented; every one of the app's 9 interest themes (food, history, culture, nature, art, shopping, architecture, family, religion) appears in at least 2 itineraries. This set underlies both Phase 1's 300 real edit commands and Phase 2's 300 real questions, plus the ~35 fresh-phrasing commands/questions in the post-fix recheck.

### Adversarial test suite run against the golden dataset

Every case below was run for real against the live app (real Gemini classifier calls, real RAG lookups) — none simulated. Grouped by what each class of test is designed to break.

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

**Totals:** 15 adversarial categories, spanning both the edit surface (Phase 1: 300 real commands across the 20 golden itineraries) and the question/explain surface (Phase 2: 300 real questions across the same 20 itineraries), plus a further ~35 fresh, differently-phrased commands/questions in the post-fix recheck. Full transcripts: `phase7_qa/results/itinerary_*.json`, `phase7_qa/results/phase2_itinerary_*.json`, `phase7_qa/results/_recheck_log.json`.

---

## 1. Voice UX & Intent Handling — 25%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| STT/TTS pipeline quality & resilience | 20% | 95/100 | Groq Whisper (`whisper-large-v3-turbo`) for STT, `edge-tts` neural voice for TTS with automatic `pyttsx3` fallback on failure (`phase3/stt.py`, `phase3/tts.py`). Mic timeout tuned down from ~25s to ~15s worst-case (R-4) after a real QA finding of accidental-click quota burn. Docked for being server-side capture only in the CLI path — a documented, deliberate limitation there, not a defect (the deployed web app itself uses `st.audio_input()`, capturing from the browser's own mic). |
| Conversational state machine correctness | 25% | 95/100 | `COLLECT → CLARIFY → CONFIRM → BUILD → PRESENT → DONE`, Phase 3 test suite `T-3.1`–`T-3.7` all pass (7/7), including a real fixed bug (agent stuck looping in CLARIFY once required fields were already known) and context-aware out-of-scope-city handling (R-12) that doesn't derail mid-conversation. |
| Intent classification accuracy, incl. adversarial robustness | 35% | 90/100 | 100% top-level EDIT/EXPLAIN/NEW_PLAN accuracy across the golden dataset's original 300-command run. But genuinely adversarial testing (Phase 2 QA + the post-fix recheck) found **3 distinct real misclassification bugs** via venue names colliding with the classifier's own vocabulary/brand associations — a question about "Make My Lagan" silently misrouted to `EDIT` (H3) and, separately, to `NEW_PLAN` (investigated and fixed same session); "add a nice place to **eat**" silently failing because "eat" wasn't a recognized synonym. All three fixed and verified (deterministic guard-function tests + live repro replays), but this shows classifier robustness against real venue-name collisions isn't inherently bulletproof — a structurally similar new name could surface a fresh instance. |
| Confirmation/safety UX for risky actions | 20% | 96/100 | Vague trip-wide edits ("make the whole trip more fun") are previewed and held pending, requiring explicit yes/no before committing (M2 fix) — verified live, and reconfirmed with fresh phrasing in the recheck; an already-changed-stop removal gets a transparent explanation instead of a bare "couldn't find" (L1 fix). |
| **Category score** | | **93.5 / 100** | Weighted: 95×0.20 + 95×0.25 + 90×0.35 + 96×0.20 |

---

## 2. MCP Usage & System Design — 20%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| MCP tool definition correctness | 25% | 90/100 | 4 real `FastMCP` servers with `@mcp.tool()`-decorated functions — `poi_search.py`, `itinerary_builder.py`, `travel_time.py`, `weather.py` (`phase2/`). Tested via Phase 2's own suite (7/7, including a dedicated "Bonus Travel Time + Weather" check). |
| Actual runtime MCP protocol usage | 30% | 55/100 | **Real, honest gap:** the live conversational agent (`phase3/agent.py`) never invokes these tools through actual MCP client-server transport at runtime — it imports and calls the underlying `poi_search_logic()`/`itinerary_builder_logic()`/`weather_logic()` functions directly, in-process. This is a defensible engineering tradeoff for a single-process app (avoids stdio/SSE transport overhead), but it means MCP is present as a tool-definition/testing scaffold, not as an exercised protocol boundary in the live product. |
| System/module boundary design | 25% | 92/100 | Clean 6-phase layering with a consistent pattern: each phase exposes plain `_logic()` functions that both the MCP wrapper and the direct callers (Phase 3/4/5) share — no logic duplicated between the MCP tool and its consumer. `config.py` centralizes the LLM client (including 3-key rotation for rate-limit resilience); `phase4/feasibility.py`'s `check_feasibility()` is explicitly reused by Phase 5 rather than reimplemented. |
| Redundancy / duplication avoidance | 20% | 78/100 | One real duplication found during this evaluation: `phase2/travel_time.py` defines and tests a dedicated `travel_time_estimator` MCP tool, but `phase2/itinerary_builder.py` has its own separate, inline `_travel_time_min()`/`_travel_mode()` implementation and never calls the MCP tool — meaning the dedicated tool is built and tested but not actually consumed by the pipeline it appears designed for. |
| **Category score** | | **77.6 / 100** | Weighted: 90×0.25 + 55×0.30 + 92×0.25 + 78×0.20 |

---

## 3. Grounding & RAG Quality — 15%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| Retrieval pipeline quality | 20% | 90/100 | Multilingual embedding model (`paraphrase-multilingual-MiniLM-L12-v2`), sentence-aware overlapping chunking, two real scraped sources (Wikivoyage + Wikipedia) merged with a third curated source (`delhi_tourist_venues_kb.md`, 50 venues) into one 197-chunk ChromaDB corpus with a parallel citation index. |
| Relevance thresholding / noise filtering | 20% | 88/100 | `RELEVANCE_THRESHOLD = 0.45`, empirically calibrated (on-topic hits ~0.5–0.75, noise tops out ~0.35). Real, working — but its limitations directly caused two documented bugs needing dedicated fixes: feasibility/safety queries falling below threshold despite the corpus covering them (R-17/R-20 keyword-routing fixes), and KB-sourced facts scoring only ~0.29 against a bare venue-name query (H2's root cause, fixed by bypassing RAG for structured-data questions). |
| Citation authenticity | 20% | 100/100 | 0 of 300 real Phase 2 questions produced a citation pointing to a URL absent from the 197-entry citation index — 100% citation authenticity, verified via `check_grounding()`. |
| Honest fallback on missing/insufficient data | 25% | 95/100 | `NO_SOURCE_TEXT` honest-decline mechanism; H1 fix closed a real gap where a denial was still labeled `grounded: True` with citations attached (82/300 real cases → 0/300 post-fix); L1 fix added retry + graceful fallback for rare empty LLM completions. |
| Direct-answer from structured data (bypassing unreliable RAG) | 15% | 92/100 | H2/M2 fix: cost/best-time/suitability questions about a stop carrying real `kb_*` fields now answer directly from that data with a real citation, instead of depending on RAG similarity scoring — 21/21 real previously-missed cases now correctly answered. |
| **Category score** | | **93.15 / 100** | Weighted: 90×0.20 + 88×0.20 + 100×0.20 + 95×0.25 + 92×0.15 |

---

## 4. AI Evals & Iteration Depth — 20%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| Automated eval suite coverage | 20% | 96/100 | Dedicated `phase5/` suite — Feasibility, Edit Correctness, and Grounding evals, `T-5.1`–`T-5.8`, 8/8 passing; reused (not reimplemented) by Phase 3's post-build/post-edit hooks and Phase 4's own edit-guard. |
| Adversarial/QA test depth | 25% | 98/100 | Team Waypoint's two full QA phases: 300 real edit commands (Phase 1) + 300 real questions (Phase 2), across the 20 golden itineraries above, spanning 15 distinct adversarial categories (known-absent places, invalid days, vague/no-referent commands, hallucination traps, unanswerable questions, two independent venue-name/classifier-vocabulary collisions, denial-disguised-as-grounded answers, unbookable recommendations, unused structured data, crash resilience) — plus a further ~35 freshly-phrased commands/questions in the post-fix recheck. All real, end-to-end LLM calls, none mocked. |
| Fix-then-verify discipline | 20% | 97/100 | Every fix in this project's QA history is verified by replaying real recorded data or making fresh live calls — never "should work" by inspection alone. Examples: H1's fix checked against all 82 real recorded failure cases; H2's fix checked against all 21; M1's caveat heuristic checked against all 24 flagged cases plus a 20-answer false-positive sweep. |
| Iteration/recheck discipline | 20% | 95/100 | A dedicated recheck round re-tested all 13 prior fixes with **fresh, non-identical** commands specifically to catch narrow special-casing — it found and transparently corrected 2 false alarms in its own check logic, found and fixed 2 new small generalization gaps, and surfaced a distinct new issue (NEW_PLAN misclassification) that was then independently investigated (root-caused via a controlled fabricated-name experiment) and fixed in a follow-up round. |
| Documentation of findings | 15% | 95/100 | Every finding across both phases is recorded with severity (High/Medium/Low), root cause, evidence citation, fix location, and verification method in `Itinerary edit commands QA.md` (1,700+ lines) — plus the dedicated Golden Dataset & rubric document scoring the shipped product against real run data. |
| **Category score** | | **96.35 / 100** | Weighted: 96×0.20 + 98×0.25 + 97×0.20 + 95×0.20 + 95×0.15 |

---

## 5. Workflow Automation — 10%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| End-to-end pipeline orchestration | 40% | 90/100 | `phase1/main.py` is a real, flag-controllable 8-step orchestrator (scrape → venues-KB ingestion → chunk → embed → POI fetch → Wikidata enrich → venues-KB POI enrich → validate). `phase7_qa/`'s QA harness is itself a fully automated run → analyze → generate-doc pipeline, reused unchanged across every QA round in this project. |
| Delivery automation | 35% | 90/100 | `phase6/delivery.py` orchestrates `.pdf` generation (`reportlab`-based) + a two-path email send + local save + download fallback in one call. The two-path send (`send_email_via_n8n()` tried first, `send_email_with_attachment()`/SMTP only invoked if that fails) gives automatic failover instead of a single point of failure, still gracefully no-op'ing to local-save-only if neither is configured. |
| External workflow-tool integration | 25% | 90/100 | A live n8n.cloud workflow (Webhook → Convert-to-File → Send Email) receives a JSON POST (`to_email`, `subject`, `filename`, `pdf_base64`) from `send_email_via_n8n()` and delivers the actual generated PDF by email. Verified three ways: (1) a direct call to `send_email_via_n8n()` returning `sent: True`; (2) the full `deliver_itinerary()` path completing with no SMTP fallback triggered; (3) on the deployed Cloud app, a real n8n Execution timestamped to match an actual "Send itinerary" button click, with the email confirmed received. Docked from a perfect score for two real, honestly-reportable rough edges: the correct payload shape (JSON+base64, not multipart) was only discovered by reading a real n8n stack trace after a first attempt failed, and one execution reported "success" with a delayed email arrival rather than an immediate one — external-service flakiness the SMTP fallback exists specifically to hedge against. |
| **Category score** | | **90.0 / 100** | Weighted: 90×0.40 + 90×0.35 + 90×0.25 |

---

## 6. Deployment & Code Quality — 10%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| Deployment readiness | 30% | 90/100 | The app is live on Streamlit Community Cloud (`phase6/app.py` as entrypoint), verified not just by "it loads" but by full functional smoke tests run directly against the live URL with a real browser (Playwright): building an itinerary, asking a question, editing a stop, recording+transcribing a voice clip via a fake-mic device, moving a stop up/down, and sending/receiving a real email — all confirmed working on the actual deployment. Real deployment-specific engineering went into getting there: a root-level `requirements.txt` scoped to what the live app actually needs (excluding phase1's offline-indexing deps and the server-side-mic/local-speaker packages that can't work on a remote host), a `.streamlit/config.toml` duplicated to repo root (Cloud only reads config from root, not next to a subdirectory entrypoint), and a `st.secrets`→`os.environ` bootstrap so Cloud's secrets dashboard reaches the existing `os.getenv()`-based config. Docked from a perfect score for two real deploy failures hit and fixed along the way (a stale `phase6/requirements.txt` still containing `pyaudio`/`pygame` shadowed the root one; a stale partial-sync after one push needed a manual "Reboot app") and for no containerization (no Dockerfile) — fine for Community Cloud specifically, but a real gap if portability to another host mattered. |
| Version control / CI practices | 20% | 60/100 | Git is initialized with a real GitHub repo (`ShantanuNoida/delhi-travel-planner`, public) and genuine commit history — 10 commits with substantive, why-focused messages (initial commit, Cloud deploy prep, a build-failure fix, bug fixes, the voice-input rework, the docx→pdf migration, the n8n integration). One real near-miss along the way: GitHub's own push protection blocked the initial commit for a live API key accidentally left in a `.env.example` file, which had to be scrubbed from history before the push succeeded — a good outcome, but caught by GitHub's platform safeguard, not by anything the project itself had in place proactively. Still a real, honestly-scored gap: no CI pipeline (no GitHub Actions, no test-on-push), no branches (all 10 commits are directly on `master`), and no PR/code-review trail. |
| Test coverage & passing state | 25% | 98/100 | Every one of the 6 phases has a dedicated, currently-passing test suite: Phase 1 6/6, Phase 2 7/7, Phase 3 7/7 (agent) + 4/4 (narrator), Phase 4 6/6, Phase 5 8/8, Phase 6 5/5 — all reconfirmed clean as of this session's changes, including Phase 6's tests being migrated to verify the PDF output (via `pypdf` text extraction) rather than the retired `.docx` path. Tests are real end-to-end runs against live functions, not isolated mocks. |
| Code organization & documentation | 25% | 95/100 | Consistent module boundaries, centralized config, and an unusually disciplined comment style — every non-obvious decision is documented inline with the *why* (often citing the specific QA/live-usage finding that drove it), not just the *what*. Every phase (1–6) has its own `requirements.txt`, plus a root-level `requirements.txt` for deployment with its own inline rationale for what it deliberately excludes and why. |
| **Category score** | | **87.25 / 100** | Weighted: 90×0.30 + 60×0.20 + 98×0.25 + 95×0.25 |

---

## Overall Weighted Score

| Category | Category score | Weight | Contribution |
|---|---:|---:|---:|
| Voice UX & Intent Handling | 93.5 | 25% | 23.38 |
| MCP Usage & System Design | 77.6 | 20% | 15.52 |
| Grounding & RAG Quality | 93.15 | 15% | 13.97 |
| AI Evals & Iteration Depth | 96.35 | 20% | 19.27 |
| Workflow Automation | 90.0 | 10% | 9.00 |
| Deployment & Code Quality | 87.25 | 10% | 8.73 |
| **Overall** | | **100%** | **89.9 / 100** |

---

## Interpretation

**Overall: 89.9 / 100.** The score is intentionally uneven across categories, and that unevenness is the honest finding, not noise:

- **Strongest: AI Evals & Iteration Depth (96.35) and Voice UX/Grounding (93.5 / 93.15).** This is where the project's actual effort concentrated — two full rounds of real, adversarial, end-to-end QA against 600 real commands/questions on the golden dataset above, a dedicated fresh-command recheck that caught its own false positives *and* real new gaps, and every single fix verified against real recorded or live data rather than trusted on inspection.
- **Solid: Workflow Automation (90.0) and Deployment & Code Quality (87.25).** Both are backed by real, verified infrastructure rather than a documented absence: n8n is a genuinely working, tried-first delivery path (with SMTP retained as an automatic fallback), confirmed via matching execution logs on the live deployed app; the app itself is live on Streamlit Community Cloud, verified via full functional Playwright smoke tests against the real URL. Neither category is a clean 100 — the n8n setup needed real debugging (a payload-shape mismatch only surfaced via a raw stack trace, one execution that "succeeded" with delayed delivery) and the deploy process hit two real failures en route (a stale requirements file, a stuck partial redeploy needing a manual reboot).
- **Weakest: MCP Usage & System Design (77.6).** The gap is specific: the live conversational agent still calls `poi_search_logic()`/`itinerary_builder_logic()`/`weather_logic()` directly in-process rather than through actual MCP client-server transport, and `travel_time.py`'s dedicated MCP tool still isn't the code path `itinerary_builder.py` actually uses. A real, addressable gap for a future round.
- **Version control is a partial gap, honestly scored (60/100 on its sub-line, within Deployment & Code Quality):** a real git history and a public GitHub repo exist (10 substantive commits, and a close call with a leaked key caught by GitHub's push protection rather than an internal safeguard), but there's no CI pipeline and no branching — version control is real; CI practices are not yet.

A flat high score across every category would have been easy to write and would have hidden exactly this pattern — real strength concentrated in evaluation/QA rigor, voice/grounding correctness, and working delivery/deployment infrastructure, with one clearly identifiable, specific gap in MCP's runtime usage rather than diffuse weakness everywhere.

---

*Compiled by Team Waypoint from the real codebase, live test runs, and the project's own QA history (`Itinerary edit commands QA.md`).*
