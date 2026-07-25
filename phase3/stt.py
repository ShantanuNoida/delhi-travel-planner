"""
Speech-to-text wrapper.

Modes:
  "mic"    — capture from the microphone (SpeechRecognition), transcribe via
             Groq's Whisper endpoint (GROQ_API_KEY — free tier, fast, and far
             more accurate than the previous Google Web Speech API this
             replaced). Stays on Groq even though chat/reasoning moved to
             Gemini (config.get_llm_client): Gemini's OpenAI-compatible layer
             has no /audio/transcriptions endpoint.
  "text"   — read from stdin (for testing and text-only mode)
"""

import io
import os
import sys
from typing import Literal

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

STT_MODE = Literal["mic", "text"]

# turbo trades a little accuracy for much lower latency — the right call for
# a live conversation. Swap to "whisper-large-v3" if accuracy matters more
# than responsiveness for your use case.
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

# R-20 (Itinerary-Quality-Review-and-Recommendations.md QA-10): the original
# 10s cap silently truncated a natural, detailed spoken request ("I've got
# three days, I love Mughal history and street food, but I want a relaxed
# pace and my parents are with me so...") mid-sentence, with nothing telling
# the user their input was cut off. Raised with a still-bounded ceiling —
# long enough for a real multi-constraint request, short enough that an
# accidental click can't hold the mic open indefinitely.
PHRASE_TIME_LIMIT_SEC = 25


class STT:
    def __init__(self, mode: STT_MODE = "text", language: str = "en-IN"):
        self.mode = mode
        self.language = language

    def listen(self, prompt: str = "") -> str:
        """
        Block until a phrase is captured. Returns transcript string, or ""
        on any failure (silence, mic error, transcription error) — the
        simple, never-raises contract the CLI REPL (`agent.run_session`)
        relies on. Use listen_detailed() to distinguish WHY it failed.
        """
        text, _reason, _truncated = self.listen_detailed(prompt)
        return text

    def listen_detailed(self, prompt: str = "") -> tuple[str, str | None, bool]:
        """
        Returns (transcript, failure_reason, possibly_truncated).

        failure_reason is None on success, "no_speech" if nothing was said
        within the listening window, or "transcription_failed" if audio was
        captured but the Groq Whisper call itself failed (API error/timeout/
        rate-limit). R-18 (Itinerary-Quality-Review-and-Recommendations.md
        QA-11): these two failure causes used to collapse into the same ""
        result, so a user whose transcription failed because Groq was down
        or rate-limited got the same "I didn't catch that" message as
        someone who simply said nothing — they'd keep re-recording (spending
        more Whisper quota) instead of being told to wait or type.

        possibly_truncated is True when captured speech ran right up to
        PHRASE_TIME_LIMIT_SEC, meaning the user was very likely still
        talking when capture cut off (R-20/QA-10) — always False in "text"
        mode or on any failure, since it's only meaningful for a real
        successful capture.
        """
        if self.mode == "text":
            return (self._from_stdin(prompt), None, False)
        return self._from_mic(prompt)

    def _from_stdin(self, prompt: str) -> str:
        if prompt:
            print(f"\n[You]: ", end="", flush=True)
        else:
            print("[You]: ", end="", flush=True)
        return input().strip()

    def _from_mic(self, prompt: str) -> tuple[str, str | None, bool]:
        """Capture + transcribe in one call — used by the CLI REPL, which
        doesn't need split "listening" vs "transcribing" feedback."""
        audio, no_speech = self.capture_mic_audio()
        if no_speech:
            return ("", "no_speech", False)
        return self.transcribe_audio(audio)

    def capture_mic_audio(self, timeout: float = 5):
        """
        Records one phrase from the microphone and returns
        (audio, no_speech) — audio is a raw `speech_recognition.AudioData`
        object (or None if nothing was captured within `timeout`).
        Deliberately does NOT transcribe — split out (R-20/UX-16) so a
        caller (the Streamlit UI) can show a distinct "🎤 Listening..."
        state during capture and a separate "✍️ Transcribing..." state
        during the subsequent Groq Whisper network round-trip, instead of
        one spinner silently covering both (which made users think the app
        had frozen, or that it was still recording after they'd stopped
        talking).
        """
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        # User-reported bug (2026-07-16): with SpeechRecognition's default
        # pause_threshold (0.8s), a normal mid-sentence breath or a brief
        # pause between clauses ("...three days, I love Mughal history —
        # [pause] — and street food...") was already enough silence for
        # listen() to decide the phrase had ended, so transcription started
        # on a truncated sentence the user was still speaking. Widened to
        # give real conversational pauses room without waiting so long that
        # a genuinely finished sentence feels laggy to transcribe.
        recognizer.pause_threshold = 1.5

        with sr.Microphone() as source:
            print("  [listening...]")
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Second bug found via live testing (2026-07-16): widening
            # pause_threshold alone didn't fix it — the user still saw BOTH
            # premature cutoffs (mid-sentence, no real pause) AND failures
            # to cut off at all after a genuine long pause. Root cause is
            # `dynamic_energy_threshold=True` staying on for the actual
            # listen() call, not just calibration: SpeechRecognition keeps
            # re-targeting the energy threshold at 1.5x the *current*
            # buffer's energy throughout the whole recording (see its own
            # `_listen()`), so a louder word/syllable ratchets the threshold
            # up until normal-volume speech right after it reads as
            # "silence" (false early cutoff), while quiet stretches let the
            # threshold sag low enough that ordinary room/fan noise during a
            # real pause keeps registering as "still speaking" (pause never
            # accumulates, so it never cuts off). `adjust_for_ambient_noise`
            # above already calibrates a sensible baseline once per capture;
            # freezing it right after — rather than letting it keep chasing
            # every buffer for the rest of the recording — makes the
            # speech/silence boundary stable for the whole utterance instead
            # of drifting under it.
            recognizer.dynamic_energy_threshold = False
            try:
                # QA-3/R-4 shortened the original 10s/15s to cap the worst-case
                # freeze on an accidental click; PHRASE_TIME_LIMIT_SEC further
                # tuned by R-20 to give real speech more room (see its own note).
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=PHRASE_TIME_LIMIT_SEC)
            except sr.WaitTimeoutError:
                return (None, True)
        return (audio, False)

    def transcribe_audio(self, audio) -> tuple[str, str | None, bool]:
        """
        Transcribes previously-captured audio (from capture_mic_audio()).
        Returns (transcript, failure_reason, possibly_truncated) — same
        success/failure shape as listen_detailed().
        """
        # R-20/QA-10: if capture ran right up against the phrase limit, the
        # user was very likely still talking when it cut off — real audio
        # duration, not a guess (frame_data length / sample rate * width).
        duration_sec = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
        possibly_truncated = duration_sec >= PHRASE_TIME_LIMIT_SEC - 0.5

        try:
            text = self._transcribe_groq(audio)
            if text:
                print(f"[You]: {text}")
            return (text, None if text else "no_speech", possibly_truncated)
        except Exception as e:
            print(f"  [STT error] {e}")
            return ("", "transcription_failed", False)

    def _transcribe_groq(self, audio) -> str:
        from config import get_stt_client

        client = get_stt_client()
        buf = io.BytesIO(audio.get_wav_data())
        buf.name = "audio.wav"  # the client needs a filename to set the upload content-type

        # Whisper wants an ISO-639-1 code (e.g. "en"), not a locale like "en-IN"
        lang = (self.language or "en").split("-")[0]
        resp = client.audio.transcriptions.create(
            model=GROQ_WHISPER_MODEL,
            file=buf,
            language=lang,
        )
        return resp.text.strip()
