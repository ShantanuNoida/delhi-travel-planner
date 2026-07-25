"""
Mic capture for the Companion UI. Runs Phase 3's server-side STT (via the
SpeechRecognition package + the host machine's microphone) — appropriate for
a locally-run app where the browser and the Python process share a machine.
Isolated from app.py so the permission-denied / no-mic-hardware fallback
path (T-6.7) is testable without a running Streamlit session.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASE3_DIR = os.path.join(_ROOT, "phase3")

# R-18: shared across every mic entry point below so the three messages
# never drift apart between the all-in-one path and the split (R-20)
# capture/transcribe path.
_MSG_NO_SPEECH = "I didn't catch that. Please try again or use the text box instead."
_MSG_TRANSCRIPTION_FAILED = "Voice typing is unavailable right now — please type your message instead."
_MSG_MIC_UNAVAILABLE = "Microphone unavailable right now. Please use the text box instead."


def _make_stt_factory(stt_factory):
    if stt_factory is not None:
        return stt_factory
    sys.path.insert(0, PHASE3_DIR)
    from stt import STT
    return lambda: STT(mode="mic")


def try_capture_mic_audio(stt_factory=None):
    """
    Phase 1 of the split mic flow (R-20/UX-16): records audio only, no
    transcription. Returns (audio, error_message) — audio is a raw
    `speech_recognition.AudioData` object (None on failure). Pair with
    try_transcribe_audio() so the UI can show "Listening..." during this
    call and a separate "Transcribing..." during the next one.
    """
    try:
        stt = _make_stt_factory(stt_factory)()
        audio, no_speech = stt.capture_mic_audio()
        if no_speech:
            return (None, _MSG_NO_SPEECH)
        return (audio, None)
    except Exception as e:
        print(f"  [voice_input error] {e}")  # server-side only — never shown to the user
        return (None, _MSG_MIC_UNAVAILABLE)


def try_transcribe_audio(audio, stt_factory=None) -> tuple[str, str | None, bool]:
    """
    Phase 2 of the split mic flow: transcribes audio already captured by
    try_capture_mic_audio(). Returns (transcript, error_message,
    possibly_truncated).
    """
    try:
        stt = _make_stt_factory(stt_factory)()
        text, reason, possibly_truncated = stt.transcribe_audio(audio)
        if reason == "no_speech":
            return ("", _MSG_NO_SPEECH, False)
        if reason == "transcription_failed":
            return ("", _MSG_TRANSCRIPTION_FAILED, False)
        return (text, None, possibly_truncated)
    except Exception as e:
        print(f"  [voice_input error] {e}")
        return ("", _MSG_TRANSCRIPTION_FAILED, False)


def try_transcribe_wav_bytes(wav_bytes, stt_factory=None) -> tuple[str, str | None]:
    """
    Transcribes a browser-recorded clip (st.audio_input() in app.py) — the
    remote-host-compatible counterpart to try_capture_mic_audio() +
    try_transcribe_audio() above, which open the SERVER's microphone and
    have nothing to capture on a host with no physical mic attached (e.g.
    Streamlit Community Cloud). Returns (transcript, error_message).
    """
    try:
        stt = _make_stt_factory(stt_factory)()
        text, reason = stt.transcribe_wav_bytes(wav_bytes)
        if reason == "no_speech":
            return ("", _MSG_NO_SPEECH)
        if reason == "transcription_failed":
            return ("", _MSG_TRANSCRIPTION_FAILED)
        return (text, None)
    except Exception as e:
        print(f"  [voice_input error] {e}")  # server-side only — never shown to the user
        return ("", _MSG_TRANSCRIPTION_FAILED)


def try_listen_via_mic(stt_factory=None) -> tuple[str, str | None, bool]:
    """
    Attempt to capture one spoken utterance.
    Returns (transcript, error_message, possibly_truncated) — transcript is
    "" and error_message is set whenever the mic is unavailable, denied, or
    nothing was heard in time; possibly_truncated is True on a successful
    capture that likely got cut off mid-sentence (R-20/QA-10).

    R-18 (Itinerary-Quality-Review-and-Recommendations.md QA-11/QA-12): the
    error message is cause-specific — "no speech" vs. "the transcription
    service itself failed" vs. "the mic/hardware is unavailable" each get
    different guidance, and none of them leak a raw exception string to the
    user; the technical detail is logged server-side only, mirroring the
    R-5 email-copy pattern (never show the user a raw errno/API trace).
    """
    try:
        stt = _make_stt_factory(stt_factory)()
        heard, reason, possibly_truncated = stt.listen_detailed()
        if reason == "no_speech":
            return ("", _MSG_NO_SPEECH, False)
        if reason == "transcription_failed":
            return ("", _MSG_TRANSCRIPTION_FAILED, False)
        return (heard, None, possibly_truncated)
    except Exception as e:
        print(f"  [voice_input error] {e}")  # server-side only — never shown to the user
        return ("", _MSG_MIC_UNAVAILABLE, False)
