"""
Companion UI — Phase 6.

Run with: streamlit run app.py
"""

import base64
import hashlib
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
from delivery import deliver_itinerary
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
HERO_IMAGE_URL = "http://commons.wikimedia.org/wiki/Special:FilePath/Red%20Fort%2C%20Delhi%20by%20alexfurr.jpg"

# Transcribing display (user request, 2026-07-16): a prominent indicator
# shown right under the input (via `listening_slot`, declared before the
# column split so it anchors under the input rather than at the page bottom
# — see the note there), covering the Groq Whisper round-trip after a
# browser-recorded clip (st.audio_input(), see the voice-input block below)
# comes back. No separate "Listening…" banner — st.audio_input() renders
# its own native recording/waveform UI in the browser, so a second
# hand-rolled "listening" indicator here would just duplicate it.
_TRANSCRIBING_BANNER = """
<div style="border:2px solid #1971c2; background:rgba(25,113,194,0.10);
     border-radius:12px; padding:10px 16px; margin:4px 0 12px;
     display:flex; align-items:center; gap:12px; justify-content:center;">
  <span style="font-size:1.3rem; display:inline-block; animation:lsn-fade 0.9s ease-in-out infinite;">✍️</span>
  <span style="font-weight:700; color:#1971c2; font-size:1.05rem;">Transcribing what you said…</span>
</div>
<style>@keyframes lsn-fade {0%{opacity:0.4;} 50%{opacity:1;} 100%{opacity:0.4;}}</style>
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
#      itinerary's map/narrative/email content. `:has()` lets this target
#      *only* the specific column that contains a marker span app.py itself
#      renders (`_render_transcript_and_sources()`, below) -- not every
#      st.columns() pair on the page (a plain nth-of-type selector would
#      also catch the voice-toggle row and the quick-options expander's
#      columns, which is exactly the kind of fragile, overreaching match
#      this approach avoids).
#
# Team Waypoint theme proposal (2026-08-12, "Team-Waypoint-Voice-First-UI-
# Design-Review.md" section 2), applied: a type pairing (Fraunces for
# titles/headers/stop names, Plus Jakarta Sans for body/UI text, JetBrains
# Mono for tabular data like clock times), a warm neutral page background
# instead of Streamlit's cool default, a second brand accent (deep indigo)
# reserved for secondary actions, and rounded-pill buttons with a real
# primary/secondary hierarchy. Terracotta itself is UNCHANGED (#C2540C /
# #7A3608, R-26 -- already validated across five rounds) — this only adds
# the system around it. Selectors verified against the actually-installed
# Streamlit version (1.57.0)'s own compiled frontend bundle rather than
# guessed: `stBaseButton-{kind}`, `stAppViewContainer`, `stMarkdown`,
# `stCaptionContainer` are real data-testid values it emits, not emotion-
# cache class names, so this follows the same "stable selectors only"
# discipline as UI3-1/UX3-4 above, just verified against source instead of
# assumed from other Streamlit apps' conventions (which drift across
# versions). Light/dark still follows the viewer's OS preference only
# (`prefers-color-scheme`), same choice R-26 made for the accent color —
# not locked via config.toml's [theme] base, and not tied to Streamlit's
# own in-app theme toggle (a real, narrow gap: if a viewer manually
# overrides Streamlit's toggle against their OS setting, these tokens
# won't follow — the same trade-off already accepted for the h1 gradient).
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Plus+Jakarta+Sans:wght@400;500;700&family=JetBrains+Mono:wght@500&display=swap');
/* Component audit Tier 7: Material Symbols, loaded the same way as the
   type-pairing fonts above -- applied to a small, bounded set of functional
   icons (the safety/logistics bits below) as a first real slice of an
   icon-font hybrid, not a wholesale emoji replacement. Emoji stay
   everywhere else (buttons, badges, the hero tagline) -- they're
   zero-asset-cost, already work, and carry real warmth a uniform icon set
   would flatten; this only reaches for a re-tintable, cross-platform-
   consistent icon where "functional UI chrome, not expressive content" is
   the clearer read. */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20,400,0,0&display=swap');

:root {
    --wp-accent: #C2540C;
    --wp-accent-deep: #7A3608;
    --wp-secondary: #332F5C;
    --wp-secondary-deep: #211E3D;
    --wp-secondary-soft: rgba(51,47,92,0.10);
    --wp-surface: #FFFFFF;
    --wp-ink-soft: #746353;
    --wp-border: #E7DCCB;
}
@media (prefers-color-scheme: dark) {
    :root {
        --wp-accent: #E0863F;
        --wp-accent-deep: #F3B57D;
        --wp-secondary: #9490C9;
        --wp-secondary-deep: #C3C0E6;
        --wp-secondary-soft: rgba(148,144,201,0.18);
        --wp-surface: #221C17;
        --wp-ink-soft: #C2AF9C;
        --wp-border: #392F26;
    }
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
[data-testid="stMarkdown"], [data-testid="stCaptionContainer"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}
h1, h2, h3, h4, h5, h6 {
    font-family: 'Fraunces', serif;
}
code {
    font-family: 'JetBrains Mono', monospace !important;
}
.wp-icon {
    font-family: 'Material Symbols Outlined';
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 20;
    font-size: 1rem;
    vertical-align: -0.15em;
    color: var(--wp-accent);
}
/* User request (2026-08-12): remove the page background entirely, not just
   the mic's -- reverts to Streamlit's own default background (no custom
   color, no watermark pattern). Previously this held a warm-neutral fill
   plus a self-authored CSS lattice pattern (Component audit Tier 7); both
   removed rather than lightened further, per the explicit "no colour" ask. */

h1 {
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--wp-accent), var(--wp-accent-deep));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"] .wp-transcript-marker)
    > div[data-testid="stColumn"]:nth-of-type(2) {
    position: sticky;
    top: 1rem;
    align-self: flex-start;
}

/* User request (2026-08-12): "make the mic bigger and more visible" --
   round 3. Round 1 (scale 1.5) read as too subtle; round 2 (scale 2.3)
   overshot. Settling on a middle ground. st.audio_input() renders
   identically (same size) whether the itinerary exists yet or not -- the
   pre/post-build difference UX3-3 established was about removing the
   pulsing glyph + extra captions AROUND it, not the widget's own footprint
   -- so this applies safely to both instances without reopening that fix.
   Selectors verified against the actually-installed Streamlit version's
   own compiled frontend (1.57.0), same discipline as every other selector
   in this file: `stAudioInput` (the widget's outer container) and
   `stAudioInputActionButton` (the actual record button) are real
   data-testid values it emits. */
[data-testid="stAudioInput"] {
    /* User request (2026-08-12): "still in brown colour theme" -- the real
       remaining culprit was the box-shadow's terracotta glow (a soft blur
       reads as a background wash even with the fill itself transparent),
       not just the background-color. Stripped the border and shadow
       entirely rather than trying to lighten them further -- no color
       chrome at all around the control now, just the enlarged button. */
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stAudioInputActionButton"] {
    transform: scale(1.8);
    transform-origin: center;
    margin: 0 0.6rem;
}

/* Rounded-pill buttons: primary (filled) vs secondary (outlined) hierarchy,
   so a high-stakes confirm and its escape hatch read as different actions
   at a glance, not just different words (docx's confirmation-tiering
   guidance). Covers both plain st.button() and st.form_submit_button()
   kinds -- Streamlit gives form-submit buttons a distinct "FormSubmit"
   testid suffix even when styled type="primary"/"secondary". */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    border-radius: 999px !important;
    font-weight: 600 !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 14px -4px var(--wp-accent);
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
    border-radius: 999px !important;
    font-weight: 600 !important;
    border-color: var(--wp-secondary) !important;
    color: var(--wp-secondary) !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background-color: var(--wp-secondary-soft) !important;
}

/* Stop-name / clock-time treatment -- rendered via the .wp-stop-name /
   .wp-time-chip spans in the Day view's stop cards (below). */
.wp-stop-name {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 1.05rem;
}
.wp-time-chip {
    font-family: 'JetBrains Mono', monospace;
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
""",
    unsafe_allow_html=True,
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
if "voice_edit_prefill" not in st.session_state:
    st.session_state.voice_edit_prefill = None
