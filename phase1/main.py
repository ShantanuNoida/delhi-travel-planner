"""
Phase 1 pipeline orchestrator.

Runs in order:
  1. Scrape Wikivoyage + Wikipedia articles
  2. Load delhi_tourist_venues_kb.md venue write-ups (merged into the same RAG corpus)
  3. Chunk articles (sentence-aware, overlapping)
  4. Embed chunks + store in ChromaDB + build citation index
  5. Fetch New Delhi POIs from Overpass API
  6. Enrich POIs with Wikidata (CC0 — website/image/QID where matched)
  7. Enrich POIs with delhi_tourist_venues_kb.md (entry fee/visit duration/best time where matched)
  8. Run validation tests

Usage:
  python main.py                 # full pipeline
  python main.py --skip-scrape   # skip scraping (use existing articles.json)
  python main.py --skip-pois     # skip Overpass POI fetch (and Wikidata/venues-KB POI enrichment)
  python main.py --skip-wikidata # skip Wikidata enrichment only
  python main.py --skip-venues-kb # skip delhi_tourist_venues_kb.md ingestion (RAG + POI enrichment)
  python main.py --validate-only # run tests only
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Phase 1 pipeline")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip scraping, use existing articles.json")
    parser.add_argument("--skip-pois", action="store_true", help="Skip Overpass POI fetch, keep existing pois.json")
    parser.add_argument("--skip-wikidata", action="store_true", help="Skip Wikidata enrichment step")
    parser.add_argument("--skip-venues-kb", action="store_true", help="Skip delhi_tourist_venues_kb.md ingestion (RAG + POI enrichment)")
    parser.add_argument("--validate-only", action="store_true", help="Run validation tests only")
    args = parser.parse_args()

    if args.validate_only:
        from validate import run_all
        run_all()
        return

    # Step 1 — Scrape
    if not args.skip_scrape:
        print("\n[Step 1/8] Scraping Wikivoyage + Wikipedia...")
        from scraper import run as scrape
        articles = scrape()
    else:
        import json
        data_dir = os.path.join(os.path.dirname(__file__), "data", "raw")
        with open(os.path.join(data_dir, "articles.json"), encoding="utf-8") as f:
            articles = json.load(f)
        print(f"[Step 1/8] Skipped scraping — loaded {len(articles)} existing articles.")

    # Step 2 — Venues KB articles (merged into the same RAG corpus as scraped articles,
    # so explain() can retrieve and cite this source exactly like Wikivoyage/Wikipedia)
    if not args.skip_venues_kb:
        print("\n[Step 2/8] Loading delhi_tourist_venues_kb.md for RAG ingestion...")
        import datetime
        from venues_kb_loader import parse_venues, venues_to_articles

        venues = parse_venues()
        kb_articles = venues_to_articles(venues, datetime.date.today().isoformat())
        articles = articles + kb_articles
        print(f"  Parsed {len(venues)} venues -> added {len(kb_articles)} articles to the RAG corpus.")
    else:
        print("[Step 2/8] Skipped venues KB RAG ingestion.")

    # Step 3 — Chunk
    print("\n[Step 3/8] Chunking articles...")
    from chunker import run as chunk
    chunks = chunk(articles)

    # Step 4 — Embed + citation index
    print("\n[Step 4/8] Embedding chunks + building citation index...")
    from embedder import run as embed
    embed(chunks)

    # Step 5 — POIs
    if not args.skip_pois:
        print("\n[Step 5/8] Fetching POIs from Overpass API...")
        from overpass_client import run as fetch_pois
        fetch_pois()
    else:
        import json
        pois_path = os.path.join(os.path.dirname(__file__), "data", "pois.json")
        with open(pois_path, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"[Step 5/8] Skipped Overpass fetch — kept {len(existing)} existing POIs.")

    # Step 6 — Wikidata enrichment
    if not args.skip_pois and not args.skip_wikidata:
        print("\n[Step 6/8] Enriching POIs with Wikidata (CC0)...")
        from wikidata_client import run as enrich_wikidata
        enrich_wikidata()
    else:
        print("[Step 6/8] Skipped Wikidata enrichment.")

    # Step 7 — Venues KB POI enrichment (entry fee / visit duration / best time,
    # for the subset of venues that confidently match an existing OSM POI)
    if not args.skip_pois and not args.skip_venues_kb:
        print("\n[Step 7/8] Enriching POIs with delhi_tourist_venues_kb.md...")
        from venues_kb_enrich import run as enrich_venues_kb
        enrich_venues_kb()
    else:
        print("[Step 7/8] Skipped venues KB POI enrichment.")

    # Step 8 — Validate
    print("\n[Step 8/8 — Validation] Running Phase 1 tests...")
    from validate import run_all
    run_all()


if __name__ == "__main__":
    main()
