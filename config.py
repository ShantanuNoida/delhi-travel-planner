"""
Shared LLM configuration — imported by Phase 3, 4, 5, 6.

Chat/reasoning (agent, narrator, intent classifier, explain engine) runs on
Gemini Flash via its OpenAI-compatible endpoint — moved off Groq because
Groq's free tier caps llama-3.3-70b-versatile at a flat 100,000 tokens/day,
which this project was hitting repeatedly. Published Gemini free-tier numbers
vary a lot by model and aren't reliable to plan around: the "flash" bucket
(gemini-flash-latest / gemini-3.5-flash) turned out to cap at just 20
requests/day/project on this key, exhausted by a single test run — so both
LLM_MODEL and LLM_MODEL_FAST point at the "flash-lite" bucket instead, which
has shown real headroom in practice. Re-verify actual limits in AI Studio
before relying on any specific number.

Speech-to-text stays on Groq Whisper (get_stt_client / GROQ_WHISPER_MODEL in
phase3/stt.py) because Gemini's OpenAI-compatible layer has no equivalent to
the /audio/transcriptions endpoint — only Groq/OpenAI-style clients expose it.

Usage:
    from config import get_llm_client, LLM_MODEL
    client = get_llm_client()
    response = client.chat.completions.create(model=LLM_MODEL, messages=[...])
"""