if "text_input_version" not in st.session_state:
    # User report (2026-08-12): the "✏️ Edit" button on the voice-heard
    # banner prefilled `st.session_state["main_text_input"]` before the
    # widget was created, which is the standard Streamlit pattern and
    # verified correct in a headless AppTest simulation -- but a live
    # browser reportedly didn't show the prefilled text. Reassigning a
    # FIXED widget key's session-state value on a rerun relies on the
    # browser reusing/re-syncing that exact component instance, the same
    # class of fragility already hit once in this file for st.audio_input()
    # (see mic_key_version below, and its own comment on why a fixed key
    # isn't reliable for this). Bumping the text input's key on every
    # prefill forces a genuinely fresh widget instance instead, removing
    # any dependency on same-key re-sync behavior.
    st.session_state.text_input_version = 0
if "mic_key_version" not in st.session_state:
    # User report (2026-07-25): "Start a new trip" left the previous
    # recording still sitting in the mic widget. st.audio_input() has no
    # supported way to clear its displayed value directly (unlike a plain
    # text_input, you can't just reassign its session_state entry) -- the
    # documented way to reset any such widget is to change its `key`,
    # which mounts a genuinely fresh instance with no prior value. This
    # counter is that key's suffix; bumped in the "Start a new trip"
    # handler below.
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
    st.write("")  # vertical spacer so the button lines up with the title's baseline, not its top
    if st.button("🔄 Start a new trip", key="new_trip_topbar", use_container_width=True):
        _start_new_trip()

with st.sidebar:
    st.header("About this trip planner")
    st.caption(
        "Map & POI data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, "
        "ODbL. Landmark details enriched from [Wikidata](https://www.wikidata.org) (CC0). "
        "Travel guidance from [Wikivoyage](https://en.wikivoyage.org/wiki/Delhi) (CC BY-SA 4.0)."
    )
    st.caption("Every stop, distance, and opening hour is cited — nothing is invented.")

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

