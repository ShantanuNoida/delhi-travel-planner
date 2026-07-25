# Multi-Agent QA System — Travel Itinerary Application (New Delhi)

## Objective

Build and run a multi-agent system to test a travel application that generates itineraries for New Delhi. The system will stress-test the application's itinerary **edit** capability, identify weaknesses, and document findings. This is **Phase 1** of a multi-phase project; the same team will receive Phase 2 after the final deliverable is produced.

Before starting, assign the team a name and use it consistently in all outputs.

## Team Structure & Responsibilities

### Agent 1 — Team Leader / Coordinator
- Owns the overall workflow and enforces the order of execution (Agent 2 → Agent 3 → Agent 4 → Agent 5).
- Hands off outputs between agents and verifies each stage is complete before the next begins.
- Resolves conflicts or blockers between agents.

### Agent 2 — Itinerary Generator
- Generate **20 travel itineraries for New Delhi**.
- Duration mix: some **2-day** and some **3-day** itineraries.
- Interest themes to draw from: **food, history, culture, nature, art, shopping, architecture, family, religion**.
- Composition requirements:
  - A few itineraries based on a **single interest** (e.g., food-only).
  - The rest based on **combinations of multiple interests** (e.g., history + food + shopping).

### Agent 3 — Edit Command Agent
- For **each of the 20 itineraries**, apply a total of **15 diverse edit commands**.
- Edit commands must be **tailored to the structure and content of that specific itinerary** (not a fixed generic list).
- Example edit commands (use these styles as inspiration, not an exhaustive list):
  - "Make Day 2 more relaxed."
  - "Swap the Day 1 evening plan to something indoors."
  - "Swap the Day 1 evening plan to something outdoors."
  - "Reduce travel time."
  - "Add one famous local food place."
- Ensure diversity across command types: pacing changes, swaps, additions, removals, time/logistics optimizations, theme adjustments, etc.
- Record every command issued and the application's response to it.

### Agent 4 — Quality Manager / Product Manager
- Evaluate the application's response to **every edit command** issued by Agent 3.
- Identify:
  - **Loopholes** (commands the application handles incorrectly, ignores, or misinterprets).
  - **Inaccurate responses** (wrong places, broken day structure, logical inconsistencies, unrealistic travel times, etc.).
- For each issue found, write a **fix recommendation** and assign a priority: **High / Medium / Low**.
- Include a rationale for each priority assignment.

### Agent 5 — Documentation Agent
- Compile the entire project into a single document titled: **"Itinerary edit commands QA"**.
- The document must include:
  1. Team name and agent roles.
  2. All 20 generated itineraries (or a structured summary of each).
  3. The full list of edit commands applied per itinerary.
  4. The application's responses/behavior for each command.
  5. Agent 4's findings: loopholes, inaccuracies, and fix recommendations grouped by **High / Medium / Low** priority.
  6. A summary section with key takeaways and overall quality assessment.

## Workflow (Phase 1)

1. Agent 1 names the team and kicks off the workflow.
2. Agent 2 generates the 20 itineraries.
3. Agent 3 applies 15 edit commands per itinerary and logs application responses.
4. Agent 4 evaluates all responses and produces prioritized fix recommendations.
5. Agent 5 produces the final document: **"Itinerary edit commands QA"**.
6. Agent 1 confirms completion of Phase 1.

## Deliverable

A single document named **"Itinerary edit commands QA"** containing everything listed under Agent 5's responsibilities.

## Note

Once the Phase 1 document is delivered, this same team will be assigned a **Phase 2** project. Retain team structure, naming, and context for continuity.
