# Voice-First AI Travel Planner
## Phase-wise Architecture & Action Plan

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Voice Input)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Speech
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              AGENT 1 — Conversation Agent (Orchestrator)         │
│   STT → Transcript → State Machine (COLLECT/CLARIFY/CONFIRM)    │
│   Owns: user-facing conversation, TTS, session state            │
└────────┬──────────────────────────────┬──────────────────────────┘
         │ TripContext / EditIntent      │ Explanation query
         ▼                              ▼
┌─────────────────────┐      ┌──────────────────────────────────┐
│  AGENT 2            │      │  AGENT 3                          │
│  Planning & Editing │      │  Knowledge & Eval                 │
│                     │      │                                   │
│  • POI Search MCP   │      │  • RAG retrieval (Vector Store)   │
│  • Itin Builder MCP │      │  • Citation lookup                │
│  • Travel Time MCP  │      │  • Feasibility Eval (Python)      │
│  • Edit Engine      │      │  • Edit Correctness Eval (Python) │
│                     │      │  • Grounding Eval (index lookup)  │
│  Returns:           │      │                                   │
│  itinerary JSON ───────────▶ triggers eval run                 │
└──────────┬──────────┘      └──────────────┬─────────────────────┘
           │ itinerary JSON                  │ eval results + citations
           └──────────────┬──────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER                                   │
│  OpenStreetMap (Overpass API) │ Wikivoyage/Wikipedia │ Open-Meteo│
└──────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        COMPANION UI                              │
│    Day-wise Itinerary │ Mic Button │ Transcript │ Sources Panel  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     n8n WORKFLOW                                  │
│                PDF Generation → Email Delivery                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Multi-Agent Design

The system uses three agents. Each has a single, non-overlapping responsibility. Agent 1 is the only one allowed to be slow — it holds a conversation. Agents 2 and 3 must behave like fast function calls, not reasoning sessions.

### Agent Responsibilities

| | Agent 1 | Agent 2 | Agent 3 |
|---|---|---|---|
| **Name** | Conversation Agent | Planning & Editing Agent | Knowledge & Eval Agent |
| **Role** | Orchestrator | Itinerary builder / editor | RAG + evaluations |
| **Owns** | Conversation state, STT/TTS, session | Itinerary JSON, MCP tool calls | Vector store, citation index, all 3 evals |
| **Input** | User speech | `TripContext` or `EditIntent` JSON | Explanation query or itinerary JSON |
| **Output** | Spoken response to user | Updated itinerary JSON | Cited answer or eval verdict |
| **LLM calls** | Many (conversation) | ≤ 2 per session | 0–1 (evals are mostly rule-based) |
| **Introduced in** | Phase 3 | Phase 3 | Phase 4–5 |

---

### Communication Flow

```
User speaks
    │
    ▼
Agent 1 (Conversation)
    │
    ├── COLLECT / CLARIFY / CONFIRM states ──▶ responds to user via TTS
    │
    ├── On CONFIRM: sends TripContext ──────▶ Agent 2 (builds itinerary)
    │                                              │
    │                                              ├──▶ returns itinerary JSON
    │                                              │         │
    │                                              │         └──▶ Agent 3 runs evals
    │                                              │                   │
    │◀─────────────────────────────────────────────┘◀──────────────────┘
    │   itinerary JSON + eval results + citations
    │
    ├── On EDIT command: sends EditIntent ──▶ Agent 2 (modifies slot)
    │                                              │
    │                                              └──▶ Agent 3 re-runs evals
    │◀──────────────────────────────────────────────────────────────────┘
    │
    └── On EXPLAIN query: sends query ─────▶ Agent 3 (RAG + citation)
                                                   │
    Agent 1 speaks answer ◀────────────────────────┘
```

### Parallelism Benefit

After Agent 2 returns the itinerary JSON, Agent 3 runs its evals **concurrently** while Agent 1 is already reading the plan summary to the user. Eval results arrive before the user starts interacting — no added wait time.

```
t=0   Agent 2 finishes itinerary
t=0   Agent 1 starts reading summary aloud      ──┐ parallel
t=0   Agent 3 starts running evals              ──┘
t=2s  Agent 3 evals complete, results logged
t=4s  Agent 1 finishes speaking
      → UI renders itinerary + eval status simultaneously
```

---

### Keeping Agent 2 Fast & Narrow

| Strategy | Detail |
|---|---|
| No conversation history in context | Agent 1 passes only a structured `TripContext` or `EditIntent` JSON — no chat transcript |
| Minimal system prompt | Single job: "receive structured input → call MCP tools in order → return itinerary JSON" |
| MCP tools do the heavy lifting | Scheduling logic lives inside the MCP tools, not the LLM. Agent 2's LLM only decides which tool to call |
| Structured output only | JSON mode, temperature=0 — no free-form reasoning |
| Pre-loaded POI dataset | Dataset loaded into memory at server startup, not fetched per request |

Agent 2 should make at most **2 LLM calls per full plan** (one to invoke POI Search MCP, one to invoke Itinerary Builder MCP). For edits, one call to identify the right MCP tool with updated params.

---

### Keeping Agent 3 Fast & Narrow

| Strategy | Detail |
|---|---|
| Evals 1 & 2 are pure Python — no LLM | Feasibility check = arithmetic. Edit Correctness = JSON diff. Both run in milliseconds |
| Eval 3 is mostly rule-based | Grounding check = OSM ID dictionary lookup + citation index lookup. LLM only used as last resort for ambiguous cases |
| RAG retrieval is pre-indexed | Vector store built once in Phase 1; queried at runtime — no dynamic indexing during sessions |
| Top-K retrieval only | Agent 3 retrieves chunks and synthesizes a 2–3 sentence answer. No multi-hop reasoning |
| Temperature=0, JSON output | Returns `{ answer, citations[] }` — no prose deliberation |

---

### What Agent 1 Is Allowed to Do That Others Are Not

- Hold multi-turn conversation history in context
- Ask follow-up questions
- Use TTS to speak to the user
- Make judgment calls on ambiguous user input
- Queue and sequence edit commands (EC-4.5)

Agents 2 and 3 receive a single structured input and return a single structured output. They have no awareness of the conversation history.

---

## Phase 1 — Data & RAG Foundation

