# Itinerary edit commands QA

**Team Waypoint** — Multi-Agent QA System, Phase 1 deliverable

## Team & Roles

| Agent | Role | Responsibility in this run |
|---|---|---|
| Agent 1 | Team Leader / Coordinator | Named the team, enforced the Agent 2 → 3 → 4 → 5 execution order, verified each stage completed before the next began, and confirms Phase 1 completion below. |
| Agent 2 | Itinerary Generator | Built 20 real New Delhi itineraries via the app's actual scheduler (`phase2/itinerary_builder.py` + `phase2/poi_search.py`) — no fabricated content, every stop is a real POI from the app's live dataset. |
| Agent 3 | Edit Command Agent | Designed 15 commands per itinerary (300 total), tailored to each itinerary's real day count and content, and applied every one through the app's real, Gemini-backed intent classifier (`phase4/intent_classifier.py`) and edit engine (`phase4/edit_engine.py`), cumulatively, as a real editing session. |
| Agent 4 | Quality Manager / Product Manager | Evaluated all 300 real application responses, cross-checked them against the app's own eval suite (`phase5/edit_correctness.py`, `phase4/feasibility.py`), and identified loopholes, inaccuracies, and prioritized fixes. |
| Agent 5 | Documentation Agent | Compiled this document from the raw run logs and Agent 4's analysis. |

## How this run was executed

This was **not** a simulated or hand-written exercise — every itinerary and every edit response in this document came from actually running the real application code:

- **Itinerary generation**: `poi_search_logic()` → `itinerary_builder_logic()`, the same functions the live conversational agent (Phase 3) calls, against the real 5,078-POI New Delhi dataset.
- **Edit commands**: each of the 300 commands was sent to `classify_intent()` (Gemini `gemini-flash-lite-latest`, the same model and prompt the live app uses) to parse it into a structured edit, then `apply_edit()` executed it — identical to what happens when a real user edits their itinerary in the app.
- **Cumulative sessions**: all 15 commands for a given itinerary were applied in sequence to the evolving itinerary state (not independently to the original) — exactly like a real back-and-forth editing conversation.
- **Automated cross-checks**: after every edit, the app's own `check_edit_correctness()` (scope-drift detector) and `check_feasibility()` (budget/travel-time guard) were run against the result, the same safety nets the live app runs.

Harness code: `phase7_qa/run_qa.py`, `phase7_qa/itinerary_specs.py`, `phase7_qa/edit_commands.py`. Raw per-itinerary logs (full before/after itinerary state for all 15 steps): `phase7_qa/results/itinerary_01.json` … `itinerary_20.json`.

---