# Voice input: st.audio_input() records from the BROWSER's microphone via
# the viewer's own device, unlike the old sr.Microphone()-based capture
# (phase3/stt.py's capture_mic_audio(), still used by the local CLI path)
# which opens whatever mic is attached to the machine *running the Python
# process* -- fine locally where that's the same machine, but meaningless
# on a remote host like Streamlit Community Cloud, which has no physical
# mic for a remote visitor's voice to reach. This works identically either
# way, since the browser is always the one capturing audio now.
#
# Lives outside st.form(): a form only surfaces its widgets' values to
# Python on submit, but there's no separate "submit" gesture for a voice
# clip -- it should transcribe and send itself the moment recording stops,
# the same way the old mic button triggered its own top-level `if` block
# below (rather than needing Send clicked afterward).
#
# Round 3 QA (UX3-3, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"): the
# full onboarding-sized input block (pulsing glyph + full-width mic CTA +
# a whole secondary row for text) was still rendering at full size even
# after a real itinerary was built, pushing the actual plan below the fold.
# That size is the right call for a first-time, nothing-built-yet screen
# (round 5 fought hard to put it above the fold there) but is now visibly
# secondary once a plan exists -- so it shrinks to a compact single row,
# the same "ask or edit" affordance, once `agent.itinerary` is populated.
# Text stays equally reachable either way (R-29/R-33's "never harder to
# use for someone who prefers typing" constraint) -- only the mic's own
# visual size changes, matching how much real estate voice needs to
# *invite* a first-time user vs. serve a returning one who already knows
# it's there.
if not agent.itinerary:
    # R-29/UX-27: the mic is the dominant control on a first-time screen. A
    # small pulsing mic glyph above it (R-32/UX-30) gives voice a visual
    # "idle, listening for you" presence even before it's pressed, closing
    # the gap where voice previously only appeared as transient spinners
    # during an already-started capture.
    # User request (2026-08-12): bumped from 1.4rem to 2.6rem and the pulse's
    # peak scale from 1.18x to 1.3x -- "make the mic bigger and more
    # visible" applies here too, not just to st.audio_input() itself below.
    st.markdown(
        '<div style="text-align:center; margin-bottom:4px;">'
        '<span style="display:inline-block; font-size:2.6rem; '
        'animation: r30-idle-pulse 2.2s ease-in-out infinite;">🎙️</span></div>'
        '<style>@keyframes r30-idle-pulse '
        '{0%{opacity:0.55; transform:scale(1);} 50%{opacity:1; transform:scale(1.3);} '
        '100%{opacity:0.55; transform:scale(1);}}</style>',
        unsafe_allow_html=True,
    )
    # User request (2026-07-25): st.audio_input()'s own record button is a
    # single unlabeled icon that toggles start/stop -- not obviously two
    # actions at a glance. Streamlit doesn't expose separate, independently
    # labeled "Speak"/"End" buttons for this widget (its internal UI isn't
    # customizable), so this caption spells out the same tap-once/tap-again
    # interaction in words instead.
    st.caption("🎤 Tap once to start speaking, tap again to end")
    mic_audio = st.audio_input(
        "Tap to talk", label_visibility="collapsed", key=f"mic_input_{st.session_state.mic_key_version}",
        help="Tap once to start speaking, tap again to end and transcribe.",
    )
    # R-29/R-33: text stays fully visible and one action away — never
    # hidden behind an extra click, never harder to reach — just visually
    # secondary to the mic above it.
    st.caption("...or type instead:")
else:
    mic_audio = st.audio_input(
        "Tap to talk", label_visibility="collapsed", key=f"mic_input_{st.session_state.mic_key_version}",
        help="Tap once to start speaking, tap again to end and transcribe.",
    )

# HIGH-1 (Team Waypoint Voice-First UI review): when the "✏️ Edit" button on
# the voice-heard confirmation banner (below) is tapped, it stashes the
# heard text here and reruns — consumed HERE, right before the keyed
# text_input is created, since a widget's session_state value can only be
# set before that widget renders in this same script run, not after.
# User report (2026-08-12): also bumps text_input_version so the widget
# below gets a genuinely NEW key -- forces a fresh component instance
# rather than relying on the browser re-syncing an existing one with the
# same key to its new server-provided value, the same fragility class
# already documented for st.audio_input() (mic_key_version).
if st.session_state.get("voice_edit_prefill"):
    st.session_state.text_input_version += 1
    st.session_state[f"main_text_input_{st.session_state.text_input_version}"] = st.session_state.pop("voice_edit_prefill")

_text_input_key = f"main_text_input_{st.session_state.text_input_version}"

with st.form("message_form", clear_on_submit=True):
    if not agent.itinerary:
        text_cols = st.columns([5, 1])
        user_text = text_cols[0].text_input(
            "Type your trip", placeholder="Plan a 2-day trip to Delhi, I like food and history...",
            label_visibility="collapsed", key=_text_input_key,
        )
        send_clicked = text_cols[1].form_submit_button("Send", use_container_width=True)
    else:
        text_cols = st.columns([5, 1])
        user_text = text_cols[0].text_input(
            "Ask or edit", placeholder="Ask or edit your itinerary — \"make day 1 more relaxed\", \"what if it rains?\"",
            label_visibility="collapsed", key=_text_input_key,
        )
        send_clicked = text_cols[1].form_submit_button("Send", use_container_width=True)

