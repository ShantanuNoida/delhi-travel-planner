"""
Phase 1 test suite — runs tests T-1.1 through T-1.6.
Usage: python validate.py
"""

import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def _result(label: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return passed


# ---------------------------------------------------------------------------
# T-1.1  RAG Retrieval Quality
# ---------------------------------------------------------------------------
def test_rag_retrieval():
    print("\nT-1.1 — RAG Retrieval Quality")
    from embedder import query

    test_queries = [
        "safe areas in Delhi for tourists",
        "best street food in New Delhi",
        "what to avoid at night in Delhi",
        "historical monuments in Delhi",
        "markets for shopping in Delhi",
    ]

    all_passed = True
    for q in test_queries:
        hits = query(q, n_results=3)
        has_enough = len(hits) >= 3
        all_cited = all(h.get("source_url") and h.get("article_title") for h in hits)
        all_long = all(len(h["text"].split(".")) >= 2 for h in hits)
        ok = has_enough and all_cited and all_long
        _result(
            f'query: "{q[:45]}..."',
            ok,
            f"{len(hits)} hits, cited={all_cited}, min_sentences={all_long}",
        )
        if not ok:
            all_passed = False
    return all_passed


# ---------------------------------------------------------------------------
# T-1.2  Citation Index Completeness
# ---------------------------------------------------------------------------
def test_citation_index():
    print("\nT-1.2 — Citation Index Completeness")
    import chromadb

    chroma_dir = os.path.join(DATA_DIR, "chroma")
    citation_path = os.path.join(DATA_DIR, "citation_index.json")

    if not os.path.exists(citation_path):
        return _result("citation_index.json exists", False, "file not found")

    with open(citation_path, encoding="utf-8") as f:
        citation_index = json.load(f)

    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection("delhi_travel")
    all_ids = collection.get(include=[])["ids"]

    missing = [cid for cid in all_ids if cid not in citation_index]
    ok = len(missing) == 0
    _result(
        "all chunk IDs in citation index",
        ok,
        f"{len(all_ids)} chunks, {len(missing)} missing citations",
    )
    if missing:
        print(f"    missing: {missing[:5]}")
    return ok


# ---------------------------------------------------------------------------
# T-1.3  OSM POI Dataset Coverage
# ---------------------------------------------------------------------------
def test_poi_coverage():
    print("\nT-1.3 — OSM POI Dataset Coverage")
    pois_path = os.path.join(DATA_DIR, "pois.json")
    if not os.path.exists(pois_path):
        return _result("pois.json exists", False, "file not found")

    with open(pois_path, encoding="utf-8") as f:
        pois = json.load(f)

    required_categories = [
        "monument", "museum", "restaurant", "park",
        "market", "temple", "mosque", "church",
    ]
    required_fields = {"name", "lat", "lon", "osm_id", "category"}

    all_passed = True
    by_category: dict[str, int] = {}
    for p in pois:
        by_category[p.get("category", "?")] = by_category.get(p.get("category", "?"), 0) + 1

    for cat in required_categories:
        count = by_category.get(cat, 0)
        ok = count >= 10
        _result(f"category '{cat}'", ok, f"{count} POIs")
        if not ok:
            all_passed = False

    # field completeness
    missing_fields = [
        p["name"] for p in pois
        if not required_fields.issubset(p.keys()) or not p.get("name")
    ]
    fields_ok = len(missing_fields) == 0
    _result("all POIs have required fields", fields_ok, f"{len(missing_fields)} incomplete")
    return all_passed and fields_ok


# ---------------------------------------------------------------------------
# T-1.4  Opening Hours Handling
# ---------------------------------------------------------------------------
def test_opening_hours():
    print("\nT-1.4 — Opening Hours Handling")
    pois_path = os.path.join(DATA_DIR, "pois.json")
    with open(pois_path, encoding="utf-8") as f:
        pois = json.load(f)

    no_hours = [p for p in pois if p.get("opening_hours") == "unknown"]
    missing_field = [p for p in pois if "opening_hours" not in p]
    none_dropped = len(missing_field) == 0
    unknown_flagged = all(p.get("opening_hours") is not None for p in pois)

    _result(
        "no POI silently dropped for missing opening_hours",
        none_dropped,
        f"{len(missing_field)} missing field entirely",
    )
    _result(
        "unknown opening_hours flagged (not None)",
        unknown_flagged,
        f"{len(no_hours)} POIs with opening_hours='unknown'",
    )
    return none_dropped and unknown_flagged


# ---------------------------------------------------------------------------
# T-1.5  Chunk Quality Check
# ---------------------------------------------------------------------------
def test_chunk_quality():
    print("\nT-1.5 — Chunk Quality Check")
    chunks_path = os.path.join(DATA_DIR, "chunks.json")
    if not os.path.exists(chunks_path):
        return _result("chunks.json exists", False, "file not found")

    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    import random
    sample = random.sample(chunks, min(50, len(chunks)))

    conjunction_starts = {"but", "however", "and", "or", "nor", "yet", "so",
                          "although", "though", "because", "since", "while", "whereas"}
    bad_start = [
        c["chunk_id"] for c in sample
        if c["text"].strip().split()[0].lower().rstrip(",") in conjunction_starts
    ]
    too_short = [c["chunk_id"] for c in sample if len(c["text"].split(".")) < 2]
    mid_word = [c["chunk_id"] for c in sample if c["text"].strip() and c["text"].strip()[-1].isalpha() and len(c["text"]) < 20]

    _result("no chunks start with conjunction", len(bad_start) == 0, f"{len(bad_start)} bad starts in sample")
    _result("all chunks ≥ 2 sentences", len(too_short) == 0, f"{len(too_short)} too short in sample")
    print(f"    Total chunks: {len(chunks)}, sample size: {len(sample)}")
    return len(bad_start) == 0 and len(too_short) == 0


# ---------------------------------------------------------------------------
# T-1.6  Multilingual Name Retrieval (Alias Normalization)
# ---------------------------------------------------------------------------
def test_multilingual_aliases():
    print("\nT-1.6 — Multilingual Name Retrieval")
    from embedder import query

    alias_pairs = [
        ("Humayun ka Makbara", "Humayun's Tomb"),
        ("Qutub Minar", "Qutab Minar"),
        ("Jama Mosque", "Jama Masjid"),
    ]

    all_passed = True
    for hindi_query, english_query in alias_pairs:
        hindi_hits = {h["article_title"] for h in query(hindi_query, n_results=3)}
        english_hits = {h["article_title"] for h in query(english_query, n_results=3)}
        overlap = hindi_hits & english_hits
        ok = len(overlap) >= 1
        _result(
            f'"{hindi_query}" ↔ "{english_query}"',
            ok,
            f"overlap={len(overlap)} shared articles",
        )
        if not ok:
            all_passed = False
    return all_passed


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all():
    print("=" * 60)
    print("PHASE 1 VALIDATION TESTS")
    print("=" * 60)

    results = {
        "T-1.1 RAG Retrieval Quality": test_rag_retrieval(),
        "T-1.2 Citation Index": test_citation_index(),
        "T-1.3 POI Coverage": test_poi_coverage(),
        "T-1.4 Opening Hours": test_opening_hours(),
        "T-1.5 Chunk Quality": test_chunk_quality(),
        "T-1.6 Multilingual Aliases": test_multilingual_aliases(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results.values())
    total = len(results)
    for name, ok in results.items():
        status = PASS if ok else FAIL
        print(f"  [{status}] {name}")
    print(f"\n{passed}/{total} tests passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_all()
