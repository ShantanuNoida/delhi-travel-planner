# Design Alignment Review — `phase6/app.py` vs `DESIGN.md`

**As of:** 2026-11-24

Team Waypoint reviewed `DESIGN.md` (the Wandervoice visual-identity spec) against the real app's current styling in `phase6/app.py` and both `.streamlit/config.toml` files. Proposal only — nothing has been implemented. Every item below is confirmed **functionality impact: NONE**; anything that would require behavior or state changes was moved to Out of scope. Core gap: the shipped app uses a terracotta/saffron palette (`#C2540C` + `#332F5C`), while DESIGN.md's identity is Peacock Teal (`#0E7C86`) + Turmeric Gold (`#E3A423`) on a warm Handloom-White page — and DESIGN.md explicitly names a cream/terracotta scheme as the pattern it deliberately avoids.

---

## High priority — ✅ IMPLEMENTED (2026-11-24)

All five items below (H1–H5) were implemented and verified: both `.streamlit/config.toml` copies and `phase6/app.py` updated; the Streamlit theming skill's docs surfaced one real bug along the way — `headingFont`/`codeFont` values with spaces (`Baloo 2`, `IBM Plex Mono`) need the font name wrapped in single quotes inside the TOML string (`"'Baloo 2':https://..."`), or Streamlit silently falls back to the body font. Fixed in both config files. Verified live via a Playwright pass against the real `streamlit run app.py` server in both light and dark mode: `--wp-accent`/`--wp-secondary` resolve to the new teal/gold hex values, H1/H3 render in Baloo 2, body text in Manrope, zero console errors. `phase6/main.py --test` still 5/5 (backend-only, unaffected).

### H1 — Primary accent: terracotta → Peacock Teal
- **What:** `primaryColor "#C2540C" → "#0E7C86"` (light); `"#E0863F" → "#2AA7B0"` (dark, lightened for legibility).
- **Where:** both `config.toml` copies (repo-root and `phase6/.streamlit/config.toml`), `[theme]`/`[theme.light]`/`[theme.dark]` `primaryColor`.
- **Why:** DESIGN §2 — Peacock Teal is the primary accent (buttons, active/selected states, links).
- **Functionality impact:** NONE.

### H2 — `--wp-accent` / `--wp-accent-deep` tokens: terracotta → teal
- **What:** light `--wp-accent: #C2540C → #0E7C86`, `--wp-accent-deep: #7A3608 → #0A5A62`; dark `--wp-accent: #E0863F → #2AA7B0`, `--wp-accent-deep: #F3B57D → #7FD0D6`.
- **Where:** `phase6/app.py` lines 221–222 and 237–238.
- **Why:** drives the transcribing banner, selected-card outline, stop-card fact chips, icon tint, and h1 gradient — all primary-accent per DESIGN §2.
- **Functionality impact:** NONE (CSS custom-property values only).

### H3 — Secondary accent: deep indigo → Turmeric Gold
- **What:** light `--wp-secondary: #332F5C → #E3A423`, `--wp-secondary-deep: #211E3D → #B07E12`, `--wp-secondary-soft: rgba(51,47,92,.10) → rgba(227,164,35,.12)`; dark `--wp-secondary: #9490C9 → #E3A423`, `--wp-secondary-deep: #C3C0E6 → #F0C45E`, `--wp-secondary-soft: → rgba(227,164,35,.18)`.
- **Where:** `phase6/app.py` lines 223–225 and 239–241.
- **Why:** DESIGN §2 — Turmeric Gold is the secondary accent; drives secondary buttons.
- **Functionality impact:** NONE. Contrast note: Gold stays a fill/border/icon accent, not a white-text background — keep the current gold-text-on-transparent pattern, don't flip to a gold fill.