### What We Are Building
The data backbone of the system — the knowledge sources the assistant will draw from to answer questions and justify recommendations. Nothing is shown to the user yet; this is all backend groundwork.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     DATA SOURCES                          │
│                                                           │
│  ┌─────────────────────┐   ┌──────────────────────────┐  │
│  │ Wikivoyage / Wiki   │   │  OpenStreetMap (Overpass) │  │
│  │ New Delhi articles  │   │  POI records for Delhi    │  │
│  └────────┬────────────┘   └────────────┬─────────────┘  │
│           │                             │                 │
│           ▼                             ▼                 │
│  ┌─────────────────────┐   ┌──────────────────────────┐  │
│  │   Text Chunker      │   │   POI Normalizer          │  │
│  │ (split into chunks) │   │  (name, lat/lon, type,   │  │
│  └────────┬────────────┘   │   opening hours, tags)    │  │
│           │                └────────────┬─────────────┘  │
│           ▼                             ▼                 │
│  ┌─────────────────────┐   ┌──────────────────────────┐  │
│  │  Embedding Model    │   │   POI Data Store          │  │
│  │  (text → vectors)   │   │   (JSON / SQLite)         │  │
│  └────────┬────────────┘   └──────────────────────────┘  │
│           ▼                                               │
│  ┌─────────────────────┐                                  │
│  │   Vector Store      │                                  │
│  │  (ChromaDB /        │                                  │
│  │   Pinecone / FAISS) │                                  │
│  └─────────────────────┘                                  │
└──────────────────────────────────────────────────────────┘
```

### Action Steps

**Step 1.1 — Scrape & Collect Wikivoyage/Wikipedia Data**
- Download Wikivoyage article for "New Delhi" and its sub-pages (neighbourhoods, cuisine, transport, safety, etiquette)
- Download Wikipedia articles for major landmarks and areas in New Delhi
- Store raw text as `.txt` or `.json` files with source URL attached

**Step 1.2 — Chunk & Embed Text**
- Split articles into overlapping chunks (~300–500 tokens with ~50 token overlap)
- Embed each chunk using an embedding model (e.g., `text-embedding-3-small` or equivalent)
- Store embeddings in a vector store (ChromaDB for local dev; Pinecone for deployment)
- Attach metadata to each chunk: `{ source_url, article_title, chunk_index }`

**Step 1.3 — Set Up Overpass API Client**
- Write a Python client that queries the Overpass API for New Delhi POIs
- Query categories: restaurants, monuments, museums, parks, markets, temples, mosques, churches
- For each POI record, extract and normalize: `name`, `lat`, `lon`, `category`, `opening_hours`, `OSM ID`, `tags`
- Save normalized POIs to a local JSON file or SQLite database

**Step 1.4 — Validate the RAG Pipeline**
- Write a test query (e.g., *"What areas should I avoid at night in New Delhi?"*)
- Run retrieval → confirm top-K chunks are returned with correct source citations
- Verify OSM records can be queried by category and location bounding box

**Step 1.5 — Citation Index**
- For every chunk, record: `chunk_id → source_url + article_title`
- This index will be used in Phase 4 to display citations in the UI

**Edge Cases to address in this phase:** EC-1.1, EC-1.2, EC-1.3, EC-1.4, EC-1.5 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- Vector store populated with New Delhi travel content
- Normalized POI dataset (JSON/SQLite) sourced from OSM
- Citation index mapping each knowledge chunk to its source
- Validated retrieval: query → chunks → source URLs

---

### Phase 1 Summary
> **In simple terms:** We are teaching the system about New Delhi — filling its "library" with travel guides, landmark information, and a map of real places. When the assistant later says "Chandni Chowk is great for street food," it will have actually read that from a real travel guide, not guessed it. This phase is all about collecting, organizing, and testing that knowledge before building anything the user sees.

---

### Phase 1 Testing Plan

**T-1.1 — RAG Retrieval Quality**
- What: Vector store returns relevant, cited chunks for travel queries
- How: Run 5 test queries (e.g., "safe areas in Delhi", "best street food", "what to avoid at night") → inspect top-3 returned chunks for relevance and metadata completeness
- Pass: Each query returns ≥ 3 chunks with `source_url` and `article_title` populated; no chunk is shorter than 2 sentences

**T-1.2 — Citation Index Completeness**
- What: Every chunk in the vector store has a corresponding entry in the citation index
- How: Iterate over all chunk IDs in the vector store → look up each in the citation index → count misses
- Pass: 0 chunks with missing citation entries

**T-1.3 — OSM POI Dataset Coverage**
- What: Overpass API client returns POIs for all required categories in New Delhi
- How: Query each category (restaurants, monuments, museums, parks, markets, temples, mosques, churches) → count results per category
- Pass: Each category returns ≥ 10 POIs; every POI record has `name`, `lat`, `lon`, `osm_id`, and `category` populated

**T-1.4 — POI Opening Hours Handling**
- What: POIs with missing `opening_hours` are included but flagged, not silently dropped
- How: Identify 5 POIs in dataset with no `opening_hours` tag → verify they appear in dataset with `opening_hours: "unknown"`
- Pass: All POIs present; none silently excluded; `opening_hours: "unknown"` flag set correctly

**T-1.5 — Chunk Quality Check**
- What: No chunk splits mid-sentence or starts with a conjunction
- How: Sample 20 random chunks → inspect first and last sentence of each for coherence
- Pass: 0 chunks begin with "but", "however", "and", or end mid-word; all chunks ≥ 2 complete sentences

**T-1.6 — Multilingual Name Retrieval**
- What: Queries using Hindi transliterations return the same chunks as English equivalents
- How: Query "Humayun ka Makbara" and "Humayun's Tomb" → compare returned chunk sets
- Pass: Both queries return overlapping top-3 results (alias normalization working)

---

## Phase 2 — MCP Tool Layer

### What We Are Building
A set of specialized tools that the AI agent can call like functions. The agent doesn't know everything — it delegates specific jobs to these tools. This phase builds those tools and makes sure they return reliable, structured results.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      MCP TOOL LAYER                           │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │               Tool 1: POI Search MCP                 │     │
│  │                                                       │     │
│  │  Input:  { city, interests[], constraints{} }         │     │
│  │                    │                                  │     │
│  │                    ▼                                  │     │
│  │  ┌─────────────────────────────────────┐             │     │
│  │  │ Query OSM POI Dataset               │             │     │
│  │  │ Filter by: category, opening hours  │             │     │
│  │  │ Rank by: relevance to interests     │             │     │
│  │  └─────────────────────────────────────┘             │     │
│  │                    │                                  │     │
│  │  Output: [ { name, category, lat, lon,               │     │
│  │               osm_id, visit_duration,                 │     │
│  │               relevance_score } ]                     │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │            Tool 2: Itinerary Builder MCP             │     │
│  │                                                       │     │
│  │  Input:  { pois[], days, pace, daily_hours }          │     │
│  │                    │                                  │     │
│  │                    ▼                                  │     │
│  │  ┌─────────────────────────────────────┐             │     │
│  │  │ Bin POIs into days                  │             │     │
│  │  │ Assign to Morning/Afternoon/Evening │             │     │
│  │  │ Check total duration per day        │             │     │
│  │  │ Add travel time between stops       │             │     │
│  │  └─────────────────────────────────────┘             │     │
│  │                    │                                  │     │
│  │  Output: { day_1: { morning: [...],                  │     │
│  │                     afternoon: [...],                 │     │
│  │                     evening: [...] }, ... }           │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │        Tool 3: Travel Time Estimator MCP (Bonus)     │     │
│  │  Input:  { origin_coords, destination_coords }        │     │
│  │  Output: { estimated_minutes, mode: "auto/metro" }   │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │        Tool 4: Weather Adjustment MCP (Bonus)        │     │
│  │  Input:  { city, date_range }                         │     │
│  │  Output: { forecast[], outdoor_risk_flag }            │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Action Steps

**Step 2.1 — Define MCP Tool Schemas**
- Write the input/output JSON schema for each tool
- Tool schemas tell the LLM agent exactly what each tool accepts and returns
- Register tools with the MCP server or agent framework being used

**Step 2.2 — Build POI Search MCP**
- Load the normalized POI dataset (from Phase 1)
- Implement filtering logic: match user interests to POI categories (e.g., "food" → restaurants + markets; "culture" → museums + monuments)
- Implement ranking: sort POIs by relevance score (category match + popularity tags from OSM)
- Return top-N ranked POIs with all metadata fields

**Step 2.3 — Build Itinerary Builder MCP**
- Accept a list of candidate POIs and trip parameters (days, pace, available hours/day)
- Bin POIs into days using a simple scheduling algorithm:
  - Group geographically close POIs to minimize travel
  - Assign heavy visits (monuments, museums) to morning
  - Assign lighter visits (markets, food) to afternoon/evening
  - Cap total daily duration based on pace (relaxed: ~6h, moderate: ~8h, intensive: ~10h)
- Add heuristic travel time between consecutive stops (10–30 min depending on distance)
- Return a structured day-wise itinerary object

**Step 2.4 — Build Travel Time Estimator MCP (Bonus)**
- Accept two coordinate pairs
- Use a heuristic formula based on straight-line distance + a Delhi traffic multiplier
- Return estimated travel time in minutes and suggested mode (metro / auto)

**Step 2.5 — Build Weather Adjustment MCP (Bonus)**
- Call Open-Meteo API with city and date range
- Return daily forecast summary and flag outdoor-risk days (rain / extreme heat)
- Agent uses this to suggest indoor alternatives when needed

**Step 2.6 — Unit Test All Tools**
- Test each tool in isolation with sample inputs
- Verify output schemas are consistent and match what the agent expects
- Test edge cases: no POIs found, day-count = 1, pace = relaxed

**Edge Cases to address in this phase:** EC-2.1, EC-2.2, EC-2.3, EC-2.4, EC-2.5 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- 2 required MCP tools (POI Search, Itinerary Builder) — functional and tested
- 2 optional MCP tools (Travel Time Estimator, Weather Adjustment) — if building bonus
- Tool schema definitions registered with the agent framework

---

### Phase 2 Summary
> **In simple terms:** We are building the specialized "helpers" that the AI will use behind the scenes. One helper knows how to find the best places to visit (based on what you like). Another knows how to arrange those places into a logical day-by-day plan without overloading any single day. Think of these as the AI's internal tools — like a calculator it can call whenever it needs a specific job done precisely.

---

### Phase 2 Testing Plan

**T-2.1 — POI Search MCP: Interest Mapping**
- What: Tool returns relevant POIs when given user interest categories
- How: Call tool with `{ city: "New Delhi", interests: ["food", "culture"], constraints: {} }` → inspect returned POI list
- Pass: ≥ 10 POIs returned; categories include restaurants/markets (food) and museums/monuments (culture); each POI has `osm_id`, `lat`, `lon`, `relevance_score`

**T-2.2 — POI Search MCP: Zero Results Fallback**
- What: Tool handles niche interests gracefully without returning empty list
- How: Call tool with `{ interests: ["graffiti art", "underground music"] }` → verify fallback kicks in
- Pass: Tool returns general POIs with a fallback flag set; does not return an empty array

**T-2.3 — Itinerary Builder MCP: Day Structure**
- What: Tool produces a valid day-wise itinerary within time budget
- How: Call tool with 10 candidate POIs, `{ days: 2, pace: "relaxed", daily_hours: 6 }` → inspect output
- Pass: Output has exactly 2 days; each day has morning/afternoon/evening slots; total visit + travel time per day ≤ 6h

**T-2.4 — Itinerary Builder MCP: Geographic Clustering**
- What: POIs assigned to the same day are geographically close
- How: For each day in the output, compute max straight-line distance between consecutive stops → flag if > 15km
- Pass: No two consecutive stops within the same day are > 15km apart (Old Delhi and South Delhi not on the same day)

**T-2.5 — Itinerary Builder MCP: No Day Overflow**
- What: Builder never exceeds daily time budget regardless of how many POIs are passed
- How: Call tool with 20 POIs, pace=relaxed (6h cap) → measure total scheduled time per day
- Pass: Every day's total time ≤ 6h; excess POIs are dropped, not squeezed in

**T-2.6 — MCP Tool Schema Validation**
- What: Both tools reject malformed inputs and return descriptive errors
- How: Call each tool with missing required fields (e.g., no `city`, no `pois[]`) → inspect error responses
- Pass: Tools return structured error objects, not unhandled exceptions; agent can parse and surface the error

---

## Phase 3 — Conversational Voice Agent

### What We Are Building
The brain of the system — the AI agent that listens to the user, holds a conversation to collect trip details, and then calls the Phase 2 tools to produce an itinerary. This is where voice input, LLM reasoning, and MCP tools come together for the first time.

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    VOICE AGENT PIPELINE                        │
│                                                               │
│  User speaks                                                  │
│       │                                                       │
│       ▼                                                       │
│  ┌─────────────┐                                             │
│  │  STT Engine │  (e.g., Whisper API / Web Speech API)       │
│  └──────┬──────┘                                             │
│         │ transcript text                                     │
│         ▼                                                     │
│  ┌──────────────────────────────────────────────┐            │
│  │           CONVERSATIONAL AGENT (LLM)          │            │
│  │                                               │            │
│  │  State Machine:                               │            │
│  │  ┌──────────┐   ┌────────────┐   ┌────────┐  │            │
│  │  │ COLLECT  │──▶│  CLARIFY   │──▶│CONFIRM │  │            │
│  │  │ (listen) │   │ (ask ≤ 6Q) │   │& BUILD │  │            │
│  │  └──────────┘   └────────────┘   └───┬────┘  │            │
│  │                                       │       │            │
│  │                              ┌────────▼─────┐ │            │
│  │                              │  CALL MCP    │ │            │
│  │                              │  TOOLS       │ │            │
│  │                              └────────┬─────┘ │            │
│  └──────────────────────────────────────┼────────┘            │
│                                         │                     │
│         ┌───────────────────────────────┤                     │
│         │                               │                     │
│         ▼                               ▼                     │
│  ┌──────────────┐              ┌─────────────────┐            │
│  │ POI Search   │              │ Itinerary Builder│            │
│  │     MCP      │──────────────│      MCP         │            │
│  └──────────────┘              └────────┬─────────┘            │
│                                         │                     │
│                                         ▼                     │
│                              ┌─────────────────┐             │
│                              │  Itinerary JSON  │             │
│                              │  (structured     │             │
│                              │   day-wise plan) │             │
│                              └─────────────────┘             │
└───────────────────────────────────────────────────────────────┘
```

