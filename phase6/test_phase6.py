"""
Phase 6 test suite — automated coverage of T-6.1, T-6.3, T-6.4, T-6.5, T-6.7.

T-6.2 (mic + live transcript), T-6.6 (mobile layout), and T-6.8 (full
deployed-URL smoke test) require an actual browser session and are not
automatable here — see the manual verification notes printed at the end.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase2"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def _result(label: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


def _build_fixture_itinerary() -> dict:
    from poi_search import poi_search_logic
    from itinerary_builder import itinerary_builder_logic

    pois = poi_search_logic("New Delhi", ["history", "food"], top_n=10)
    return itinerary_builder_logic(pois, days=2, pace="moderate")


# ---------------------------------------------------------------------------
# T-6.1  Itinerary document rendering (PDF equivalent of the Itinerary Panel)
# ---------------------------------------------------------------------------
def test_pdf_rendering() -> bool:
    print("\nT-6.1 — Itinerary Document Rendering")
    from pypdf import PdfReader
    from pdf_generator import build_itinerary_pdf

    itinerary = _build_fixture_itinerary()
    ctx = {"num_days": 2, "pace": "moderate", "interests": ["history", "food"], "group_size": 2}

    stream = build_itinerary_pdf(itinerary, ctx)
    reader = PdfReader(stream)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    day_headings_present = all(f"Day {i}" in text for i in (1, 2))
    has_slot_headings = any(h in text for h in ("Morning", "Afternoon", "Evening"))
    non_empty = len(text.strip()) > 200

    _result("valid, re-openable .pdf produced", non_empty)
    _result("all days present as headings", day_headings_present)
    _result("time-slot headings present", has_slot_headings)
    return non_empty and day_headings_present and has_slot_headings


# ---------------------------------------------------------------------------
# T-6.3  Sources Panel population (citation formatting)
# ---------------------------------------------------------------------------
def test_sources_population() -> bool:
    print("\nT-6.3 — Sources Panel Population")
    from pypdf import PdfReader
    from pdf_generator import build_itinerary_pdf

    itinerary = _build_fixture_itinerary()
    citations = [
        {"source_title": "Humayun's Tomb", "source_url": "https://en.wikipedia.org/wiki/Humayun%27s_Tomb"},
        {"source_title": "Delhi/Old Delhi", "source_url": "https://en.wikivoyage.org/wiki/Delhi/Old_Delhi"},
    ]
    stream = build_itinerary_pdf(itinerary, {"num_days": 2, "pace": "moderate"}, citations=citations)
    reader = PdfReader(stream)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    all_present = all(c["source_title"] in text and c["source_url"] in text for c in citations)
    has_sources_heading = "Sources" in text

    _result("Sources heading present", has_sources_heading)
    _result("every citation's title and URL appear", all_present)
    return has_sources_heading and all_present


# ---------------------------------------------------------------------------
# T-6.4  Delivery: document generation + graceful email fallback
# ---------------------------------------------------------------------------
def test_delivery_fallback() -> bool:
    print("\nT-6.4 — Delivery: Document Generation + Email Fallback")
    from delivery import deliver_itinerary

    itinerary = _build_fixture_itinerary()
    ctx = {"num_days": 2, "pace": "moderate", "interests": ["history"], "group_size": 1}

    result = deliver_itinerary(itinerary, ctx, "traveler@example.com")

    file_saved = bool(result["file_path"]) and os.path.exists(result["file_path"])
    has_bytes = bool(result["file_bytes"])

    if os.environ.get("SMTP_HOST"):
        # Real SMTP configured — whatever happens is a live network result, not ours to assert on.
        _result("document generated (SMTP configured — live send attempted)", file_saved and has_bytes, result["message"])
        return file_saved and has_bytes

    graceful_fallback = (
        result["emailed"] is False
        and "download it below" in result["message"]
        and "SMTP" not in result["message"]  # QA-4/R-5: no internal config details leaked to the user
    )
    _result("document saved locally", file_saved, result["file_path"])
    _result("email gracefully skipped (SMTP not configured)", graceful_fallback, result["message"])
    return file_saved and has_bytes and graceful_fallback


# ---------------------------------------------------------------------------
# T-6.5  Email validation before sending
# ---------------------------------------------------------------------------
def test_email_validation() -> bool:
    print("\nT-6.5 — Email Validation")
    from delivery import is_valid_email

    cases = {
        "user@example.com": True,
        "first.last@sub.domain.co.in": True,
        "not-an-email": False,
        "missing@domain": False,
        "": False,
        "@nodomain.com": False,
    }
    all_ok = True
    for email, expected in cases.items():
        got = is_valid_email(email)
        ok = got == expected
        _result(f'"{email}"', ok, f"expected={expected}, got={got}")
        if not ok:
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# T-6.7  Microphone unavailable fallback
# ---------------------------------------------------------------------------
def test_mic_fallback() -> bool:
    print("\nT-6.7 — Microphone Unavailable Fallback")
    from voice_input import try_listen_via_mic

    def broken_factory():
        raise OSError("No Default Input Device Available (Errno -9996)")

    # R-18: return signature grew a 3rd element (possibly_truncated); this
    # branch (raw hardware exception) also must never leak the exception
    # text itself into the user-facing message (QA-12).
    text, error, truncated = try_listen_via_mic(stt_factory=broken_factory)
    no_crash_no_text = text == ""
    has_friendly_error = bool(error) and "text box" in error.lower()
    no_raw_exception_leaked = bool(error) and "-9996" not in error and "Errno" not in error
    not_truncated = truncated is False

    _result("returns empty transcript, does not raise", no_crash_no_text)
    _result("returns a friendly fallback message", has_friendly_error, error)
    _result("does not leak the raw exception text (QA-12)", no_raw_exception_leaked, error)
    _result("possibly_truncated is False on a hard failure", not_truncated)
    return no_crash_no_text and has_friendly_error and no_raw_exception_leaked and not_truncated


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all() -> dict[str, bool]:
    print("=" * 60)
    print("PHASE 6 VALIDATION TESTS")
    print("=" * 60)

    results = {
        "T-6.1 Itinerary Document Rendering": test_pdf_rendering(),
        "T-6.3 Sources Population":           test_sources_population(),
        "T-6.4 Delivery Fallback":            test_delivery_fallback(),
        "T-6.5 Email Validation":             test_email_validation(),
        "T-6.7 Mic Fallback":                 test_mic_fallback(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results.values())
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{passed}/{len(results)} tests passed")

    print(
        "\nNOT AUTOMATED (require a real browser session):\n"
        "  T-6.2 Mic button + live transcript — verify manually via `streamlit run app.py`\n"
        "  T-6.6 Mobile layout — verify manually by narrowing the browser window\n"
        "  T-6.8 Full end-to-end smoke test — verify manually (local URL, not yet deployed)"
    )
    return results


if __name__ == "__main__":
    run_all()