# User request (2026-07-16): the "transcribing" display renders into this
# slot, declared HERE — directly beneath the input area and, crucially,
# BEFORE the st.columns() split below. A Streamlit placeholder anchors where
# it's *declared*, so this sits right under the mic input (above the fold,
# where the user is looking). The `if mic_audio is not None:` block further
# down that writes into it runs at top level AFTER st.columns() — and would
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
    # R-32/UX-30: nothing previously indicated on screen that the app was
    # actively speaking — voice only ever appeared as transient spinners
    # during capture, then vanished. Streamlit can't observe browser-side
    # audio-element completion without a custom JS component, so this is a
    # static (not duration-aware) cue rather than a live waveform — still a
    # real improvement over no signal at all, and consistent with how every
    # other state in this app is shown (cleared on the next interaction).
    st.markdown("🔊 *Speaking your reply...*")
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
        # Component audit Tier 7: a one-time celebration for the moment the
        # trip actually comes together — st.balloons() is a real, built-in
        # Streamlit primitive designed for exactly this, unused anywhere in
        # the app until now. Gated on celebrated_first_build so it fires
        # once per trip, not on every subsequent edit (which would get old
        # fast — same restraint already applied to the post-edit nudges).
        # Called before st.rerun(): the balloons event is flushed as part of
        # THIS script run's output before the rerun begins, so it isn't
        # lost the way UI elements would be.
        if not st.session_state.get("celebrated_first_build"):
            st.session_state.celebrated_first_build = True
            st.balloons()
        # R-27: the itinerary-hero column layout is decided once, near the
        # top of the script, before this function (called from a button
        # handler further down) runs in that same execution — so a build
        # that happens INSIDE this call wouldn't switch to the full-width
        # layout until some unrelated later rerun without this. Force one
        # now so the hero layout applies on the very render the plan
        # finishes, not one interaction late.
        st.rerun()


if send_clicked and user_text.strip():
    _send(user_text)

if mic_audio is not None:
    # st.audio_input()'s value persists across reruns until a new clip is
    # recorded — without this fingerprint check, every unrelated rerun
    # (e.g. clicking Send, reordering a stop) would re-transcribe and
    # re-send the SAME old clip again. Only act on a genuinely new one.
    _audio_bytes = mic_audio.getvalue()
    _audio_fp = hashlib.md5(_audio_bytes).hexdigest()
    if _audio_fp != st.session_state.get("_last_mic_fingerprint"):
        st.session_state["_last_mic_fingerprint"] = _audio_fp
        # User request (2026-07-16): a prominent "transcribing" display at a
        # suitable location — rendered into `listening_slot` (declared above,
        # before the column split) so it appears directly under the input the
        # user just recorded into, not at the bottom of the page. No separate
        # "Listening…" phase here (R-20's original two-phase design) since
        # st.audio_input() already shows its own native recording/waveform UI
        # in the browser while capturing — this banner only covers the Groq
        # Whisper round-trip afterward.
        listening_slot.markdown(_TRANSCRIBING_BANNER, unsafe_allow_html=True)
        heard, error = try_transcribe_wav_bytes(_audio_bytes)
        if error:
            listening_slot.warning(error)
        elif heard:
            # HIGH-1 (Team Waypoint Voice-First UI review): don't act on a
            # transcription immediately — surface it for a one-tap
            # confirm/edit/discard first, so a misheard word ("Nice" for
            # "Nikko," the docx's own example) never silently executes.
            # Rendered below, into `listening_slot` again, so it still
            # appears right under the mic — the placeholder pattern this
            # file already relies on works from anywhere later in the
            # script, not just where it's declared.
            st.session_state.pending_voice_text = heard
            st.rerun()
        else:
            listening_slot.empty()

if st.session_state.get("pending_voice_text"):
    with listening_slot.container():
        st.markdown(f'🎙️ **Heard:** "{st.session_state.pending_voice_text}"')
        vcol1, vcol2, vcol3 = st.columns([1.6, 1, 1])
        if vcol1.button("✅ Send", type="primary", use_container_width=True, key="voice_confirm_send"):
            heard_text = st.session_state.pending_voice_text
            st.session_state.pending_voice_text = None
            _send(heard_text)
            st.rerun()
        if vcol2.button("✏️ Edit", use_container_width=True, key="voice_confirm_edit"):
            st.session_state.voice_edit_prefill = st.session_state.pending_voice_text
            st.session_state.pending_voice_text = None
            st.rerun()
        if vcol3.button("✕ Discard", use_container_width=True, key="voice_confirm_discard"):
            st.session_state.pending_voice_text = None
            st.rerun()