### Conversation State Machine

```
START
  │
  ▼
[COLLECT] ──── Agent listens to initial request
  │             Extracts: city, days, dates, interests, pace
  │
  ▼
[CLARIFY] ──── Agent identifies missing/ambiguous parameters
  │             Asks up to 6 clarifying questions one at a time
  │             e.g., "How many people are travelling?"
  │                   "Do you prefer mornings or evenings for sightseeing?"
  │
  ▼
[CONFIRM] ──── Agent summarizes collected constraints
  │             User confirms or corrects via voice
  │
  ▼
[BUILD]   ──── Agent calls POI Search MCP → Itinerary Builder MCP
  │             Returns structured itinerary
  │
  ▼
[PRESENT] ──── Agent reads out a summary of the plan
               UI displays full day-wise itinerary
```

### Action Steps

**Step 3.1 — Set Up STT Pipeline**
- Choose STT method: OpenAI Whisper API (accurate, async) or Web Speech API (browser-native, real-time)
- Wire microphone input → audio buffer → STT API → transcript text
- Test with noisy and accented speech; ensure transcript quality is acceptable

**Step 3.2 — Design the Agent System Prompt**
- Write the LLM system prompt that defines the agent's persona and rules:
  - Role: friendly travel planning assistant
  - Rules: ask ≤ 6 clarifying questions, always confirm before building, never hallucinate
  - Output format: structured JSON for tool calls, natural language for user responses
- Include the MCP tool definitions in the prompt/tool registry

**Step 3.3 — Implement the Conversation State Machine**
- Track conversation state: `COLLECT → CLARIFY → CONFIRM → BUILD → PRESENT`
- Use the LLM to determine which state to transition to based on what information is known
- Store collected parameters in a `TripContext` object:
  ```
  TripContext {
    city, num_days, travel_dates,
    interests[], pace, group_size,
    constraints{} (budget, accessibility, dietary)
  }
  ```

**Step 3.4 — Wire MCP Tools into the Agent**
- Register POI Search MCP and Itinerary Builder MCP as callable tools in the agent framework
- When the agent reaches the BUILD state, it automatically calls:
  1. POI Search MCP with `{ city, interests, constraints }`
  2. Itinerary Builder MCP with returned POIs + `{ days, pace }`
- Store the returned itinerary in session state

**Step 3.5 — Voice Output (TTS)**
- Convert agent text responses to speech using a TTS API (e.g., OpenAI TTS or browser Speech Synthesis)
- Agent reads out a brief spoken summary; full itinerary is shown in the UI

**Step 3.6 — End-to-End Test (Voice → Itinerary)**
- Run a full flow: speak a trip request → clarifying questions → confirm → itinerary generated
- Verify the MCP tools are actually called (check logs)
- Verify the itinerary JSON is correctly structured

**Edge Cases to address in this phase:** EC-3.1, EC-3.2, EC-3.3, EC-3.4, EC-3.5, EC-3.6, EC-X.3 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- Working STT pipeline (mic → transcript)
- LLM agent with conversation state machine
- MCP tools wired into agent — callable during BUILD state
- End-to-end test: voice input → structured itinerary output

---

### Phase 3 Summary
> **In simple terms:** This is where the assistant comes alive. It can now listen to you speak, have a real back-and-forth conversation to understand what kind of trip you want, and then produce a day-by-day plan. It's like talking to a travel agent over the phone — you tell it what you want, it asks a few smart follow-up questions, confirms the details, and hands you a plan. This is the core feature of the whole project.

---

### Phase 3 Testing Plan

**T-3.1 — STT Accuracy**
- What: Speech-to-text produces accurate transcripts for travel-domain vocabulary
- How: Record 10 spoken inputs covering place names (Red Fort, Chandni Chowk, Qutub Minar), pace words (relaxed, moderate), and numbers (3 days, 2 people) → compare STT output to ground truth
- Pass: ≥ 90% word accuracy on place names; no critical words (city, day count) are mis-transcribed

**T-3.2 — TripContext Extraction**
- What: Agent correctly extracts all parameters from a single spoken request
- How: Feed transcript *"Plan a 3-day trip to Delhi next weekend. I like food and culture, relaxed pace, group of 2"* → inspect extracted `TripContext`
- Pass: `city=Delhi`, `num_days=3`, `interests=["food","culture"]`, `pace=relaxed`, `group_size=2` all correctly populated; 0 clarifying questions asked

**T-3.3 — Clarifying Questions Cap**
- What: Agent asks at most 6 clarifying questions even for a vague request
- How: Feed transcript *"Plan me a trip"* → count questions asked before reaching CONFIRM state
- Pass: ≤ 6 questions asked; agent reaches CONFIRM with remaining unknowns filled by sensible defaults

**T-3.4 — State Machine Transitions**
- What: Agent correctly transitions through COLLECT → CLARIFY → CONFIRM → BUILD → PRESENT
- How: Run 3 scripted conversations (vague input, fully-specified input, mid-conversation correction) → log each state transition
- Pass: No state is skipped incorrectly; fully-specified input skips directly to CONFIRM; corrections re-enter CLARIFY

