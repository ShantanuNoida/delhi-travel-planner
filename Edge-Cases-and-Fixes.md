# Voice-First AI Travel Planner
## Edge Cases & Recommended Fixes

---

## How to Read This Document

Each edge case follows this format:

- **Scenario** — what goes wrong and when
- **Impact** — what breaks or degrades for the user
- **Fix** — the recommended implementation-level solution

Edge cases are organized by phase so they can be addressed during that phase's build.

---

## Phase 1 — Data & RAG Foundation

---

### EC-1.1 — Wikivoyage / Wikipedia Article Is Outdated or Missing

**Scenario:** The Wikivoyage article for a New Delhi neighbourhood hasn't been updated in years, or an article for a specific area simply doesn't exist.

**Impact:** The RAG pipeline returns stale or no information, leading the explanation engine to either hallucinate or say nothing useful.

**Fix:**
- At scrape time, record the `last_modified` date of each article and store it in chunk metadata
- At retrieval time, if the most recent chunk for a query is older than 18 months, append a disclaimer: *"This information was last verified in [date] — details may have changed."*
- Maintain a fallback: if no chunk is found for a specific area, return a generic New Delhi city-level chunk rather than an empty result

---

### EC-1.2 — OSM Data Is Incomplete for a POI Category

**Scenario:** The Overpass API query for "restaurants near Lodi Garden" returns very few results, or a well-known landmark has no `opening_hours` tag in OSM.

**Impact:** POI Search MCP returns too few candidates; itinerary has gaps. Opening-hours logic cannot filter correctly.

**Fix:**
- Set a minimum result threshold (e.g., 5 POIs per category per query). If below threshold, widen the bounding box radius and retry once
- Treat missing `opening_hours` as "hours unknown" — include the POI but flag it in the UI: *"Opening hours unverified — check before visiting"*
- Never silently drop a POI because metadata is incomplete; surface the gap to the user

---

### EC-1.3 — Text Chunk Splits Mid-Sentence or Mid-Paragraph

**Scenario:** The chunker splits an article at a fixed token boundary, cutting a sentence like *"Avoid travelling to Paharganj after—"* mid-thought, making the chunk useless for retrieval.

**Impact:** Retrieved chunks are incoherent; explanation engine produces incomplete or misleading answers.

**Fix:**
- Use sentence-aware chunking (split on sentence boundaries, not token count)
- Use overlapping chunks (~50 token overlap) so context from the previous chunk carries into the next
- After chunking, run a quick coherence check: discard any chunk shorter than 2 sentences or that begins with a conjunction word ("but", "however", "and")

---

### EC-1.4 — Embedding Model Handles Hindi / Mixed-Language Text Poorly

**Scenario:** Wikivoyage articles occasionally contain Hindi place names or mixed-language phrases. The embedding model (trained primarily on English) creates poor-quality vectors for these, causing relevant chunks to rank low in retrieval.

**Impact:** Searches for local landmarks with Hindi names (e.g., "Qutub Minar", "Humayun ka Makbara") return low-relevance results.

**Fix:**
- Use a multilingual embedding model (e.g., `multilingual-e5-large` or equivalent) to handle Hindi transliterations
- Normalize all POI names to their most common English spelling in both the POI dataset and the text chunks before embedding
- Add a name alias list for common spellings (e.g., "Humayun's Tomb" = "Humayun ka Makbara" = "Humayun Tomb")

---

### EC-1.5 — Overpass API Rate Limit or Timeout

**Scenario:** During initial data collection or a live query, the Overpass API returns a 429 (rate limited) or times out due to a large bounding box query.

**Impact:** POI dataset is incomplete; live queries during trip building fail.

**Fix:**
- For initial data collection: add exponential backoff retry logic (wait 5s, 15s, 45s before failing)
- Cache all Overpass results locally — never query Overpass live during a user session; always serve from the pre-built local dataset
- Split large bounding box queries into smaller sub-region queries (e.g., query by Delhi district, not the entire city at once)

---

## Phase 2 — MCP Tool Layer

---

