# DESIGN — Wandervoice visual identity & design system

> **Living document** for the Companion UI (the itinerary/voice/sources surface
> named in `architecture.md` Layer 5). Written to be handed to **Lovable**
> alongside `Docs/DESIGN_PROMPTS.md` — every token here is restated in the
> prompts so Lovable can build from it directly.
>
> **Last updated:** 2026-07-02 06:54 IST

---

## 1. Why this direction

Wandervoice plans real trips inside one real place: the Greater Chennai region.
The design draws from that place's own material and visual vernacular — Kanchipuram
silk color families, Chettinad/Athangudi tile geometry, the EMU suburban-rail
departure board, temple gopuram carving, hand-painted bus and shop-sign lettering
— rather than generic "travel app" visuals (globe icons, postcard gradients,
stock beach photography).

**Explicitly avoided:** a warm cream background with a high-contrast serif
display and a terracotta accent. This is one of the three defaults AI design
tools reach for regardless of subject, and it's already sitting in this repo —
`.claude/skills/voice-travel-assistant-workspace/review-iteration-1.html` (an
internal eval dashboard, cream `#faf9f5` / near-black `#141413` / terracotta
`#d97757` / Poppins+Lora) is exactly that pattern. It is *not* a starting point
for the product UI. This design's palette, type, and structure are chosen to be
unmistakably different from it.

## 2. Color tokens

| Name | Hex | Role | Notes |
|---|---|---|---|
| Indigo Night | `#1B2A4A` | Dark surface | Header, voice-listening mode background, footer |
| Peacock Teal | `#0E7C86` | Primary accent | Primary buttons, active/selected states, waveform, links |
| Turmeric Gold | `#E3A423` | Secondary accent | Citation marks, confirm affordances, **soft/warning** feasibility state |
| Vermilion | `#C1442D` | Alert | **Hard-fail** feasibility state only — never decorative, never a default button color |
| Handloom White | `#EDE7D6` | Page background | Warm off-white with a cotton/khadi undertone — deliberately *not* paper-cream `#F4F1EA` |
| Charcoal Slate | `#26241F` | Body text | Warm near-black, not pure black |
| Granite Grey | `#8B8578` | Structure | Borders, dividers, muted/meta text, disabled states |

Contrast notes for Lovable: Charcoal Slate on Handloom White and White on Indigo
Night/Peacock Teal/Vermilion all clear WCAG AA for body text. Turmeric Gold is a
**fill/border/icon accent, not a large-text background** — pair Gold fills with
Charcoal Slate text, not white.

## 3. Type tokens

| Role | Typeface | Weights | Google Fonts import | Usage |
|---|---|---|---|---|
| Display | **Baloo 2** | 700, 800 | `Baloo+2:wght@700;800` | Screen titles, day headers, the mic prompt line. Bold, rounded, warm — the register of hand-painted Tamil Nadu bus and shop signage. Has a genuine Tamil-script sibling (Baloo Thambi 2), a real vernacular tie rather than decoration. Use at large sizes only; never body text. |
| Body | **Manrope** | 400, 500, 600 | `Manrope:wght@400;500;600` | Paragraphs, questions, confirmations, buttons, labels. Quiet geometric-humanist counterpoint to Baloo 2. |
| Utility / data | **IBM Plex Mono** | 400, 500 | `IBM+Plex+Mono:wght@400;500` | Times, durations, `poi_id`s, source URLs, coordinates. Evokes a rail/airport timetable board — reinforces the Departure Board signature (§6). |

Type scale (rem, mobile-first, body = 1rem/16px):
`display-xl` 2.75rem/800 · `display-lg` 2rem/700 · `display-md` 1.5rem/700 ·
`body-lg` 1.125rem/500 · `body` 1rem/400 · `caption` 0.875rem/500 (mono, tracked
+0.02em) · `micro` 0.75rem/500 (mono).

## 4. Spacing, radius, elevation

- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 (px), used as Tailwind's
  default `4`-based scale — no custom scale needed.
- Radius: `8px` default (cards, buttons, chips), `4px` for the Departure Board's
  stop rows (ticket/timetable feel, not soft app-card feel), `999px` (pill) only
  for the mic button and status chips.
- Elevation: flat by default (Granite Grey `1px` hairline borders do the
  separation work, not shadows). One soft shadow token, `0 4px 16px rgba(27,42,74,0.12)`,
  reserved for the mic button's listening state and modals — elevation should
  mean "this is actively happening," not decorate static content.

## 5. Motion principles

- **Listening state:** the mic button emits a live waveform in Peacock
  Teal→Turmeric Gold gradient bars, amplitude-driven by input level. At rest, the
  same bar grid settles into a faint static pattern echoing Athangudi tile
  geometry — the waveform *is* the recurring motif, active or idle.
- **Surgical edit:** when a voice edit lands, animate **only** the changed
  day/platform/row — a brief Turmeric Gold outline pulse plus a height/opacity
  transition on that block. Everything else must not visibly move. This makes
  F3's "only the affected block changes" promise something the user *sees*, not
  just a backend guarantee.
- **Feasibility transitions:** a hard-fail banner slides in from the top with a
  short, firm motion (200ms ease-out) — it should read as urgent but not jarring.
  A soft-warning chip fades in in place (150ms) — it should read as incidental,
  not alarming.
- Respect `prefers-reduced-motion`: replace waveform animation with a static
  bar-level indicator, replace slide/pulse transitions with instant state swaps
  plus a color change.

