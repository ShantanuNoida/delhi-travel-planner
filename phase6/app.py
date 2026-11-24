"""
Companion UI — Phase 6.

Run with: streamlit run app.py
"""

import base64
import html
import os
import sys
from datetime import date

# Windows' default console codepage (cp1252) can't encode many characters
# that show up in ordinary text — arrows, "approximately equal", smart
# quotes, emoji. agent.py's _say() (and other app code) still calls print()
# when TTS is off, and a single UnicodeEncodeError there crashes the whole
# turn (surfaced as R-14 testing hit a real one from a duplicate-POI log
# message). Reconfiguring stdout/stderr to UTF-8 here fixes it at the root
# instead of just the one symptom, for any future non-ASCII text too.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import pydeck as pdk
import streamlit as st

# On Streamlit Community Cloud, secrets pasted into the dashboard land in
# st.secrets, not the process environment — but config.py and every phase
# module read keys via os.getenv(), so mirror them into os.environ before
# anything below imports those modules. Locally, .streamlit/secrets.toml
# doesn't exist, so st.secrets is just empty and this is a no-op; .env
# (loaded below) covers local dev instead.
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase2"))
sys.path.insert(0, os.path.join(_ROOT, "phase3"))
sys.path.insert(0, os.path.join(_ROOT, "phase4"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from agent import TravelAgent, State
from tts import TTS
from delivery import deliver_itinerary, build_pdf_bytes
from voice_input import try_transcribe_wav_bytes
from citation_format import format_citation_label
from stop_format import format_opening_hours, format_display_name
from feasibility import check_day_balance
from image_cache import get_cached_image_path

# R-22/R-23: icon shown in a stop's card when it has no real photo — never a
# fabricated image, just a neutral category glyph so the layout stays a
# consistent card grid either way.
CATEGORY_ICON = {
    "monument": "🏛️", "museum": "🖼️", "temple": "🛕", "mosque": "🕌",
    "church": "⛪", "gurdwara": "🙏", "park": "🌳", "market": "🛍️",
    "restaurant": "🍽️",
}

# Travel-planner color identity pass (2026-11-24, T1): groups the categories
# above into 3 travel-semantic families, reusing DESIGN.md's existing
# tokens. Deliberately CARD-ONLY (never the map) -- the map's marker colors
# already carry two other meanings (time-of-day, day-index), and a third
# meaning on the same 3 hues there would be unreadable.
CATEGORY_COLOR = {
    "monument": "#1B2A4A", "museum": "#1B2A4A", "temple": "#1B2A4A",
    "mosque": "#1B2A4A", "church": "#1B2A4A", "gurdwara": "#1B2A4A",
    "park": "#0E7C86",
    "market": "#E3A423", "restaurant": "#E3A423",
}
CATEGORY_COLOR_FALLBACK = "#8B8578"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# Design-alignment pass (2026-11-24, DESIGN.md M7): remapped from the old
# terracotta/indigo/blue/brick-red set to DESIGN.md §2's palette. Vermilion
# (#C1442D) is deliberately EXCLUDED from both maps -- DESIGN.md §2/§7
# reserves it for hard-fail feasibility only, "never decorative"; the old
# brick-red Day 5 and red slot fallback read as alerts and are replaced with
# a warm, non-alert tone instead. The two palettes stay SEPARATE (one
# slot-based, one day-based; collapsing them into one would make the two
# different semantics harder to tell apart at a glance).
SLOT_MARKER_COLOR = {
    "morning": [227, 164, 35],   # Turmeric Gold
    "afternoon": [27, 42, 74],   # Indigo Night
    "evening": [14, 124, 134],   # Peacock Teal
}
DAY_COLORS = [
    [14, 124, 134],   # Peacock Teal -- Day 1
    [227, 164, 35],   # Turmeric Gold -- Day 2
    [27, 42, 74],     # Indigo Night -- Day 3
    [139, 133, 120],  # Granite Grey -- Day 4
    [178, 127, 51],   # warm ochre (khadi/cotton family, not alert-red) -- Day 5
]
# UI/UX review (2026-10-24): the legend text (st.markdown's :color[] syntax)
# now maps to the SAME index as the RGB actually drawn above, each name
# chosen as the closest built-in Streamlit color keyword to that RGB --
# no more separate, independently hand-picked label-vs-color mapping that
# could silently drift apart. Streamlit's markdown color syntax only
# supports {red, orange, yellow, green, blue, violet, gray/grey, primary} --
# "red" is intentionally never used here (reserved for hard-fail/Vermilion).
DAY_COLOR_NAMES = ["green", "yellow", "violet", "gray", "orange"]


# Component audit Tier 3: measured the ACTUAL cached files before shipping
# this, not assumed — R-22's cache holds original Wikimedia Commons
# resolution, which ranges 100 KB to 17 MB per photo in this dataset.
# Inlining several of those as base64 in one carousel would balloon the
# page payload to tens of MB per rerun, a real performance problem, not a
# cosmetic one. Thumbnails are generated once (via Pillow, already a hard
# Streamlit dependency — st.image() itself needs it, so nothing new to
# install) and disk-cached alongside the originals, so only the FIRST
# render of a given photo pays the resize cost.
_CAROUSEL_THUMB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_cache", "_carousel_thumbs")
_CAROUSEL_THUMB_HEIGHT_PX = 160


def _carousel_thumbnail_data_uri(path: str | None) -> str | None:
    """Small, disk-cached JPEG thumbnail of an already-locally-cached stop
    photo (image_cache.py, R-22), base64-embedded for the day carousel's raw
    <img> tags — st.image() has no way to lay multiple images out in a
    horizontal scroll-snap strip, so this is the one place this file reaches
    for a raw <img> instead. Returns None (never a fabricated placeholder)
    on any failure, same discipline as get_cached_image_path itself."""
    if not path:
        return None
    try:
        os.makedirs(_CAROUSEL_THUMB_DIR, exist_ok=True)
        thumb_path = os.path.join(_CAROUSEL_THUMB_DIR, os.path.splitext(os.path.basename(path))[0] + ".jpg")
        if not os.path.exists(thumb_path):
            from PIL import Image

            with Image.open(path) as img:
                img = img.convert("RGB")
                ratio = _CAROUSEL_THUMB_HEIGHT_PX / img.height
                resized = img.resize((max(1, round(img.width * ratio)), _CAROUSEL_THUMB_HEIGHT_PX))
                resized.save(thumb_path, "JPEG", quality=72)
        with open(thumb_path, "rb") as f:
            data = f.read()
        return f"data:image/jpeg;base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None

# R-26 (round 4 UX benchmark, UX-23): a real hero photo for the empty state
# instead of a small info box in an otherwise-blank page — same real,
# license-clean Wikidata source as every stop's photo (R-22), not a
# licensed stock image this project doesn't have a budget for.
# Real bug fixed (2026-11-24): "the main home page picture is not loading in
# streamlit" (i.e. on Streamlit Community Cloud). Root cause, confirmed by
# fetching this exact URL directly: Wikimedia Commons returned
# "429 Too many requests" — Community Cloud apps share a small pool of
# outbound IPs across many unrelated apps, which Wikimedia's abuse
# protection rate-limits much more aggressively than an individual home
# connection. `image_cache.py`'s cache directory (`phase6/image_cache/`) is
# gitignored by design (it exists to avoid re-fetching PER-POI photos on
# every rerun, not to ship binaries in the repo) — so on every fresh Cloud
# deploy the cache starts empty and this fixed, never-changing hero image
# was being re-fetched live and silently failing (get_cached_image_path()
# returns None on any fetch error, by design — see its docstring). Unlike a
# POI photo, the hero image is a single constant asset, so the fix is to
# ship it as a committed static file instead of fetching it at all; this
# source URL is kept only as provenance for where `static/hero.jpg` came
# from (real Wikimedia Commons photo, same licensing as every other photo
# in the app), not as something the app fetches from at runtime anymore.
HERO_IMAGE_URL = "http://commons.wikimedia.org/wiki/Special:FilePath/Red%20Fort%2C%20Delhi%20by%20alexfurr.jpg"
HERO_IMAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "hero.jpg")


@st.cache_data
def _hero_image_data_uri() -> str | None:
    """
    Further fix (2026-11-24), same bug as above: bundling hero.jpg as a
    static file stopped the Wikimedia 429s, but on Cloud the image still
    silently failed -- confirmed live (a temporary debug caption + direct
    frame inspection) that os.path.exists(HERO_IMAGE_PATH) was True and
    Streamlit's MediaFileManager had registered it (the <img> tag carried a
    correct content-hash URL), yet the actual /media/<hash>.jpg HTTP request
    came back 404/500 right after the app woke from Cloud's sleep -- a
    serving-layer race, not a code bug. st.image(path) depends on that
    separate HTTP round-trip; base64-embedding the bytes directly into the
    page (the same pattern _carousel_thumbnail_data_uri already uses for
    stop photos) removes that dependency entirely -- the browser decodes it
    from the HTML it already has, no second request to fail. @st.cache_data
    avoids re-reading + re-encoding this fixed file on every rerun (the
    script reruns top-to-bottom on every interaction).
    """
    try:
        with open(HERO_IMAGE_PATH, "rb") as f:
            data = f.read()
        return f"data:image/jpeg;base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None

# Transcribing display (user request, 2026-07-16): a prominent indicator
# shown right under the input (via `listening_slot`, declared before the
# column split so it anchors under the input rather than at the page bottom
# — see the note there), covering the Groq Whisper round-trip after a
# browser-recorded clip (st.audio_input(), see the voice-input block below)
# comes back. No separate "Listening…" banner — st.audio_input() renders
# its own native recording/waveform UI in the browser, so a second
# hand-rolled "listening" indicator here would just duplicate it.
# UI/UX review (2026-10-24): was hard-coded blue (#1971c2), off-brand and
# invisible-risk in dark mode -- now the same --wp-accent token every other
# brand-colored element on the page uses, which already flips for dark mode
# (defined in the :root CSS block above).
_TRANSCRIBING_BANNER = """
<div style="border:2px solid var(--wp-accent); background:var(--wp-chip-bg);
     border-radius:999px; padding:10px 16px; margin:4px 0 12px;
     display:flex; align-items:center; gap:12px; justify-content:center;">
  <span class="wp-lsn-fade" style="font-size:1.3rem; display:inline-block;">✍️</span>
  <span style="font-weight:700; color:var(--wp-accent); font-size:1.05rem;">Transcribing what you said…</span>
</div>
<style>
@keyframes lsn-fade {0%{opacity:0.4;} 50%{opacity:1;} 100%{opacity:0.4;}}
.wp-lsn-fade { animation: lsn-fade 0.9s ease-in-out infinite; }
/* Design-alignment pass (2026-11-24, DESIGN.md L1/L4): transient status
   pill shape (DESIGN.md §4) + honor prefers-reduced-motion for the one
   looping animation on the page. */
@media (prefers-reduced-motion: reduce) {
    .wp-lsn-fade { animation: none; opacity: 1; }
}
</style>
"""

# MEDIUM-4 (Team Waypoint Voice-First UI review): move_stop()/
# recompute_slot_times() now live in phase4/edit_engine.py as the single
# shared implementation — a typed/spoken "move X earlier" (_apply_reorder)
# calls the exact same logic these buttons do, so voice-only users aren't
# blocked from reordering the way they were when this only existed here.
from edit_engine import move_stop as _move_stop, recompute_slot_times as _recompute_slot_times


st.set_page_config(page_title="Delhi Travel Planner", page_icon="🧭", layout="wide")

# Round 3 QA (UI3-1, UX3-4 -- "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
# two self-contained CSS fixes, styling only elements this file fully
# controls (never a fragile selector into Streamlit's internal emotion-cache
# classes, matching this codebase's established convention):
#   1. UI3-1: the page's one-and-only <h1> (from the single st.title() call
#      below) gets a distinct gradient/weight treatment so the brand title
#      reads as a different tier from plain st.subheader() (<h3>) section
#      headers -- previously both were the same default weight/color.
#   2. UX3-4: the Transcript column's fixed-height box wasn't sticky, so
#      scrolling past it left the whole right column blank beside the
#      itinerary's map/narrative/email content. Originally fixed with an
#      invisible marker span + a `:has()` selector reaching up to the
#      enclosing column; UI/UX review (2026-10-24) replaced that with
#      `st.container(key="transcript")` (`_render_transcript_and_sources()`,
#      below) + a direct `.st-key-transcript` rule -- same effect, no marker
#      element, no reaching through an ancestor selector.
#
# Team Waypoint theme proposal (2026-08-12) applied a type pairing, a second
# brand accent (deep indigo) for secondary actions, and pill buttons with a
# real primary/secondary hierarchy. UI/UX review (2026-10-24) moved what
# Streamlit's native theme CAN express — fonts, button/base radius, the
# accent — into config.toml (both copies, kept in sync by hand; see their
# header comments), so only what theming genuinely can't do stays here: the
# --wp-* tokens for bespoke elements (badge pills, secondary accent, card
# borders, the gradient-clipped h1) that have no native theme key, plus the
# handful of hand-built components (carousel, sticky map/transcript,
# enlarged mic, stop-name/time-chip spans). Selectors verified against the
# actually-installed Streamlit version (1.57.0)'s own compiled frontend
# bundle rather than guessed: `stBaseButton-{kind}`, `stChatInputMicButton`
# are real data-testid values it emits, not emotion-cache class names.
# User request (2026-11-24): light mode removed entirely (config.toml now
# sets `base = "dark"` with no `[theme.light]`) -- the --wp-* tokens below
# used to be split between a light-mode `:root` default and a
# `@media (prefers-color-scheme: dark)` override; now there's only one mode,
# so they're a single unconditional block (the former dark-mode values).
st.html(
    """
<style>
/* Component audit Tier 7: Material Symbols -- applied to a small, bounded
   set of functional icons (the safety/logistics bits below) as a slice of
   an icon-font hybrid, not a wholesale emoji replacement. Emoji stay
   everywhere else (buttons, badges, the hero tagline) -- they're
   zero-asset-cost, already work, and carry real warmth a uniform icon set
   would flatten; this only reaches for a re-tintable, cross-platform-
   consistent icon where "functional UI chrome, not expressive content" is
   the clearer read. */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20,400,0,0&display=swap');

/* Design-alignment pass (2026-11-24, DESIGN.md H2/H3/M2/M3/M5/L2): Peacock
   Teal primary + Turmeric Gold secondary, Indigo Night surfaces, Granite
   Grey structure, Vermilion reserved for hard-fail only -- the single
   (dark-only, see the note above) token set. */
:root {
    --wp-accent: #2AA7B0;
    --wp-accent-deep: #7FD0D6;
    --wp-secondary: #E3A423;
    --wp-secondary-deep: #F0C45E;
    --wp-secondary-soft: rgba(227,164,35,0.18);
    --wp-surface: #243655;
    --wp-ink-soft: #A8A394;
    --wp-border: #5A5445;
    --wp-error: #E0624A;
    --wp-error-soft: rgba(224,98,74,0.16);
    --wp-h1-gradient-end: var(--wp-accent-deep);
    /* UI/UX review (2026-10-24): fact-chip background -- was a hard-coded
       rgba() literal inline on each badge, now a token so every badge
       adapts alongside --wp-accent-deep's text color together. */
    --wp-chip-bg: rgba(42,167,176,.18);
}
/* User request (2026-11-24): flat Indigo Night read as "just blue," with no
   particular tie to travel/geography. Replaces the solid page background
   with a deep map-navy -> Indigo Night gradient plus a sparse, fixed-
   position "night sky" star field -- evokes travel/wanderlust (night
   flights, stargazing) without competing with the foreground content.
   Scoped to `.stApp` (verified directly against the installed Streamlit
   1.57.0 DOM -- it's the one element actually painting the page
   background; `stAppViewContainer`/`stMain` are both transparent). Stars
   are a handful of fixed-position radial-gradient dots, not a repeating
   pattern, so it reads as deliberate rather than noisy; `background-size`
   keeps them from scaling oddly on resize. Previously gated behind
   `@media (prefers-color-scheme: dark)`; unconditional now that dark is the
   app's only mode. */
/* `!important` needed here (unlike most rules in this file): Streamlit's
   own emotion-generated stylesheet sets `.stApp`'s background-color via an
   equal-specificity class rule injected later in the DOM, so on a pure
   specificity/order tie it would otherwise win. Verified directly against
   the installed 1.57.0 frontend -- without `!important` this rule is
   silently dropped and the flat color shows through. */
.stApp {
    background-image:
        radial-gradient(1.5px 1.5px at 12% 18%, rgba(237,231,214,0.55), transparent),
        radial-gradient(1px 1px at 28% 9%, rgba(237,231,214,0.35), transparent),
        radial-gradient(2px 2px at 50% 14%, rgba(237,231,214,0.5), transparent),
        radial-gradient(1px 1px at 68% 6%, rgba(237,231,214,0.3), transparent),
        radial-gradient(1.5px 1.5px at 83% 20%, rgba(237,231,214,0.45), transparent),
        radial-gradient(1px 1px at 93% 11%, rgba(237,231,214,0.3), transparent),
        radial-gradient(1px 1px at 8% 38%, rgba(237,231,214,0.3), transparent),
        radial-gradient(1.5px 1.5px at 37% 42%, rgba(237,231,214,0.35), transparent),
        radial-gradient(1px 1px at 72% 36%, rgba(237,231,214,0.3), transparent),
        radial-gradient(1px 1px at 95% 48%, rgba(237,231,214,0.25), transparent),
        linear-gradient(180deg, #0B1526 0%, #16243F 45%, #1B2A4A 100%) !important;
    background-size: 100% 100% !important;
    background-attachment: fixed !important;
}

.wp-icon {
    font-family: 'Material Symbols Outlined';
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
    font-size: 1rem;
    vertical-align: -0.15em;
    color: var(--wp-accent);
}

h1 {
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--wp-accent), var(--wp-h1-gradient-end));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
/* UI/UX review (2026-10-24): replaces the old invisible-marker + :has()
   selector -- _render_transcript_and_sources() now renders into a real
   st.container(key="transcript"), which Streamlit exposes as this stable
   .st-key-* class directly, no marker element needed. */
.st-key-transcript {
    position: sticky;
    top: 1rem;
    align-self: flex-start;
}
/* UI/UX review (2026-10-24), overhaul #2: each Day tab's map container is
   keyed `day_map_{day_key}` (one distinct class per day, e.g.
   `st-key-day_map_day_1`) -- a substring attribute selector targets all of
   them without listing every possible day key. */
[class*="st-key-day_map_"] {
    position: sticky;
    top: 1rem;
    align-self: flex-start;
}

/* User request (2026-08-12): "make the mic bigger and more visible" --
   round 3. Round 1 (scale 1.5) read as too subtle; round 2 (scale 2.3)
   overshot. UI/UX review (2026-10-24) retargets this from the old
   st.audio_input() testids to st.chat_input()'s own, now that the composer
   migration (overhaul #1) replaced that widget -- `stChatInputMicButton`
   verified against the actually-installed Streamlit version's own compiled
   frontend bundle (1.57.0), same discipline as every other selector in
   this file. A smaller scale than the old 1.8 since this icon sits inside
   a single-line input row rather than its own dedicated widget -- 1.8
   overlapped the text area and submit button when checked live. */
[data-testid="stChatInputMicButton"] {
    transform: scale(1.4);
    transform-origin: center;
}

/* Secondary-button accent: Streamlit's theme has one primary accent, not a
   second one for secondary actions -- this app's two-accent hierarchy
   (Peacock Teal primary / Turmeric Gold secondary, DESIGN.md §2) has no
   native key, so it's still set here. Pill shape itself now comes from
   config.toml's buttonRadius. */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    border-color: var(--wp-secondary) !important;
    color: var(--wp-secondary) !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background-color: var(--wp-secondary-soft) !important;
}
/* Design-alignment pass (2026-11-24, DESIGN.md L5): standardized on
   DESIGN.md §4's single reserved soft-shadow token (Indigo-Night-based) --
   was an accent-tinted shadow that varied by theme; the app otherwise stays
   flat-by-default (hairline borders only), so this is kept as the one
   shadow on the page. */
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    box-shadow: 0 4px 16px rgba(27,42,74,0.12);
}

/* Design-alignment pass (2026-11-24, DESIGN.md M5): recolor native
   st.error/st.warning chrome toward DESIGN.md §7's severity language
   (error = Vermilion, warning = Turmeric Gold) instead of Streamlit's stock
   red/yellow. Selectors verified live against the installed 1.57.0 frontend
   bundle, same discipline as the mic-button selector above. Only the color
   changes -- the widgets themselves (st.error/st.warning calls) are
   untouched. */
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
    background-color: var(--wp-error-soft) !important;
}
[data-testid="stAlertContentError"] {
    color: var(--wp-error) !important;
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    background-color: var(--wp-secondary-soft) !important;
}
[data-testid="stAlertContentWarning"] {
    color: var(--wp-secondary-deep) !important;
}

/* Design-alignment pass (2026-11-24, DESIGN.md M8): visible keyboard focus
   ring on interactive elements, both surfaces. */
:focus-visible {
    outline: 2px solid var(--wp-accent);
    outline-offset: 2px;
}

/* Stop-name / clock-time treatment -- rendered via the .wp-stop-name /
   .wp-time-chip spans in the Day view's stop cards (below). */
.wp-stop-name {
    font-family: 'Baloo 2', sans-serif;
    font-weight: 600;
    font-size: 1.05rem;
}
.wp-time-chip {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    background: var(--wp-surface);
    border: 1px solid var(--wp-border);
    color: var(--wp-ink-soft);
    border-radius: 999px;
    padding: 0.05rem 0.6rem;
    white-space: nowrap;
}

/* Component audit Tier 3: a horizontal-scroll photo carousel at the top of
   each Day tab (CSS scroll-snap, no JS component needed) -- reuses the
   same cached Wikidata photos already loaded per stop card, giving an
   immediate "mood board" for the day before scrolling into the detailed
   card list below it. */
.wp-carousel {
    display: flex;
    gap: 0.6rem;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    padding: 0.3rem 0 0.9rem;
    margin-bottom: 0.2rem;
}
.wp-carousel-img {
    height: 112px;
    width: auto;
    border-radius: 10px;
    scroll-snap-align: start;
    flex: 0 0 auto;
    object-fit: cover;
    border: 1px solid var(--wp-border);
}
</style>
"""
)

if "agent" not in st.session_state:
    st.session_state.agent = TravelAgent(tts=None, log_level="quiet")
if "transcript" not in st.session_state:
    st.session_state.transcript = []
if "pending_audio_text" not in st.session_state:
    st.session_state.pending_audio_text = None
if "pending_voice_text" not in st.session_state:
    # HIGH-1 (Team Waypoint Voice-First UI review): a mic clip that's been
    # transcribed but not yet sent — the user gets a beat to spot a
    # misheard word before it's acted on, instead of it firing immediately.
    st.session_state.pending_voice_text = None
if "voice_editing" not in st.session_state:
    # UI/UX review (2026-10-24): True while the small "Edit what I heard"
    # text_input (below) is shown in place of the Send/Edit/Discard trio.
    st.session_state.voice_editing = False
if "text_input_version" not in st.session_state:
    # User report (2026-08-12): a widget prefilled via session_state before
    # a fixed-key rerun relies on the browser reusing/re-syncing that exact
    # component instance, which proved unreliable live even though it's the
    # standard Streamlit pattern (and passed in a headless AppTest
    # simulation). Bumping the key on every prefill forces a genuinely fresh
    # widget instance instead, removing any dependency on same-key re-sync
    # behavior. Used for the voice-edit box below (see mic_key_version for
    # the composer's own equivalent).
    st.session_state.text_input_version = 0
if "mic_key_version" not in st.session_state:
    # "Start a new trip" bumps this so the composer mounts a genuinely fresh
    # instance — same reasoning as text_input_version above.
    st.session_state.mic_key_version = 0
if "celebrated_first_build" not in st.session_state:
    # Component audit Tier 7: st.balloons() only ever fires ONCE per trip —
    # a build success is worth a real moment; a follow-up edit shouldn't
    # trigger the same celebration again, which would get old fast (the
    # same "occasionally, not always" discipline already applied to the
    # post-edit nudges). Reset alongside everything else in _start_new_trip()
    # below, so a genuinely new trip earns its own first-build moment.
    st.session_state.celebrated_first_build = False

agent: TravelAgent = st.session_state.agent

# R-17/QA-13: never give the agent a "speak" TTS — that used to make
# `process_turn` block synchronously on server-side audio playback
# (a busy-wait inside `st.spinner`), freezing the whole app for the
# entire spoken duration with no way to stop it. Voice output is
# handled separately in _send()/_play_reply_audio() below: synthesize
# audio bytes (no playback) after the reply is ready, then hand them to
# st.audio() for non-blocking browser playback.
agent.tts = None


def _start_new_trip() -> None:
    agent.reset()
    st.session_state.transcript = []
    st.session_state.mic_key_version += 1  # discards any previously recorded clip (see init comment above)
    st.session_state.text_input_version += 1  # discards any unsent, un-submitted text left in the box
    st.session_state.pending_voice_text = None
    st.session_state.voice_editing = False
    st.session_state.celebrated_first_build = False  # Tier 7: a fresh trip earns its own first-build celebration
    st.rerun()


# Component audit (2026-08-12, "Team-Waypoint-Component-Level-UI-Audit.md",
# Tier 6): "Start a new trip" used to live ONLY in the sidebar -- the one
# place R-31 already found "most users never look," now holding the app's
# single most consequential destructive action. Promoted to a slim top-bar
# row next to the title instead, where every benchmark travel app (Wanderlog,
# TripIt) keeps its "new trip" action visible at all times. The sidebar is
# repurposed for what sidebars are actually for in those apps -- settings and
# trust/attribution info -- rather than left holding nothing.
title_col, newtrip_col = st.columns([5, 1.4])
with title_col:
    st.title("🧭 Delhi Travel Planner")
with newtrip_col:
    # UI/UX review (2026-10-24), quick win #5: nothing to reset before a
    # trip exists, so the button only renders once there's actually a trip
    # to discard — Tier 6's "visible at all times" reasoning still holds
    # for every state where that's literally true.
    if agent.itinerary:
        st.write("")  # vertical spacer so the button lines up with the title's baseline, not its top
        if st.button("🔄 Start a new trip", key="new_trip_topbar", use_container_width=True):
            _start_new_trip()

# UI/UX review (2026-10-24), quick win #6: this attribution text appeared
# 4 times across the app (sidebar, landing caption, plan badge, footer) --
# the same wording as the footer below, which already covers it. This
# sidebar block had nothing else in it, so removing the duplicate left it
# empty; removed entirely rather than leave a header over nothing. Kept
# surviving: the badge's hover-help text (a different kind of mention, not
# standing visible copy) and the footer.

# --------------------------------------------------------------------------- #
# Input area — voice-first (round 5, R-29/R-30/R-31/R-32/R-33)
# --------------------------------------------------------------------------- #
# Rendered as a genuine top-level element BEFORE the column layout below,
# not after: Streamlit anchors a column's content to wherever st.columns()
# is *called*, so an un-columned element declared after that call still
# renders below everything later written into those columns, regardless of
# its own position in script order. The old input row was declared after
# st.columns() and so silently rendered below the entire onboarding
# column's content (hero photo, tagline, capability list, chips) — a real
# bug confirmed by measuring live element positions (Send/Speak buttons at
# y=1250 vs. the hero image at y=246) before concluding it, not assumed.
# Moving the input here, genuinely before any column, is what actually
# puts it above the fold (fixes UX-28).
_, toggle_col = st.columns([5, 2])
with toggle_col:
    # R-31/UX-29: moved out of the sidebar (where most users never look)
    # and defaulted on — safe now that playback is non-blocking browser
    # audio (R-17) using free, keyless edge-tts, so defaulting it on adds
    # no freeze risk and no API cost.
    # Component audit Tier 4: a live on/off setting reads as a switch, not a
    # form checkbox — st.toggle() renders a real sliding switch (unlike
    # st.checkbox's square box), matching how comparable apps present this
    # exact kind of preference.
    voice_output = st.toggle(
        "🔊 Speak replies", value=True,
        help="Plays right here in your browser after each reply.",
    )

# UI/UX review (2026-10-24), overhaul #1: ONE composer for voice and text,
# replacing the separate st.audio_input() + st.form text input below. It
# still records from the BROWSER's microphone (unlike the old
# sr.Microphone()-based capture in phase3/stt.py's capture_mic_audio(),
# still used by the local CLI path, which opens whatever mic is attached to
# the machine *running the Python process* -- meaningless on a remote host
# like Streamlit Community Cloud). st.chat_input() is also inherently an
# event-returning widget (its value is only non-None on the run it was
# submitted, same as a button) -- so, unlike st.audio_input(), it needs no
# fingerprint check to avoid re-processing a stale clip on an unrelated
# rerun, and no st.form() wrapper (it already has its own submit gesture).
#
# Round 3 QA (UX3-3) / R-29/R-33 reasoning still holds and still applies:
# text stays equally reachable either way -- now trivially true, since
# there's only one control. User request (2026-10-25): the standalone
# pulsing mic glyph that used to sit above the composer here (R-29-33) was
# removed -- the chat_input's own built-in mic button already carries that
# affordance, so a second decorative one above it was redundant.
if not agent.itinerary:
    composer_placeholder = "Tell me about your trip, or tap the mic to speak"
else:
    composer_placeholder = "Ask or edit your itinerary, or tap the mic to speak"

msg = st.chat_input(
    composer_placeholder,
    accept_audio=True,
    key=f"composer_{st.session_state.mic_key_version}",
)

# User request (2026-07-16): the "transcribing" display renders into this
# slot, declared HERE — directly beneath the input area and, crucially,
# BEFORE the st.columns() split below. A Streamlit placeholder anchors where
# it's *declared*, so this sits right under the composer (above the fold,
# where the user is looking). The `if msg and msg.audio:` block further down
# that writes into it runs at top level AFTER st.columns() — and would
# otherwise surface at the very bottom of the page (the same render-order
# quirk documented for the input area above) without this.
listening_slot = st.empty()

# User request (2026-07-17): a permanent right-hand transcript pane —
# previously the transcript was only a real side column before a plan
# existed (R-27); once built, it demoted to a collapsed expander at the
# very bottom with no persistent presence and no way to scroll through
# history. Now always a co-equal column, both pre- and post-build, so the
# ratio never changes and there's no layout jump the moment a build
# finishes.
col_itinerary, col_side = st.columns([2, 1])

THINKING_MESSAGE = "Thinking... (building a full itinerary can take up to 30s — searching real places and checking feasibility)"

# UX-11/R-14: clickable example prompts for first-time users — each one is a
# real send (same path as typing it), so it costs nothing extra beyond what
# the user would have spent typing it themselves.
EXAMPLE_PROMPTS = [
    ("🍛 Food & history, 2 days", "Plan a 2-day trip to Delhi, I like food and history, moderate pace"),
    ("🏛️ Culture & shopping, 3 days", "Plan a 3-day trip to Delhi focused on culture and shopping"),
    ("👨‍👩‍👧 Relaxed family trip", "Plan a relaxed 2-day family-friendly trip to Delhi"),
]


def _play_reply_audio(text: str) -> None:
    """
    R-17/QA-13: synthesizes speech and hands the bytes to st.audio() for
    non-blocking browser playback, instead of the old server-side pygame
    busy-wait that froze the whole UI for the entire spoken duration with
    no way to stop it. st.audio()'s player also gives native pause/seek
    controls for free — no custom "Stop" button needed.
    """
    result = TTS(mode="speak").synthesize(text)
    if result is None:
        st.caption("⚠️ Voice playback is unavailable right now.")
        return
    audio_bytes, mime, backend = result
    # UI/UX review (2026-10-24): this static caption used to stay on screen
    # after playback ended, since Streamlit can't observe browser-side
    # audio-element completion without a custom JS component (R-32/UX-30's
    # original reasoning for adding it) — removed in favor of the audio
    # player's own visible controls, which already show playing/paused
    # state natively and don't go stale the way a fixed caption does.
    st.audio(audio_bytes, format=mime, autoplay=True)
    if backend == "pyttsx3":
        # R-19/QA-14: this fallback used to be a server-console-only print,
        # invisible in the browser — an unexplained drop to a robotic voice
        # reads as a glitch without this.
        st.caption("🔉 Using the offline voice right now — reconnect for the natural voice.")


def _send(text: str) -> None:
    had_itinerary_before = bool(agent.itinerary)
    st.session_state.transcript.append(("You", text))
    if not had_itinerary_before:
        # Component audit Tier 5: a build genuinely does these steps in
        # order (agent.py's _build_itinerary(): poi_search_logic ->
        # itinerary_builder_logic -> feasibility eval -> weather/safety/
        # transit enrichment -> the narrator). st.status() can't observe
        # REAL completion of each one without deeper callback plumbing into
        # agent.py (process_turn() is one opaque blocking call from here) --
        # so these render up front as "what a build involves," not a
        # live-synchronized tracker. Still an honest, real upgrade over one
        # flat spinner sentence for the whole ~30s wait: a real checkmark on
        # completion, and it only claims steps a build actually performs —
        # never shown for a plain edit/question turn, which doesn't do any
        # of them.
        with st.status(THINKING_MESSAGE, expanded=True) as status:
            st.write("🔎 Searching real places that match your interests")
            st.write("🧭 Checking feasibility and travel times")
            st.write("📝 Writing your trip overview")
            reply, _ = agent.process_turn(text)
            status.update(label="Your itinerary is ready!", state="complete", expanded=False)
    else:
        with st.spinner("Thinking..."):
            reply, _ = agent.process_turn(text)
    st.session_state.transcript.append(("Agent", reply))
    if voice_output:
        # Round 3 QA (UX3-2, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
        # this used to call _play_reply_audio(reply) directly, right here —
        # but _send() runs from a top-level button handler *after*
        # `col_itinerary, col_side = st.columns(...)` is already called
        # without itself being inside either column's `with` block. By this
        # app's own documented Streamlit render-anchoring rule (see the
        # input-row and listening-banner comments above), that meant the
        # "Speaking your reply..." caption + audio player always rendered
        # below BOTH columns — a stray full-width strip nowhere near the
        # actual reply bubble it belongs to (confirmed live: it landed
        # between the map/expanders and the email section). Deferring to a
        # flag that `_render_transcript_and_sources()` reads and clears --
        # from *inside* `with col_side:` — puts playback directly under the
        # transcript it accompanies, the same fix shape already proven twice
        # in this codebase (R-27, the Listening Indicator round).
        st.session_state.pending_audio_text = reply
    if agent.itinerary and not had_itinerary_before:
        # UI/UX review (2026-10-24): st.balloons() read as playful but
        # off-tone for a planning tool (Component audit Tier 7's original
        # reasoning for adding it focused on marking the moment, not on
        # balloons specifically). st.toast() gives the same one-time
        # acknowledgment with far less motion. Still gated on
        # celebrated_first_build so it fires once per trip, not on every
        # subsequent edit.
        if not st.session_state.get("celebrated_first_build"):
            st.session_state.celebrated_first_build = True
            n_days = len([k for k in agent.itinerary if k.startswith("day_")])
            st.toast(f"🎉 Your {n_days}-day plan is ready!")
        # R-27: the itinerary-hero column layout is decided once, near the
        # top of the script, before this function (called from a button
        # handler further down) runs in that same execution — so a build
        # that happens INSIDE this call wouldn't switch to the full-width
        # layout until some unrelated later rerun without this. Force one
        # now so the hero layout applies on the very render the plan
        # finishes, not one interaction late.
        st.rerun()


# UI/UX review (2026-10-24): msg is None on every rerun except the one where
# the composer was actually submitted (text or audio) -- an event, not a
# persisted value, so there's no stale-clip fingerprint check needed the way
# st.audio_input() required.
if msg and msg.audio:
    _audio_bytes = msg.audio.getvalue()
    # User request (2026-07-16): a prominent "transcribing" display at a
    # suitable location — rendered into `listening_slot` (declared above,
    # before the column split) so it appears directly under the input the
    # user just recorded into, not at the bottom of the page. No separate
    # "Listening…" phase here (R-20's original two-phase design) since
    # st.chat_input()'s own recording UI already covers that — this banner
    # only covers the Groq Whisper round-trip afterward.
    listening_slot.markdown(_TRANSCRIBING_BANNER, unsafe_allow_html=True)
    heard, error = try_transcribe_wav_bytes(_audio_bytes)
    if error:
        listening_slot.warning(error)
    elif heard:
        # HIGH-1 (Team Waypoint Voice-First UI review): don't act on a
        # transcription immediately — surface it for a one-tap
        # confirm/edit/discard first, so a misheard word ("Nice" for
        # "Nikko," the docx's own example) never silently executes. Kept
        # as-is through the composer migration (explicit user decision,
        # 2026-10-24) rather than adopting the review's "auto-send short
        # clips" suggestion.
        st.session_state.pending_voice_text = heard
        st.rerun()
    else:
        listening_slot.empty()
elif msg and msg.text.strip():
    _send(msg.text)

if st.session_state.get("pending_voice_text"):
    with listening_slot.container():
        if st.session_state.get("voice_editing"):
            # UI/UX review (2026-10-24): st.chat_input() has no supported way
            # to set its own value from session_state (unlike the old
            # text_input, which the "✏️ Edit" button used to prefill) -- so
            # editing a misheard clip now happens in this small, separate,
            # self-contained text_input instead of trying to route back
            # through the main composer. Same versioned-key pattern already
            # used elsewhere in this file (mic_key_version) for forcing a
            # genuinely fresh widget instance rather than relying on same-key
            # re-sync.
            edit_key = f"voice_edit_box_{st.session_state.text_input_version}"
            edited = st.text_input("Edit what I heard", key=edit_key, label_visibility="collapsed")
            ecol1, ecol2 = st.columns([1.6, 1])
            if ecol1.button("✅ Send", type="primary", use_container_width=True, key="voice_edit_send"):
                st.session_state.pending_voice_text = None
                st.session_state.voice_editing = False
                _send(edited)
                st.rerun()
            if ecol2.button("✕ Cancel", use_container_width=True, key="voice_edit_cancel"):
                st.session_state.voice_editing = False
                st.rerun()
        else:
            st.markdown(f'🎙️ **Heard:** "{st.session_state.pending_voice_text}"')
            vcol1, vcol2, vcol3 = st.columns([1.6, 1, 1])
            if vcol1.button("✅ Send", type="primary", use_container_width=True, key="voice_confirm_send"):
                heard_text = st.session_state.pending_voice_text
                st.session_state.pending_voice_text = None
                _send(heard_text)
                st.rerun()
            if vcol2.button("✏️ Edit", use_container_width=True, key="voice_confirm_edit"):
                st.session_state.text_input_version += 1
                st.session_state[f"voice_edit_box_{st.session_state.text_input_version}"] = st.session_state.pending_voice_text
                st.session_state.voice_editing = True
                st.rerun()
            if vcol3.button("✕ Discard", use_container_width=True, key="voice_confirm_discard"):
                st.session_state.pending_voice_text = None
                st.rerun()

def _render_overview_tab(agent: TravelAgent, day_keys: list[str]) -> None:
    """
    UI/UX review (2026-10-24), overhaul #3: the narrator's prose overview,
    the transit-info expander, the degraded-enrichment retry, and the
    all-days map used to render below every day tab (so they were usually
    below the fold, after scrolling past the full day-by-day list). Now
    they're the content of a dedicated first "Overview" tab instead.
    """
    if agent.enrichment_degraded:
        # QA-8/R-13: narrative/safety/transit hit a real error (e.g. rate
        # limit) during the build — say so honestly instead of just
        # rendering nothing, with an explicit (not automatic) retry.
        st.warning(
            "Couldn't load the full overview / safety notes just now — "
            "your day-by-day plan is unaffected."
        )
        if st.button("🔄 Retry overview & safety info"):
            with st.spinner("Retrying..."):
                agent.retry_enrichment()
            st.rerun()

    if agent.narrative:
        if agent.narrative_stale:
            # User report (2026-07-25): this section didn't "refresh
            # automatically" after an edit -- true by design (QA-2/R-3:
            # regenerating the full narrative on every single edit would
            # mean an extra LLM call per edit, and this project has hit real
            # Gemini free-tier rate limits from far less), but there was
            # previously no way to refresh it at all, only a caption saying
            # it was stale. Reuses retry_enrichment() -- the same explicit,
            # user-triggered-only regeneration used for the
            # enrichment-degraded retry button above -- against the CURRENT
            # (already-edited) itinerary.
            st.caption(
                "⚠️ This overview describes your original plan — the Day tabs "
                "already reflect your latest edits."
            )
            if st.button("🔄 Refresh this overview for your latest edits"):
                with st.spinner("Regenerating the full overview..."):
                    agent.retry_enrichment()
                st.rerun()
        st.markdown(agent.narrative)

    if agent.transit_info:
        with st.expander("🚇 Getting around Delhi", expanded=not agent.narrative):
            st.write(agent.transit_info["answer"])
            for c in agent.transit_info.get("citations", []):
                st.caption(f"Source: [{format_citation_label(c)}]({c.get('source_url', '')})")

    # Round 3 QA (UX3-6, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
    # the per-day map in each Day tab only ever shows one day at a time --
    # this is a real, working second view with every stop across the whole
    # trip on one map, colored by DAY instead of time-of-day (so it doesn't
    # collide with the per-day map's own color legend). Deliberately not
    # attempting per-day route lines or a click-to-jump-to-stop interaction
    # here: pydeck's Python wrapper has no click callback for this, so a
    # real "jump to stop" would need a day-toggle + selectbox substitute --
    # a larger effort than this Low-priority item warrants; this delivers
    # the finding's core ask (see everything at once) honestly, without
    # overclaiming full feature parity with a dedicated mapping product.
    if len(day_keys) > 1:
        with st.expander("🗺️ All days on one map"):
            all_days_stops = []
            for d_idx, d_key in enumerate(day_keys):
                d = agent.itinerary[d_key]
                for slot in ("morning", "afternoon", "evening"):
                    for stop in d.get(slot, []):
                        all_days_stops.append({
                            "lat": stop["lat"], "lon": stop["lon"],
                            "name": format_display_name(stop["name"]),
                            "day": d_key.split("_")[1],
                            "tooltip_text": f"Day {d_key.split('_')[1]}: {format_display_name(stop['name'])} ({stop.get('category', 'stop')})",
                            "color": DAY_COLORS[d_idx % len(DAY_COLORS)],
                        })
            if all_days_stops:
                all_df = pd.DataFrame(all_days_stops)
                all_view = pdk.data_utils.compute_view(all_df[["lon", "lat"]])
                all_view.pitch = 0
                all_deck = pdk.Deck(
                    map_style=None,
                    initial_view_state=all_view,
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer", data=all_df, get_position=["lon", "lat"],
                            get_fill_color="color", get_radius=90, radius_min_pixels=10,
                            pickable=True,
                        ),
                    ],
                    tooltip={"text": "{tooltip_text}"},
                )
                st.pydeck_chart(all_deck)
                # UI/UX review (2026-10-24), quick win #7: color_name is
                # indexed the same way as the "color" field actually drawn
                # above (both by d_idx % len(...)), so the legend text can't
                # drift out of sync with the real RGB values the way a
                # separately hand-picked :orange:/:blue:/... chain could.
                legend = " · ".join(
                    f":{DAY_COLOR_NAMES[d_idx % len(DAY_COLOR_NAMES)]}[●] Day {d_key.split('_')[1]}"
                    for d_idx, d_key in enumerate(day_keys)
                )
                st.caption(f"Colors mark which day a stop belongs to: {legend}")


