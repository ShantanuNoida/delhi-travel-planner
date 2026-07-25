"""
Queries the Overpass API for New Delhi POIs and saves a normalized dataset.

Implements:
- EC-1.2: minimum result threshold with bounding-box widening retry
- EC-1.5: exponential backoff on rate limit / timeout
- POI alias normalization for common Hindi/English spelling variants (EC-1.4)
"""

import json
import os
import time
import requests
from tqdm import tqdm

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POIS_PATH = os.path.join(DATA_DIR, "pois.json")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "User-Agent": "DelhiTravelPlanner/1.0 (educational project; generative-ai-course)",
}

# New Delhi bounding box (south, west, north, east)
DELHI_BBOX = (28.40, 76.80, 28.95, 77.40)

MIN_RESULTS_PER_CATEGORY = 5

# Overpass queries per category.
# NOTE: large landmarks (Red Fort, Humayun's Tomb, India Gate, Jama Masjid,
# Lotus Temple, ...) are frequently mapped as `way` or `relation` polygons in
# OSM, not `node` points. A node-only query silently misses them entirely —
# discovered while cross-referencing against Wikidata (delhi-additional-data-sources.md)
# and confirmed directly against the live Overpass API. way/relation variants
# added to every category where a large complex is plausible.
CATEGORY_QUERIES = {
    "monument": (
        'node["tourism"="attraction"]{bbox};way["tourism"="attraction"]{bbox};relation["tourism"="attraction"]{bbox};'
        'node["historic"="monument"]{bbox};way["historic"="monument"]{bbox};relation["historic"="monument"]{bbox};'
    ),
    "museum": 'node["tourism"="museum"]{bbox};way["tourism"="museum"]{bbox};',
    "restaurant": 'node["amenity"="restaurant"]{bbox};',
    "park": 'node["leisure"="park"]{bbox};way["leisure"="park"]{bbox};',
    "market": 'node["amenity"="marketplace"]{bbox};way["amenity"="marketplace"]{bbox};node["shop"="mall"]{bbox};way["shop"="mall"]{bbox};',
    "temple": 'node["amenity"="place_of_worship"]["religion"="hindu"]{bbox};way["amenity"="place_of_worship"]["religion"="hindu"]{bbox};',
    "mosque": 'node["amenity"="place_of_worship"]["religion"="muslim"]{bbox};way["amenity"="place_of_worship"]["religion"="muslim"]{bbox};',
    "church": 'node["amenity"="place_of_worship"]["religion"="christian"]{bbox};way["amenity"="place_of_worship"]["religion"="christian"]{bbox};',
    "gurdwara": 'node["amenity"="place_of_worship"]["religion"="sikh"]{bbox};way["amenity"="place_of_worship"]["religion"="sikh"]{bbox};',
    "hospital": 'node["amenity"="hospital"]{bbox};way["amenity"="hospital"]{bbox};',
    "pharmacy": 'node["amenity"="pharmacy"]{bbox};',
    # Metro stations — supports nearest-station lookups (delhi-additional-data-sources.md,
    # OpenStreetMap section); a distance-based substitute for the OTD Delhi GTFS
    # integration, which requires portal registration we can't complete automatically.
    "metro_station": 'node["railway"="station"]["station"="subway"]{bbox};',
}

# EC-1.4: alias normalization — maps alternate spellings to canonical name
ALIASES = {
    "Humayun's Tomb": ["Humayun ka Makbara", "Humayun Tomb", "Humayun's Mausoleum"],
    "Qutab Minar": ["Qutb Minar", "Qutub Minar", "Kutab Minar"],
    "Jama Masjid": ["Jama Mosque", "Jami Masjid"],
    "Akshardham": ["Swaminarayan Akshardham"],
    "Chandni Chowk": ["Chandni Chawk"],
    "Raj Ghat": ["Rajghat"],
}

ALIAS_LOOKUP: dict[str, str] = {}
for canonical, variants in ALIASES.items():
    for v in variants:
        ALIAS_LOOKUP[v.lower()] = canonical


def _normalize_name(name: str) -> str:
    return ALIAS_LOOKUP.get(name.lower(), name)