### EC-2.1 — POI Search Returns Zero Results for Niche Interests

**Scenario:** The user says *"I'm into street photography and graffiti art"* — categories that don't map to any standard OSM tag.

**Impact:** POI Search MCP returns an empty list; Itinerary Builder has nothing to work with.

**Fix:**
- Build an interest-to-category mapping table that maps niche interests to the nearest OSM categories:
  - "street photography" → markets, old city areas, bazaars
  - "graffiti / street art" → parks, cultural hubs, youth areas
- If the mapped category also returns 0 results, fall back to "top-rated general" POIs and inform the user: *"I couldn't find specific spots for street art, but here are some vibrant areas you'll enjoy."*
- Never return an empty itinerary without explanation

---

### EC-2.2 — Itinerary Builder Cannot Fit All Candidate POIs into Available Days

**Scenario:** POI Search returns 15 ranked POIs but the user only has 2 days, making it impossible to visit all of them without exceeding the daily time budget.

**Impact:** Itinerary Builder silently drops lower-ranked POIs, or stuffs too many into each day, failing the Feasibility Eval.

**Fix:**
- Strictly cap daily hours based on pace (relaxed=6h, moderate=8h, intensive=10h) — never exceed this
- Rank POIs and select the top N that fit within the budget; discard the rest gracefully
- Inform the user: *"I've picked the 6 best stops for your 2 days. I left out [X] and [Y] to keep the pace relaxed — want me to swap any in?"*

---

### EC-2.3 — Geographically Scattered POIs Assigned to the Same Day

**Scenario:** The Itinerary Builder assigns Red Fort (Old Delhi) and Qutub Minar (South Delhi) to the same morning, requiring a 45-minute transit between them.

**Impact:** Travel time eats into the day; Feasibility Eval flags the day as over budget.

**Fix:**
- Group POIs geographically before day-binning: cluster by neighbourhood/district using lat/lon proximity
- Assign POIs from the same cluster to the same day; cross-cluster travel is only allowed at day-start or day-end
- If clustering is impossible (user has specific POI requests across zones), flag the transit cost explicitly in the itinerary

---

### EC-2.4 — POI Is Closed on the User's Travel Day

**Scenario:** The user is visiting on a Monday but the National Museum is closed on Mondays. The Itinerary Builder places it in the itinerary without checking.

**Impact:** User shows up at a closed attraction.

**Fix:**
- During POI ranking, cross-reference the POI's `opening_hours` tag against the user's travel dates
- Filter out closed POIs before passing candidates to the Itinerary Builder
- If no open alternative exists for that category on that day, inform the user: *"The National Museum is closed on Mondays. I've replaced it with the Crafts Museum, which is open."*

---

### EC-2.5 — User's Daily Time Budget Is Too Short for Even One Stop

**Scenario:** The user says "relaxed pace" and "I only have 3 hours each day" — not enough time to meaningfully visit even a single major attraction with travel included.

**Impact:** Itinerary Builder produces an empty or degenerate plan.

**Fix:**
- Detect this constraint conflict before calling the Itinerary Builder
- Inform the user during the CONFIRM stage: *"With 3 hours per day, I can fit 1–2 nearby stops. That's quite limited — would you like to extend to 4–5 hours, or focus on one area per day?"*
- If the user confirms the short window, build a minimal 1-stop-per-day itinerary with full transparency

---

## Phase 3 — Conversational Voice Agent

---

### EC-3.1 — STT Mishears a Place Name

**Scenario:** The user says "Jaipur" but the STT transcribes it as "Java" or "Japper." Or the user says "Lodi Garden" and it becomes "Lodi Garten."

**Impact:** The agent tries to plan a trip to a non-existent or wrong location; the scope constraint (New Delhi only) may not trigger.

**Fix:**
- After STT, run a place-name validation step: check if the city/place name exists in a known New Delhi location list
- If validation fails, ask the user to confirm: *"Just to confirm — did you say Lodi Garden?"*
- For city-level mismatches (e.g., user says "Jaipur"), gently redirect: *"This planner is focused on New Delhi. Want me to plan a trip there instead?"*