# --------------------------------------------------------------------------- #
# Itinerary Panel
# --------------------------------------------------------------------------- #
with col_itinerary:
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
        st.badge(
            "Real data — OpenStreetMap + Wikidata + Wikivoyage", icon="✅", color="green",
            help="Every stop, distance, and opening hour shown below is sourced from these three "
                 "real datasets — never invented or guessed.",
        )

        # HIGH-3 (Team Waypoint Voice-First UI review): a strong,
        # always-available undo — previously the only recovery from an edit
        # you regret was issuing another edit command to manually
        # reconstruct the prior state. Only rendered once there's actually
        # something to undo.
        # Component audit Tier 6: shows how many steps of history are
        # actually available, not just that undo exists — so the depth of
        # the safety net is visible, not just its presence.
        if agent.itinerary_history:
            n_undo = len(agent.itinerary_history)
            undo_label = f"↩️ Undo last change ({n_undo} available)"
            if st.button(undo_label, key="undo_last_change"):
                if agent.undo_last_edit():
                    st.toast("↩️ Last change undone")  # Tier 5: transient confirmation, not a persistent banner
                    st.rerun()

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
        tabs = st.tabs([f"Day {k.split('_')[1]} ({day_stop_counts[k]})" for k in day_keys])
        for tab, key in zip(tabs, day_keys):
            with tab:
                day = agent.itinerary[key]
                day_num = int(key.split("_")[1])
                st.caption(f"Total scheduled time: {day.get('total_hours', 0)}h")
                # MEDIUM-3 (Team Waypoint Voice-First UI review): "surface
                # contextual example prompts that change based on where the
                # person is ('Try: make day 2 more relaxed' while viewing
                # day 2)." Streamlit's st.tabs() renders every tab's content
                # in the same script run (the browser just shows/hides them),
                # so there's no server-side "which tab is active" signal to
                # key off of — but writing the Day-N-specific line INSIDE
                # this tab's own block still achieves exactly what the user
                # sees: whichever tab is open shows its own matching example.
                st.caption(f"💬 Try: \"make Day {day_num} more relaxed\" or \"swap a Day {day_num} stop for something else\"")
                for note in balance_notes_by_day.get(day_num, []):
                    st.caption(f"🕓 {note}")

                # Component audit Tier 3: the day's real stop photos as a
                # scroll-snap carousel, reusing the exact same cache R-22
                # already populates per stop card (no new fetch, no new
                # data). Capped at 8 images to keep the base64-inlined
                # payload bounded even on a long, photo-rich day.
                day_photo_uris = [
                    _carousel_thumbnail_data_uri(get_cached_image_path(s.get("image")))
                    for slot_ in ("morning", "afternoon", "evening")
                    for s in day.get(slot_, [])
                ]
                day_photo_uris = [u for u in day_photo_uris if u][:8]
                if day_photo_uris:
                    imgs_html = "".join(f'<img src="{uri}" class="wp-carousel-img">' for uri in day_photo_uris)
                    st.markdown(f'<div class="wp-carousel">{imgs_html}</div>', unsafe_allow_html=True)

                SLOT_MARKER_COLOR = {
                    "morning": [255, 140, 0],     # orange
                    "afternoon": [30, 144, 255],  # blue
                    "evening": [147, 112, 219],   # purple
                }
                all_stops = []
                for slot_label, slot_key in (("☀️ Morning", "morning"), ("🌤️ Afternoon", "afternoon"), ("🌙 Evening", "evening")):
                    stops = day.get(slot_key, [])
                    if not stops:
                        continue
                    st.markdown(f"**{slot_label}**")
                    for stop_idx, stop in enumerate(stops):
                        # R-11: cosmetic-only display-name cleanup ("HANUMAN
                        # MANDIR" -> "Hanuman Mandir") — never touches the
                        # stored name (dedup/citations/narrator all still
                        # see the original OSM string via `stops`/`itin`).
                        stop = {**stop, "_slot_key": slot_key, "name": format_display_name(stop["name"])}
                        all_stops.append(stop)

                        # R-23 (fixes UX-20): a bordered card per stop instead
                        # of a flat markdown bullet — photo + name/time on one
                        # row, category/duration/travel as a caption, grounded
                        # facts promoted to visible badges (R-24/UX-21 — these
                        # used to be the quietest gray text on the page despite
                        # being the app's actual credibility payload).
                        with st.container(border=True):
                            img_col, info_col, move_col = st.columns([1, 3.6, 0.5])
                            with img_col:
                                # R-22 (fixes QA-17/UX-19): a real photo when
                                # one exists (Wikidata P18, cached locally) —
                                # previously fetched into the dataset and then
                                # silently dropped one stage before the UI.
                                img_path = get_cached_image_path(stop.get("image"))
                                if img_path:
                                    st.image(img_path, use_container_width=True)
                                else:
                                    # Round 3 QA (UI3-2, "Team-Waypoint-QA-
                                    # Round3-and-UXUI-Benchmark.md"): a flat
                                    # neutral-gray box next to real photo
                                    # cards read as "half-finished," not as
                                    # "this venue has no public photo" (a
                                    # genuine fact of the open dataset — meal
                                    # stops almost never carry a Wikidata
                                    # image the way monuments do). A subtle
                                    # tint of the app's own brand accent reads
                                    # as a deliberate, on-brand placeholder
                                    # instead of a missing asset.
                                    st.markdown(
                                        "<div style='background:linear-gradient(135deg,"
                                        "rgba(194,84,12,0.20),rgba(194,84,12,0.06));"
                                        "border-radius:8px;height:80px;display:flex;"
                                        "align-items:center;justify-content:center;"
                                        f"font-size:1.8rem;'>{CATEGORY_ICON.get(stop['category'], '📍')}</div>",
                                        unsafe_allow_html=True,
                                    )
                            with move_col:
                                # Round 3 QA (UX3-5, the UI-side fix paired
                                # with E-3): no natural-language command can
                                # reorder stops yet (phase4/edit_engine.py's
                                # "reorder" edit type honestly declines and
                                # points here) — these are a real, working
                                # substitute: move a stop one position
                                # earlier/later through the day, swapping
                                # within a slot or crossing into the
                                # adjacent one, with times recomputed
                                # immediately after (_move_stop, above).
                                up_disabled = stop_idx == 0 and slot_key == "morning"
                                down_disabled = stop_idx == len(stops) - 1 and slot_key == "evening"
                                if st.button("↑", key=f"up_{key}_{slot_key}_{stop_idx}",
                                             disabled=up_disabled, help="Move earlier", use_container_width=True):
                                    agent.push_itinerary_snapshot()  # HIGH-3: undoable like any other edit
                                    _move_stop(agent.itinerary, key, slot_key, stop_idx, -1)
                                    # User report (2026-07-25): moving a stop
                                    # up/down didn't mark the "Full Itinerary"
                                    # overview stale the way a chat edit
                                    # command does (agent.py's own
                                    # narrative_stale sets) -- same real
                                    # inconsistency (schedule changed, prose
                                    # overview didn't), just reached through a
                                    # different UI control. Mirrors that
                                    # existing signal so the same refresh
                                    # button surfaces here too.
                                    agent.narrative_stale = True
                                    st.rerun()
                                if st.button("↓", key=f"down_{key}_{slot_key}_{stop_idx}",
                                             disabled=down_disabled, help="Move later", use_container_width=True):
                                    agent.push_itinerary_snapshot()  # HIGH-3: undoable like any other edit
                                    _move_stop(agent.itinerary, key, slot_key, stop_idx, 1)
                                    agent.narrative_stale = True
                                    st.rerun()
                            with info_col:
                                gem_badge = " 💎" if stop.get("is_hidden_gem") else ""
                                # R-25 (fixes UX-22): a real clock time, not
                                # just a duration — turns the stop list into
                                # an actual timeline.
                                # Theme proposal (2026-08-12): the name and
                                # time render via the .wp-stop-name /
                                # .wp-time-chip spans (Fraunces display face
                                # + a JetBrains Mono pill, matching the
                                # theme mockup's sample card) instead of
                                # plain markdown bold + backtick-code — the
                                # one stop-card element this round's
                                # implementation targets directly rather
                                # than only via a broad heading/code rule.
                                # html.escape() guards against a stop name
                                # containing HTML-special characters (OSM
                                # data, not sanitized for markup) now that
                                # this goes through unsafe_allow_html.
                                escaped_name = html.escape(stop["name"])
                                arrival = stop.get("arrival_time")
                                title_line = f"<span class='wp-stop-name'>{escaped_name}</span>{gem_badge}"
                                if arrival:
                                    title_line += f" <span class='wp-time-chip'>{arrival}</span>"
                                # MEDIUM-2 (Team Waypoint Voice-First UI
                                # review): "inline highlights on whatever
                                # just changed so the eye is drawn to the
                                # edit" — a swap/add changes WHICH stop is
                                # here, not just its position, so a chat
                                # confirmation alone is easy to miss if the
                                # user's eyes are on the itinerary itself.
                                # agent.last_changed_stops is cleared at the
                                # start of every new turn, so this only ever
                                # reflects the edit that JUST landed.
                                if (key, slot_key, stop_idx) in agent.last_changed_stops:
                                    title_line += "  :green[✨ Updated]"
                                st.markdown(title_line, unsafe_allow_html=True)

                                travel = stop.get("travel_time_from_prev_min", 0)
                                mode = stop.get("travel_mode_from_prev")
                                mode_icon = {"walk": "🚶", "auto": "🛺", "metro": "🚇"}.get(mode, "")
                                travel_note = f" · ↳ {mode_icon} {travel} min from previous stop" if travel else ""
                                # "· lunch" inside the same caption instead of a nested
                                # paren group — was "(restaurant (lunch))" (QA-9/R-15).
                                meal = stop.get("meal")
                                meal_note = f" · {meal}" if meal else ""
                                st.caption(
                                    f"{stop['category']}{meal_note} · {stop['visit_duration_min']} min{travel_note}"
                                )

                                # Round 3 QA (UI3-3, "Team-Waypoint-QA-Round3-
                                # and-UXUI-Benchmark.md"): Streamlit's stock
                                # :blue-badge/:green-badge colors are unrelated
                                # to the app's own terracotta accent -- these
                                # two facts are exactly the app's credibility
                                # payload (R-24), so they get real
                                # brand-derived tints instead of arbitrary
                                # framework defaults, while staying visually
                                # distinguishable from each other (a lighter
                                # tint for hours, a deeper one for the fee).
                                # The map's time-of-day marker colors
                                # (morning/afternoon/evening) are deliberately
                                # NOT touched here -- collapsing those three
                                # into one brand hue would make them harder to
                                # tell apart at a glance, trading away real
                                # legibility for cosmetic consistency.
                                badges = []
                                hours = stop.get("opening_hours")
                                if hours and hours != "unknown":
                                    badges.append(
                                        "<span style='background:rgba(194,84,12,0.12);"
                                        "border:1px solid rgba(194,84,12,0.35);color:#7A3608;"
                                        "border-radius:999px;padding:2px 10px;font-size:0.85rem;"
                                        f"display:inline-block;'>🕒 {format_opening_hours(hours)}</span>"
                                    )
                                entry_fee = stop.get("kb_entry_fee")
                                if entry_fee:
                                    badges.append(
                                        "<span style='background:rgba(194,84,12,0.28);"
                                        "border:1px solid rgba(194,84,12,0.6);color:#5C2A06;"
                                        "border-radius:999px;padding:2px 10px;font-size:0.85rem;"
                                        f"display:inline-block;'>🎟️ {entry_fee}</span>"
                                    )
                                if badges:
                                    st.markdown(" ".join(badges), unsafe_allow_html=True)
                                website = stop.get("website")
                                if website:
                                    st.markdown(f"[🌐 Official site]({website})")

                # R-25 (fixes UX-22): safety/logistics moved into a collapsed
                # expander below the day's actual stops — previously this was
                # the first full-contrast text a user read about their day,
                # ahead of the attractions themselves.
                # Component audit Tier 7: a bounded, real slice of the
                # icon-font hybrid — these three lines are pure functional
                # chrome (not expressive content), so a re-tintable,
                # cross-platform-consistent Material Symbols glyph reads
                # better here than an emoji whose exact rendering (and
                # color, unrelated to the brand accent) varies by OS.
                # html.escape() guards the real place names now that this
                # goes through unsafe_allow_html.
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
                            st.markdown(bit, unsafe_allow_html=True)

                if all_stops:
                    numbered = [
                        {
                            "lat": s["lat"], "lon": s["lon"], "name": s["name"],
                            # Round 3 QA (UI3-4): category added so it's
                            # accessible on hover. A full custom-icon-per-
                            # category glyph layer (the finding's more
                            # ambitious fix direction) needs pydeck's
                            # IconLayer, which takes image URLs, not emoji --
                            # a real, separate asset-generation effort out of
                            # proportion to a Low-priority item; this is the
                            # honest, immediately-real slice of it.
                            "tooltip_text": f"{s['name']} ({s.get('category', 'stop')})",
                            "num": str(i + 1),
                            "color": SLOT_MARKER_COLOR.get(s["_slot_key"], [200, 30, 30]),
                        }
                        for i, s in enumerate(all_stops)
                    ]
                    marker_df = pd.DataFrame(numbered)
                    route_df = pd.DataFrame([{"path": [[s["lon"], s["lat"]] for s in all_stops]}])
                    # Auto-fit to this day's actual stops instead of a fixed
                    # zoom=11 — previously overlapping markers (e.g. stop "3"
                    # hidden under 1/2/4) when a day's stops clustered tighter
                    # than that fixed zoom assumed (UX-15/R-16).
                    view_state = pdk.data_utils.compute_view(marker_df[["lon", "lat"]])
                    view_state.pitch = 0

                    deck = pdk.Deck(
                        map_style=None,
                        initial_view_state=view_state,
                        layers=[
                            pdk.Layer(
                                "PathLayer", data=route_df, get_path="path",
                                get_color=[120, 120, 120], get_width=3, width_min_pixels=2,
                            ),
                            pdk.Layer(
                                "ScatterplotLayer", data=marker_df, get_position=["lon", "lat"],
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
                    st.pydeck_chart(deck)
                    # Text alternative to the map's visual-only info (UX-8/R-10):
                    # marker numbers = visiting order, colors = time of day.
                    st.caption(
                        "Numbers show visiting order for the day; colors mark time of day "
                        "(🟠 morning · 🔵 afternoon · 🟣 evening). Line traces the route between stops."
                    )

        # Round 3 QA (UX3-6, "Team-Waypoint-QA-Round3-and-UXUI-Benchmark.md"):
        # the per-day map above only ever shows one day at a time -- this
        # adds a real, working second view with every stop across the whole
        # trip on one map, colored by DAY instead of time-of-day (so it
        # doesn't collide with the per-day map's own color legend just above
        # it). Deliberately not attempting per-day route lines or a
        # click-to-jump-to-stop interaction here: pydeck's Python wrapper has
        # no click callback, so a real "jump to stop" would need a
        # day-toggle + selectbox substitute -- a larger effort than this
        # Low-priority item warrants; this delivers the finding's core ask
        # (see everything at once) honestly, without overclaiming full
        # feature parity with a dedicated mapping product.
        if len(day_keys) > 1:
            with st.expander("🗺️ All days on one map"):
                DAY_COLORS = [
                    [194, 84, 12], [30, 144, 255], [60, 160, 60],
                    [147, 112, 219], [220, 20, 60],
                ]
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
                    legend = " · ".join(
                        f":violet[●] Day {d_key.split('_')[1]}" if d_idx == 3 else
                        f":blue[●] Day {d_key.split('_')[1]}" if d_idx == 1 else
                        f":green[●] Day {d_key.split('_')[1]}" if d_idx == 2 else
                        f":red[●] Day {d_key.split('_')[1]}" if d_idx == 4 else
                        f":orange[●] Day {d_key.split('_')[1]}"
                        for d_idx, d_key in enumerate(day_keys)
                    )
                    st.caption(f"Colors mark which day a stop belongs to: {legend}")

        if agent.enrichment_degraded:
            # QA-8/R-13: narrative/safety/transit hit a real error (e.g. rate
            # limit) during the build — say so honestly instead of just
            # rendering nothing, with an explicit (not automatic) retry.
            st.warning(
                "Couldn't load the full overview / safety notes just now — "
                "your day-by-day plan above is unaffected."
            )
            if st.button("🔄 Retry overview & safety info"):
                with st.spinner("Retrying..."):
                    agent.retry_enrichment()
                st.rerun()

        if agent.transit_info:
            with st.expander("🚇 Getting around Delhi"):
                st.write(agent.transit_info["answer"])
                for c in agent.transit_info.get("citations", []):
                    st.caption(f"Source: [{format_citation_label(c)}]({c.get('source_url', '')})")

        if agent.narrative:
            with st.expander("📖 Full Itinerary (overview, food, budget estimate, practical tips)"):
                if agent.narrative_stale:
                    # User report (2026-07-25): this section didn't
                    # "refresh automatically" after an edit -- true by
                    # design (QA-2/R-3: regenerating the full narrative on
                    # every single edit would mean an extra LLM call per
                    # edit, and this project has hit real Gemini free-tier
                    # rate limits from far less), but there was previously
                    # no way to refresh it at all, only a caption saying it
                    # was stale. Reuses retry_enrichment() -- the same
                    # explicit, user-triggered-only regeneration already
                    # used for the enrichment-degraded retry button below --
                    # against the CURRENT (already-edited) itinerary.
                    st.caption(
                        "⚠️ This overview describes your original plan — the Day tabs above "
                        "already reflect your latest edits."
                    )
                    if st.button("🔄 Refresh this overview for your latest edits"):
                        with st.spinner("Regenerating the full overview..."):
                            agent.retry_enrichment()
                        st.rerun()
                st.markdown(agent.narrative)

        st.divider()
        st.subheader("📧 Email me this plan")
        email = st.text_input("Your email address", key="email_input")
        if st.button("Send itinerary"):
            # User report (2026-07-25): "once the itinerary is refreshed,
            # the same should be sent on email" -- the emailed/downloaded
            # PDF's structured day-by-day section always reads live from
            # agent.itinerary (already current), but its prose overview
            # section came from agent.narrative, which can be stale after
            # an edit command or an up/down move (see narrative_stale sets
            # above and in agent.py). Refresh it here, once, right before
            # building the document -- so the two sections of the emailed
            # PDF can't describe two different plans -- rather than
            # requiring the user to remember to click the separate
            # "Refresh this overview" button first.
            if agent.narrative_stale and agent.narrative:
                with st.spinner("Updating the overview for your latest edits before sending..."):
                    agent.retry_enrichment()
            result = deliver_itinerary(agent.itinerary, agent.ctx.to_dict(), email, citations=agent.last_citations, narrative=agent.narrative)
            if result["emailed"]:
                st.success(result["message"])
            elif result["file_bytes"]:
                st.info(result["message"])
            else:
                st.error(result["message"])

            if result["file_bytes"]:
                st.download_button(
                    "⬇️ Download itinerary (.pdf)",
                    data=result["file_bytes"],
                    file_name=os.path.basename(result["file_path"]),
                    mime="application/pdf",
                )
    elif not pending_confirm:
        # R-26 (fixes UX-23): a real hero photo + a confident one-line
        # promise instead of a small info box floating in an empty white
        # void — the landing screen previously had no imagery and no
        # value-prop tagline at all.
        hero_path = get_cached_image_path(HERO_IMAGE_URL)
        if hero_path:
            st.image(hero_path, use_container_width=True)
        # R-34/UX-32: the tagline and capability list previously never told a
        # first-time user that speaking is the intended primary mode — every
        # line was framed around typing/chatting. Now leads with the mic.
        st.markdown("#### 🎤 Tap the mic above and tell me about your trip — real, grounded Delhi itineraries, no guesswork")
        st.caption(
            "Every stop, distance, and opening hour is sourced from OpenStreetMap, "
            "Wikidata, and Wikivoyage — cited, never invented."
        )
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
        st.caption("🎤 Tap the mic above and say one of these, or type your own trip below:")
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
            # Component audit Tier 4: Days is a small bounded range (1-4) --
            # a slider gives larger touch targets and shows the whole range
            # at a glance, more tactile than a number-entry stepper.
            quick_days = qc1.slider("Days", min_value=1, max_value=4, value=2)
            # Component audit Tier 4: three mutually-exclusive options are
            # exactly the case a dropdown handicaps -- every option should
            # be visible without a click, the way Kayak renders cabin class.
            quick_pace = qc2.radio("Pace", ["relaxed", "moderate", "intensive"], index=1, horizontal=True)
            quick_interests = st.multiselect(
                "Interests",
                ["food", "history", "culture", "architecture", "shopping", "nature", "religion", "art", "family"],
                default=["food", "history"],
            )
            quick_group = st.slider("Group size", min_value=1, max_value=10, value=1)
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
                composed = (
                    f"Plan a {quick_days}-day trip to Delhi, I like {interests_text}, "
                    f"{quick_pace} pace, {group_text}{dates_text}."
                )
                _send(composed)
                st.rerun()

# --------------------------------------------------------------------------- #
# Transcript + Sources Panel
# --------------------------------------------------------------------------- #
def _render_transcript_and_sources() -> None:
    # Round 3 QA (UX3-4): an invisible marker this file fully controls, that
    # the CSS `:has()` rule declared near the top of the script uses to
    # scope sticky positioning to *this* column only -- rendered before the
    # empty-transcript early return so the column is sticky from the very
    # first render, not only once messages exist (which would otherwise
    # cause a layout jump the moment the first message arrives).
    st.markdown('<span class="wp-transcript-marker" style="display:none;"></span>', unsafe_allow_html=True)

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
