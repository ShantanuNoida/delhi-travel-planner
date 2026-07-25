"""
Companion UI — Phase 6.

Run with: streamlit run app.py
"""

import hashlib
import os
import sys

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

DAY_SLOTS = ("morning", "afternoon", "evening")


def _day_total_hours(day: dict) -> float:
    minutes = sum(
        s.get("visit_duration_min", 0) + s.get("travel_time_from_prev_min", 0)
        for slot in DAY_SLOTS for s in day.get(slot, [])
    )
    return round(minutes / 60, 2)


def _recompute_slot_times(day: dict, slot: str) -> None:
    """UX3-5 (Round 3 QA): recomputes travel_time_from_prev_min /
    travel_mode_from_prev / arrival_time (and the restaurant meal timestamp)
    for every stop in one slot, in its current order -- mirrors
    phase2/itinerary_builder.py's own per-stop arrival-time formula (R-25:
    slot start hour + minutes already used in that slot + travel to reach
    this stop) so a manually reordered slot shows times consistent with a
    fresh build, not stale positions with the old order's times."""
    from itinerary_builder import SLOTS, _travel_time_min, _travel_mode, _haversine_km, _format_clock

    stops = day.get(slot, [])
    slot_start_min = SLOTS[slot][0] * 60
    minutes_used = 0
    prev = None
    for stop in stops:
        if prev is not None:
            travel = _travel_time_min(prev, stop)
            road_km = _haversine_km(prev["lat"], prev["lon"], stop["lat"], stop["lon"]) * 1.4
            mode = _travel_mode(road_km)
        else:
            travel, mode = 0, None
        stop["travel_time_from_prev_min"] = travel
        stop["travel_mode_from_prev"] = mode
        arrival_min = slot_start_min + minutes_used + travel
        stop["arrival_time"] = _format_clock(arrival_min)
        if stop.get("category") == "restaurant":
            stop["meal"] = f"meal ~{_format_clock(arrival_min)}"
        minutes_used += stop.get("visit_duration_min", 0) + travel
        prev = stop


