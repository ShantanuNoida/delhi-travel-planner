# AI Evaluation Rubric — Voice-First AI Travel Planner (New Delhi)

Scored against the 6-category rubric provided, using real evidence from the codebase, test suites, and Team Waypoint's QA rounds (`Itinerary edit commands QA.md`, `Golden-Dataset-and-Evaluation-Rubric.md`). Every score below cites the specific file, test, or run it's based on — including honest, low scores where the project made a deliberate scope tradeoff (deployment, external workflow tooling) or where a real gap was found (MCP runtime usage, version control). A rubric that only ever scores high isn't a credible rubric.

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

## 1. Voice UX & Intent Handling — 25%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| STT/TTS pipeline quality & resilience | 20% | 95/100 | Groq Whisper (`whisper-large-v3-turbo`) for STT, `edge-tts` neural voice for TTS with automatic `pyttsx3` fallback on failure (`phase3/stt.py`, `phase3/tts.py`). Mic timeout tuned down from ~25s to ~15s worst-case (R-4) after a real QA finding of accidental-click quota burn. Docked for being server-side capture only — a documented, deliberate limitation for this project's local-only scope, not a defect. |
| Conversational state machine correctness | 25% | 95/100 | `COLLECT → CLARIFY → CONFIRM → BUILD → PRESENT → DONE`, Phase 3 test suite `T-3.1`–`T-3.7` all pass (7/7), including a real fixed bug (agent stuck looping in CLARIFY once required fields were already known) and context-aware out-of-scope-city handling (R-12) that doesn't derail mid-conversation. |
| Intent classification accuracy, incl. adversarial robustness | 35% | 90/100 | 100% top-level EDIT/EXPLAIN/NEW_PLAN accuracy across Phase 1's original 300-command run. But genuinely adversarial testing (Phase 2 QA + the post-fix recheck) found **3 distinct real misclassification bugs** via venue names colliding with the classifier's own vocabulary/brand associations — a question about "Make My Lagan" silently misrouted to `EDIT` (H3) and, separately, to `NEW_PLAN` (investigated and fixed same session); "add a nice place to **eat**" silently failing because "eat" wasn't a recognized synonym. All three fixed and verified (deterministic guard-function tests + live repro replays), but this shows classifier robustness against real venue-name collisions isn't inherently bulletproof — a structurally similar new name could surface a fresh instance. |
| Confirmation/safety UX for risky actions | 20% | 96/100 | Vague trip-wide edits ("make the whole trip more fun") are previewed and held pending, requiring explicit yes/no before committing (M2 fix) — verified live, and reconfirmed with fresh phrasing in the recheck; an already-changed-stop removal gets a transparent explanation instead of a bare "couldn't find" (L1 fix). |
| **Category score** | | **93.5 / 100** | Weighted: 95×0.20 + 95×0.25 + 90×0.35 + 96×0.20 |

---

## 2. MCP Usage & System Design — 20%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| MCP tool definition correctness | 25% | 90/100 | 4 real `FastMCP` servers with `@mcp.tool()`-decorated functions — `poi_search.py`, `itinerary_builder.py`, `travel_time.py`, `weather.py` (`phase2/`). Tested via Phase 2's own suite (7/7, including a dedicated "Bonus Travel Time + Weather" check). |
| Actual runtime MCP protocol usage | 30% | 55/100 | **Real, honest gap:** the live conversational agent (`phase3/agent.py`) never invokes these tools through actual MCP client-server transport at runtime — it imports and calls the underlying `poi_search_logic()`/`itinerary_builder_logic()`/`weather_logic()` functions directly, in-process. This is a defensible engineering tradeoff for a single-process local app (avoids stdio/SSE transport overhead), but it means MCP is present as a tool-definition/testing scaffold, not as an exercised protocol boundary in the live product. |
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
| Adversarial/QA test depth | 25% | 98/100 | Team Waypoint's two full QA phases: 300 real edit commands (Phase 1) + 300 real questions (Phase 2), across 20 golden itineraries, spanning 15 distinct adversarial categories (known-absent places, invalid days, vague/no-referent commands, hallucination traps, unanswerable questions, two independent venue-name/classifier-vocabulary collisions, denial-disguised-as-grounded answers, unbookable recommendations, unused structured data, crash resilience) — plus a further ~35 freshly-phrased commands/questions in the post-fix recheck. All real, end-to-end LLM calls, none mocked. |
| Fix-then-verify discipline | 20% | 97/100 | Every fix in this project's QA history is verified by replaying real recorded data or making fresh live calls — never "should work" by inspection alone. Examples: H1's fix checked against all 82 real recorded failure cases; H2's fix checked against all 21; M1's caveat heuristic checked against all 24 flagged cases plus a 20-answer false-positive sweep. |
| Iteration/recheck discipline | 20% | 95/100 | A dedicated recheck round re-tested all 13 prior fixes with **fresh, non-identical** commands specifically to catch narrow special-casing — it found and transparently corrected 2 false alarms in its own check logic, found and fixed 2 new small generalization gaps, and surfaced a distinct new issue (NEW_PLAN misclassification) that was then independently investigated (root-caused via a controlled fabricated-name experiment) and fixed in a follow-up round. |
| Documentation of findings | 15% | 95/100 | Every finding across both phases is recorded with severity (High/Medium/Low), root cause, evidence citation, fix location, and verification method in `Itinerary edit commands QA.md` (1,700+ lines) — plus a dedicated Golden Dataset & rubric document scoring the shipped product against real run data. |
| **Category score** | | **96.35 / 100** | Weighted: 96×0.20 + 98×0.25 + 97×0.20 + 95×0.20 + 95×0.15 |