@st.fragment
def _render_day_tab(agent: TravelAgent, key: str, balance_notes_by_day: dict[int, list[str]]) -> None:
    """
    UI/UX review (2026-10-24), overhaul #2 + #7: stop cards beside a sticky
    map instead of the map after every card and the safety expander (so it
    used to be below the fold); clicking a marker highlights its card.
    @st.fragment (overhaul #7) means a reorder move only reruns this one
    day's tab, not the whole page.
    """
    day = agent.itinerary[key]
    day_num = int(key.split("_")[1])
    all_stops: list[dict] = []
    cards_col, map_col = st.columns([3, 2], gap="medium")

    with cards_col:
        st.caption(f"Total scheduled time: {day.get('total_hours', 0)}h")
        # MEDIUM-3 (Team Waypoint Voice-First UI review): "surface
        # contextual example prompts that change based on where the person
        # is ('Try: make day 2 more relaxed' while viewing day 2)."
        # Streamlit's st.tabs() renders every tab's content in the same
        # script run (the browser just shows/hides them), so there's no
        # server-side "which tab is active" signal to key off of — but
        # writing the Day-N-specific line INSIDE this tab's own block still
        # achieves exactly what the user sees: whichever tab is open shows
        # its own matching example.
        st.caption(f"💬 Try: \"make Day {day_num} more relaxed\" or \"swap a Day {day_num} stop for something else\"")
        # Design-alignment pass (2026-11-24, DESIGN.md M4): balance notes are
        # exactly DESIGN.md §7's never-blocking "warning" severity, whose
        # prescribed visual is a small Turmeric Gold chip -- was a neutral
        # grey caption. Styling only; check_day_balance()'s data/text is
        # unchanged. html.escape() guards the note text the same way the
        # fact-chip badges below do, since this also goes through st.html.
        for note in balance_notes_by_day.get(day_num, []):
            st.html(
                "<div style='display:inline-flex;align-items:center;gap:6px;"
                "background:var(--wp-secondary-soft);border:1px solid var(--wp-secondary);"
                "color:var(--wp-secondary-deep);border-radius:999px;"
                "padding:3px 12px;font-size:0.85rem;margin:2px 0 8px;'>"
                f"⚠ {html.escape(note)}</div>"
            )

        # Component audit Tier 3: the day's real stop photos as a
        # scroll-snap carousel, reusing the exact same cache R-22 already
        # populates per stop card (no new fetch, no new data). Capped at 8
        # images to keep the base64-inlined payload bounded even on a long,
        # photo-rich day.
        day_photo_uris = [
            _carousel_thumbnail_data_uri(get_cached_image_path(s.get("image")))
            for slot_ in ("morning", "afternoon", "evening")
            for s in day.get(slot_, [])
        ]
        day_photo_uris = [u for u in day_photo_uris if u][:8]
        if day_photo_uris:
            imgs_html = "".join(f'<img src="{uri}" class="wp-carousel-img">' for uri in day_photo_uris)
            st.html(f'<div class="wp-carousel">{imgs_html}</div>')

        for slot_label, slot_key in (("☀️ Morning", "morning"), ("🌤️ Afternoon", "afternoon"), ("🌙 Evening", "evening")):
            stops = day.get(slot_key, [])
            if not stops:
                continue
            st.markdown(f"**{slot_label}**")
            for stop_idx, stop in enumerate(stops):
                # R-11: cosmetic-only display-name cleanup ("HANUMAN MANDIR"
                # -> "Hanuman Mandir") — never touches the stored name
                # (dedup/citations/narrator all still see the original OSM
                # string via `stops`/`itin`).
                stop = {**stop, "_slot_key": slot_key, "_stop_idx": stop_idx, "name": format_display_name(stop["name"])}
                all_stops.append(stop)

                # R-23 (fixes UX-20): a bordered card per stop instead of a
                # flat markdown bullet — photo + name/time on one row,
                # category/duration/travel as a caption, grounded facts
                # promoted to visible badges (R-24/UX-21). UI/UX review
                # (2026-10-24): keyed so a marker click below can target
                # this exact card's border via CSS (see the highlight block
                # at the end of this function).
                card_key = f"stopcard_{key}_{slot_key}_{stop_idx}"
                # Travel-planner color identity pass (2026-11-24, T1): a
                # thin category-colored left border (Indigo=heritage/sacred,
                # Teal=park, Gold=food/market) -- card-only, see
                # CATEGORY_COLOR's comment for why this never touches the map.
                cat_color = CATEGORY_COLOR.get(stop["category"], CATEGORY_COLOR_FALLBACK)
                st.html(
                    f"<style>.st-key-{card_key} {{ border-left: 3px solid {cat_color} !important; }}</style>"
                )
                with st.container(border=True, key=card_key):
                    img_col, info_col, move_col = st.columns([1, 4, 0.4])
                    with img_col:
                        # R-22 (fixes QA-17/UX-19): a real photo when one
                        # exists (Wikidata P18, cached locally) — previously
                        # fetched into the dataset and then silently dropped
                        # one stage before the UI. UI/UX review (2026-10-24),
                        # quick win: rendered as a fixed-height, cropped
                        # thumbnail (reusing the same cache the carousel
                        # above already builds) so every card's photo has a
                        # consistent aspect ratio instead of each venue's
                        # own native photo proportions.
                        thumb_uri = _carousel_thumbnail_data_uri(get_cached_image_path(stop.get("image")))
                        if thumb_uri:
                            st.html(f'<img src="{thumb_uri}" style="width:100%;height:90px;object-fit:cover;border-radius:8px;display:block;">')
                        else:
                            # Round 3 QA (UI3-2): a flat neutral-gray box next
                            # to real photo cards read as "half-finished,"
                            # not as "this venue has no public photo" (a
                            # genuine fact of the open dataset — meal stops
                            # almost never carry a Wikidata image the way
                            # monuments do). A subtle tint of the app's own
                            # brand accent reads as a deliberate, on-brand
                            # placeholder instead of a missing asset.
                            # Travel-planner color identity pass (2026-11-24,
                            # T2): was hard-coded to the retired terracotta
                            # accent (rgba(194,84,12,...)), missed by the
                            # earlier DESIGN.md migration -- now uses T1's
                            # category color, so a monument's placeholder is
                            # indigo, a food stop's is gold, etc.
                            cat_rgba_strong = _hex_to_rgba(cat_color, 0.20)
                            cat_rgba_soft = _hex_to_rgba(cat_color, 0.06)
                            st.html(
                                f"<div style='background:linear-gradient(135deg,"
                                f"{cat_rgba_strong},{cat_rgba_soft});"
                                "border-radius:8px;height:90px;display:flex;"
                                "align-items:center;justify-content:center;"
                                f"font-size:1.8rem;'>{CATEGORY_ICON.get(stop['category'], '📍')}</div>"
                            )
                    with move_col:
                        # Round 3 QA (UX3-5, the UI-side fix paired with
                        # E-3): no natural-language command can reorder
                        # stops yet (phase4/edit_engine.py's "reorder" edit
                        # type honestly declines and points here) — this is
                        # a real, working substitute: move a stop one
                        # position earlier/later through the day, swapping
                        # within a slot or crossing into the adjacent one,
                        # with times recomputed immediately after (_move_stop,
                        # above). UI/UX review (2026-10-24), quick win: the
                        # old 0.5-width column held two separate buttons
                        # (cramped); now one small popover trigger holds both.
                        up_disabled = stop_idx == 0 and slot_key == "morning"
                        down_disabled = stop_idx == len(stops) - 1 and slot_key == "evening"
                        with st.popover("⋮", use_container_width=True):
                            if st.button("↑ Move earlier", key=f"up_{key}_{slot_key}_{stop_idx}",
                                         disabled=up_disabled, use_container_width=True):
                                agent.push_itinerary_snapshot()  # HIGH-3: undoable like any other edit
                                _move_stop(agent.itinerary, key, slot_key, stop_idx, -1)
                                # User report (2026-07-25): moving a stop
                                # up/down didn't mark the "Full Itinerary"
                                # overview stale the way a chat edit command
                                # does (agent.py's own narrative_stale sets)
                                # -- same real inconsistency (schedule
                                # changed, prose overview didn't), just
                                # reached through a different UI control.
                                # Mirrors that existing signal so the same
                                # refresh button surfaces here too.
                                agent.narrative_stale = True
                                st.rerun()
                            if st.button("↓ Move later", key=f"down_{key}_{slot_key}_{stop_idx}",
                                         disabled=down_disabled, use_container_width=True):
                                agent.push_itinerary_snapshot()  # HIGH-3: undoable like any other edit
                                _move_stop(agent.itinerary, key, slot_key, stop_idx, 1)
                                agent.narrative_stale = True
                                st.rerun()
                    with info_col:
                        gem_badge = " 💎" if stop.get("is_hidden_gem") else ""
                        # R-25 (fixes UX-22): a real clock time, not just a
                        # duration — turns the stop list into an actual
                        # timeline. Theme proposal (2026-08-12): the name
                        # and time render via the .wp-stop-name /
                        # .wp-time-chip spans (Baloo 2 display face +
                        # an IBM Plex Mono pill). html.escape() guards
                        # against a stop name containing HTML-special
                        # characters (OSM data, not sanitized for markup)
                        # now that this goes through st.html.
                        escaped_name = html.escape(stop["name"])
                        arrival = stop.get("arrival_time")
                        title_line = f"<span class='wp-stop-name'>{escaped_name}</span>{gem_badge}"
                        if arrival:
                            title_line += f" <span class='wp-time-chip'>{arrival}</span>"
                        # MEDIUM-2 (Team Waypoint Voice-First UI review):
                        # "inline highlights on whatever just changed so the
                        # eye is drawn to the edit" — agent.last_changed_stops
                        # is cleared at the start of every new turn, so this
                        # only ever reflects the edit that JUST landed.
                        if (key, slot_key, stop_idx) in agent.last_changed_stops:
                            # Travel-planner color identity pass (2026-11-24,
                            # T9): DESIGN.md §5 defines the edit affordance as
                            # Turmeric Gold, not Streamlit's stock green.
                            # ":orange[]" is the closest built-in markdown
                            # color keyword to gold (a true #E3A423 would
                            # need an st.html span instead).
                            title_line += "  :orange[✨ Updated]"
                        st.markdown(title_line, unsafe_allow_html=True)

                        travel = stop.get("travel_time_from_prev_min", 0)
                        mode = stop.get("travel_mode_from_prev")
                        mode_icon = {"walk": "🚶", "auto": "🛺", "metro": "🚇"}.get(mode, "")
                        travel_note = f" · ↳ {mode_icon} {travel} min from previous stop" if travel else ""
                        # "· lunch" inside the same caption instead of a
                        # nested paren group — was "(restaurant (lunch))"
                        # (QA-9/R-15).
                        meal = stop.get("meal")
                        meal_note = f" · {meal}" if meal else ""
                        st.caption(
                            f"{stop['category']}{meal_note} · {stop['visit_duration_min']} min{travel_note}"
                        )

                        # Round 3 QA (UI3-3): Streamlit's stock
                        # :blue-badge/:green-badge colors are unrelated to
                        # the app's own terracotta accent -- these two facts
                        # are exactly the app's credibility payload (R-24),
                        # so they get real brand-derived tints instead of
                        # arbitrary framework defaults. UI/UX review
                        # (2026-10-24): these used to hard-code dark-brown
                        # text (#7A3608/#5C2A06) on a translucent fill --
                        # fine in light mode, but nearly invisible on a dark
                        # background since the color never flipped. Now the
                        # same --wp-accent-deep/--wp-chip-bg tokens every
                        # other brand-colored element uses, which already
                        # flip via the :root @media rule above.
                        badges = []
                        hours = stop.get("opening_hours")
                        if hours and hours != "unknown":
                            badges.append(
                                "<span style='background:var(--wp-chip-bg);"
                                "border:1px solid var(--wp-accent);color:var(--wp-accent-deep);"
                                "border-radius:999px;padding:2px 10px;font-size:0.85rem;"
                                f"display:inline-block;'>🕒 {format_opening_hours(hours)}</span>"
                            )
                        entry_fee = stop.get("kb_entry_fee")
                        if entry_fee:
                            # Design-alignment pass (2026-11-24, DESIGN.md
                            # L3): entry-fee is a "confirm affordance"-style
                            # fact per DESIGN.md §2, so it uses the Turmeric
                            # Gold (secondary) family instead of the teal
                            # accent the hours badge above uses -- the two
                            # badge kinds now read as visually distinct.
                            badges.append(
                                "<span style='background:var(--wp-secondary-soft);"
                                "border:1px solid var(--wp-secondary);color:var(--wp-secondary-deep);"
                                "border-radius:999px;padding:2px 10px;font-size:0.85rem;"
                                f"display:inline-block;'>🎟️ {entry_fee}</span>"
                            )
                        if badges:
                            st.html(" ".join(badges))
                        website = stop.get("website")
                        if website:
                            # Travel-planner color identity pass (2026-11-24,
                            # T10): was a default Streamlit markdown link
                            # (generic link-blue), unrelated to the teal/gold
                            # badges just above it -- now a matching
                            # teal-outlined chip, same visual family as the
                            # hours badge. Still a real <a> (not a button),
                            # so it stays a genuine clickable link.
                            st.html(
                                f"<a href='{html.escape(website)}' target='_blank' "
                                "rel='noopener noreferrer' style='background:var(--wp-chip-bg);"
                                "border:1px solid var(--wp-accent);color:var(--wp-accent-deep);"
                                "border-radius:999px;padding:2px 10px;font-size:0.85rem;"
                                "display:inline-block;text-decoration:none;'>🌐 Official site</a>"
                            )

        # R-25 (fixes UX-22): safety/logistics moved into a collapsed
        # expander below the day's actual stops — previously this was the
        # first full-contrast text a user read about their day, ahead of
        # the attractions themselves. Component audit Tier 7: a bounded,
        # real slice of the icon-font hybrid for these pure-functional-chrome
        # lines. html.escape() guards the real place names.
        emergency_bits = []
        if day.get("nearest_hospital"):
            h = day["nearest_hospital"]
            emergency_bits.append(
                f"<span class='wp-icon'>local_hospital</span> Nearest hospital: "
                f"{html.escape(format_display_name(h['name']))} ({h['distance_km']} km)"
            )
        if day.get("nearest_pharmacy"):
            p = day["nearest_pharmacy"]
            emergency_bits.append(
                f"<span class='wp-icon'>medication</span> Nearest pharmacy: "
                f"{html.escape(format_display_name(p['name']))} ({p['distance_km']} km)"
            )
        if day.get("nearest_metro_station"):
            m = day["nearest_metro_station"]
            emergency_bits.append(
                f"<span class='wp-icon'>directions_subway</span> Nearest metro: "
                f"{html.escape(format_display_name(m['name']))} ({m['distance_km']} km)"
            )
        if emergency_bits:
            with st.expander("🚑 Safety & logistics"):
                for bit in emergency_bits:
                    st.html(bit)

    selected_card_key = None
    # UI/UX review (2026-10-24), overhaul #2: the map now sits beside the
    # cards instead of after them, in a sticky container (CSS near the top
    # of the file targets .st-key-day_map_* ) so the route stays visible
    # while scrolling the card list.
    with map_col, st.container(key=f"day_map_{key}"):
        if all_stops:
            numbered = [
                {
                    "lat": s["lat"], "lon": s["lon"], "name": s["name"],
                    # Round 3 QA (UI3-4): category added so it's accessible
                    # on hover. A full custom-icon-per-category glyph layer
                    # needs pydeck's IconLayer, which takes image URLs, not
                    # emoji -- a real, separate asset-generation effort out
                    # of proportion to a Low-priority item; this is the
                    # honest, immediately-real slice of it.
                    "tooltip_text": f"{s['name']} ({s.get('category', 'stop')})",
                    "num": str(i + 1),
                    # Design-alignment pass (2026-11-24, DESIGN.md M7): the
                    # fallback (an unrecognized slot key) used to be a bright
                    # red -- reads as an error marker, and Vermilion is
                    # reserved for hard-fail feasibility only. Granite Grey
                    # is a neutral "unclassified" fallback instead.
                    "color": SLOT_MARKER_COLOR.get(s["_slot_key"], [139, 133, 120]),
                }
                for i, s in enumerate(all_stops)
            ]
            marker_df = pd.DataFrame(numbered)
            route_df = pd.DataFrame([{"path": [[s["lon"], s["lat"]] for s in all_stops]}])
            # Auto-fit to this day's actual stops instead of a fixed
            # zoom=11 — previously overlapping markers (e.g. stop "3"
            # hidden under 1/2/4) when a day's stops clustered tighter than
            # that fixed zoom assumed (UX-15/R-16).
            view_state = pdk.data_utils.compute_view(marker_df[["lon", "lat"]])
            view_state.pitch = 0

            deck = pdk.Deck(
                map_style=None,
                initial_view_state=view_state,
                layers=[
                    pdk.Layer(
                        # Travel-planner color identity pass (2026-11-24,
                        # T3): Peacock Teal instead of flat grey -- the line
                        # connecting a day's stops IS the journey, the core
                        # travel-planner metaphor; grey read as an
                        # incidental gridline.
                        "PathLayer", data=route_df, get_path="path",
                        get_color=[14, 124, 134], get_width=3, width_min_pixels=2,
                    ),
                    pdk.Layer(
                        # UI/UX review (2026-10-24), overhaul #2: `id` is
                        # required for st.pydeck_chart's on_select to report
                        # which object was clicked (verified against the
                        # installed Streamlit/pydeck version's own docs).
                        "ScatterplotLayer", id="stops", data=marker_df, get_position=["lon", "lat"],
                        get_fill_color="color", get_radius=90, radius_min_pixels=14,
                        pickable=True,
                    ),
                    pdk.Layer(
                        "TextLayer", data=marker_df, get_position=["lon", "lat"], get_text="num",
                        get_size=14, get_color=[255, 255, 255], get_text_anchor="'middle'",
                        get_alignment_baseline="'center'",
                    ),
                ],
                tooltip={"text": "{tooltip_text}"},
            )
            map_state = st.pydeck_chart(
                deck, on_select="rerun", selection_mode="single-object", key=f"map_{key}",
            )
            # UI/UX review (2026-10-24), overhaul #2: clicking a marker
            # highlights the matching stop card instead of doing nothing —
            # the docx's own "jump to stop" ask, delivered as a highlight
            # (Streamlit has no scroll-to-element API) rather than
            # overclaiming a true scroll-jump.
            if map_state and map_state.selection:
                sel_indices = map_state.selection.get("indices", {}).get("stops", [])
                if sel_indices:
                    s = all_stops[sel_indices[0]]
                    selected_card_key = f"stopcard_{key}_{s['_slot_key']}_{s['_stop_idx']}"
            # Text alternative to the map's visual-only info (UX-8/R-10):
            # marker numbers = visiting order, colors = time of day. Emoji
            # dots updated (2026-11-24, DESIGN.md M7) to match the new
            # SLOT_MARKER_COLOR values -- morning is now Turmeric Gold
            # (yellow dot), not the old terracotta (orange dot).
            st.caption(
                "Numbers show visiting order for the day; colors mark time of day "
                "(🟡 morning · 🟣 afternoon · 🟢 evening). Click a marker to highlight its card."
            )

    if selected_card_key:
        st.html(
            f"<style>.st-key-{selected_card_key} {{ border-color: var(--wp-accent) !important; "
            f"box-shadow: 0 0 0 2px var(--wp-accent); }}</style>"
        )


