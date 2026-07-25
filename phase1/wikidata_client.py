"""
Wikidata enrichment for the Phase 1 POI dataset.

Wikidata is CC0 (public domain) — no attribution required, no registration,
no rate-limit friction. It gives us three things OSM often lacks: an
official website, a heritage-designation flag, and a canonical QID that
cross-links to Wikipedia/Wikivoyage.

Per delhi-additional-data-sources.md's integration order, Wikidata is the
first source layered on top of the existing OSM-based pois.json — it only
*enriches* existing POI records (adds wikidata_qid/website/heritage/image
where a confident match exists); it never invents or replaces a POI.
"""

import json
import math
import os
import time

import requests

from overpass_client import _normalize_name

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
POIS_PATH = os.path.join(DATA_DIR, "pois.json")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "DelhiTravelPlanner/1.0 (educational project; generative-ai-course)",
    "Accept": "application/sparql-results+json",
}

# delhi-additional-data-sources.md's suggested query walks the P131
# (located-in-admin-entity) chain up to NCT of Delhi (Q1353). Tested against
# this project's real data and found too narrow — it misses Humayun's Tomb,
# India Gate, Jama Masjid, Red Fort, Akshardham, and most other major
# landmarks, because their P131 chain doesn't reliably resolve to Q1353 in
# Wikidata's actual graph. Replaced the admin-hierarchy filter with a
# coordinate bounding box (same Delhi bbox as overpass_client.py) — far more
# robust since it doesn't depend on consistent administrative tagging — and
# broadened the "what counts as a POI" filter beyond tourist-attraction/
# heritage to also include museums, palaces, mosques, Hindu temples, and
# forts, since many real landmarks aren't classified as P1435 heritage sites
# or Q570116 tourist-attraction subclasses in Wikidata's ontology.
#
# R-38 (Itinerary-Coverage-Gap-Analysis.md, "Food / Nature / Shopping
# Popularity Gap", 2026-07-16): added park/garden (Q22698/Q1107656) and
# marketplace/bazaar (Q330284/Q219760) branches — restaurant/park/market
# previously had zero notability signal at all. Empirically tested each
# candidate QID against the live endpoint before adding it, same discipline
# as the landmark branches above: Q22698+Q1107656 return real, meaningful
# results (Lodhi Gardens, Deer Park, Buddha Jayanti Park, Roshanara Bagh,
# Coronation Park — several not already on any hand-curated list, e.g.
# Roshanara Bagh). Markets are messier in Wikidata's own ontology — Khan
# Market is typed "neighbourhood", Chandni Chowk is "area", Dilli Haat is
# "bazaar" (not "marketplace") — confirmed by querying their actual P31
# values directly rather than guessing; Q330284+Q219760 together still find
# real value (Urdu Bazar, sitelinks=8, not on any existing list) without
# the false-positive risk of broadening to generic "neighbourhood"/"area"
# types, which would pull in irrelevant residential areas across all of
# Delhi. Restaurant coverage (Q11707) was tested too and found too thin to
# matter (2 results in the whole bbox, one already hand-curated) — not
# added, staying honest about what Wikidata actually has rather than
# padding the query with an empty branch.
#
# Venue-Tourist-Importance-Scoring-Plan.md, Phase C (2026-07-23): the query
# had a mosque branch (Q32815) and a Hindu temple branch (Q1370598) but no
# equivalent for the app's other two religious categories, church and
# gurdwara — both structurally the most under-covered categories in the
# whole dataset (only 3/3 randomly-sampled temples in the plan's own audit
# had zero signal at all). Added church building (Q16970) and gurdwara
# (Q337986), and protected area (Q473972) for parks/nature (the other
# flagged category) — each empirically tested against the live endpoint
# first, same discipline as every branch above: church+gurdwara returned 40
# real results (Sacred Heart Cathedral sitelinks=15, St. James' Church
# sitelinks=11, Gurudwara Bangla Sahib sitelinks=22, Gurdwara Sis Ganj Sahib
# sitelinks=12, among others); protected area returned 4 (Asola Bhatti
# Wildlife Sanctuary, Sultanpur National Park sitelinks=17, Najafgarh drain
# bird sanctuary, Okhla Sanctuary) — smaller, but real and directly on-topic
# for the flagged park/nature gap, not padding.
DELHI_POI_QUERY = """
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
SELECT ?item ?itemLabel ?coord ?image ?website ?sitelinks WHERE {
  SERVICE wikibase:box {
    ?item wdt:P625 ?coord.
    bd:serviceParam wikibase:cornerWest "Point(76.80 28.40)"^^geo:wktLiteral.
    bd:serviceParam wikibase:cornerEast "Point(77.40 28.95)"^^geo:wktLiteral.
  }
  {
    { ?item wdt:P31/wdt:P279* wd:Q570116. }       # tourist attraction
    UNION { ?item wdt:P1435 ?heritage. }           # heritage designation
    UNION { ?item wdt:P31/wdt:P279* wd:Q33506. }   # museum
    UNION { ?item wdt:P31/wdt:P279* wd:Q16560. }   # palace
    UNION { ?item wdt:P31 wd:Q32815. }             # mosque
    UNION { ?item wdt:P31/wdt:P279* wd:Q1370598. } # Hindu temple
    UNION { ?item wdt:P31/wdt:P279* wd:Q23413. }   # castle/fort
    UNION { ?item wdt:P31/wdt:P279* wd:Q22698. }   # park (R-38)
    UNION { ?item wdt:P31/wdt:P279* wd:Q1107656. } # garden (R-38)
    UNION { ?item wdt:P31/wdt:P279* wd:Q330284. }  # marketplace (R-38)
    UNION { ?item wdt:P31/wdt:P279* wd:Q219760. }  # bazaar (R-38)
    UNION { ?item wdt:P31/wdt:P279* wd:Q16970. }   # church building (Phase C)
    UNION { ?item wdt:P31/wdt:P279* wd:Q337986. }  # gurdwara (Phase C)
    UNION { ?item wdt:P31/wdt:P279* wd:Q473972. }  # protected area (Phase C)
  }
  OPTIONAL { ?item wdt:P18 ?image. }
  OPTIONAL { ?item wdt:P856 ?website. }
  ?item wikibase:sitelinks ?sitelinks.
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

MATCH_DISTANCE_KM = 0.2  # ~200m — tight enough to avoid false-positive name matches
RETRIES = 3


def _parse_point(wkt: str) -> tuple[float, float] | None:
    """Wikidata coord literal is WKT 'Point(lon lat)' — note lon before lat."""
    if not wkt or not wkt.startswith("Point("):
        return None
    try:
        lon_str, lat_str = wkt[len("Point("):-1].split(" ")
        return float(lat_str), float(lon_str)
    except (ValueError, IndexError):
        return None


def _qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def fetch_delhi_wikidata_pois() -> list[dict]:
    """Runs the SPARQL extraction query and returns normalized records."""
    for attempt in range(RETRIES):
        try:
            resp = requests.get(
                SPARQL_ENDPOINT,
                params={"query": DELHI_POI_QUERY, "format": "json"},
                headers=HEADERS,
                timeout=90,
            )
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt == RETRIES - 1:
                print(f"  [warn] Wikidata SPARQL query failed after {RETRIES} attempts: {e}")
                return []
            wait = 5 * (2 ** attempt)
            print(f"  [retry] Wikidata query error ({e}), waiting {wait}s...")
            time.sleep(wait)

    bindings = resp.json().get("results", {}).get("bindings", [])
    records = []
    seen_qids = set()
    for b in bindings:
        qid = _qid_from_uri(b["item"]["value"])
        if qid in seen_qids:
            continue
        point = _parse_point(b.get("coord", {}).get("value", ""))
        if point is None:
            continue
        seen_qids.add(qid)
        sitelinks_raw = b.get("sitelinks", {}).get("value")
        records.append({
            "qid": qid,
            "name": b.get("itemLabel", {}).get("value", ""),
            "lat": point[0],
            "lon": point[1],
            "image": b.get("image", {}).get("value") or None,
            "website": b.get("website", {}).get("value") or None,
            # R-38: a real, article-count-based notability signal — how many
            # language Wikipedias have an article on this place. Used as a
            # ranking tier in phase2/poi_search.py for categories (park,
            # market) that otherwise have none at all.
            "sitelinks": int(sitelinks_raw) if sitelinks_raw is not None else 0,
        })
    return records


def enrich_pois_with_wikidata(pois: list[dict], wikidata_records: list[dict] | None = None) -> tuple[list[dict], int]:
    """
    Adds wikidata_qid/website/image to POIs with a confident match. A POI
    matches if its OSM `wikidata` tag already names a QID we fetched, or —
    for POIs without that tag — if a Wikidata record sits within
    MATCH_DISTANCE_KM and shares a case-insensitive name.

    Venue-Tourist-Importance-Scoring-Plan.md, Phase B: a real, confirmed gap
    -- 46 POIs carry a real OSM `wikidata` tag (a human mapper's own
    verified link) that neither of the two paths above ever matches, because
    the QID isn't present in this fetch's restrictive P31/P279 type-filtered
    result set (e.g. a church/gurdwara sub-type the SPARQL query's UNION
    branches don't enumerate). Those POIs fall through to a third path: the
    OSM tag is trusted directly, even with no fetched record to cross-check
    against, since the match itself (this exact place = this exact Wikidata
    entity) was already made by a human, not something this function is
    inferring. No website/image/sitelinks are added via this path -- those
    only ever come from an actual fetched record.

    Returns (enriched_pois, match_count). Never removes or invents a POI.
    """
    if wikidata_records is None:
        wikidata_records = fetch_delhi_wikidata_pois()

    # Phase B note: deliberately NOT early-returning when wikidata_records is
    # empty (a failed/skipped fetch) -- the raw-tag-trust fallback below
    # doesn't depend on a fetch having succeeded at all, unlike the two
    # fetch-dependent match paths above it.
    by_qid = {r["qid"]: r for r in wikidata_records}
    match_count = 0

    for poi in pois:
        tagged_qid = poi.get("tags", {}).get("wikidata")
        record = by_qid.get(tagged_qid) if tagged_qid else None

        if record is None and wikidata_records:
            # POI names in pois.json are already alias-normalized (e.g. OSM's
            # "Qutb Minar" -> canonical "Qutab Minar"); Wikidata labels are
            # not, so normalize its side too before comparing, or aliased
            # landmarks would silently never match.
            poi_name = poi.get("name", "").strip().lower()
            for r in wikidata_records:
                if _normalize_name(r["name"]).strip().lower() != poi_name:
                    continue
                if _haversine_km(poi["lat"], poi["lon"], r["lat"], r["lon"]) <= MATCH_DISTANCE_KM:
                    record = r
                    break

        if record is not None:
            poi["wikidata_qid"] = record["qid"]
            if record.get("website"):
                poi["website"] = record["website"]
            if record.get("image"):
                poi["image"] = record["image"]
            if record.get("sitelinks"):
                poi["wikidata_sitelinks"] = record["sitelinks"]
            match_count += 1
        elif tagged_qid and not poi.get("wikidata_qid"):
            # Phase B fallback (see docstring): the OSM tag itself is the match.
            poi["wikidata_qid"] = tagged_qid
            match_count += 1

    return pois, match_count


def run() -> list[dict]:
    """Loads pois.json, enriches in place, and saves it back."""
    if not os.path.exists(POIS_PATH):
        print(f"  [warn] {POIS_PATH} not found — run Overpass fetch first.")
        return []

    with open(POIS_PATH, encoding="utf-8") as f:
        pois = json.load(f)

    print("Querying Wikidata for Delhi POIs (CC0, no key required)...")
    wikidata_records = fetch_delhi_wikidata_pois()
    print(f"  Fetched {len(wikidata_records)} Wikidata entities in scope.")

    pois, match_count = enrich_pois_with_wikidata(pois, wikidata_records)
    print(f"  Matched {match_count}/{len(pois)} POIs to a Wikidata QID (website/image where available).")

    with open(POIS_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"  Saved enriched dataset -> {POIS_PATH}")
    return pois


if __name__ == "__main__":
    run()