**T-3.5 — MCP Tools Are Called During BUILD**
- What: Agent invokes POI Search MCP and Itinerary Builder MCP during the BUILD state
- How: Enable MCP call logging → run a full voice-to-itinerary flow → inspect logs
- Pass: Both MCP tools appear in the call log with correctly structured inputs; itinerary JSON is returned

**T-3.6 — End-to-End Voice → Itinerary**
- What: Full pipeline produces a valid itinerary from a spoken request
- How: Speak *"Plan a 2-day Delhi trip. I like history and street food, moderate pace"* → inspect final itinerary JSON
- Pass: Itinerary has 2 days; each day has 3 time slots; each stop has `name`, `osm_id`, `visit_duration`, `travel_time_to_next`; no slot is empty

**T-3.7 — City Scope Enforcement**
- What: Agent refuses to plan trips outside New Delhi
- How: Speak *"Plan a trip to Mumbai"* → inspect agent response
- Pass: Agent declines and redirects to New Delhi; no Mumbai POIs appear in any output

---

## Phase 4 — Voice Editing & Explanations

### What We Are Building
The ability to refine the itinerary through voice ("Make Day 2 more relaxed") and the ability to explain any decision the assistant made, backed by real data. This makes the assistant genuinely useful, not just a one-shot planner.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EDIT & EXPLAIN LAYER                          │
│                                                                  │
│  User voice command                                              │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────┐                        │
│  │          INTENT CLASSIFIER           │                        │
│  │                                      │                        │
│  │  "Make Day 2 relaxed"  ──▶ EDIT      │                        │
│  │  "Why did you pick X?" ──▶ EXPLAIN   │                        │
│  │  "What if it rains?"   ──▶ EXPLAIN   │                        │
│  │  "Is this doable?"     ──▶ EXPLAIN   │                        │
│  └──────────────┬───────────────────────┘                        │
│                 │                                                │
│        ┌────────┴────────┐                                       │
│        │                 │                                       │
│        ▼                 ▼                                       │
│  ┌───────────┐    ┌──────────────────────────────────────────┐  │
│  │  EDIT     │    │              EXPLAIN                      │  │
│  │  ENGINE   │    │                                           │  │
│  │           │    │  1. RAG Query → retrieve relevant chunks  │  │
│  │  Parse:   │    │  2. LLM synthesizes answer from chunks    │  │
│  │  - which  │    │  3. Attach citation (source_url, title)   │  │
│  │    day    │    │  4. Return: spoken answer + citation list │  │
│  │  - which  │    └──────────────────────────────────────────┘  │
│  │    slot   │                                                   │
│  │  - what   │                                                   │
│  │    change │                                                   │
│  │           │                                                   │
│  │  Modify   │                                                   │
│  │  only     │                                                   │
│  │  affected │                                                   │
│  │  slot in  │                                                   │
│  │  JSON     │                                                   │
│  └───────────┘                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Edit Command Types

| Voice Command | Target | What Changes |
|---|---|---|
| "Make Day 2 more relaxed" | Day 2 — all slots | Swap intense POIs for lighter ones; add buffer time |
| "Swap Day 1 evening to something indoors" | Day 1 Evening slot only | Replace outdoor POI with indoor alternative |
| "Reduce travel time" | All days — transitions | Re-cluster POIs geographically |
| "Add one famous local food place" | Best-fit day + slot | Insert one food POI without displacing others |
| "Remove the museum on Day 3" | Day 3 — specific POI | Remove POI; re-balance time for that slot |

### Action Steps

**Step 4.1 — Build the Intent Classifier**
- Prompt the LLM to classify incoming voice commands into: `EDIT`, `EXPLAIN`, or `NEW_PLAN`
- Extract structured edit parameters from EDIT commands:
  ```
  EditIntent {
    target_day,       // 1, 2, 3, or "all"
    target_slot,      // "morning", "afternoon", "evening", or "all"
    edit_type,        // "relax", "swap", "add", "remove", "reduce_travel"
    constraint        // "indoors", "food", specific POI name, etc.
  }
  ```

**Step 4.2 — Build the Edit Engine**
- Load current itinerary JSON from session state
- Apply the edit to only the identified `target_day + target_slot`
- For slot-level changes: call POI Search MCP with updated constraints to find a replacement POI
- For pace changes: adjust slot timing without replacing POIs
- Write back the modified itinerary JSON to session state
- Verify unchanged slots are untouched (no drift)

**Step 4.3 — Build the Explanation Engine**
- For "Why did you pick X?" — retrieve the RAG chunk that mentions the POI → summarize
- For "Is this plan doable?" — run Feasibility Eval (Phase 5) on the current itinerary → narrate result
- For "What if it rains?" — check weather data (if available) or retrieve indoor alternatives from RAG
- All explanations must:
  - Be grounded in retrieved data (not LLM memory)
  - Be brief in voice (2–3 sentences)
  - Include full citation in the UI

**Step 4.4 — Attach Citations to Every Explanation**
- Every explanation response must carry: `[ { source_title, source_url } ]`
- These are passed to the UI's Sources panel (built in Phase 6)
- If no source is found, the system must say: "I don't have a verified source for this — treat it as a general suggestion."

**Step 4.5 — Test Edit Flows**
- Test each edit command type from the table above
- Verify the itinerary JSON before and after — confirm only the targeted slot changed
- Verify explanation responses include citations

**Edge Cases to address in this phase:** EC-4.1, EC-4.2, EC-4.3, EC-4.4, EC-4.5, EC-4.6 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- Intent classifier routing EDIT vs EXPLAIN commands
- Edit engine with slot-level precision
- Explanation engine with RAG-backed, cited answers
- All edit command types tested

---

### Phase 4 Summary
> **In simple terms:** Now the assistant can do two more things. First, you can change the plan just by speaking — say "make tomorrow more chill" and only tomorrow's plan changes; nothing else gets touched. Second, you can ask it questions like "why did you pick this place?" or "what if it rains?" and it will give you a real answer based on actual sources, not just make something up. The sources it used are shown to you so you can check for yourself.

---

### Phase 4 Testing Plan

**T-4.1 — Intent Classification Accuracy**
- What: Intent classifier correctly distinguishes EDIT, EXPLAIN, and NEW_PLAN commands
- How: Run 15 test commands (5 per intent type) through the classifier → compare predicted vs expected intent
- Pass: ≥ 93% classification accuracy (14/15 correct); no EXPLAIN misclassified as EDIT or vice versa

**T-4.2 — Slot-Level Edit Precision**
- What: Voice edits modify only the declared target slot; all other slots are unchanged
- How: For each edit type in the command table, snapshot itinerary before → apply edit → diff before/after → verify only the target slot changed
- Pass: 0 unintended changes detected across all 5 edit command types

**T-4.3 — Edit Does Not Cause Feasibility Failure**
- What: No edit is committed that pushes a day over its time budget
- How: On a Day 1 already at 5.5h (relaxed cap = 6h), issue *"Add two food stops to Day 1"* → verify agent catches the overflow
- Pass: Agent declines the edit as-stated and offers an alternative (replace existing stop or move to Day 2); itinerary is not overwritten with an infeasible plan

**T-4.4 — Explanation Cites a Source**
- What: Every explanation response includes at least one citation
- How: Ask *"Why did you pick Red Fort?"*, *"Is this plan doable?"*, and *"What if it rains?"* → inspect each response for `citations[]` field
- Pass: All 3 responses contain ≥ 1 citation with non-empty `source_title` and `source_url`

**T-4.5 — Explanation Acknowledges Missing Source**
- What: When no RAG chunk covers a POI, agent explicitly says so rather than hallucinating
- How: Manually remove all chunks mentioning a specific POI from the vector store → ask *"Why did you pick [that POI]?"*
- Pass: Agent responds with a "no verified source" message; no fabricated justification is returned

**T-4.6 — Rapid Edit Queue Handling**
- What: Three back-to-back voice edit commands are processed sequentially without state corruption
- How: Issue 3 edit commands in quick succession (*"Make Day 1 relaxed"*, *"Add a food place"*, *"Remove the museum"*) → inspect final itinerary
- Pass: All 3 edits are applied in order; itinerary is internally consistent; no slots are duplicated or lost

---

## Phase 5 — Evaluations

