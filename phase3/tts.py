"""
Text-to-speech wrapper.

Modes:
  "speak"  — edge-tts (free, natural neural voices, no API key — just needs
             internet). Falls back automatically to pyttsx3 (offline, more
             robotic) if edge-tts fails, e.g. no network.
  "print"  — silent, just print text (for tests and headless environments)
"""

import asyncio
import io
import os
import tempfile
import threading
from typing import Literal

TTS_MODE = Literal["speak", "print"]

# Natural US English neural voice. List alternatives with `edge-tts --list-voices`
# (e.g. "en-IN-NeerjaNeural" for an Indian-English voice fits this project's
# New Delhi focus, "en-GB-SoniaNeural" for British English, etc.)
EDGE_VOICE = "en-US-AriaNeural"

_mixer_ready = False
_audio_lock = threading.Lock()


def _ensure_mixer() -> None:
    global _mixer_ready
    if not _mixer_ready:
        import pygame
        pygame.mixer.init()
        _mixer_ready = True


class TTS:
    def __init__(self, mode: TTS_MODE = "speak"):
        self.mode = mode

    def speak(self, text: str) -> None:
        """
        CLI/REPL playback (`phase3/main.py --voice`): synthesizes and plays
        server-side, blocking until finished — correct there, since a
        terminal conversation has nothing else to keep responsive while it
        talks. The Streamlit UI does NOT use this method (R-17/QA-13: this
        used to be the only path, and its busy-wait ran inside the request
        thread under `st.spinner`, freezing the whole app for the entire
        spoken duration with no way to stop it). The UI calls synthesize()
        instead and plays the returned bytes non-blockingly via
        `st.audio(..., autoplay=True)`, which also gives native browser
        playback controls (pause/seek) for free.
        """
        print(f"\n[Agent]: {text}")
        if self.mode != "speak":
            return
        result = self.synthesize(text)
        if result is None:
            return  # both backends failed; already logged by synthesize()
        audio_bytes, _mime, _backend = result
        self._play_bytes(audio_bytes)

    def synthesize(self, text: str) -> tuple[bytes, str, str] | None:
        """
        Generates audio bytes WITHOUT playing them. Returns
        (audio_bytes, mime_type, backend_used) — backend_used is "edge-tts"
        or "pyttsx3", so a caller (e.g. the Streamlit UI) can tell the user
        when playback has degraded to the offline voice (R-19/QA-14 — this
        used to be a server-console-only print, invisible in the browser).
        Returns None if both backends fail.
        """
        try:
            return (self._generate_edge_mp3(text), "audio/mp3", "edge-tts")
        except Exception as e:
            print(f"  [TTS] edge-tts unavailable ({e}) — falling back to offline voice")
            try:
                return (self._generate_pyttsx3_wav(text), "audio/wav", "pyttsx3")
            except Exception as e2:
                print(f"  [TTS] offline voice also failed ({e2})")
                return None

    def _generate_edge_mp3(self, text: str) -> bytes:
        import edge_tts

        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            async def _generate():
                communicate = edge_tts.Communicate(text, EDGE_VOICE)
                await communicate.save(path)

            asyncio.run(_generate())
            with open(path, "rb") as f:
                return f.read()
        finally:
            # R-21/QA-16: always clean up, even on failure — the old code
            # only removed this file on the success path, so a load/play
            # exception after generation (corrupt file, mixer init issue)
            # orphaned it in the system temp dir; repeated failures leaked
            # unbounded temp files over a long session.
            if os.path.exists(path):
                os.remove(path)

    def _generate_pyttsx3_wav(self, text: str) -> bytes:
        """
        R-19/QA-15: a fresh pyttsx3 engine per call, not a cached module
        global. Reusing one persisted engine across repeated
        say()/runAndWait() calls is a well-documented failure mode on
        Windows' SAPI5 backend — the first utterance works, later ones can
        hang or go silent. This fallback only ever triggers when edge-tts
        is already down, which is exactly when reliability matters most —
        a fallback that only reliably speaks once isn't much of a fallback.
        """
        import pyttsx3

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 0.9)
            engine.save_to_file(text, path)
            engine.runAndWait()
            with open(path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def _play_bytes(self, audio_bytes: bytes) -> None:
        import pygame

        with _audio_lock:
            _ensure_mixer()
            pygame.mixer.music.load(io.BytesIO(audio_bytes))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