import os
import threading
from dotenv import load_dotenv
from openai import (
    OpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

load_dotenv()

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# "-latest" aliases always resolve to Google's current recommended Flash model —
# pinned version names (e.g. gemini-2.5-flash) get retired from new API keys as
# newer generations ship, which is what broke this on first deploy.
#
# LLM_MODEL was originally "gemini-flash-latest" (currently resolves to
# gemini-3.5-flash), but that bucket's free tier turned out to be only 20
# requests/day/project — a single test run or short conversation exhausts it.
# Both constants now point at the lite bucket, which has shown real headroom
# in practice; kept as two names (not collapsed into one) so LLM_MODEL can be
# repointed at a stronger model later without touching every call site, e.g.
# if billing gets enabled on the Gemini project.
LLM_MODEL = "gemini-flash-lite-latest"       # was gemini-flash-latest — see note above
LLM_MODEL_FAST = "gemini-flash-lite-latest"  # cheaper/faster for classification / evals

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Exceptions that unambiguously mean "this specific key is the problem"
# (exhausted quota, expired/revoked key) regardless of message content —
# these always trigger a rotation to the next key.
_ROTATE_ON = (RateLimitError, AuthenticationError, PermissionDeniedError)

# Gemini's OpenAI-compat endpoint doesn't return 401 for a malformed/invalid
# key like a typical OpenAI-style API — it returns a 400 BadRequestError with
# status "INVALID_ARGUMENT" and a message like "Please pass a valid API key"
# (confirmed empirically against the real endpoint, not assumed from docs).
# A 400 for any OTHER reason (bad model name, malformed messages, invalid
# response_format schema) would fail identically on every key, so rotating
# on those would waste calls and mask a real bug — only rotate a 400 when
# its own message specifically calls out the key.
_KEY_ERROR_PHRASES = ("api key", "api_key")


def _is_key_problem(exc: Exception) -> bool:
    if isinstance(exc, _ROTATE_ON):
        return True
    if isinstance(exc, BadRequestError):
        text = str(exc).lower()
        return any(phrase in text for phrase in _KEY_ERROR_PHRASES)
    return False


def _load_gemini_api_keys() -> list[str]:
    """
    Collects every configured Gemini API key, in order: GEMINI_API_KEY, then
    key #2, #3, ... (stops at the first gap). Lets the free-tier daily/
    per-minute quota limits that repeatedly blocked testing this session
    (GenerateRequestsPerDayPerProjectPerModel-FreeTier, GenerateRequestsPer
    MinutePerProjectPerModel-FreeTier) be worked around by adding more keys
    rather than waiting out a reset.

    Accepts both `GEMINI_API_KEY_2` and `GEMINI_API_KEY2` (with or without
    the underscore) for each numbered key — the documented convention is
    the underscored form, but the no-underscore form is an easy, natural
    typo to make by hand and there's no reason to make the user go back
    and rename it.
    """
    keys = []
    primary = os.environ.get("GEMINI_API_KEY")
    if primary:
        keys.append(primary)
    i = 2
    while True:
        extra = os.environ.get(f"GEMINI_API_KEY_{i}") or os.environ.get(f"GEMINI_API_KEY{i}")
        if not extra:
            break
        keys.append(extra)
        i += 1
    return keys


class _RotatingChatCompletions:
    def __init__(self, client: "RotatingGeminiClient"):
        self._client = client

    def create(self, **kwargs):
        return self._client._call_with_rotation(**kwargs)


class _RotatingChat:
    def __init__(self, client: "RotatingGeminiClient"):
        self.completions = _RotatingChatCompletions(client)


class RotatingGeminiClient:
    """
    Drop-in stand-in for `openai.OpenAI` exposing just the
    `chat.completions.create(...)` surface every call site in this project
    uses — so nothing downstream (agent.py, itinerary_narrator.py,
    intent_classifier.py, explain_engine.py) needs to change to get
    rotation; they already just call `get_llm_client().chat.completions
    .create(...)`.

    Holds one real `OpenAI` client per configured Gemini key and remembers
    which one last worked (`_current`). On a rotation-worthy failure — see
    `_is_key_problem()` — tries the remaining keys in order before giving
    up, and if a *different* key succeeds, that becomes the new default —
    so once key 1 is exhausted, every subsequent call across the whole app
    goes straight to key 2 instead of re-discovering key 1 is dead on every
    call. Only raises (to callers' existing RateLimitError/
    AuthenticationError handling — e.g. R-1's _handle_turn_failure in
    agent.py) once every configured key has failed, or immediately for a
    non-key-related error (rotating those would just waste calls on every
    key before failing anyway).
    """

    def __init__(self, api_keys: list[str], base_url: str):
        if not api_keys:
            raise EnvironmentError(
                "No Gemini API key is set. "
                "Copy .env.example to .env and add your Gemini API key "
                "(free at https://aistudio.google.com/apikey). "
                "Add GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc. for additional keys to rotate through."
            )
        self._clients = [OpenAI(api_key=k, base_url=base_url) for k in api_keys]
        self._current = 0
        self._lock = threading.Lock()
        self.chat = _RotatingChat(self)

    def _call_with_rotation(self, **kwargs):
        last_exc: Exception | None = None
        start = self._current
        n = len(self._clients)
        for attempt in range(n):
            idx = (start + attempt) % n
            try:
                result = self._clients[idx].chat.completions.create(**kwargs)
            except (*_ROTATE_ON, BadRequestError) as e:
                if not _is_key_problem(e):
                    raise  # a genuine bad request — would fail on every key, don't mask it
                last_exc = e
                more = attempt < n - 1
                print(
                    f"  [config] Gemini key #{idx + 1}/{n} failed ({type(e).__name__})"
                    + (" — trying next key" if more else " — no keys left")
                )
                continue
            if idx != self._current:
                with self._lock:
                    self._current = idx
                print(f"  [config] switched default Gemini key to #{idx + 1}/{n}")
            return result
        raise last_exc


_rotating_client: RotatingGeminiClient | None = None


def get_llm_client() -> RotatingGeminiClient:
    """
    Chat/reasoning client — Gemini Flash (OpenAI-compatible endpoint),
    rotating across every GEMINI_API_KEY[_N] configured in .env. A single
    shared instance (not rebuilt per call) so the "which key currently
    works" state is remembered across every module that calls this, not
    just within one function's retries.
    """
    global _rotating_client
    if _rotating_client is None:
        _rotating_client = RotatingGeminiClient(_load_gemini_api_keys(), GEMINI_BASE_URL)
    return _rotating_client


def get_stt_client() -> OpenAI:
    """Speech-to-text client — Groq Whisper. Gemini has no transcription endpoint."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Copy .env.example to .env and add your Groq API key."
        )
    return OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