---

## 5. Workflow Automation — 10%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| End-to-end pipeline orchestration | 40% | 90/100 | `phase1/main.py` is a real, flag-controllable 8-step orchestrator (scrape → venues-KB ingestion → chunk → embed → POI fetch → Wikidata enrich → venues-KB POI enrich → validate). `phase7_qa/`'s QA harness is itself a fully automated run → analyze → generate-doc pipeline, reused unchanged across every QA round in this project. |
| Delivery automation | 35% | 85/100 | `phase6/delivery.py` orchestrates `.docx` generation + SMTP email + local save + download fallback in one call, gracefully no-op'ing email when SMTP isn't configured rather than failing the whole flow. Solid, but entirely bespoke Python — not built on any dedicated automation platform. |
| External workflow-tool integration | 25% | 20/100 | **Explicitly, deliberately absent.** n8n was evaluated and consciously rejected (documented reasoning: it requires an external account, judged out of scope) in favor of local Python delivery. A defensible scope decision for a local-only capstone — but on a rubric line item literally titled "Workflow Automation," there is no external orchestration/automation-platform integration to score. |
| **Category score** | | **70.75 / 100** | Weighted: 90×0.40 + 85×0.35 + 20×0.25 |

---

## 6. Deployment & Code Quality — 10%

| Sub-criterion | Sub-weight | Score | Evidence |
|---|---:|---:|---|
| Deployment readiness | 30% | 15/100 | Explicitly local-only by scope decision — "Step 6.5 (public URL, deployment)" was deliberately deferred and documented as such. No Dockerfile, no hosting config, no reverse proxy/TLS setup; the app only runs via `streamlit run app.py` on `localhost`. Honest and consciously scoped, but a real, low score on this specific axis. |
| Version control / CI practices | 20% | 10/100 | **Real gap:** the project directory is not a git repository at all (`git status` → "fatal: not a git repository"). No commit history, no branching, no code review trail, and consequently no CI pipeline is possible. For a multi-week, multi-phase project with this much iteration, the absence of version control is a genuine process gap, not a scope choice. |
| Test coverage & passing state | 25% | 98/100 | Every one of the 6 phases has a dedicated, currently-passing test suite: Phase 1 6/6, Phase 2 7/7, Phase 3 7/7 (agent) + 4/4 (narrator), Phase 4 6/6, Phase 5 8/8, Phase 6 5/5 — all reconfirmed clean as of this session's changes. Tests are real end-to-end runs against live functions, not isolated mocks. |
| Code organization & documentation | 25% | 92/100 | Consistent module boundaries, centralized config, and an unusually disciplined comment style — every non-obvious decision is documented inline with the *why* (often citing the specific QA finding that drove it), not just the *what*. Minor deduction: `requirements.txt` exists for Phases 1–3 but not Phases 4–6. |
| **Category score** | | **54.0 / 100** | Weighted: 15×0.30 + 10×0.20 + 98×0.25 + 92×0.25 |

---

## Overall Weighted Score

| Category | Category score | Weight | Contribution |
|---|---:|---:|---:|
| Voice UX & Intent Handling | 93.5 | 25% | 23.38 |
| MCP Usage & System Design | 77.6 | 20% | 15.52 |
| Grounding & RAG Quality | 93.15 | 15% | 13.97 |
| AI Evals & Iteration Depth | 96.35 | 20% | 19.27 |
| Workflow Automation | 70.75 | 10% | 7.08 |
| Deployment & Code Quality | 54.0 | 10% | 5.40 |
| **Overall** | | **100%** | **84.6 / 100** |

---

## Interpretation

**Overall: 84.6 / 100.** The score is intentionally uneven across categories, and that unevenness is the honest finding, not noise:

- **Strongest: AI Evals & Iteration Depth (96.35) and Voice UX/Grounding (93.5 / 93.15).** This is where the project's actual effort concentrated — two full rounds of real, adversarial, end-to-end QA against 600 real commands/questions, a dedicated fresh-command recheck that caught its own false positives *and* real new gaps, and every single fix verified against real recorded or live data rather than trusted on inspection.
- **Mid: MCP Usage & System Design (77.6) and Workflow Automation (70.75).** Both categories contain genuinely good work (clean module boundaries, a real automated QA harness, a working delivery pipeline) alongside one clear, specific, honestly-scored gap each — MCP tools defined but not exercised via real protocol transport at runtime, and no external workflow-automation platform (a conscious scope decision, documented at the time it was made).
- **Weakest: Deployment & Code Quality (54.0)**, driven almost entirely by two items on a 4-item sub-rubric: no public deployment (a documented scope decision) and no version control at all (not a scope decision — a real process gap for a project this size). Test coverage and code organization, the other two sub-criteria in this same category, both score in the low-to-mid 90s.

A flat high score across every category would have been easy to write and would have hidden exactly this pattern — real strength concentrated in evaluation/QA rigor and voice/grounding correctness, with clearly identifiable, specific gaps in infrastructure maturity (MCP runtime usage, workflow tooling, deployment, version control) rather than diffuse weakness everywhere.

---

*Compiled by Team Waypoint from the real codebase, live test runs, and the project's own QA history (`Itinerary edit commands QA.md`, `Golden-Dataset-and-Evaluation-Rubric.md`).*