### What We Are Building
A set of automated checks that run against the itinerary to verify it is correct, realistic, and trustworthy. These are not tests for the developer — they are checks the system runs on itself before presenting results to the user.

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      EVAL ENGINE                              │
│                                                               │
│  Input: current itinerary JSON + session context             │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Eval 1: FEASIBILITY CHECK                          │     │
│  │                                                      │     │
│  │  For each day:                                       │     │
│  │    total_time = sum(visit_duration + travel_time)    │     │
│  │    available_time = pace_hours (6h / 8h / 10h)      │     │
│  │                                                      │     │
│  │  PASS if: total_time ≤ available_time               │     │
│  │           AND no single travel leg > 45 min          │     │
│  │           AND pace tag matches user preference        │     │
│  │  FAIL → flag the offending day + suggest fix         │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Eval 2: EDIT CORRECTNESS CHECK                     │     │
│  │                                                      │     │
│  │  After every voice edit:                             │     │
│  │    diff(itinerary_before, itinerary_after)           │     │
│  │                                                      │     │
│  │  PASS if: only target_day + target_slot changed      │     │
│  │  FAIL → rollback edit + log the drift                │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  Eval 3: GROUNDING & HALLUCINATION CHECK            │     │
│  │                                                      │     │
│  │  For each POI in itinerary:                          │     │
│  │    verify osm_id exists in POI dataset               │     │
│  │  For each tip/explanation:                           │     │
│  │    verify citation exists in citation index          │     │
│  │  For missing data:                                   │     │
│  │    verify system explicitly said "I don't know"      │     │
│  │                                                      │     │
│  │  PASS if: all POIs traceable + all tips cited         │     │
│  │  FAIL → flag ungrounded claim + remove from output   │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
│  Output: { eval_1: PASS/FAIL, eval_2: PASS/FAIL,            │
│            eval_3: PASS/FAIL, issues: [...] }                │
└──────────────────────────────────────────────────────────────┘
```

### Action Steps

**Step 5.1 — Implement Feasibility Eval**
- Write a function `check_feasibility(itinerary, pace)`:
  - For each day, sum all `visit_duration` + `travel_time` values
  - Compare against pace threshold: relaxed=6h, moderate=8h, intensive=10h
  - Flag any day where total exceeds threshold
  - Flag any single travel leg exceeding 45 minutes
- Return: `{ pass: bool, issues: [{ day, problem, suggestion }] }`

**Step 5.2 — Implement Edit Correctness Eval**
- Before every edit, snapshot the current itinerary JSON
- After edit is applied, compute a structural diff between before and after
- Check that changes are confined to the declared `target_day + target_slot`
- If drift is detected: rollback to snapshot + log the issue
- Return: `{ pass: bool, drifted_slots: [...] }`

**Step 5.3 — Implement Grounding & Hallucination Eval**
- For each POI in the itinerary, look up its `osm_id` in the local POI dataset → flag if not found
- For each explanation/tip displayed in the UI, check it has an entry in the citation index → flag if missing
- For any flagged ungrounded claim: remove it from the output and replace with a "no verified source" notice
- Return: `{ pass: bool, ungrounded_pois: [...], uncited_tips: [...] }`

**Step 5.4 — Wire Evals into the Agent Flow**
- Feasibility Eval: runs automatically after itinerary is built and after every edit
- Edit Correctness Eval: runs automatically after every voice edit
- Grounding Eval: runs on the full itinerary before it is shown to the user
- If any eval fails: agent informs the user and either auto-corrects or asks for guidance

**Step 5.5 — Make Evals Runnable in Isolation**
- Each eval must be runnable as a standalone script with a sample itinerary JSON as input
- Add a simple CLI: `python evals.py --input sample_itinerary.json`
- Output results to terminal and a log file

**Edge Cases to address in this phase:** EC-5.1, EC-5.2, EC-5.3, EC-5.4, EC-X.2 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- Three runnable eval functions (Feasibility, Edit Correctness, Grounding)
- Evals wired into agent flow — run automatically at the right moments
- Standalone CLI to run evals against any itinerary JSON
- Sample itinerary test fixture for eval testing

---

### Phase 5 Summary
> **In simple terms:** The system now checks its own work before showing it to you. It verifies that the plan actually fits in a day (you won't be running from place to place for 14 hours), that when you ask it to change one thing only that one thing changes, and that every recommendation it makes can be traced back to a real source. Think of this as the system's quality control department — it catches mistakes before they reach you.

---

### Phase 5 Testing Plan

**T-5.1 — Feasibility Eval: Passing Plan**
- What: Eval returns PASS for a correctly budgeted itinerary
- How: Feed a sample itinerary where each day totals 5.5h at relaxed pace → run `check_feasibility(itinerary, pace="relaxed")`
- Pass: Returns `{ pass: true, issues: [] }`

**T-5.2 — Feasibility Eval: Failing Plan**
- What: Eval returns FAIL and identifies the correct offending day
- How: Feed a sample itinerary where Day 2 totals 9h at relaxed pace → run eval
- Pass: Returns `{ pass: false, issues: [{ day: 2, problem: "exceeds 6h budget", suggestion: "..." }] }`; Day 1 and Day 3 not flagged

**T-5.3 — Feasibility Eval: Long Travel Leg**
- What: Eval flags any single travel leg exceeding 45 minutes
- How: Insert a stop with `travel_time_to_next: 60` into an otherwise valid itinerary → run eval
- Pass: Returns FAIL with the specific leg identified; other days unaffected

**T-5.4 — Edit Correctness Eval: Clean Edit**
- What: Eval returns PASS when only the target slot changes
- How: Apply a valid slot-level edit → run `check_edit_correctness(before, after, target_day=1, target_slot="evening")`
- Pass: Returns `{ pass: true, drifted_slots: [] }`

**T-5.5 — Edit Correctness Eval: Drift Detection**
- What: Eval catches when an edit accidentally modifies an unintended slot
- How: Manually alter Day 2 morning in the "after" snapshot while targeting Day 1 evening → run eval
- Pass: Returns `{ pass: false, drifted_slots: ["day_2.morning"] }`; rollback is triggered

**T-5.6 — Grounding Eval: All POIs Verified**
- What: Eval returns PASS when all itinerary POIs have valid OSM IDs
- How: Feed itinerary where every POI `osm_id` exists in the local POI dataset → run grounding eval
- Pass: Returns `{ pass: true, ungrounded_pois: [], uncited_tips: [] }`

**T-5.7 — Grounding Eval: Unverified POI Detection**
- What: Eval flags POIs whose `osm_id` does not exist in the dataset
- How: Insert a POI with a fabricated `osm_id` into the itinerary → run eval
- Pass: Returns `{ pass: false, ungrounded_pois: ["<fabricated_name>"] }`; POI is flagged, not silently kept

**T-5.8 — Eval CLI Runner**
- What: All 3 evals are runnable from the command line with a JSON fixture
- How: Run `python evals.py --input sample_itinerary.json` → inspect terminal output and log file
- Pass: Command completes without error; terminal shows PASS/FAIL for each eval; log file is written

---

## Phase 6 — UI & Delivery

### What We Are Building
The interface the user sees and interacts with — a clean, minimal companion UI showing the itinerary and a microphone button — plus the automated workflow that emails a PDF version of the itinerary to the user.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        COMPANION UI                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  HEADER: "Delhi Travel Planner"   [Mic Button] 🎤        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────┐  ┌───────────────────────┐  │
│  │       ITINERARY PANEL          │  │   TRANSCRIPT PANEL    │  │
│  │                                │  │                       │  │
│  │  [ Day 1 ] [ Day 2 ] [ Day 3 ] │  │  You: "Plan a 3-day  │  │
│  │                                │  │   trip to Delhi..."   │  │
│  │  ▸ MORNING                     │  │                       │  │
│  │    🏛 Red Fort                 │  │  AI: "Sure! What      │  │
│  │      Visit: 2h                 │  │   pace do you         │  │
│  │      ↓ 20 min travel           │  │   prefer?"           │  │
│  │    🍜 Paranthe Wali Gali       │  │                       │  │
│  │      Visit: 1h                 │  │  You: "Relaxed."     │  │
│  │                                │  │                       │  │
│  │  ▸ AFTERNOON                   │  └───────────────────────┘  │
│  │    🕌 Jama Masjid              │                             │
│  │      Visit: 1.5h               │  ┌───────────────────────┐  │
│  │      ↓ 30 min travel           │  │    SOURCES PANEL      │  │
│  │    🏪 Chandni Chowk Market     │  │                       │  │
│  │      Visit: 2h                 │  │  • Red Fort —         │  │
│  │                                │  │    Wikipedia          │  │
│  │  ▸ EVENING                     │  │  • Chandni Chowk —   │  │
│  │    🍽 Karim's Restaurant       │  │    Wikivoyage Delhi   │  │
│  │      Visit: 1.5h               │  │  • Karim's —          │  │
│  │                                │  │    Wikivoyage Cuisine │  │
│  │  [ Email me this plan 📧 ]     │  │                       │  │
│  └────────────────────────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

```