---

### EC-3.2 — User Provides All Information Upfront (No Clarification Needed)

**Scenario:** The user says: *"Plan a 3-day trip to Delhi for next weekend. I want food and culture, relaxed pace, group of 2, no budget issues."* — all parameters are already known.

**Impact:** Agent still asks clarifying questions it doesn't need, frustrating the user.

**Fix:**
- After extracting parameters from the initial request, check which fields in `TripContext` are still `null`
- Only ask clarifying questions for genuinely missing fields
- If all fields are populated, skip directly to the CONFIRM state: *"Got it — let me confirm before I build your plan..."*
- Never ask a question whose answer was already given

---

### EC-3.3 — User Gives Conflicting Constraints

**Scenario:** The user says *"relaxed pace"* but also *"I want to visit 10 places in 2 days."*

**Impact:** The Itinerary Builder cannot satisfy both; it will either violate the pace or drop most POIs.

**Fix:**
- Detect constraint conflicts during the CLARIFY state before building
- Surface the conflict explicitly: *"Visiting 10 places in 2 days would mean a pretty packed schedule — that's closer to an intensive pace. Should I aim for 10 places, or keep it relaxed with 5–6 stops?"*
- Let the user decide which constraint takes priority before proceeding

---

### EC-3.4 — User Goes Silent or Abandons Mid-Conversation

**Scenario:** The agent asks a clarifying question and the user stops responding for 30+ seconds (walked away, microphone issue, etc.).

**Impact:** The conversation hangs indefinitely; no itinerary is built.

**Fix:**
- Implement a 30-second inactivity timeout on the listening state
- After timeout, gently prompt once: *"Still there? Take your time — I'm ready when you are."*
- After a second timeout (60 seconds total), suspend the session and save `TripContext` to session storage
- On next session start, offer to resume: *"Welcome back — want to continue planning your Delhi trip?"*

---

### EC-3.5 — User Requests a City Outside New Delhi

**Scenario:** The user asks to plan a trip to Mumbai, Goa, or a foreign city.

**Impact:** The system has no data for that city; producing an itinerary would require hallucination.

**Fix:**
- Maintain a strict city allowlist: `["New Delhi", "Delhi"]`
- If any other city is detected, decline gracefully: *"I'm currently set up for New Delhi only. I can plan a great Delhi trip if you're interested!"*
- Do not attempt partial planning or hallucinate data for unsupported cities

---

### EC-3.6 — More Than 6 Clarifying Questions Are Needed

**Scenario:** The user's initial request is so vague that the agent genuinely needs more than 6 questions to fill all parameters (e.g., *"Plan me a trip"*).

**Impact:** If the agent strictly stops at 6 questions, some parameters remain unknown; the itinerary may be poorly fitted to the user.

**Fix:**
- Prioritize questions: rank which missing parameters matter most (city, days, interests are highest priority; group size, dietary needs are lower)
- Ask compound questions to gather multiple parameters at once: *"How many days, and what kind of activities do you enjoy?"*
- After 6 questions, fill remaining unknowns with sensible defaults (pace=moderate, group=2) and state them explicitly in the CONFIRM step so the user can correct them

---

## Phase 4 — Voice Editing & Explanations

---

### EC-4.1 — Edit Command Is Ambiguous

**Scenario:** The user says *"change tomorrow"* — it's unclear what should change (the pace? a specific slot? all of it?).

**Impact:** The intent classifier cannot determine `edit_type`, so it either guesses wrong or does nothing.

**Fix:**
- If `edit_type` cannot be determined with high confidence, ask one targeted follow-up: *"What would you like to change about tomorrow — the pace, a specific place, or the time of day?"*
- Never make a guess and apply it silently; always confirm ambiguous edits before executing
- Cap clarifying follow-ups for edits at 1 question — if still unclear, ask the user to rephrase

---

### EC-4.2 — Edit Makes the Day Infeasible

**Scenario:** The user says *"Add two more food stops to Day 1"* but Day 1 is already at the maximum daily time budget.

