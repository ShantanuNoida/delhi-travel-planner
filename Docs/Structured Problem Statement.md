# Voice-First AI Travel Planning Assistant
## Structured Problem Statement

---

## 1. Project Overview

**Domain:** Generative AI — Voice-Based Conversational Planning  
**Scope:** Single city (New Delhi), 2–4 day itinerary  
**Deployment:** Publicly accessible URL (deployed prototype)

### Core Objective
Build a voice-first AI travel planning assistant that:
- Understands spoken trip requests
- Generates realistic, grounded day-wise itineraries
- Allows itinerary edits via voice
- Explains its decisions with citations
- Delivers a PDF itinerary via email through an n8n workflow

### The Problem Being Solved
People don't struggle to find places to visit — they struggle to turn preferences, time constraints, travel effort, weather, and personal pace into a *doable* plan. This system solves that gap conversationally.

---

## 2. Goals

### G1 — Voice-Based Trip Planning
- Accept spoken inputs (e.g., *"Plan a 3-day trip to Jaipur next weekend. I like food and culture, relaxed pace."*)
- Ask clarifying questions only when necessary (max 6 questions)
- Confirm all constraints before generating the itinerary

### G2 — Voice-Based Itinerary Editing
- Accept spoken edit commands (e.g., *"Make Day 2 more relaxed"*, *"Add one famous local food place"*)
- Modify only the affected section — no unintended changes to other days or slots

### G3 — Explainable Recommendations
- Answer questions like *"Why did you pick this place?"*, *"Is this plan doable?"*, *"What if it rains?"*
- All explanations must be grounded in data, not generic filler

### G4 — Grounded Data (No Hallucination)
- POIs must map back to OpenStreetMap dataset records
- Travel tips must cite RAG sources (Wikivoyage / Wikipedia)
- System must explicitly state when data is missing

### G5 — Automated PDF Delivery
- An n8n workflow must generate a formatted PDF of the itinerary and email it to the user

---

## 3. Functional Requirements

### 3.1 Voice Interface
| Requirement | Detail |
|---|---|
| Input method | Speech-to-text (STT required) |
| Interaction style | Conversational; clarifying questions capped at 6 |
| Edit commands | Voice-driven, slot-level granularity |
| Live feedback | Live transcript shown in UI |

### 3.2 Itinerary Structure
| Requirement | Detail |
|---|---|
| Format | Day-wise (Day 1, Day 2, …) |
| Time blocks | Morning / Afternoon / Evening |
| Metadata per stop | Duration + estimated travel time to next stop |
| City constraint | New Delhi only |
| Length | 2–4 days max |

### 3.3 Companion UI
| UI Element | Purpose |
|---|---|
| Day-wise itinerary view | Display Morning / Afternoon / Evening blocks |
| Travel time between stops | Show estimated transit durations |
| Microphone button + live transcript | Voice input control |
| Sources / References section | Cite where each tip or POI came from |

---

## 4. Technical Requirements

### 4.1 Data Sources
| Source | Used For |
|---|---|
| OpenStreetMap (Overpass API) | Points of Interest (POIs) |
| Wikivoyage / Wikipedia | City guides, travel tips, area descriptions |
| Open-Meteo API *(bonus)* | Weather forecasts |

**Rules:**
- POIs must be traceable to OSM records
- Tips must come from RAG-indexed sources
- Missing data must be acknowledged explicitly — never fabricated

### 4.2 MCP Integration (Minimum 2 tools)

**Required MCP Tools:**

| Tool | Inputs | Outputs |
|---|---|---|
| POI Search MCP | city, interests, constraints | Ranked POIs with metadata |
| Itinerary Builder MCP | candidate POIs, daily time window, pace | Structured day-wise itinerary |

**Bonus MCP Tools:**
- Travel Time Estimator MCP
- Weather Adjustment MCP

MCP calls must be clearly demonstrable in the project demo.

### 4.3 RAG Requirements
RAG must be used for:
- Practical city guidance (areas to visit, safety, etiquette)
- Explanations and justifications for recommendations

**Rules:**
- All factual tips must carry citations
- No hallucinated claims permitted
- Voice explanations may be brief; full citations must appear in the UI

### 4.4 Infrastructure
| Requirement | Detail |
|---|---|
| LLM | LLM APIs (Claude / OpenAI) |
| Voice | Speech-to-text integration required |
| Version control | Git |
| Deployment | Publicly accessible URL |
| PDF + Email | n8n workflow |
| UI Builder | Lovable or Figma Make (or custom) |

---

## 5. AI Evaluations (Minimum 3 required)

### Eval 1 — Feasibility Check
- Daily itinerary duration ≤ available hours in the day
- Travel times are reasonable
- Pace is consistent with user's stated preference (relaxed / moderate / intensive)

### Eval 2 — Edit Correctness Check
- Voice edits modify only the intended day/slot
- No unintended changes appear elsewhere in the itinerary

### Eval 3 — Grounding & Hallucination Check
- POIs map to OSM dataset records
- Tips cite RAG sources
- Uncertainty is explicitly stated when data is missing

**Implementation:** Evals may be rule-based or LLM-assisted, but must be runnable programmatically.

---

## 6. Phase-wise Breakdown (Suggested)

### Phase 1 — Data & RAG Foundation
- Index Wikivoyage / Wikipedia content for New Delhi into a vector store
- Set up Overpass API client for OSM POI queries
- Validate data retrieval and citation pipeline

### Phase 2 — MCP Tool Layer
- Implement POI Search MCP tool
- Implement Itinerary Builder MCP tool
- (Bonus) Travel Time Estimator and Weather Adjustment MCPs

### Phase 3 — Conversational Voice Agent
- Build voice STT pipeline (microphone → transcript)
- Implement conversational planner (preference collection → clarifying questions → itinerary generation)
- Wire MCP tools into the agent's orchestration layer

### Phase 4 — Voice Editing & Explanations
- Implement slot-level voice edit commands
- Build explanation engine (grounded, RAG-backed, cited)
- Add "What if it rains?" and feasibility Q&A

### Phase 5 — Evaluations
- Implement Feasibility Eval
- Implement Edit Correctness Eval
- Implement Grounding & Hallucination Eval
- Make all evals runnable (automated)

### Phase 6 — UI & Delivery
- Build Companion UI (day-wise view, microphone, sources panel)
- Build n8n workflow: PDF generation → email to user
- Deploy to public URL

---

## 7. Constraints & Scope Limits

| Constraint | Value |
|---|---|
| City | New Delhi only |
| Itinerary length | 2–4 days max |
| Clarifying questions | Max 6 |
| Transit estimates | Heuristic (not real-time routing) |
| Focus | Quality of plan > breadth of coverage |

---

## 8. Success Criteria

| Goal | How It Is Verified |
|---|---|
| Voice input works end-to-end | Demo: spoken request → itinerary |
| Edits are slot-precise | Edit Correctness Eval passes |
| No hallucinations | Grounding Eval passes; citations visible in UI |
| Plan is realistic | Feasibility Eval passes |
| PDF delivered via email | n8n workflow demo |
| MCP tools are used | Visible in demo / logs (min 2 tools) |
| RAG citations present | Sources panel in UI |
| Deployed | Public URL accessible |