def _move_stop(itinerary: dict, day_key: str, slot: str, idx: int, direction: int) -> None:
    """UX3-5 (Round 3 QA, fixes the UX side of E-3): move a stop one position
    earlier/later through the day's morning->afternoon->evening sequence --
    swap within the same slot when possible, otherwise move across the slot
    boundary onto the end/start of the adjacent slot. direction: -1 = earlier,
    +1 = later. No natural-language command does this yet (see E-3/_apply_reorder
    in phase4/edit_engine.py, which honestly declines and points here) --
    this is a real, working substitute, not a placeholder."""
    day = itinerary[day_key]
    slot_idx = DAY_SLOTS.index(slot)
    stops = day[slot]
    target_idx = idx + direction

    if 0 <= target_idx < len(stops):
        stops[idx], stops[target_idx] = stops[target_idx], stops[idx]
        _recompute_slot_times(day, slot)
        day["total_hours"] = _day_total_hours(day)
        return

    neighbor_slot_idx = slot_idx + direction
    if not (0 <= neighbor_slot_idx < len(DAY_SLOTS)):
        return  # already at the very start/end of the day -- nothing to do
    neighbor_slot = DAY_SLOTS[neighbor_slot_idx]
    stop = stops.pop(idx)
    if direction == -1:
        day[neighbor_slot].append(stop)      # becomes the last stop of the earlier slot
    else:
        day[neighbor_slot].insert(0, stop)   # becomes the first stop of the later slot
    _recompute_slot_times(day, slot)
    _recompute_slot_times(day, neighbor_slot)
    day["total_hours"] = _day_total_hours(day)


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
st.markdown(
    """
<style>
h1 {
    font-weight: 800 !important;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #C2540C, #7A3608);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"] .wp-transcript-marker)
    > div[data-testid="stColumn"]:nth-of-type(2) {
    position: sticky;
    top: 1rem;
    align-self: flex-start;
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

agent: TravelAgent = st.session_state.agent

with st.sidebar:
    st.header("Settings")
    # R-17/QA-13: never give the agent a "speak" TTS — that used to make
    # `process_turn` block synchronously on server-side audio playback
    # (a busy-wait inside `st.spinner`), freezing the whole app for the
    # entire spoken duration with no way to stop it. Voice output is
    # handled separately in _send()/_play_reply_audio() below: synthesize
    # audio bytes (no playback) after the reply is ready, then hand them to
    # st.audio() for non-blocking browser playback.
    agent.tts = None
    if st.button("🔄 Start a new trip"):
        agent.reset()
        st.session_state.transcript = []
        st.rerun()

st.title("🧭 Delhi Travel Planner")

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
    voice_output = st.checkbox(
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
    st.markdown(
        '<div style="text-align:center; margin-bottom:2px;">'
        '<span style="display:inline-block; font-size:1.4rem; '
        'animation: r30-idle-pulse 2.2s ease-in-out infinite;">🎙️</span></div>'
        '<style>@keyframes r30-idle-pulse '
        '{0%{opacity:0.55; transform:scale(1);} 50%{opacity:1; transform:scale(1.18);} '
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
        "Tap to talk", label_visibility="collapsed", key="mic_input",
        help="Tap once to start speaking, tap again to end and transcribe.",
    )
    # R-29/R-33: text stays fully visible and one action away — never
    # hidden behind an extra click, never harder to reach — just visually
    # secondary to the mic above it.
    st.caption("...or type instead:")
else:
    mic_audio = st.audio_input(
        "Tap to talk", label_visibility="collapsed", key="mic_input",
        help="Tap once to start speaking, tap again to end and transcribe.",
    )

with st.form("message_form", clear_on_submit=True):
    if not agent.itinerary:
        text_cols = st.columns([5, 1])
        user_text = text_cols[0].text_input(
            "Type your trip", placeholder="Plan a 2-day trip to Delhi, I like food and history...",
            label_visibility="collapsed",
        )
        send_clicked = text_cols[1].form_submit_button("Send", use_container_width=True)
    else:
        text_cols = st.columns([5, 1])
        user_text = text_cols[0].text_input(
            "Ask or edit", placeholder="Ask or edit your itinerary — \"make day 1 more relaxed\", \"what if it rains?\"",
            label_visibility="collapsed",
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
    with st.spinner(THINKING_MESSAGE):
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
        else:
            listening_slot.empty()
            _send(heard)

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
    if pending_confirm:
        last_text = st.session_state.transcript[-1][1]
        st.info(f"🧭 **{last_text}**")
        confirm_cols = st.columns(2)
        if confirm_cols[0].button("✅ Yes, build it", use_container_width=True, type="primary", key="confirm_yes"):
            _send("Yes")
            st.rerun()
        if confirm_cols[1].button("✏️ No, let me change something", use_container_width=True, key="confirm_no"):
            _send("No")
            st.rerun()
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
        st.badge("Real data — OpenStreetMap + Wikidata + Wikivoyage", icon="✅", color="green")

        # UX-12/R-14: persistent, always-visible reminder that editing/explain
        # is possible mid-conversation — previously only mentioned once the
        # user already said goodbye (agent.py's DONE-state reply).
        st.caption(
            "💬 Want changes? Try \"make day 1 more relaxed\" or ask "
            "\"is the metro safe at night?\" — just type it in below."
        )
        # UX-14/R-16: honest note on light/evening-open days instead of
        # letting the narrator's generic "explore the streets" filler paper
        # over it — informational only, doesn't affect the itinerary itself.
        balance_notes_by_day: dict[int, list[str]] = {}
        for note in check_day_balance(agent.itinerary, agent.ctx.pace or "moderate")["notes"]:
            balance_notes_by_day.setdefault(note["day"], []).append(note["note"])

        tabs = st.tabs([f"Day {k.split('_')[1]}" for k in day_keys])
        for tab, key in zip(tabs, day_keys):
            with tab:
                day = agent.itinerary[key]
                day_num = int(key.split("_")[1])
                st.caption(f"Total scheduled time: {day.get('total_hours', 0)}h")
                for note in balance_notes_by_day.get(day_num, []):
                    st.caption(f"🕓 {note}")

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
                                    _move_stop(agent.itinerary, key, slot_key, stop_idx, -1)
                                    st.rerun()
                                if st.button("↓", key=f"down_{key}_{slot_key}_{stop_idx}",
                                             disabled=down_disabled, help="Move later", use_container_width=True):
                                    _move_stop(agent.itinerary, key, slot_key, stop_idx, 1)
                                    st.rerun()
                            with info_col:
                                gem_badge = " 💎" if stop.get("is_hidden_gem") else ""
                                # R-25 (fixes UX-22): a real clock time, not
                                # just a duration — turns the stop list into
                                # an actual timeline.
                                arrival = stop.get("arrival_time")
                                title_line = f"**{stop['name']}**{gem_badge}"
                                if arrival:
                                    title_line += f"  `{arrival}`"
                                st.markdown(title_line)

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
                emergency_bits = []
                if day.get("nearest_hospital"):
                    h = day["nearest_hospital"]
                    emergency_bits.append(f"🏥 Nearest hospital: {format_display_name(h['name'])} ({h['distance_km']} km)")
                if day.get("nearest_pharmacy"):
                    p = day["nearest_pharmacy"]
                    emergency_bits.append(f"💊 Nearest pharmacy: {format_display_name(p['name'])} ({p['distance_km']} km)")
                if day.get("nearest_metro_station"):
                    m = day["nearest_metro_station"]
                    emergency_bits.append(f"🚇 Nearest metro: {format_display_name(m['name'])} ({m['distance_km']} km)")
                if emergency_bits:
                    with st.expander("🚑 Safety & logistics"):
                        for bit in emergency_bits:
                            st.markdown(bit)

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
            quick_days = qc1.number_input("Days", min_value=1, max_value=4, value=2, step=1)
            quick_pace = qc2.selectbox("Pace", ["relaxed", "moderate", "intensive"], index=1)
            quick_interests = st.multiselect(
                "Interests",
                ["food", "history", "culture", "architecture", "shopping", "nature", "religion", "art", "family"],
                default=["food", "history"],
            )
            quick_group = st.number_input("Group size", min_value=1, max_value=10, value=1, step=1)
            if st.button("Build this trip", use_container_width=True):
                interests_text = ", ".join(quick_interests) if quick_interests else "a mix of culture and food"
                group_text = "solo" if quick_group == 1 else f"a group of {quick_group}"
                composed = (
                    f"Plan a {quick_days}-day trip to Delhi, I like {interests_text}, "
                    f"{quick_pace} pace, {group_text}."
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