**Impact:** Itinerary Builder adds the stops; Feasibility Eval fails on Day 1.

**Fix:**
- Run the Feasibility Eval immediately after every edit, before confirming it to the user
- If the edit causes a feasibility failure, offer a choice: *"Adding two food stops would make Day 1 about 10 hours — that's quite packed. Should I replace an existing stop instead, or move one food stop to Day 2?"*
- Never silently commit an edit that fails the Feasibility Eval

---

### EC-4.3 — No Alternative POI Available for a Requested Swap

**Scenario:** The user says *"Swap the Day 1 evening to something indoors"* but there are no indoor POIs left in the dataset that haven't already been used in the itinerary.

**Impact:** The edit engine has nothing to swap in; it either duplicates a POI or leaves the slot empty.

**Fix:**
- Before confirming a swap, check that at least one valid unused alternative exists in the POI dataset
- If none exists, tell the user: *"I couldn't find an unused indoor option for that slot. Want me to keep the current plan, or remove the evening slot entirely?"*
- Never duplicate a POI that already appears elsewhere in the itinerary

---

### EC-4.4 — Explanation Requested for a POI With No RAG Source

**Scenario:** The user asks *"Why did you pick Hauz Khas Village?"* but no Wikivoyage or Wikipedia chunk in the vector store mentions this POI.

**Impact:** The explanation engine has no grounded content to retrieve; it must not hallucinate an answer.

**Fix:**
- If RAG retrieval returns 0 chunks above the confidence threshold, do not generate an explanation from LLM memory
- Respond explicitly: *"I picked Hauz Khas Village based on its category match to your interests, but I don't have a verified write-up for it right now. You can check [wikivoyage.org/wiki/New_Delhi] for more details."*
- Log the missing POI for future data collection

---

### EC-4.5 — Rapid Successive Edits Create Inconsistent State

**Scenario:** The user fires 3 voice edit commands quickly before any of them has been applied and confirmed — e.g., "Make Day 1 relaxed", "Add a food place", "Remove the museum."

**Impact:** Edits may be applied out of order or on top of each other's intermediate states, corrupting the itinerary.

**Fix:**
- Process edits sequentially — queue incoming edit commands and process one at a time
- While an edit is being applied, display a visual indicator ("Updating your plan...") and do not accept new edit commands
- Only dequeue and process the next edit after the previous one passes its Feasibility and Edit Correctness evals

---

### EC-4.6 — Edit Empties a Slot Entirely

**Scenario:** The user says *"Remove the afternoon plans on Day 2"* — which removes all POIs from that slot, leaving it blank.

**Impact:** The UI shows an empty afternoon block; the itinerary has a gap the user may not have intended.

**Fix:**
- After removing all POIs from a slot, ask: *"Day 2's afternoon is now free. Should I leave it open, or fill it with something light?"*
- If the user wants it open, mark the slot as "Free time — explore at your own pace" rather than leaving it blank
- Never display a slot with no content and no label

---

## Phase 5 — Evaluations

---

### EC-5.1 — Feasibility Eval Fails but No Fix Is Possible

**Scenario:** The user has specified a 1-day trip with 6 interests and a relaxed pace — mathematically impossible to satisfy all constraints simultaneously.

**Impact:** Feasibility Eval fails, but no combination of POIs can make it pass within the given constraints.

**Fix:**
- Detect irreconcilable constraint conflicts before the eval runs (during the CONFIRM stage)
- If the eval still fails post-build, surface the specific conflict to the user with a concrete trade-off: *"A relaxed 1-day itinerary fits about 3 stops. I've picked the top 3 — want me to swap any of them?"*
- Never loop endlessly trying to pass an eval that is mathematically impossible

---

### EC-5.2 — Grounding Eval Flags a Real, Valid Place That Is Missing From OSM

**Scenario:** A well-known restaurant or market exists in reality but has no OSM record (or its OSM record was deleted/merged), so the Grounding Eval fails even though the recommendation is legitimate.

**Impact:** A valid POI gets flagged as ungrounded and removed from the itinerary.