### n8n Workflow

```
User clicks "Email me this plan"
          │
          ▼
┌─────────────────────┐
│  Webhook Trigger    │  ← receives itinerary JSON + user email
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Format Itinerary   │  ← transforms JSON into readable HTML/text
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  PDF Generator Node │  ← converts formatted HTML to PDF
│  (HTML to PDF)      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Email Node         │  ← sends PDF attachment to user email
│  (SMTP / SendGrid)  │
└────────┬────────────┘
         │
         ▼
     Email delivered ✓
```

### Action Steps

**Step 6.1 — Build the Companion UI**
- Set up the UI project (Lovable / Figma Make / custom React)
- Build the Itinerary Panel:
  - Day tabs (Day 1, Day 2, Day 3...)
  - Time blocks: Morning / Afternoon / Evening as collapsible sections
  - Each stop: name, visit duration, travel time to next stop
- Build the Transcript Panel:
  - Live scrolling display of conversation transcript
  - Microphone button with active recording indicator
- Build the Sources Panel:
  - List of citations for all POIs and tips shown in current itinerary
  - Each citation: title + clickable source URL

**Step 6.2 — Wire UI to Agent State**
- Connect the UI to the backend agent via WebSocket or REST polling
- When the agent produces a new/updated itinerary JSON → re-render the Itinerary Panel
- When citations are returned → update the Sources Panel
- When agent speaks → display in Transcript Panel

