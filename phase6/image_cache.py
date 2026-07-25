"""
Local image cache for POI photos (R-22, Itinerary-Quality-Review round 4
UX benchmark / QA-17). Wikidata's P18 images are Wikimedia Commons
Special:FilePath URLs, fetched fresh into `phase1/data/pois.json` by
`phase1/wikidata_client.py` but never previously rendered anywhere.

Downloaded once per URL and cached to disk rather than hotlinked directly
in `st.image(url)`: Streamlit reruns the whole script on every interaction,
so a hotlinked image would be re-requested from Commons on every rerun —
risking Commons' hotlink throttling on a live demo, and breaking outright
if the machine is offline. A local cache also survives across Streamlit
sessions, not just within one.

Never fabricates an image: a POI with no `image` field, or a failed
download for any reason (network, 404, throttling), just renders with no
photo — the caller checks for None and falls back to text-only display.
"""

import hashlib
import os

import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_cache")
_TIMEOUT_SEC = 5
# Wikimedia's own policy throttles/blocks requests with no identifying
# User-Agent — this is a real, documented requirement, not decoration.
_USER_AGENT = "DelhiTravelPlanner/1.0 (educational capstone project; contact via GitHub)"


def get_cached_image_path(url: str | None) -> str | None:
    """
    Downloads `url` to a local cache file (once) and returns the local file
    path, or None if `url` is falsy or the download fails for any reason.
    Safe to call every render — a second call for the same URL just hits
    the on-disk cache, no network round-trip.
    """
    if not url:
        return None

    os.makedirs(CACHE_DIR, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if not ext or len(ext) > 5:
        ext = ".jpg"  # Commons' Special:FilePath doesn't always carry a real extension
    cache_key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}{ext}")

    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return cache_path

    try:
        resp = requests.get(url, timeout=_TIMEOUT_SEC, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        with open(cache_path, "wb") as f:
            f.write(resp.content)
        return cache_path
    except Exception as e:
        print(f"  [image_cache] failed to fetch {url}: {e}")
        return None