**Fix:**
- Don't automatically remove a POI on a Grounding Eval failure — instead flag it in the UI with a warning: *"We couldn't verify this place in our dataset. It's a known local spot, but please confirm it's still open before visiting."*
- Distinguish between "not in OSM" (uncertain) and "hallucinated" (confidently wrong) — only hard-remove the latter
- Maintain a small manual whitelist of verified-but-not-in-OSM places that bypass the eval check

---

### EC-5.3 — Edit Correctness Eval Detects Drift but Rollback Fails

**Scenario:** An edit modifies an unintended slot (drift detected), but the pre-edit snapshot is corrupted or missing, making rollback impossible.

**Impact:** The itinerary is in a corrupted state with no way to recover automatically.

**Fix:**
- Always write the pre-edit snapshot to a separate, append-only log file — not just in-memory
- If rollback fails, load the last known good snapshot from the log file
- If even that fails, inform the user: *"Something went wrong with that edit. I've reset to your original plan — want to try the edit again?"*
- Implement snapshots as immutable versions (keep last 5) rather than a single mutable state

---

### EC-5.4 — LLM-Assisted Eval Gives Inconsistent Results Across Runs

**Scenario:** An LLM-assisted Grounding Eval judges the same itinerary as PASS on one run and FAIL on another due to LLM non-determinism.

**Impact:** Evals are unreliable; the system behaves unpredictably.

**Fix:**
- Set LLM temperature to 0 for all eval calls to minimize non-determinism
- For grounding checks, prefer rule-based logic (OSM ID lookup, citation index lookup) over LLM judgment — only use LLM for nuanced cases where rules cannot decide
- When LLM is used, ask for a structured JSON verdict (`{ pass: bool, reason: string }`) rather than free-form text to reduce variance

---

## Phase 6 — UI & Delivery

---

### EC-6.1 — Browser Denies Microphone Permission

**Scenario:** The user's browser blocks microphone access (permission denied, or no HTTPS), so the microphone button does nothing.

**Impact:** The core voice input feature is completely unavailable.

**Fix:**
- On mic permission denial, detect the error and display a clear message: *"Microphone access is needed for voice input. Please allow it in your browser settings."* with a direct link to how to do so
- Provide a text input fallback — a text box where the user can type their request instead of speaking
- Ensure the app is served over HTTPS (required for Web Speech API in all browsers)

---

### EC-6.2 — n8n Webhook Times Out or Fails

**Scenario:** The user clicks "Email me this plan" but the n8n workflow fails — webhook times out, PDF generation crashes, or the email node errors.

**Impact:** The user receives no PDF and no feedback about what went wrong.

**Fix:**
- Show an optimistic UI state ("Sending your itinerary...") with a spinner immediately on button click
- Set a 30-second timeout on the webhook call; if it exceeds that, show: *"It's taking longer than expected. We'll send it shortly — check your inbox in a few minutes."*
- Implement a retry mechanism in n8n (retry PDF + email steps up to 2 times before failing)
- On definitive failure, offer the user a "Download PDF" button as a fallback (generate PDF client-side or via a direct API call)

---

### EC-6.3 — PDF Generation Fails for Long Itineraries

**Scenario:** A 4-day itinerary with long explanations and many citations exceeds the PDF generator's size or timeout limits.

**Impact:** n8n's PDF node crashes; the email is never sent.

**Fix:**
- Before passing the itinerary to the PDF node, truncate explanation text to a max character limit per slot
- Citations in the PDF should be shortened URLs or reference numbers (e.g., [1], [2]) with a references section at the end — not full inline text
- Test PDF generation with a 4-day maximum-content itinerary during Phase 6 to validate size limits before deployment

---

### EC-6.4 — UI Breaks on Mobile Browser

**Scenario:** The companion UI is designed for desktop and the day-tabs + three-panel layout doesn't render correctly on a mobile screen.

**Impact:** Mobile users see a broken layout; microphone button may be obscured or unreachable.