**Step 6.3 — Build the n8n Workflow**
- Set up n8n (cloud or self-hosted)
- Create a Webhook trigger node — accepts `{ itinerary_json, user_email }`
- Add a Function node to transform the JSON into an HTML template (Day 1, stops, times)
- Add a PDF conversion node (n8n's HTML-to-PDF or a third-party node)
- Add an Email node (SMTP or SendGrid) — sends PDF as attachment
- Test the full flow with a sample itinerary JSON

**Step 6.4 — Add "Email Me This Plan" Button**
- Add a button to the UI that calls the n8n webhook with the current itinerary JSON
- Prompt the user for their email address if not already collected
- Show a confirmation message: "Your itinerary has been sent to [email]"

**Step 6.5 — Deploy**
- Deploy the backend (agent + MCP tools + RAG + evals) to a cloud server (e.g., Railway, Render, or AWS)
- Deploy the frontend UI to a static host (e.g., Vercel, Netlify)
- Ensure the public URL is accessible without login
- Smoke test: visit the URL on a different device, run a full voice trip planning session

**Step 6.6 — Final Integration Test**
- Run a complete end-to-end session:
  1. Speak a trip request
  2. Answer clarifying questions
  3. Receive itinerary in UI
  4. Make a voice edit
  5. Ask an explanation question — verify citation appears in Sources panel
  6. Click "Email me this plan" — verify PDF arrives in inbox
  7. Check evals passed in logs

**Edge Cases to address in this phase:** EC-6.1, EC-6.2, EC-6.3, EC-6.4, EC-6.5, EC-6.6, EC-X.1 — see `Edge-Cases-and-Fixes.md`

### Deliverables
- Deployed Companion UI at a public URL
- Day-wise itinerary view, microphone button, live transcript, sources panel
- n8n workflow: itinerary JSON → PDF → email
- Full end-to-end integration test passing

---

### Phase 6 Summary
> **In simple terms:** This is the part the user actually sees and uses. We build the web page with your day-by-day trip shown clearly, a microphone button you click to talk, and a panel that shows where every recommendation came from. We also set up an automated pipeline so that when you click a button, the app emails you a clean PDF of your entire trip plan — no copy-pasting required. Finally, we put the whole thing online so anyone can use it from a browser.

---

### Phase 6 Testing Plan

**T-6.1 — Itinerary Panel Rendering**
- What: Day-wise itinerary renders correctly with all required fields
- How: Load a sample 3-day itinerary JSON into the UI → visually inspect Day tabs, Morning/Afternoon/Evening blocks, stop names, visit durations, travel times between stops
- Pass: All 3 days render; all 3 time slots visible per day; visit duration and travel time shown for every stop; no blank or undefined fields visible

**T-6.2 — Microphone Button & Live Transcript**
- What: Mic button activates STT and transcript appears in real time
- How: Click mic button → speak a sentence → inspect transcript panel
- Pass: Recording indicator activates on click; spoken words appear in transcript panel within 2 seconds; transcript matches spoken words with ≥ 90% accuracy

**T-6.3 — Sources Panel Population**
- What: Sources panel shows correct citations for the current itinerary
- How: Load a known itinerary and its citations → inspect Sources panel entries
- Pass: Every citation has a visible title and a clickable URL; count of citations matches the citation index entries for that itinerary

**T-6.4 — n8n PDF Email Delivery**
- What: Clicking "Email me this plan" triggers the n8n workflow and delivers a PDF to the given email
- How: Enter a test email address → click the button → wait up to 60 seconds → check inbox
- Pass: Email arrives within 60 seconds; attachment is a valid PDF; PDF contains all days, stops, and durations from the itinerary; no nodes error in n8n logs

**T-6.5 — Email Prompt on Missing Address**
- What: UI prompts for email if none has been provided before calling the webhook
- How: Click "Email me this plan" without entering an email → inspect UI behaviour
- Pass: Modal or inline prompt appears requesting email; webhook is not called until a valid email is entered; invalid format is rejected client-side

**T-6.6 — Mobile Layout**
- What: UI is usable on a mobile screen without broken layout or inaccessible controls
- How: Open the deployed URL on Chrome (Android) and Safari (iOS) → interact with mic button, day tabs, sources panel
- Pass: No horizontal overflow; mic button is visible and tappable without scrolling; day tabs switch correctly; sources panel accessible via tab or scroll

**T-6.7 — Microphone Permission Denied Fallback**
- What: UI shows a helpful message and text input fallback when mic is blocked
- How: Block microphone permission in browser settings → click mic button
- Pass: Error message displayed with instructions to enable mic; a text input field appears as fallback; app does not crash or hang

**T-6.8 — Full End-to-End Smoke Test (Deployed URL)**
- What: The complete user journey works on the live public URL from a fresh browser session
- How: Open the public URL on a device that has never visited it → complete the full flow: speak request → answer questions → receive itinerary → make one voice edit → ask one explanation question → click email button
- Pass: Every step completes without errors; itinerary renders with sources; email arrives with PDF; all evals logged as PASS in server logs

---

## Dependency Map

```
Phase 1 (Data & RAG)
    │
    ├──▶ Phase 2 (MCP Tools)        [needs POI dataset from Phase 1]
    │         │
    │         └──▶ Phase 3 (Voice Agent)   [needs MCP tools from Phase 2]
    │                   │                   [needs RAG from Phase 1]
    │                   │
    │                   └──▶ Phase 4 (Edit & Explain) [needs agent + RAG]
    │                               │
    │                               └──▶ Phase 5 (Evals) [needs itinerary JSON + citations]
    │                                           │
    │                                           └──▶ Phase 6 (UI & Delivery) [needs everything]
    │
    └──▶ Phase 6 (UI) also needs Phase 1 citations for Sources panel
```

---

## Milestone Checklist

| # | Milestone | Phase |
|---|---|---|
| M1 | Vector store populated + RAG query returns cited results | Phase 1 |
| M2 | OSM POI dataset available + queryable | Phase 1 |
| M3 | POI Search MCP returns ranked POIs for a test query | Phase 2 |
| M4 | Itinerary Builder MCP returns valid day-wise JSON | Phase 2 |
| M5 | Voice input → transcript → agent conversation working | Phase 3 |
| M6 | Full voice flow: speak request → itinerary JSON produced | Phase 3 |
| M7 | Voice edit modifies only the targeted slot | Phase 4 |
| M8 | Explanation response includes citation | Phase 4 |
| M9 | All 3 evals pass on a sample itinerary | Phase 5 |
| M10 | UI shows day-wise itinerary with sources panel | Phase 6 |
| M11 | n8n workflow delivers PDF to email | Phase 6 |
| M12 | Deployed at public URL — end-to-end test passes | Phase 6 |

---

## Addendum — Trained Itinerary Narrator (post-Phase-6)

### What this is

`llm-itinerary-training-document.md` (project root) is a training specification describing a full LLM-driven workflow for generating 2-3 day metropolitan itineraries: required inputs, a 9-step generation process, a fixed 6-section output format (TRIP OVERVIEW / DAY-BY-DAY ITINERARY / FOOD HIGHLIGHTS / GETTING AROUND / BUDGET ESTIMATE / PRACTICAL TIPS), hard rules, and edge-case handling.

The system was "trained" on this document by adding `phase3/itinerary_narrator.py` as a **narration layer**, not by replacing the Phase 2 itinerary builder.

### Why a layer, not a replacement

Phases 1-6 are built around one grounded itinerary schema (`day_1: {morning:[...], afternoon:[...], evening:[...], total_hours, nearest_hospital, nearest_pharmacy}`) produced deterministically by Phase 2's geographic-clustering + time-budget scheduler. Phase 4's edit engine, Phase 5's evals, and Phase 6's UI all depend on that exact schema. Replacing it with free-form LLM generation would discard four already-complete, tested phases and trade real grounding (actual OSM places, actual distances, actual time budgets) for unverified LLM output on exactly the parts — geography, timing, POI existence — the deterministic backend already gets right.

The training document's own Rule 1 ("never invent specifics you are unsure of... say verify current hours/prices rather than stating a guess as fact") is compatible with, not opposed to, this project's existing no-hallucination principle (Phase 5's Grounding Eval exists for exactly this reason). So the narrator is instructed to treat the given schedule as fixed ground truth, and to explicitly hedge anything it must estimate (accommodation rates, ticket prices, budget totals) as `"(estimated — verify locally)"` rather than stating it as fact.

### How it fits in the pipeline

After Phase 3's `_build_itinerary()` runs the Phase 2 scheduler, Phase 5's evals, and the proactive weather/safety/transit enrichment (all already-grounded data), `_generate_narrative()` calls `itinerary_narrator.generate_narrative_itinerary()` with that grounded data and gets back the full Section-4-formatted narrative, stored as `agent.narrative`. It never blocks itinerary presentation if it fails (same best-effort pattern as the weather/safety/transit calls).

- `phase6/app.py` shows it in a "📖 Full Itinerary" expander.
- `phase6/docx_generator.py` renders it (via a small Markdown→docx line renderer) as the leading section of the emailed/downloaded document, followed by the precise structured day-by-day breakdown as before.

### What's now covered, and how

Several items from `Itinerary-Coverage-Gap-Analysis.md` that were previously "❌ Missing" (no real data source) are now produced by the narrator, explicitly hedged: accommodation neighborhood/price suggestions, food highlights, a per-day and total budget estimate, and booking-required flags. See that document's "Trained Narrator Integration" section for the full reclassification.

---

## Addendum — Additional Delhi Data Sources (Phase 1)

### What this is

`delhi-additional-data-sources.md` (project root) documents three additional open data sources for Delhi tourism data: Wikidata (CC0), OpenStreetMap (ODbL — already Phase 1's primary source), and Open Transit Data Delhi / OTD GTFS (portal-registration-gated). Per its stated integration order, all three were evaluated for Phase 1.

### Wikidata (integrated)

`phase1/wikidata_client.py` runs a SPARQL query against `https://query.wikidata.org/sparql` (CC0, no key, no rate-limit friction) and enriches existing `pois.json` records — never invents or replaces a POI — with `wikidata_qid`, `website`, and `image` where a confident match exists (via the OSM `wikidata` tag when present, else alias-normalized name + <200m proximity match).

The document's own suggested SPARQL query (walking the `P131` located-in-administrative-entity chain to NCT of Delhi, Q1353) was tested against this project's real data and found to miss most major landmarks — Humayun's Tomb, India Gate, Jama Masjid, Red Fort, Akshardham — because their `P131` chain doesn't reliably resolve to Q1353 in Wikidata's actual graph. Replaced with a coordinate bounding-box filter (`wikibase:box` service, same bbox as `overpass_client.py`) plus a broadened "what counts as a POI" filter (tourist attraction, heritage site, museum, palace, mosque, Hindu temple, fort) — verified directly against the live endpoint before shipping.

Wired into `phase1/main.py` as pipeline Step 5 (`--skip-wikidata` to skip).

### OpenStreetMap (existing source, real bug fixed)

While cross-referencing OSM against Wikidata, discovered that `overpass_client.py`'s `monument`/`temple`/`mosque`/`church`/`gurdwara`/`market` categories only ever queried `node` elements. Large landmarks (Red Fort, Humayun's Tomb, India Gate, Jama Masjid, Lotus Temple, ...) are frequently mapped as `way` or `relation` polygons in OSM, not point nodes — a node-only query silently missed them entirely, confirmed directly against the live Overpass API. Fixed by adding `way`/`relation` variants to every category where a large complex is plausible, and changing the Overpass `out` statement from `out body;` to `out body center;` (required for way/relation elements to carry a lat/lon at all).

This also surfaced a latent id-collision risk: OSM ids are only unique within their element type, so a node and a way can share the same numeric id. `osm_id` is now stored as `"{type}/{id}"` (e.g. `"way/12345"`) instead of a bare number, to avoid silently conflating two different real-world places now that node+way+relation are queried together.

Also added per the document: a `metro_station` category (`railway=station, station=subway`) for nearest-station lookups, and `fee`/`wheelchair`/`website` OSM tags (real data — `fee` is yes/no only, never an invented amount).

### Open Transit Data Delhi / GTFS (not integrated — requires manual registration)

The static GTFS "download" endpoints (`https://otd.delhi.gov.in/data/staticDMRC/`, `.../data/static/`) are not directly downloadable files — they resolve to an HTML page requiring the user to state a purpose of use and (per the portal) register for an API key, which an automated agent cannot complete on the user's behalf. This is documented as an explicit, deliberate gap rather than skipped silently.

As a partial, real-data substitute: OSM's new `metro_station` category gives distance-based "nearest metro station" per day (`nearest_metro_station` field, surfaced in Phase 6's UI, the emailed document, and the narrator's grounded summary) — not real transit times/fares, but genuine station locations. If the user later registers for an OTD API key, `phase2/itinerary_builder.py`'s `_load_reference_pois()` / `_nearest_summary()` pattern is the natural integration point for real GTFS stop/route data.

### Compliance

Per the document's compliance rules: an attribution footer ("Map & POI data © OpenStreetMap contributors, ODbL... enriched from Wikidata (CC0)... guidance from Wikivoyage (CC BY-SA 4.0)") was added to both the Phase 6 UI and the emailed/downloaded document. Wikidata (CC0) and OSM (ODbL) data remain distinguishable in `pois.json` — Wikidata-sourced fields (`wikidata_qid`, `website`, `image`) are only ever added on top of an existing OSM record, never used to create a standalone entry, so the two license regimes don't need physical separation into different files.

---

## Addendum — Voice Agent Upgrade (STT/TTS quality)

### What this is

Phase 3's original voice pipeline used the free Google Web Speech API (via `SpeechRecognition`'s `recognize_google()`) for STT and `pyttsx3` (offline, robotic system voices) for TTS — functional, but low fidelity. Several voice-agent architecture options were considered (hosted platforms like Vapi/Retell/OpenAI Realtime, open-source real-time frameworks like Pipecat/LiveKit Agents, or a quick engine swap) — a quick, free, open-source engine swap was chosen: same turn-based architecture as before, no new accounts, no new cost, meaningfully better audio quality.

### What changed

- **STT (`phase3/stt.py`):** microphone capture still goes through `SpeechRecognition`'s `sr.Microphone()` (reliable, unchanged), but the captured audio is now transcribed via **Groq's Whisper endpoint** (`whisper-large-v3-turbo`) instead of Google's free API — same `GROQ_API_KEY` already used for the LLM, no new account, and substantially more accurate. `_transcribe_groq()` sends the captured audio as an in-memory WAV (`audio.get_wav_data()` wrapped in a named `BytesIO`) directly to `client.audio.transcriptions.create()`.
- **TTS (`phase3/tts.py`):** now uses **edge-tts** (free, no API key — wraps Microsoft Edge's neural voices) as the primary voice, played via `pygame.mixer`. Falls back automatically to the original `pyttsx3` engine if edge-tts fails (e.g. no network) — never blocks the conversation on a TTS failure.
- Both changes are internal to the `STT`/`TTS` classes — their public interface (`STT(mode=...).listen()`, `TTS(mode=...).speak()`) is unchanged, so Phase 6's `voice_input.py` and the sidebar TTS toggle needed no changes at all.
- New dependencies: `edge-tts`, `pygame` (added to `phase3/requirements.txt`).

### Options considered but not built

- **Vapi.ai / Retell AI / OpenAI Realtime API** — hosted conversational voice platforms. Would preserve (Vapi/Retell) or replace (OpenAI Realtime) the existing Groq/Llama reasoning, but all three need a new paid account and a publicly-reachable webhook (ngrok or real deployment) for the platform to call back into this project's Phase 2-5 logic — a bigger pivot than the project's local-only, free-tier scope warranted right now.
- **Pipecat / LiveKit Agents** — open-source real-time voice agent frameworks giving true streaming/interruptible conversation. Free and self-hostable, but a meaningful restructuring of Phase 3's turn-based state machine into a streaming pipeline. Left as a documented option if a more natural "cut the agent off mid-sentence" experience is wanted later.
- **Piper TTS** — fully local/offline neural TTS, genuinely open source. Documented as the offline alternative to edge-tts if internet-free operation is ever required; not implemented since edge-tts's zero-setup (no voice model downloads) fit the "quick upgrade" scope better and this project already requires internet for Groq/OSM/Wikidata/Open-Meteo.

## Addendum — LLM Provider Migration: Groq → Gemini Flash

### What this is

Groq's free tier for `llama-3.3-70b-versatile` caps at a flat 100,000 tokens/day. Across QA-fix regression testing this quota was exhausted repeatedly, blocking clean end-to-end verification multiple sessions in a row. Chat/reasoning (agent turns, itinerary narrator, intent classification, RAG-grounded explanations) was migrated to **Gemini Flash** via its OpenAI-compatible endpoint.

### What changed

- **`config.py`** now exposes two separate client factories instead of one: `get_llm_client()` (chat/reasoning — points at Gemini's OpenAI-compatible endpoint, `https://generativelanguage.googleapis.com/v1beta/openai/`, via `GEMINI_API_KEY`) and `get_stt_client()` (speech-to-text — still points at Groq via `GROQ_API_KEY`). Every existing chat/reasoning call site (`phase3/agent.py`, `phase3/itinerary_narrator.py`, `phase4/intent_classifier.py`, `phase4/explain_engine.py`) needed zero code changes, since they already went through `config.get_llm_client()`/`LLM_MODEL`/`LLM_MODEL_FAST`.
- **STT stayed on Groq Whisper** (`phase3/stt.py`, now via `get_stt_client()`) — Gemini's OpenAI-compatible layer has no equivalent to the `/audio/transcriptions` endpoint; a Gemini-based transcription path would require a rewrite using Gemini's native base64 `input_audio` chat-completions pattern instead, not a client swap. Not built — STT was never actually the quota bottleneck.
- `LLM_MODEL`/`LLM_MODEL_FAST` use Google's `-latest` alias names rather than pinned versions — a pinned `gemini-2.5-flash` was already retired for new API keys at time of migration, confirmed via a direct 404 on first deploy.
- Verified Gemini's OpenAI-compat endpoint supports `response_format={"type": "json_object"}` (load-bearing for `agent.py` and `intent_classifier.py`) before committing to the swap.
- **Model bucket correction (2026-07-14):** `LLM_MODEL` initially pointed at `gemini-flash-latest` (which currently resolves to `gemini-3.5-flash`), on the assumption its free tier was similarly generous to what's publicly documented for Gemini Flash models. In practice this bucket's real free-tier cap turned out to be only **20 requests/day/project** — small enough that a single full regression run or a couple of live conversations exhausts it, confirmed by repeated `RESOURCE_EXHAUSTED` (`limit: 20`) errors. `LLM_MODEL_FAST` (`gemini-flash-lite-latest`) is a separate quota bucket that consistently showed real headroom in the same testing. `LLM_MODEL` was repointed at `gemini-flash-lite-latest` too (kept as a distinct constant from `LLM_MODEL_FAST` rather than merged, so it can be repointed at a stronger model later — e.g. if billing is enabled on the Gemini project — without touching call sites). Lesson: published free-tier numbers vary a lot by model/key and shouldn't be trusted without verifying empirically against the actual key in use.

### Result

Phase 3 7/7 agent + 4/4 narrator, Phase 4 6/6, Phase 5 8/8, Phase 6 5/5 — all clean, and (after the 2026-07-14 bucket fix) fast, with no rate-limit retries.

## Addendum — Venues Knowledge Base Data Source (delhi_tourist_venues_kb.md)

### What this is

`delhi_tourist_venues_kb.md` (project root) is a hand-curated, structured knowledge base of the 50 most popular New Delhi/NCR tourist venues — real entry fees, recommended visit durations, best-time-to-visit guidance, transport access, and audience notes, one consistent template per venue, written in the same "approx." / "Verify locally" hedged style this project's own no-hallucination principle already requires. It's a static local file rather than a live API, but treated exactly like every other source in this pipeline: parsed into records, never extended beyond what's written, integrated as a fifth data source alongside OSM/Overpass, Wikidata, Wikivoyage, and Wikipedia.

### What changed

- **New `phase1/venues_kb_loader.py`** — parses the 50 `### N. Venue Name` entries into structured records (category, tags, why-famous prose, timings, entry fee, visit-duration text + a parsed midpoint in minutes, best-time-to-visit, how-to-reach, suitable-for, nearby attractions). Also converts venues into scraper.py-shaped article dicts (`venues_to_articles()`) so they flow through the *existing* `chunk()` → `embed()` RAG pipeline unmodified — no special-cased ingestion path.
- **New `phase1/venues_kb_enrich.py`** — mirrors `wikidata_client.py`'s enrichment-only contract: only adds fields to POIs that already exist in the OSM-derived dataset (the KB has no coordinates, so it can never invent a new schedulable stop). Matching is fuzzy (`difflib`, tries the full name plus any pre-parenthesis core / parenthetical alternate name, e.g. "Red Fort (Lal Qila)" matches OSM's plain "Red Fort" via the pre-paren candidate) and gated by category-family compatibility. **Threshold tuning mattered a lot here**: an initial pass at a permissive threshold produced real false positives — "National Museum" incorrectly matched "National Gandhi Museum", "Waste to Wonder Park" matched an unrelated "royal tower park" — which would have silently attributed the wrong entry fee to the wrong physical place, worse than not enriching at all. Raised the threshold until zero false positives were observed on manual review of every match; landed on **23 of 50 venues** confidently matched, trading recall for precision deliberately (a missed enrichment costs nothing; a wrong one corrupts real data).
- **`phase1/main.py`** — two new pipeline steps (KB article loading into the RAG corpus; KB POI enrichment after Wikidata), each with its own `--skip-venues-kb` flag mirroring the existing `--skip-wikidata` pattern.
- **`phase2/poi_search.py`** — `_visit_duration()` now prefers a matched venue's real recommended duration over the flat per-category default (previously every "monument" got the same 90 minutes regardless of whether it was a small memorial or Qutub Minar Complex) — a genuine scheduling-accuracy improvement, not just a display change, for the 23 matched landmarks.
- **`phase3/itinerary_narrator.py`** — system prompt now uses a matched venue's real entry fee verbatim instead of estimating one, and does *not* apply the `"(estimated...)"` hedge to that specific figure (it isn't a guess) — while still hedging any aggregate budget total computed from a mix of real and estimated inputs.
- **`phase6/app.py` / `docx_generator.py`** — real entry fee shown per matched stop in both the live UI and the downloaded document; new shared `citation_format.py` entry so KB citations display as "(Delhi Tourist Venues KB)".
- **Real bug found and fixed during regression, not just a data-quality note**: `phase4/test_phase4.py`'s T-4.6 (Rapid Edit Queue) started failing after this integration — not a code regression, but a *stale test fixture*: several KB-matched landmarks (Jama Masjid, Gurdwara Bangla Sahib) now have more accurate, often longer, real visit durations than the old flat defaults, making the test's real-data fixture legitimately too tight for its third edit to fit feasibility-wise. Same root cause and same fix philosophy as an earlier T-4.2 fragility fix (see the code comment above `test_edit_precision()` in `phase4/test_phase4.py`): replaced the live-data fixture with a hand-crafted, deliberately spacious one, since this test's actual purpose is verifying the edit-queue mechanism, not re-testing the feasibility guard (T-4.3's job).

### Result

RAG corpus grew from 147 to 197 chunks (67 wikivoyage + 80 wikipedia + 50 KB, all citations preserved and merged, none overwritten). 23/50 POIs enriched with real entry fee/visit duration/best-time data, zero false positives on manual review. Full regression: Phase 1 6/6, Phase 2 7/7, Phase 3 7/7 agent + 4/4 narrator, Phase 4 6/6 (after the T-4.6 fixture fix), Phase 5 8/8, Phase 6 5/5 — all clean. Live Playwright verification confirmed real entry fees rendering per-stop in the built itinerary and flowing correctly into the narrator's budget section, with zero console errors.