# --------------------------------------------------------------------------- #
# Itinerary Panel
# --------------------------------------------------------------------------- #
with col_itinerary:
    # UI/UX review (2026-10-24), quick win #5: "Your Itinerary" used to head
    # this panel even in the empty state, where it was showing onboarding
    # content instead of an itinerary. Only shown once there's actually one.
    if agent.itinerary:
        st.subheader("Your Itinerary")
    # Round 3 QA (UX3-1, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
    # the app deliberately confirms trip details before building
    # (COLLECT -> CLARIFY -> CONFIRM -> BUILD -> PRESENT, phase3/agent.py) --
    # but that question used to surface *only* as a chat bubble in the small
    # Transcript column, while this dominant, 2/3-width panel kept showing
    # the full pre-build onboarding content completely unchanged. A user
    # looking at the large panel (where rounds 4-5 deliberately put all the
    # visual weight) could easily miss that the agent was waiting on them.
    # This banner — plus real Yes/No buttons, not just a typed reply — makes
    # the pending confirmation impossible to miss regardless of which panel
    # has the user's attention.
    pending_confirm = (
        not agent.itinerary and agent.state == State.CONFIRM and st.session_state.transcript
        and st.session_state.transcript[-1][0] == "Agent"
    )

    # Component audit Tier 1: a real modal instead of an inline banner —
    # every benchmark app (Wanderlog, TripIt, Airbnb) handles an "are you
    # sure?" moment as a focused overlay, not a banner competing with
    # everything else on the page for attention. Calling the decorated
    # function each rerun while `pending_confirm` stays True is the
    # documented Streamlit pattern for keeping a dialog open across reruns —
    # it only actually "reopens" (visually) the first time; once the state
    # that gates it flips False (here, via _send() advancing agent.state),
    # the next rerun simply doesn't call it again and it closes.
    @st.dialog("🧭 Confirm your trip")
    def _confirm_dialog(last_text: str) -> None:
        st.write(last_text)
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("✅ Yes, build it", use_container_width=True, type="primary", key="confirm_yes"):
            _send("Yes")
            st.rerun()
        if confirm_cols[1].button("✏️ No, let me change something", use_container_width=True, key="confirm_no"):
            _send("No")
            st.rerun()

    if pending_confirm:
        _confirm_dialog(st.session_state.transcript[-1][1])
    if agent.itinerary:
        day_keys = sorted(
            (k for k in agent.itinerary if k.startswith("day_")),
            key=lambda k: int(k.split("_")[1]),
        )
        # R-24 (Itinerary-Quality-Review... round 4 UX benchmark, UX-22): a
        # trip-summary header band anchors context the way real result pages
        # do (Kayak/Expedia show "X nights · Y travelers · dates" up top) —
        # previously these facts only existed buried in a chat bubble.
        num_stops = sum(
            len(agent.itinerary[k].get(slot, []))
            for k in day_keys for slot in ("morning", "afternoon", "evening")
        )
        interests = ", ".join(agent.ctx.interests or []) or "your interests"
        pace = agent.ctx.pace or "moderate"
        st.markdown(
            f"##### 🗓️ {len(day_keys)} day{'s' if len(day_keys) != 1 else ''} · "
            f"📍 {num_stops} stop{'s' if num_stops != 1 else ''} · "
            f"{interests} · {pace} pace"
        )
        # R-24/UX-21: the app's real differentiator (grounded, real data) as
        # a visible trust marker — previously the only signal was a small
        # attribution line in the page footer.
        # Component audit Tier 6: a help tooltip explaining what "grounded"
        # actually means, right where the eye lands on the badge itself —
        # previously that explanation only lived in the onboarding text and
        # the page footer, never here.
        # Travel-planner color identity pass (2026-11-24, T8): this is the
        # app's core trust marker -- "primary" ties it to the app's own
        # Peacock Teal accent instead of Streamlit's unrelated stock green.
        st.badge(
            "Real data — OpenStreetMap + Wikidata + Wikivoyage", icon="✅", color="primary",
            help="Every stop, distance, and opening hour shown below is sourced from these three "
                 "real datasets — never invented or guessed.",
        )

        # UI/UX review (2026-10-24), overhaul #3: a real metric row above the
        # tabs (days/stops/time-in-transit — the docx's own sample also
        # included an "Est. budget" tile, deliberately left out here: this
        # project never computes a numeric priced budget, by design, to
        # avoid presenting an invented figure as fact; the narrator's own
        # hedged prose estimate still lives in the Overview tab below).
        total_travel_min = sum(
            stop.get("travel_time_from_prev_min", 0) or 0
            for k in day_keys for slot in ("morning", "afternoon", "evening")
            for stop in agent.itinerary[k].get(slot, [])
        )
        metric_cols = st.columns(3)
        metric_cols[0].metric("Days", len(day_keys), border=True)
        metric_cols[1].metric("Stops", num_stops, border=True)
        metric_cols[2].metric("Time in transit", f"{total_travel_min} min", border=True)

        # UI/UX review (2026-10-24), overhaul #3: Undo / Download / Email
        # grouped into one action row instead of scattered across the page
        # (undo above the tabs, download hidden behind a sent email, email
        # at the very bottom). "Start a new trip" stays in its own
        # already-persistent top-bar spot (Tier 6) rather than joining this
        # row — it's a different kind of action (leaves this trip
        # entirely) and that placement was a deliberate earlier decision
        # this review doesn't touch.
        with st.container(horizontal=True):
            # HIGH-3 (Team Waypoint Voice-First UI review): a strong,
            # always-available undo — previously the only recovery from an
            # edit you regret was issuing another edit command to manually
            # reconstruct the prior state. Component audit Tier 6: shows how
            # many steps of history are actually available, not just that
            # undo exists.
            if agent.itinerary_history:
                n_undo = len(agent.itinerary_history)
                if st.button(f"↩️ Undo ({n_undo})", key="undo_last_change", icon=":material/undo:"):
                    if agent.undo_last_edit():
                        st.toast("↩️ Last change undone")  # Tier 5: transient confirmation, not a persistent banner
                        st.rerun()

            # UI/UX review (2026-10-24), quick win #4: the PDF used to be
            # generated (and thus downloadable) only after a "Send itinerary"
            # click, which always required an email address first even for
            # someone who only wants the file. build_pdf_bytes() (new,
            # phase6/delivery.py) produces the identical document with no
            # email step. Regenerated fresh on every click so an edit since
            # the last download is reflected — cheap (no LLM call) unlike
            # the narrative refresh, so no staleness guard is needed here.
            if agent.narrative_stale and agent.narrative:
                with st.spinner("Updating the overview for your latest edits..."):
                    agent.retry_enrichment()
            _pdf_bytes = build_pdf_bytes(agent.itinerary, agent.ctx.to_dict(), citations=agent.last_citations, narrative=agent.narrative)
            st.download_button(
                "Download PDF", data=_pdf_bytes, file_name="delhi_itinerary.pdf", mime="application/pdf",
                icon=":material/download:", key="direct_download",
            )

            with st.popover("Email", icon=":material/mail:"):
                email = st.text_input("Your email address", key="email_input")
                if st.button("Send", key="send_email_popover"):
                    result = deliver_itinerary(
                        agent.itinerary, agent.ctx.to_dict(), email,
                        citations=agent.last_citations, narrative=agent.narrative,
                    )
                    if result["emailed"]:
                        st.success(result["message"])
                    elif result["file_bytes"]:
                        st.info(result["message"])
                    else:
                        st.error(result["message"])

        # HIGH-2 (Team Waypoint Voice-First UI review): when a swap names an
        # existing stop that matches 2+ real candidates ("swap the temple"
        # with two temples on the trip), edit_engine.py now surfaces them
        # instead of guessing or silently declining — shown here as
        # tappable cards (docx: "show three tappable cards instead of
        # reading options aloud one by one"), resolved instantly with no
        # LLM roundtrip. A spoken/typed ordinal reply ("the first one")
        # works too — see agent.py's _parse_ordinal_choice.
        # Component audit Tier 1: same reasoning as the build-confirm dialog
        # above — a real modal focuses attention on the choice instead of
        # competing with the rest of the itinerary panel for it.
        @st.dialog("🔀 Which one did you mean?")
        def _choice_dialog(candidates: list[dict]) -> None:
            st.write(f"I found {len(candidates)} stops matching that — which one did you mean?")
            choice_cols = st.columns(len(candidates))
            for i, (choice_col, cand) in enumerate(zip(choice_cols, candidates)):
                with choice_col:
                    with st.container(border=True):
                        st.markdown(f"**{format_display_name(cand['name'])}**")
                        day_num = cand["day_key"].split("_")[1]
                        st.caption(f"{cand['category']} · Day {day_num} {cand['slot']}")
                        if st.button("Choose this", key=f"choice_{i}", use_container_width=True):
                            choice_reply, _ = agent.resolve_pending_choice(i)
                            st.session_state.transcript.append(("You", f"(chose: {format_display_name(cand['name'])})"))
                            st.session_state.transcript.append(("Agent", choice_reply))
                            st.toast(f"✅ {format_display_name(cand['name'])} selected")  # Tier 5
                            st.rerun()

        if agent.pending_choice:
            _choice_dialog(agent.pending_choice["candidates"])

        # UX-12/R-14: persistent, always-visible reminder that editing/explain
        # is possible mid-conversation — previously only mentioned once the
        # user already said goodbye (agent.py's DONE-state reply).
        st.caption(
            "💬 Want changes? Just type or say it — \"swap the museum for a market,\" "
            "\"is the metro safe at night?\", or anything else about your trip."
        )
        # UX-14/R-16: honest note on light/evening-open days instead of
        # letting the narrator's generic "explore the streets" filler paper
        # over it — informational only, doesn't affect the itinerary itself.
        balance_notes_by_day: dict[int, list[str]] = {}
        for note in check_day_balance(agent.itinerary, agent.ctx.pace or "moderate")["notes"]:
            balance_notes_by_day.setdefault(note["day"], []).append(note["note"])

        # Component audit Tier 6: a stop count in each tab's own label
        # ("Day 1 (5)") — Streamlit tab labels are plain text with no rich
        # HTML slot inside them, so this is the one real information-density
        # lever available in the app's primary navigational element.
        day_stop_counts = {
            k: sum(len(agent.itinerary[k].get(slot, [])) for slot in ("morning", "afternoon", "evening"))
            for k in day_keys
        }
        # UI/UX review (2026-10-24), overhaul #3: the narrative/transit/
        # all-days-map content that used to render below every day tab (so
        # it was usually below the fold, after scrolling past the full
        # day-by-day list) now lives in its own first tab instead.
        all_tabs = st.tabs(["🗺️ Overview"] + [f"Day {k.split('_')[1]} ({day_stop_counts[k]})" for k in day_keys])
        overview_tab, day_tabs = all_tabs[0], all_tabs[1:]

        with overview_tab:
            _render_overview_tab(agent, day_keys)

        for tab, key in zip(day_tabs, day_keys):
            with tab:
                _render_day_tab(agent, key, balance_notes_by_day)
    elif not pending_confirm:
        # R-26 (fixes UX-23): a real hero photo + a confident one-line
        # promise instead of a small info box floating in an empty white
        # void — the landing screen previously had no imagery and no
        # value-prop tagline at all.
        # Fixed (2026-11-24): was get_cached_image_path(HERO_IMAGE_URL) --
        # a live fetch on every cold start with an empty (gitignored) cache,
        # silently failing under Wikimedia's Cloud-IP rate limiting (see
        # HERO_IMAGE_PATH's comment above). The hero image never changes, so
        # it ships as a committed file instead of being fetched at runtime.
        # Further fixed (2026-11-24): st.image(path) still failed on Cloud
        # specifically (Streamlit's own /media/ serving route, not this
        # file) -- rendered as a base64 data URI instead, same as every
        # other photo's _carousel_thumbnail_data_uri (see its docstring).
        _hero_uri = _hero_image_data_uri()
        if _hero_uri:
            st.html(f'<img src="{_hero_uri}" style="width:100%;border-radius:8px;display:block;">')
        # R-34/UX-32: the tagline and capability list previously never told a
        # first-time user that speaking is the intended primary mode — every
        # line was framed around typing/chatting. Now leads with the mic.
        # Fixed (2026-11-24): "tap the mic above" was stale copy from before
        # the decorative mic icon above the hero image was removed — the
        # real mic lives in the chat composer below, not above.
        st.markdown("#### 🎤 Tell me about your trip — real, grounded Delhi itineraries, no guesswork")
        # UI/UX review (2026-10-24), quick win #6: this attribution caption
        # was one of 4 near-duplicate mentions on the page (sidebar, here,
        # the plan badge, the footer) — dropped in favor of the footer,
        # which already says the same thing and is always visible.
        # UX-11/R-14: real onboarding instead of one placeholder sentence —
        # explains scope (Delhi-only, ties into QA-7) and every capability,
        # not just "type your trip."
        st.info(
            "**Here's what I can do:**\n"
            "- Build a real, grounded **2–3 day New Delhi** itinerary from your interests — "
            "just say it out loud, or type\n"
            "- Edit it by voice or chat — \"make day 1 more relaxed\", \"swap the museum for a market\"\n"
            "- Answer questions with real sources — \"is this doable?\", \"what if it rains?\"\n"
            "- Email or download the finished plan as a document"
        )
        st.caption("🎤 Say one of these, or type your own trip below:")
        ex_cols = st.columns(len(EXAMPLE_PROMPTS))
        for col, (label, prompt) in zip(ex_cols, EXAMPLE_PROMPTS):
            if col.button(label, key=f"example_{label}", use_container_width=True):
                _send(prompt)
                st.rerun()

        # R-28 (fixes UX-26): optional structured scaffolding for users who
        # don't know what to type — composes into the exact same free-text
        # message the agent already parses (no new code path in agent.py),
        # so conversational input stays primary; this is just a shortcut
        # into it, not a parallel system.
        with st.expander("🎛️ Or build your request with quick options"):
            qc1, qc2 = st.columns(2)
            # UI/UX review (2026-10-24), quick win #2: the planner only ever
            # supports 1-3 days (onboarding text above says so), but this
            # slider's range went up to 4 — a real mismatch between what the
            # control offered and what the product does. st.segmented_control
            # also means every option is visible without a click, same
            # reasoning Component audit Tier 4 already applied to Pace below.
            quick_days = qc1.segmented_control("Days", [1, 2, 3], default=2)
            # Component audit Tier 4: three mutually-exclusive options are
            # exactly the case a dropdown handicaps -- every option should
            # be visible without a click, the way Kayak renders cabin class.
            quick_pace = qc2.segmented_control("Pace", ["relaxed", "moderate", "intensive"], default="moderate")
            # UI/UX review (2026-10-24), quick win #2: budget is one of the
            # three things the onboarding text says users pick, but there
            # was no control for it at all. Composes into the same free-text
            # sentence as everything else here — a stated preference, not a
            # number this app computes or prices itself, so it carries no
            # grounding risk.
            quick_budget = st.segmented_control(
                "Budget per day (optional)",
                ["Under ₹2,000", "₹2,000–5,000", "₹5,000+"],
            )
            # UI/UX review (2026-10-24), quick win #2: interests hidden
            # behind a multiselect dropdown click vs. every option visible
            # and tappable as pills — same reasoning as Pace/Days above.
            quick_interests = st.pills(
                "Interests",
                ["food", "history", "culture", "architecture", "shopping", "nature", "religion", "art", "family"],
                selection_mode="multi", default=["food", "history"],
            )
            # UI/UX review (2026-10-24), quick win #2: a 1-10 slider is slow
            # for picking an exact headcount — a number input is direct.
            quick_group = st.number_input("Travellers", min_value=1, max_value=10, value=2)
            # Component audit Tier 2: the single most conspicuous absence
            # against every mainstream travel app (Kayak, Expedia, Airbnb,
            # Google Travel, TripIt, Wanderlog all lead with a date picker).
            # Composes into the same free-text sentence the agent already
            # parses via TripContext.travel_dates -- no new backend date
            # logic needed. Left genuinely optional (empty by default): the
            # itinerary builder doesn't require specific calendar dates, only
            # the weather lookup benefits from a real one (_resolve_travel_dates
            # already falls back to "starting tomorrow" when none is given).
            quick_dates = st.date_input(
                "Travel dates (optional)", value=(), min_value=date.today(),
                help="Only used for the weather heads-up — leave blank if you're not sure yet.",
            )
            if st.button("Build this trip", use_container_width=True):
                interests_text = ", ".join(quick_interests) if quick_interests else "a mix of culture and food"
                group_text = "solo" if quick_group == 1 else f"a group of {quick_group}"
                dates_text = ""
                if isinstance(quick_dates, (tuple, list)) and len(quick_dates) == 2:
                    dates_text = f", traveling {quick_dates[0].isoformat()} to {quick_dates[1].isoformat()}"
                elif isinstance(quick_dates, date):
                    dates_text = f", traveling around {quick_dates.isoformat()}"
                budget_text = f", budget around {quick_budget} per day" if quick_budget else ""
                composed = (
                    f"Plan a {quick_days or 2}-day trip to Delhi, I like {interests_text}, "
                    f"{quick_pace or 'moderate'} pace, {group_text}{budget_text}{dates_text}."
                )
                _send(composed)
                st.rerun()