## 6. Signature: the Departure Board

Each day of the itinerary renders like a rail/airport departure board rather than
a generic card grid:

```
┌───────────┬──────────────────────────────────────────────┐
│  DAY 02    │  MAHABALIPURAM EXCURSION          moderate    │
│  Sat 12    ├──────────────────────────────────────────────┤
│  600 min   │  MORNING                                       │
│  avail.    │   08:40  Shore Temple, Mamallapuram    50 min │
│            │          → 10 min travel          [source ↗] │
│            │  AFTERNOON                                     │
│            │   11:00  Pancha Rathas                 40 min │
│            │          → 10 min travel          [source ↗] │
│            │   11:50  Arjuna's Penance               45 min │
│            │  EVENING — free                                │
└───────────┴──────────────────────────────────────────────┘
```

- The left stub (day number, date, pace tag, `available_min`) is fixed-width and
  set in the Utility/mono face — a literal timetable stub, perforated-edge
  hairline optional as a subtle divider, not a heavy skeuomorphic effect.
- Stop rows are set in Body (name) + Utility/mono (time, duration, travel), one
  row per `Stop` object — field-for-field the same shape as
  `Docs/schemas/common.itinerary.schema.json`'s `Stop`.
- Day numbering and stop ordering are a genuine sequence here — the board *is*
  the schedule — so numbering earns its place, unlike a generic "01/02/03"
  feature list.
- When `start_point` is known, the board gains a top/bottom "platform" line:
  `↳ from hotel in T. Nagar · 15 min` above Morning and `↳ return to base · 20 min`
  below Evening, in Granite Grey. When absent, these lines are simply omitted —
  see §7.

## 7. Feasibility severity → visual language

This maps directly to the `severity` field added to `v1.feasibility.schema.json`
this session (`error` default, `warning` for the new `start_point_coverage`
check) — the UI should not invent its own severity concept, it should render
this one:

| `severity` | Visual | Behavior |
|---|---|---|
| `error` | Vermilion banner across the top of the affected day, or a blocking modal for a whole-plan failure | Blocks acceptance until resolved; plan is rebalanced automatically first, banner only shows if rebalance still fails |
| `warning` | Small Turmeric Gold chip, inline, e.g. under the day stub: "⚠ base not set — travel to/from your stay isn't counted" | Never blocks; dismissible; also surfaced once in the S3 confirmation readback if `start_point` was never given |

## 8. UI copy & voice

- **Active voice, named by what the user did/controls.** "Save changes," not
  "Submit." A button's label persists through the flow it triggers: "Build my
  plan" → the confirmation that follows never renames the action.
- **User's side of the screen.** Never surface system/internal names — no
  "S2 clarifier," no "MCP tool," no `poi_id` in spoken or primary copy (mono
  `poi_id` display is fine in the Sources panel as a technical footnote, not in
  headline copy).
- **Grounding honesty is a voice trait, not just a data rule.** When a fact is
  missing, say so plainly in-product: "No verified hours for this place yet" —
  never invent, never hedge vaguely.
- **Errors don't apologize and are never vague.** "Day 2 is over your 10-hour
  budget by 45 minutes" beats "Something went wrong with your itinerary."
- **Empty states are an invitation, not a dead end.** First load: "Tell me about
  your trip" under the mic, not a blank itinerary shell.

## 9. Component inventory

1. **Mic / voice bar** — pill-shaped, Indigo Night ground, live waveform, states:
   idle / listening / thinking / speaking.
2. **Departure Board day card** — see §6.
3. **Stop row** — name, dwell, travel-to-next, `area` tag chip, source mark.
4. **Source chip** — small Turmeric Gold-outlined mark, click/tap opens the
   Sources panel scrolled to that citation.
5. **Live transcript panel** — scrolling Body-face text, current utterance in
   Charcoal Slate, prior turns in Granite Grey.
6. **Sources / References panel** — list of `{text, source_url, section}` /
   `sources[]` entries grouped by day; every entry is a real clickable URL.
7. **Confirmation banner** (S3 readback) — one spoken-style sentence + Yes/No.
8. **Hard-fail banner / modal** — Vermilion, `severity: error`.
9. **Soft-warning chip** — Turmeric Gold, `severity: warning`.
10. **Accept & Export action** — "Email me this plan" → success state ("Sent to
    you@example.com") / failure state (itinerary stays visible + "Resend").

## 10. Accessibility & responsive floor

- Responsive down to **360px** width; the Departure Board's stub collapses above
  the platforms (stacked, not side-by-side) below `640px`.
- Visible keyboard focus ring on every interactive element: `2px solid` Peacock
  Teal with a `2px` offset, on both light and dark surfaces.
- `prefers-reduced-motion` honored everywhere per §5.
- Minimum tap target `44×44px` for the mic button and all row-level source
  chips.
- Every color pairing used for text must be checked against WCAG AA before
  shipping (see §2 contrast notes).

## 11. Data grounding

The UI must not invent its own shapes. Build directly against:
- `Docs/schemas/common.itinerary.schema.json` — the canonical itinerary object
  (drives the Departure Board).
- `Docs/schemas/v1.feasibility.schema.json` — the `checks[]`/`severity` shape
  (drives §7).
- `Docs/schemas/w1.poi-search.schema.json` / `common.poi.schema.json` — POI
  fields shown in stop rows and the Sources panel.

When wiring real data later, treat these schemas as the API contract, not the
mock JSON in the prompts — the prompts' sample data exists only to give Lovable
something concrete to render.
