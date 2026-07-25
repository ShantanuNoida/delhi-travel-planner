"""
Scrapes Wikivoyage and Wikipedia articles for New Delhi.
Stores raw text as JSON with source URL and last-modified date attached (EC-1.1).
"""

import json
import os
import time
from datetime import datetime
import requests
from tqdm import tqdm

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)

WIKIVOYAGE_PAGES = [
    "New Delhi",
    "Delhi",
    "Old Delhi",
]

WIKIPEDIA_PAGES = [
    "Red Fort",
    "Qutab Minar",
    "Humayun's Tomb",
    "India Gate",
    "Lotus Temple",
    "Jama Masjid, Delhi",
    "Chandni Chowk",
    "Connaught Place, New Delhi",
    "Lodi Garden",
    "National Museum, New Delhi",
    "Hauz Khas, Delhi",
    "Akshardham, Delhi",
    "Raj Ghat",
    "Safdarjung's Tomb",
    "Rashtrapati Bhavan",
    "Dilli Haat",
    "Purana Qila",
    "Jantar Mantar, New Delhi",
    "Swaminarayan Akshardham (Delhi)",
    "Nizamuddin Dargah",
]


HEADERS = {
    "User-Agent": "DelhiTravelPlanner/1.0 (educational project; generative-ai-course)",
    "Accept": "application/json",
}


def _mediawiki_fetch(api_url: str, title: str, retries: int = 3) -> dict | None:
    """Fetch plain text + last-modified date from any MediaWiki API."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|revisions",
        "explaintext": True,
        "exsectionformat": "plain",
        "rvprop": "timestamp",
        "rvlimit": 1,
        "format": "json",
        "redirects": 1,
    }
    for attempt in range(retries):
        try:
            r = requests.get(api_url, params=params, timeout=15, headers=HEADERS)
            if r.status_code == 429:
                wait = 10 * (2 ** attempt)
                print(f"  [rate limit] '{title}' — waiting {wait}s before retry {attempt + 1}/{retries}...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            page = next(iter(pages.values()))
            if "missing" in page:
                return None
            text = page.get("extract", "").strip()
            if not text:
                return None
            timestamp = (
                page.get("revisions", [{}])[0].get("timestamp", "")
                if page.get("revisions")
                else ""
            )
            last_modified = timestamp[:10] if timestamp else datetime.utcnow().strftime("%Y-%m-%d")
            resolved_title = page.get("title", title)
            return {"title": resolved_title, "text": text, "last_modified": last_modified}
        except Exception as e:
            print(f"  [warn] failed to fetch '{title}': {e}")
            return None
    print(f"  [warn] gave up on '{title}' after {retries} retries")
    return None


def scrape_wikivoyage() -> list[dict]:
    """Fetch all Wikivoyage pages and return list of article dicts."""
    api = "https://en.wikivoyage.org/w/api.php"
    results = []
    print("Scraping Wikivoyage...")
    for page_title in tqdm(WIKIVOYAGE_PAGES):
        data = _mediawiki_fetch(api, page_title)
        if data:
            results.append(
                {
                    "source": "wikivoyage",
                    "title": data["title"],
                    "url": f"https://en.wikivoyage.org/wiki/{data['title'].replace(' ', '_')}",
                    "text": data["text"],
                    "last_modified": data["last_modified"],
                }
            )
        time.sleep(1.5)
    return results


def scrape_wikipedia() -> list[dict]:
    """Fetch all Wikipedia pages and return list of article dicts."""
    api = "https://en.wikipedia.org/w/api.php"
    results = []
    print("Scraping Wikipedia...")
    for page_title in tqdm(WIKIPEDIA_PAGES):
        data = _mediawiki_fetch(api, page_title)
        if data:
            results.append(
                {
                    "source": "wikipedia",
                    "title": data["title"],
                    "url": f"https://en.wikipedia.org/wiki/{data['title'].replace(' ', '_')}",
                    "text": data["text"],
                    "last_modified": data["last_modified"],
                }
            )
        time.sleep(1.5)
    return results


def save_articles(articles: list[dict]) -> str:
    # Deduplicate by resolved title (Wikipedia can redirect two titles to the same page)
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for a in articles:
        key = a["title"].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(a)
        else:
            print(f"  [dedup] skipping duplicate title: {a['title']!r}")
    out_path = os.path.join(DATA_DIR, "articles.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(unique)} articles ({len(articles) - len(unique)} dupes dropped) -> {out_path}")
    return out_path


def run() -> list[dict]:
    articles = scrape_wikivoyage() + scrape_wikipedia()
    save_articles(articles)
    return articles


if __name__ == "__main__":
    run()