**Fix:**
- Design with a mobile-first approach: single column layout on small screens, with tabs switching between Itinerary, Transcript, and Sources panels
- Test on at least two mobile browsers (Chrome Android, Safari iOS) before deployment
- The microphone button must always be in a fixed, thumb-reachable position on mobile (bottom-center)

---

### EC-6.5 — User Does Not Provide an Email Address

**Scenario:** The user clicks "Email me this plan" but has never given their email — not during conversation and not in a UI field.

**Impact:** The n8n webhook is called without a valid email; the workflow fails at the email node.

**Fix:**
- Show a modal prompt for email input when the button is clicked, if no email is on file
- Validate the email format client-side before calling the webhook
- Store the email in session state so the user isn't asked again for subsequent sends in the same session

---

### EC-6.6 — Sources Panel Has Broken or Dead Links

**Scenario:** A Wikivoyage or Wikipedia article URL that was valid at scrape time has since moved, been deleted, or redirected.

**Impact:** Users click a citation link and get a 404, undermining trust in the system's credibility.

**Fix:**
- At scrape time, store both the full URL and a plain-text citation (`"Wikivoyage — New Delhi, Safety section"`) so the citation is still readable even if the link breaks
- Display citations as `title (source)` first, with the URL as a secondary hyperlink — a dead link doesn't erase the citation's value
- Run a link-health check as part of the deployment pipeline to flag dead URLs before going live

---

## Cross-Phase Edge Cases

---

### EC-X.1 — The System Confidently Recommends a Permanently Closed Business

**Scenario:** A restaurant or attraction that existed in OSM data and Wikivoyage articles has since permanently closed. No data source reflects this.

**Impact:** User shows up to a closed place; trust in the system is damaged.

**Fix:**
- Include a disclaimer on all POI cards in the UI: *"Hours and availability are based on publicly available data. We recommend confirming before visiting."*
- Mark POI dataset with a `last_verified` date — flag POIs whose data is older than 12 months with a visible staleness warning in the UI

---

### EC-X.2 — All MCP Tool Calls Fail Simultaneously

**Scenario:** A downstream dependency (Overpass API unavailable, vector store unreachable) causes all MCP tools to fail during an active user session.

**Impact:** The agent cannot build or update any itinerary; the session is dead.

**Fix:**
- Wrap all MCP tool calls in try/catch with descriptive error returns
- If both required MCP tools fail, inform the user gracefully: *"I'm having trouble reaching the data I need right now. Please try again in a moment."*
- Do not let MCP failures propagate as unhandled exceptions that crash the session

---

### EC-X.3 — LLM Ignores the New Delhi Scope Constraint and Suggests Other Cities

**Scenario:** The LLM, despite instructions, suggests a day trip to Agra or Jaipur as part of a "Delhi trip."

**Impact:** Scope constraint is violated; the system has no data for those cities and any content about them would be hallucinated.

**Fix:**
- Add an explicit hard rule in the system prompt: *"You must only suggest locations within New Delhi city limits. Do not suggest day trips to other cities."*
- Add a post-generation check: scan the itinerary JSON for any `city` field that is not "New Delhi" — flag and strip those entries before displaying
- Log violations for prompt tuning

---

## Edge Case Coverage Summary

| Phase | Edge Cases | Highest Risk |
|---|---|---|
| Phase 1 — Data & RAG | EC-1.1 to EC-1.5 | EC-1.3 (bad chunking → bad retrieval) |
| Phase 2 — MCP Tools | EC-2.1 to EC-2.5 | EC-2.3 (scattered POIs → infeasible day) |
| Phase 3 — Voice Agent | EC-3.1 to EC-3.6 | EC-3.1 (STT misreads place names) |
| Phase 4 — Edit & Explain | EC-4.1 to EC-4.6 | EC-4.2 (edit breaks feasibility silently) |
| Phase 5 — Evaluations | EC-5.1 to EC-5.4 | EC-5.4 (non-deterministic LLM evals) |
| Phase 6 — UI & Delivery | EC-6.1 to EC-6.6 | EC-6.1 (mic denied = no voice input) |
| Cross-Phase | EC-X.1 to EC-X.3 | EC-X.3 (LLM ignores city scope) |
