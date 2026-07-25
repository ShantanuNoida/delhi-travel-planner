# New Delhi Tourism — Top 3 Open Data Sources

> Reference/training supplement for the 2–3 day Delhi itinerary application.
> Base corpus: Wikivoyage Delhi (https://en.wikivoyage.org/wiki/Delhi, CC BY-SA 4.0).
> Scope: the three highest-priority integration sources only.
> Compiled: 2026-07-11. Re-verify licenses and endpoints before each ingestion cycle.

---

## 1. Wikidata

| Field | Detail |
|-------|--------|
| URL | https://www.wikidata.org |
| Coverage | Structured Delhi POI entities: coordinates, opening hours, official websites, heritage status, images, cross-links to Wikipedia/Wikivoyage |
| License | **CC0 (public domain)** — any use incl. commercial and ML training; no attribution required |
| Update frequency | Continuous (live API/SPARQL) |
| Itinerary value | Canonical machine-readable POI spine with zero license friction; QIDs make every other source joinable |

### Endpoints

- **SPARQL endpoint:** `https://query.wikidata.org/sparql`
- **Interactive UI:** `https://query.wikidata.org`
- **Single entity JSON:** `https://www.wikidata.org/wiki/Special:EntityData/{QID}.json` (e.g., Humayun's Tomb = `Q201705`)
- **Key QIDs:** NCT of Delhi = `Q1353` · New Delhi = `Q987`

### Extraction query — Delhi tourist POIs

```sparql
SELECT ?item ?itemLabel ?coord ?image ?website WHERE {
  ?item wdt:P131* wd:Q1353;          # located in NCT of Delhi (recursive)
        wdt:P625 ?coord.             # has coordinates
  { ?item wdt:P31/wdt:P279* wd:Q570116. }    # tourist attraction
  UNION
  { ?item wdt:P1435 ?heritage. }             # heritage designation (ASI etc.)
  OPTIONAL { ?item wdt:P18 ?image. }
  OPTIONAL { ?item wdt:P856 ?website. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

Programmatic call: `https://query.wikidata.org/sparql?format=json&query=<URL-encoded-query>`

---

## 2. OpenStreetMap

| Field | Detail |
|-------|--------|
| URL | https://www.openstreetmap.org |
| Coverage | All mapped Delhi POIs: monuments, restaurants, hotels, metro stations; tags: `opening_hours`, `fee`, `wheelchair`; full geometry for routing |
| License | **ODbL 1.0** — free for any purpose incl. commercial; **requires attribution + share-alike on derivative databases**; rendered itineraries (Produced Works) may be licensed freely |
| Update frequency | Continuous; extracts rebuilt daily |
| Itinerary value | Densest structured data for walkability, nearest-metro lookups, and routing between stops |

### Endpoints

- **Overpass API:** `https://overpass-api.de/api/interpreter` (POST query as `data` parameter)
- **Test UI:** `https://overpass-turbo.eu`
- **Delhi bounding box (S,W,N,E):** `28.40, 76.84, 28.90, 77.35`

### Extraction query — tourism POIs, monuments, metro stations

```
[out:json][timeout:120];
area["name"="Delhi"]["admin_level"="4"]->.delhi;
(
  nwr["tourism"~"attraction|museum|gallery|viewpoint"](area.delhi);
  nwr["historic"~"monument|fort|tomb|memorial|castle"](area.delhi);
  nwr["railway"="station"]["station"="subway"](area.delhi);
);
out center tags;
```

### Bulk extracts (.pbf)

- India extract: `https://download.geofabrik.de/asia/india-latest.osm.pbf`
  - Clip to Delhi: `osmium extract -b 76.84,28.40,77.35,28.90 india-latest.osm.pbf -o delhi.osm.pbf`
- Pre-clipped city extract: `https://extract.bbbike.org`

---

## 3. Open Transit Data Delhi (GTFS)

| Field | Detail |
|-------|--------|
| URL | https://otd.delhi.gov.in |
| Coverage | GTFS static (DMRC metro + DTC/cluster buses): routes, stops, stop_times, frequencies; GTFS-RT realtime bus positions |
| License | Free with registration/API key; published for third-party developers under portal T&C (not GODL — review before ingest) |
| Update frequency | Metro static last refreshed Aug 2023; bus realtime is live |
| Itinerary value | Travel-time realism — sequence sights by actual transit time/cost instead of straight-line distance |

### Endpoints

- **Registration / API key:** `https://otd.delhi.gov.in` → "Get API Key" (free)
- **Static GTFS, DMRC metro:** `https://otd.delhi.gov.in/data/staticDMRC/` (routes.txt, stops.txt, stop_times.txt, frequencies.txt)
- **Static GTFS, buses (DTC/cluster):** `https://otd.delhi.gov.in/data/static/`
- **Realtime bus positions (GTFS-RT protobuf):** `https://otd.delhi.gov.in/api/realtime/VehiclePositions.pb?key=YOUR_API_KEY`

### Known data caveat

DMRC static files were last refreshed Aug 2023; metro fares were revised Aug 2025 (₹11–₹64 slabs; Airport Express ₹11–₹75; smart card 10% discount). **Do not trust `fare_attributes.txt`** — validate fares against https://delhimetrorail.com.

---

## Integration Order

1. **Wikidata first** — CC0 spine; resolve every Wikivoyage listing to a QID carrying coordinates, hours, images, and cross-links.
2. **OpenStreetMap second** — walking distances, nearest-metro lookups, dense supporting POIs. Implement ODbL attribution and decide early whether the merged POI database triggers share-alike.
3. **OTD Delhi GTFS third** — join `stops.txt` station coordinates against Wikidata/OSM POIs to compute nearest-metro-station per attraction and realistic inter-sight travel times.

---

## Compliance Rules (pipeline)

1. **Corpus separation:** keep ODbL data (OSM) separable from CC0 (Wikidata) and OTD-licensed (GTFS) records so share-alike obligations remain traceable.
2. **Attribution manifest:** "© OpenStreetMap contributors, ODbL" for OSM-derived data; no attribution required for Wikidata (CC0); follow OTD portal T&C for GTFS.
3. **API etiquette:** send a descriptive `User-Agent`; batch Overpass queries; cache SPARQL results; poll only the GTFS-RT feed at high frequency.
4. **Re-verification cadence:** re-check OTD T&C quarterly; refresh metro fares before each model/data release.