### H4 — Type pairing: Fraunces / Plus Jakarta Sans / JetBrains Mono → Baloo 2 / Manrope / IBM Plex Mono
- **What:** `font → "Manrope:...wght@400;500;600"`, `headingFont → "Baloo 2:...wght@700;800"`, `codeFont → "IBM Plex Mono:...wght@400;500"`.
- **Where:** both `config.toml` copies; plus hard-coded refs in `phase6/app.py` — `.wp-stop-name` (line 316, `'Fraunces', serif → 'Baloo 2', sans-serif`) and `.wp-time-chip` (line 321, `'JetBrains Mono' → 'IBM Plex Mono'`).
- **Why:** DESIGN §3 — Baloo 2 (display), Manrope (body), IBM Plex Mono (times/durations/IDs/URLs).
- **Functionality impact:** NONE (typeface swap only).

### H5 — Heading weight for Baloo 2
- **What:** `headingFontWeights = [800] → [700]` (Baloo 2 700 for most display; 800 reserved for the h1 gradient title, loaded via H4's font import).
- **Where:** both `config.toml` copies.
- **Why:** DESIGN §3 specifies Baloo 2 at 700/800; the current `[800]`-only setting was a Fraunces faux-bold workaround that no longer applies.
- **Functionality impact:** NONE.

---

## Medium priority — ✅ IMPLEMENTED (2026-11-24)

All eight items (M1–M8) implemented and verified. One extra fix found and applied along the way, not in the original list: the day-map legend caption ("🟠 morning · 🟣 afternoon · 🟢 evening") had hardcoded emoji dots tied to the *old* slot colors — after M7's remap (morning → Turmeric Gold) the orange dot no longer matched, so it's now a yellow dot. Verified live:
- M1: real page background resolves to `rgb(237,231,214)` (`#EDE7D6`) in light and `rgb(27,42,74)` (`#1B2A4A`) in dark, via a Playwright check against the actual Streamlit theme engine.
- M4: the gold balance-chip markup verified in isolation — background `rgba(227,164,35,.12)`, border `rgb(227,164,35)`, text `rgb(176,126,18)` — all exactly the intended tokens.
- M5: `st.error`/`st.warning` verified live against real alert DOM (`stAlertContainer`/`stAlertContentError`/`stAlertContentWarning` testids) — error renders Vermilion (`rgb(193,68,45)`), warning renders Gold (`rgb(176,126,18)` text / gold-tinted background) — both distinct and legible, using a `:has()` selector confirmed working in the installed Chromium engine.
- M7: remapped via the real app's sample-itinerary fixture rendered through a monkeypatched harness (no fabricated data) — map markers and legend now show Gold/Indigo/Teal, no red/Vermilion anywhere in the day or slot palette.
- M2/M3/M6/M8: verified by direct token/computed-style inspection; `buttonRadius` was already "medium" from the High-priority pass.

`phase6/main.py --test` still 5/5 throughout.

## (reference) Medium priority — original proposal

### M1 — Warm page background + body text
- **What:** `[theme.light]`: add `backgroundColor = "#EDE7D6"` (Handloom White), `textColor = "#26241F"` (Charcoal Slate), `secondaryBackgroundColor = "#E4DCC9"`. `[theme.dark]`: `backgroundColor = "#1B2A4A"` (Indigo Night), `textColor = "#EDE7D6"`, `secondaryBackgroundColor = "#243655"`.
- **Where:** both `config.toml` copies.
- **Why:** DESIGN §2 — neither file currently sets background/text, so it falls back to Streamlit's stock white/near-black; this is the single biggest reason the app doesn't read as DESIGN.md even after the accent swaps.
- **Functionality impact:** NONE (verify WCAG AA together with M2/M3).

### M2 — `--wp-surface` to match the warm palette
- **What:** `--wp-surface: #FFFFFF → #F5F0E2` (light); dark `#221C17 → #243655`.
- **Where:** `phase6/app.py` lines 226 / 242.
- **Why:** DESIGN §2 — surfaces in the warm/indigo family; used by the time-chip background.
- **Functionality impact:** NONE.

### M3 — Borders & muted text → Granite Grey
- **What:** `--wp-border: #E7DCCB → #8B8578` (light) / `#392F26 → #5A5445` (dark); `--wp-ink-soft: #746353 → #8B8578` (light) / `#C2AF9C → #A8A394` (dark).
- **Where:** `phase6/app.py` lines 227–228 / 243–244.
- **Why:** DESIGN §2 Granite Grey = structure/borders/muted text; §4 hairline borders do the separation work instead of shadows.
- **Functionality impact:** NONE.

### M4 — Feasibility severity → DESIGN color language
- **What:** balance notes currently render as a neutral grey caption (🕓 {note}). Re-render each as a small Turmeric Gold inline chip (⚠), reusing the same chip styling as the existing fact-chip badges.
- **Where:** `phase6/app.py` lines 829–830.
- **Why:** DESIGN §7 — balance notes are exactly the never-blocking "warning" severity, whose prescribed visual is a Gold chip.
- **Functionality impact:** NONE (styling of the same note strings only — no change to `check_day_balance`, the balance-notes data, or shown text).

### M5 — Align hard-fail path toward Vermilion
- **What:** scoped CSS tinting the native `st.error(...)` (line 1269) toward Vermilion `#C1442D` and `st.warning(...)` (line 712) toward Turmeric Gold, rather than stock red/yellow.
- **Where:** new rules in the `phase6/app.py` `<style>` block; the widgets themselves (712 / 1269) stay unchanged.
- **Why:** DESIGN §7 — error = Vermilion, warning = Gold; §2 reserves Vermilion for hard-fail only.
- **Functionality impact:** NONE (recolors native alert chrome). Caveat: native Streamlit alert internals are the most selector-fragile item here — if a clean selector can't be found for 1.57.0, drop this item rather than target unstable internal classes.

### M6 — Button radius: pill → 8px default
- **What:** `buttonRadius = "full" → "medium"` (~8px).
- **Where:** both `config.toml` copies.
- **Why:** DESIGN §4 — 8px default for cards/buttons/chips; the 999px pill is reserved for the mic button and status chips only. The time-chip pill and the mic button's own shape are untouched.
- **Functionality impact:** NONE (corner radius only).

### M7 — Map day/slot marker palette → DESIGN colors (Vermilion reserved)
- **What:** remap `DAY_COLORS` and `SLOT_MARKER_COLOR` to DESIGN RGBs — Peacock Teal `[14,124,134]`, Turmeric Gold `[227,164,35]`, Indigo Night `[27,42,74]`, Granite Grey `[139,133,120]`, plus one more warm tone for Day 5; `DAY_COLOR_NAMES` stays index-aligned.
- **Where:** `phase6/app.py` lines 76–93, and the slot fallback `[200,30,30]` at line 1057.
- **Why:** DESIGN §2 palette cohesion. Important: do not use Vermilion for any day/slot marker — §2 reserves it for hard-fail only, "never decorative." The current brick-red Day 5 and red slot fallback should move off the red family so they stop reading as alerts.
- **Functionality impact:** NONE (marker RGB values only; day/slot index mapping unchanged).

### M8 — Visible focus ring (accessibility)
- **What:** add `:focus-visible { outline: 2px solid var(--wp-accent); outline-offset: 2px; }` on interactive elements.
- **Where:** new rule in the `phase6/app.py` `<style>` block.
- **Why:** DESIGN §10 — 2px Peacock Teal ring, 2px offset, on both surfaces.
- **Functionality impact:** NONE (focus outline only).

---

## Low priority — ✅ IMPLEMENTED (2026-11-24)

All six items (L1–L6) implemented and verified:
- L1/L4 done together: the transcribing banner's pulsing icon now respects `prefers-reduced-motion` (moved into a named `.wp-lsn-fade` class so it can be switched off) and is pill-shaped (999px). The carousel was re-checked — it's a plain CSS `scroll-snap` row with no autoplaying animation, so there was nothing to suppress there.
- L2: h1's gradient now sweeps Peacock Teal → Indigo Night in light mode (verified live: `linear-gradient(135deg, rgb(14,124,134), rgb(27,42,74))`); dark mode intentionally keeps the lightened-teal-only sweep since a dark Indigo Night stop would lose legibility clipped against a dark page.
- L3: confirmed already satisfied as a side effect of the High-priority accent swap (chip-bg tokens already teal-based, not stale terracotta). Took the review's optional suggestion further: the entry-fee badge now uses the Turmeric Gold family (distinct from the teal hours badge) since DESIGN.md treats cost/ticket info as a "confirm affordance." The now-unused `--wp-chip-bg-strong` token was removed rather than left dead.
- L5: button-hover shadow standardized to DESIGN.md's one reserved token, `0 4px 16px rgba(27,42,74,0.12)`.
- L6: audited the CTA-label-persistence and error-copy claims directly — found no violation (the "Build this trip" quick-option button and the "✅ Yes, build it" confirm button are different stages of the flow, not a renamed action; error/empty-state copy already specific). No change needed.

Verified live via Playwright: h1 gradient colors, reduced-motion CSS, and the two distinct badge colors (teal `rgba(14,124,134,.12)` for hours vs gold `rgba(227,164,35,.12)` for entry fee) all confirmed against real computed styles, zero console errors. `phase6/main.py --test` still 5/5.

## (reference) Low priority — original proposal

### L1 — `prefers-reduced-motion` fallback
- **What:** wrap the `lsn-fade` keyframe and carousel scroll in `@media (prefers-reduced-motion: reduce){ animation:none; }`.
- **Where:** `phase6/app.py` `<style>` block / transcribing-banner CSS.
- **Why:** DESIGN §5/§10 — honor reduced-motion everywhere.
- **Functionality impact:** NONE.

### L2 — h1 gradient recolor
- **What:** the h1 gradient becomes teal automatically once H2 lands; optionally shift to Peacock Teal → Indigo Night for a richer sweep.
- **Where:** `phase6/app.py` lines 258–263.
- **Why:** DESIGN §2 accent family.
- **Functionality impact:** NONE.

### L3 — Chip-bg tokens follow the new accent
- **What:** `--wp-chip-bg: rgba(194,84,12,.12) → rgba(14,124,134,.12)`, `--wp-chip-bg-strong: rgba(194,84,12,.28) → rgba(14,124,134,.28)` (+ dark equivalents). Optionally map the entry-fee "strong" chip to the Gold confirm/citation family per §2.
- **Where:** `phase6/app.py` lines 232–233 / 245–246.
- **Why:** chips should derive from the live accent, not a stale terracotta literal.
- **Functionality impact:** NONE.

### L4 — Transcribing banner radius
- **What:** `border-radius: 12px → 999px` (transient status chip per §4), or 8px to match the card default.
- **Where:** `phase6/app.py` lines 154–155.
- **Why:** DESIGN §4 radius language.
- **Functionality impact:** NONE.

### L5 — Standardize the one soft-shadow token
- **What:** primary-button hover shadow `0 4px 14px -4px var(--wp-accent)` → DESIGN's reserved `0 4px 16px rgba(27,42,74,0.12)`, kept as the only shadow in the app.
- **Where:** `phase6/app.py` line 310.
- **Why:** DESIGN §4 — one soft shadow token (Indigo-Night-based), flat by default elsewhere.
- **Functionality impact:** NONE.

### L6 — Voice/copy tone audit (wording only)
- **What:** confirm the primary CTA label persists verbatim through its confirmation step; keep error copy specific and non-apologetic (balance notes already do this); empty state already matches §8.
- **Where:** label/caption strings around `phase6/app.py` lines 712–715 and 828.
- **Functionality impact:** NONE (string text only) — keep out anything that renames an action mid-flow, since that edges into behavior.

---

## Out of scope for this pass

Structural or behavioral items from `DESIGN.md` that are **not** included above — real, but each needs its own separately-scoped follow-up, not a color/font swap:

- **"Departure Board" day layout (§6, §9.2/9.3)** — a full structural redesign of the day view (tabs + stop cards + carousel + map), not a token substitution. The largest future item.
- **Waveform mic motion / idle tile pattern (§5, §9.1)** — the mic input is a native Streamlit widget; an amplitude-driven waveform needs a custom component plus live audio-level state.
- **Surgical single-block edit animation (§5)** — animating only the changed block requires edit-diffing and targeted state, not just CSS.
- **Slide-in hard-fail banner / blocking modal that gates acceptance (§5, §7)** — the *color* of errors is covered above (M5); a timed blocking banner/modal is new interaction and state.
- **Severity schema wiring (§7, §11)** — rendering balance notes as gold chips is covered above (M4); plumbing a real blocking `error`-severity path from a feasibility schema is a behavioral change.
- **Source-chip → Sources-panel scroll-to-citation (§9.4)** — new interaction logic, not styling.

---

# Travel-Planner Color Identity Review (2026-11-24)

A second pass, asked separately: with the DESIGN.md migration complete, where is color still flat/generic, and where could deliberate color make the app read as a *travel planner* — wayfinding, itinerary, journey, geography — rather than a generic dashboard or chat app? All suggestions below stay inside DESIGN.md's existing 7-token palette unless explicitly flagged otherwise. Proposal only — nothing implemented. Every item is confirmed **Functionality impact: NONE**, or moved to the flagged/out-of-scope notes.

**Palette tension to keep in mind:** DESIGN.md gives only ~4 usable hues (Teal, Gold, Indigo, Granite Grey — Vermilion is error-only, Handloom White/Charcoal Slate are bg/text). Those 3 hues already carry two meanings today — time-of-day on the per-day map (morning=Gold, afternoon=Indigo, evening=Teal) and day-index on the all-days map (Teal/Gold/Indigo/Grey/Ochre). Any category color scheme is a *third* meaning on the same hues — avoided by keeping each meaning confined to a context where the others don't appear.

## High — ✅ IMPLEMENTED (2026-11-24)

All three items (T1–T3) implemented and verified. `CATEGORY_COLOR`/`CATEGORY_COLOR_FALLBACK` dicts added alongside `CATEGORY_ICON`, plus a small `_hex_to_rgba()` helper. Verified live via Playwright against a monkeypatched real-data harness: every stop card now shows a 3px Indigo Night left border (`rgb(27,42,74)`) for the monument/mosque stops in the fixture, the photo placeholder's gradient resolves to `rgba(27,42,74,0.2)/rgba(27,42,74,0.06)` (no more retired terracotta literal), and the map's day route line renders teal instead of grey — all confirmed by screenshot and computed-style inspection, zero console errors. `phase6/main.py --test` still 5/5.

### T1 — Category color-coding for stop types (the headline "travel planner" move)
- **What:** add a `CATEGORY_COLOR` dict parallel to `CATEGORY_ICON` (app.py 61–65), grouping the 9 categories into 3 travel-semantic families: Landmarks & sacred sites (`monument, museum, temple, mosque, church, gurdwara`) → **Indigo Night `#1B2A4A`**; Parks & open space (`park`) → **Peacock Teal `#0E7C86`**; Food & markets (`restaurant, market`) → **Turmeric Gold `#E3A423`**; fallback → **Granite Grey `#8B8578`**.
- **Where:** card-only (deliberately not the map, to avoid colliding with slot/day color meanings) — the stop-card photo-placeholder box (app.py 966–972, see T2) and/or a 3px left-border accent on the stop-card container.
- **Why:** real travel planners (Google Maps, TripIt, Wanderlog) color POI pins/rows by category — the single most recognizable "this is an itinerary tool" cue. Currently category is emoji-only with no color.
- **Functionality impact:** NONE.
- **Palette honesty:** finer-grained category colors (temple ≠ monument, market ≠ restaurant) would need colors outside the 7-token palette — see F1. Recommend staying at 3 families.

### T2 — Fix the stale terracotta placeholder tint (un-migrated leftover)
- **What:** the photo-placeholder box still hard-codes the retired terracotta accent: `linear-gradient(135deg, rgba(194,84,12,0.20), rgba(194,84,12,0.06))` (app.py 967–968) — this is the one spot the earlier palette migration missed.
- **Where:** `phase6/app.py` 966–972. Replace with T1's category color at low alpha, or at minimum `var(--wp-accent)`.
- **Why:** every placeholder card currently shows pre-migration terracotta, directly contradicting the new identity.
- **Functionality impact:** NONE (gradient color literals only).

### T3 — Color the map route line as a "journey" path
- **What:** the per-day route `PathLayer` is hard-coded neutral grey `get_color=[120, 120, 120]` (app.py 1161). Change to **Peacock Teal `[14, 124, 134]`**.
- **Where:** `phase6/app.py` 1160–1161.
- **Why:** the line connecting a day's stops *is* the journey — the core travel-planner metaphor. Grey reads as incidental; teal reads as "your path through the day," and is DESIGN §2's primary/wayfinding accent.
- **Functionality impact:** NONE (pure styling arg on the layer; path data/interaction unchanged).

## Medium

### T4 — Carry time-of-day color from the map onto the slot headers
- **What:** slot headers (`**☀️ Morning**` etc., app.py 921, 925) are plain bold text even though the map already encodes morning=Gold/afternoon=Indigo/evening=Teal. Add a matching colored dot/border using the existing `SLOT_MARKER_COLOR` values.
- **Where:** `phase6/app.py` 921–925.
- **Why:** unifies the card list and the map under one time-of-day color system — a legitimate reuse of an existing meaning, no new collision.
- **Functionality impact:** NONE.

### T5 — Day-identity color dot inside each Day tab
- **What:** add a small colored dot in that day's `DAY_COLORS[day_idx]` near the "Total scheduled time" caption (app.py 879–880), so each day carries a consistent identity color from the map legend through to its tab content.
- **Where:** `phase6/app.py` 879–880 (tab content, not the tab label — see O1).
- **Why:** gives each day a persistent color identity across views, reinforcing the multi-day journey/sequence.
- **Functionality impact:** NONE.

### T6 — Transit legs as a mono "timetable" chip
- **What:** travel-between-stops is plain grey caption text (app.py 1034–1037, 1043–1045). Style it as a small inline chip in IBM Plex Mono with a Granite Grey hairline, matching the existing `.wp-time-chip`.
- **Where:** `phase6/app.py` 1034–1045 (+ a new `.wp-transit-chip` rule near 382).
- **Why:** DESIGN §3 assigns IBM Plex Mono to times/durations/travel specifically to evoke a rail/airport timetable board. Keeping it Granite Grey (neutral, not a hue) keeps transit as connective tissue rather than competing with category/slot colors.
- **Functionality impact:** NONE (wraps the same travel string; data unchanged).

### T7 — Marker number contrast on gold markers
- **What:** the map's stop-number text layer is hard white `[255,255,255]` (app.py 1174) — low-contrast on the morning/Gold markers, and DESIGN §2 explicitly says to pair Gold fills with Charcoal Slate text, not white. Change to **Charcoal Slate `[38,36,31]`** (legible on gold, teal, and indigo alike).
- **Where:** `phase6/app.py` 1172–1176.
- **Why:** direct DESIGN §2 compliance + real legibility fix on numbered wayfinding dots, a travel-planner signature element.
- **Functionality impact:** NONE (text layer color only).

## Low — ✅ IMPLEMENTED (2026-11-24)

All three items (T8–T10) implemented and verified live: the trust badge now resolves to `background-color: rgba(14,124,134,0.1); color: rgb(14,124,134)` (Peacock Teal) via `color="primary"`; the "Updated" tag is `:orange[✨ Updated]` (Streamlit's closest built-in keyword to gold); the "Official site" link is now a real `<a>` styled as a teal-outlined chip (`rgba(14,124,134,0.12)` bg / teal border), matching the hours badge. `phase6/main.py --test` still 5/5, zero console errors.

### T8 — Trust badge: stock green → app primary
- **What:** `st.badge("Real data …", icon="✅", color="green", …)` (app.py 1284–1285) uses Streamlit's stock green. Change `color="green"` → `color="primary"` (resolves to the theme's Peacock Teal).
- **Where:** `phase6/app.py` 1284–1285.
- **Why:** the grounded-data badge is the app's core trust marker — tying it to the app's own accent instead of a generic green reinforces identity.
- **Functionality impact:** NONE.

### T9 — "Updated" edit highlight → gold family
- **What:** the just-edited tag is `:green[✨ Updated]` (app.py 1030–1031), stock green, though DESIGN §5 defines the surgical-edit affordance as a Turmeric Gold pulse. Change to `:orange[✨ Updated]` — the closest built-in Streamlit markdown color keyword to gold.
- **Where:** `phase6/app.py` 1030–1031.
- **Why:** aligns the "what just changed" cue with DESIGN's gold edit language.
- **Functionality impact:** NONE. A true `#E3A423` would need an `st.html` span instead of `:orange[]`; `:orange[]` is the zero-risk approximation.

### T10 — "Official site" link as a source chip
- **What:** `[🌐 Official site](website)` (app.py 1085–1087) renders as a default Streamlit link (generic link-blue), inconsistent with the teal/gold badges beside it. Style it as a small Peacock-Teal-outlined chip matching the hours/fee badges.
- **Where:** `phase6/app.py` 1085–1087.
- **Why:** unifies the card's fact row (hours=teal, fee=gold, site=teal-outline) into one chip language.
- **Functionality impact:** NONE (styling only — keep it a real `<a>`, not a button).

## Flagged — would need a color outside the palette

### F1 — Finer per-category colors need new tokens
If T1's 3 families aren't granular enough (e.g. temple ≠ monument, market ≠ restaurant), the DESIGN.md palette doesn't have enough hues — Vermilion is locked to errors, and reusing Teal/Gold/Indigo a 4th–5th time would be unreadable. New tokens (a muted sage for parks, a clay/sandstone for markets) would be needed, but that edges back toward the terracotta family DESIGN §1 explicitly avoids. **Recommend against it** — keep T1 at 3 families.

## Out of scope for this pass

- **O1 — Per-tab-label coloring of `st.tabs`.** Would require reaching into Streamlit's internal tab emotion-cache classes (fragile, version-specific). T5 delivers the day-color cue via in-content markup instead.
- **O2 — Geographic basemap under the maps.** `map_style=None` (app.py 841, 1156) renders a blank canvas — the single biggest reason the maps read as "a dashboard scatterplot" rather than a city map. A real basemap (e.g. CARTO light) would fix this dramatically, but it's a new external network dependency and a behavior change, not a color edit. Flagged as the highest-value *non-color* follow-up for a separately-scoped map pass.
- **O3 — Multi-day route lines on the all-days map.** New layer/data work (app.py 822–852 currently shows markers only), not recoloring — already a documented deliberate deferral in the existing code comments.
- **O4 — Surgical-edit gold pulse animation (DESIGN §5).** T9 recolors the static tag; an animated outline pulse on the changed block is motion/state work, not color.

## Files reviewed
- `.streamlit/config.toml` (repo root)
- `phase6/.streamlit/config.toml`
- `phase6/app.py` — color constants (lines 76–93), injected `<style>` block (207–354), transcribing banner (153–161), balance notes (829–830), fact chips (990–1001), native alerts (712, 1269), slot-color fallback (1057)
- `DESIGN.md`

Reviewed by Team Waypoint. Proposal only — nothing has been implemented; say which items to apply and they'll be made directly in the files above.