# --------------------------------------------------------------------------- #
# Transcript + Sources Panel
# --------------------------------------------------------------------------- #
def _render_transcript_and_sources() -> None:
    # UI/UX review (2026-10-24): was an invisible marker span + a CSS `:has()`
    # selector reaching up to find the enclosing column -- st.container(key=...)
    # gives a direct, stable `.st-key-transcript` hook (verified against the
    # installed Streamlit version, 1.57.0) with no marker element needed, and
    # the sticky CSS rule now targets this container itself, not an ancestor.
    with st.container(key="transcript"):
        st.subheader("Transcript")
        msg_count = len(st.session_state.transcript)
        if not msg_count:
            st.caption("Your conversation will appear here.")
            return
        st.caption(f"{msg_count} message{'s' if msg_count != 1 else ''} — scroll to see earlier ones")

        # User request (2026-07-17): a scrollable pane so the full conversation
        # stays reachable instead of being capped to the last 20 turns — a fixed-
        # height bordered container gives a native scrollbar for free (no custom
        # JS), and every message is rendered into it as the conversation grows.
        with st.container(height=480, border=True):
            # Chat-bubble grouping instead of a flat bold-label list (UX-4/R-9) —
            # makes long agent turns (build summary + weather + safety tip)
            # visually distinct from short user turns rather than blurring
            # together down the column.
            for speaker, text in st.session_state.transcript:
                role = "user" if speaker == "You" else "assistant"
                avatar = "🧑" if role == "user" else "🧭"
                with st.chat_message(role, avatar=avatar):
                    st.markdown(text)

        # Round 3 QA (UX3-2): play the reply audio here, inside col_side and
        # directly under the transcript it belongs to, instead of at the top
        # level where it used to strand as a disconnected strip below both
        # columns (see the matching comment in _send() for the full root cause).
        if st.session_state.get("pending_audio_text"):
            _play_reply_audio(st.session_state.pending_audio_text)
            st.session_state.pending_audio_text = None

        if agent.last_citations:
            st.subheader("Sources")
            for c in agent.last_citations:
                st.markdown(f"- [{format_citation_label(c)}]({c.get('source_url', '')})")


with col_side:
    _render_transcript_and_sources()

st.divider()
st.caption(
    "Map & POI data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, "
    "ODbL. Landmark details enriched from [Wikidata](https://www.wikidata.org) (CC0). "
    "Travel guidance from [Wikivoyage](https://en.wikivoyage.org/wiki/Delhi) (CC BY-SA 4.0)."
)