def _build_query(category: str, bbox: tuple) -> str:
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    raw = CATEGORY_QUERIES[category].replace("{bbox}", f"({bbox_str})")
    # "center" is required for way/relation elements to get a lat/lon at all
    # (out body; alone omits it) — see _normalize_poi()'s center fallback.
    return f"[out:json][timeout:30];({raw});out body center;"


def _overpass_request(query: str, retries: int = 3) -> list[dict]:
    """Run an Overpass query with exponential backoff (EC-1.5)."""
    for attempt in range(retries):
        try:
            r = requests.post(
                OVERPASS_URL,
                data=f"data={requests.utils.quote(query)}",
                headers=OVERPASS_HEADERS,
                timeout=40,
            )
            if r.status_code == 429:
                wait = 5 * (2 ** attempt)
                print(f"  [rate limit] waiting {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("elements", [])
        except requests.exceptions.Timeout:
            wait = 5 * (2 ** attempt)
            print(f"  [timeout] retrying in {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"  [error] {e}")
            break
    return []


def _normalize_poi(element: dict, category: str) -> dict | None:
    tags = element.get("tags", {})
    name = tags.get("name:en") or tags.get("name") or ""
    if not name:
        return None

    lat = element.get("lat") or (element.get("center", {}).get("lat"))
    lon = element.get("lon") or (element.get("center", {}).get("lon"))
    if lat is None or lon is None:
        return None

    return {
        # OSM ids are only unique within their element type — a node and a
        # way can share the same numeric id — so prefix with the type to
        # avoid silently conflating two different real-world places now that
        # way/relation elements are queried alongside nodes.
        "osm_id": f"{element.get('type', 'node')}/{element.get('id', '')}",
        "name": _normalize_name(name),
        "category": category,
        "lat": lat,
        "lon": lon,
        "opening_hours": tags.get("opening_hours", "unknown"),
        # fee/wheelchair/website: real OSM tags (delhi-additional-data-sources.md),
        # not fabricated — "fee" is yes/no only, never an invented amount.
        "tags": {
            k: v for k, v in tags.items()
            if k in ("cuisine", "tourism", "historic", "religion", "wikidata", "fee", "wheelchair", "website")
        },
    }


def fetch_category(category: str, bbox: tuple = DELHI_BBOX) -> list[dict]:
    """Fetch POIs for one category; widens bbox if below minimum threshold (EC-1.2)."""
    query = _build_query(category, bbox)
    elements = _overpass_request(query)
    pois = [p for e in elements if (p := _normalize_poi(e, category)) is not None]

    # EC-1.2: widen bbox by 10% and retry once if below threshold
    if len(pois) < MIN_RESULTS_PER_CATEGORY:
        south, west, north, east = bbox
        wider = (south - 0.05, west - 0.05, north + 0.05, east + 0.05)
        print(f"  [warn] {category}: only {len(pois)} results, widening bbox and retrying...")
        query2 = _build_query(category, wider)
        elements2 = _overpass_request(query2)
        pois = [p for e in elements2 if (p := _normalize_poi(e, category)) is not None]

    return pois


def fetch_all_pois() -> list[dict]:
    all_pois: list[dict] = []
    seen_ids: set[str] = set()

    print("Querying Overpass API for New Delhi POIs...")
    for category in tqdm(CATEGORY_QUERIES.keys()):
        pois = fetch_category(category)
        for poi in pois:
            if poi["osm_id"] not in seen_ids:
                seen_ids.add(poi["osm_id"])
                all_pois.append(poi)
        print(f"  {category}: {len(pois)} POIs fetched")
        time.sleep(1)

    return all_pois


def save_pois(pois: list[dict]) -> str:
    with open(POIS_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(pois)} POIs → {POIS_PATH}")
    return POIS_PATH


def load_pois() -> list[dict]:
    with open(POIS_PATH, encoding="utf-8") as f:
        return json.load(f)


def run() -> list[dict]:
    pois = fetch_all_pois()
    if not pois:
        print("  [warn] Overpass returned 0 POIs — keeping existing pois.json unchanged.")
        return load_pois() if os.path.exists(POIS_PATH) else []
    save_pois(pois)
    return pois


if __name__ == "__main__":
    run()
