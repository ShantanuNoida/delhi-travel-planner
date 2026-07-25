# Demo script — 5-minute beat sheet

Prereqs: backend running (`PYTHONUTF8=1 uvicorn app.main:app --port 8000`),
frontend running (`npm run dev` in `frontend/`), both pointed at each other
(`VITE_API_BASE_URL`), real `GEMINI_API_KEY`/`GROQ_API_KEY` set.

Real LLM output varies run to run — this script tells you what to *ask* and
what property of the response to point at, not a verbatim script to read.
See `transcripts/` for real, previously-captured examples of each beat.

## 1. Plan by voice (~60s)

Tap the mic, say: **"3 relaxed days in Chennai, food and temples, from my
hotel in T. Nagar."** If it asks a follow-up (missing days/interests/pace —
capped at 6 questions), answer naturally; say "yes" at the readback.

**Point at:** the Departure Board rendering real day cards — real POI names
with real `osm:node/...`/`osm:way/...` sources, honest "no suggestion here"
meal placeholders where the dataset didn't have a match (never a fabricated
restaurant), and the last day correctly getting a shorter time budget.

## 2. Surgical edit (~45s)

Pick a real stop name from Day 1 and say: **"remove `<stop name>` from
day 1."**

**Point at:** only Day 1's card visually updates (pulse + "Day 1 updated"
chip) — Day 2 doesn't move. This isn't just a UI trick: click "run evals"
mentally note the **V2 Edit-Correctness** result in the response —
`changed_days` exactly equals `allowed_days`, `collateral_days` is empty.
That's a structural diff proving no other day changed, not just a visual
claim.

## 3. "Why this place?" and the Sources panel (~60s)

Click the citation icon on any stop, or say **"why this place?"** /
**"is this doable?"**.

**Point at (either outcome is a valid, honest demo point):**
- If the assistant gives a specific, cited answer — the Sources panel
  shows the exact retrieved passage and a real, clickable URL backing it.
- If it says "I don't have fully verified information to answer that
  confidently" — the Sources panel *still* shows whatever it retrieved and
  considered, letting you judge for yourself that it genuinely didn't have
  enough to back a confident claim, rather than silently failing. This is
  the intended behavior, not a bug: the RAG index has deep coverage for a
  handful of named places (Marina Beach, Kapaleeshwarar Temple, Shore
  Temple, Government Museum) and honestly defers on the rest of the
  1,596-POI dataset rather than paraphrasing an unrelated page. See
  `transcripts/explain.md` for three real captured examples of both
  outcomes and exactly why each one happened.

## 4. Show the eval gates directly (~45s)

In a terminal: `cd backend && PYTHONUTF8=1 python -m app.evals.run --all --skip-llm`

**Point at:** the schema self-test (14/14 fixtures valid) and all three
gates passing — this is the same V1/V2/V3 machinery that ran silently
behind steps 1–3, now shown explicitly. Mention `--skip-llm` runs the
deterministic checks only (CI-safe, zero quota); dropping the flag also
runs V3's real LLM judge.

## 5. Accept → PDF → email (~45s)

Scroll to the bottom of the plan, type a real email address, click "Email
me this plan."

**Point at:** the button's success state ("Sent to ..."). If n8n isn't
configured for this demo environment, the failure state ("Resend," plan
still visible) is itself worth showing — it proves the export path never
hides or discards the itinerary on failure. If n8n *is* configured
(`Docs/Details/n8nConfig.md`), open the actual received email with the
attached PDF as the closing beat.

## Fallback notes

- If Gemini's quota is exhausted mid-demo, the router silently fails over
  to Groq — `GET /api/health` shows `failover_rate` climbing. Worth
  mentioning if it happens rather than treating it as a glitch: it's the
  reliability feature working as designed.
- If a "vague" plan utterance ever produces a 500 instead of a clarifying
  question, that would be a regression of a real bug fixed in Sprint 10
  (`_extract_and_clarify` no longer trusts a premature "done" from S2) —
  shouldn't happen, but if it does, that's the first place to look.
