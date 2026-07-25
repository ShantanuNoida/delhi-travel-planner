# Golden Dataset — Links & References

Every external and internal source that backs the project's Golden Dataset (the 20 fixed reference itineraries and the data they're built from — see `Project Based AI-Evaluation-Rubric and Golden Dataset.md`'s "Golden Dataset" section for the composition table and the adversarial test suite run against it). All links below are real and were fetched/verified as part of building this dataset — nothing here is a placeholder.

---

## External sources

### Wikivoyage (3 articles scraped)

| Article | URL |
|---|---|
| Delhi | https://en.wikivoyage.org/wiki/Delhi |
| Delhi/New Delhi | https://en.wikivoyage.org/wiki/Delhi/New_Delhi |
| Delhi/Old Delhi | https://en.wikivoyage.org/wiki/Delhi/Old_Delhi |

### Wikipedia (11 articles scraped)

| Article | URL |
|---|---|
| Red Fort | https://en.wikipedia.org/wiki/Red_Fort |
| Humayun's Tomb | https://en.wikipedia.org/wiki/Humayun's_tomb |
| Qutb Minar | https://en.wikipedia.org/wiki/Qutb_Minar |
| India Gate | https://en.wikipedia.org/wiki/India_Gate |
| Jama Masjid, Delhi | https://en.wikipedia.org/wiki/Jama_Masjid,_Delhi |
| Lotus Temple | https://en.wikipedia.org/wiki/Lotus_Temple |
| Swaminarayan Akshardham (Delhi) | https://en.wikipedia.org/wiki/Swaminarayan_Akshardham_(Delhi) |
| Chandni Chowk | https://en.wikipedia.org/wiki/Chandni_Chowk |
| Jantar Mantar, New Delhi | https://en.wikipedia.org/wiki/Jantar_Mantar,_New_Delhi |
| Purana Qila | https://en.wikipedia.org/wiki/Purana_Qila |
| Hazrat Nizamuddin Dargah | https://en.wikipedia.org/wiki/Hazrat_Nizamuddin_Dargah |

These 14 articles (3 Wikivoyage + 11 Wikipedia) are chunked and embedded into the RAG corpus that `explain_engine.py` retrieves from — every citation the app ever attaches traces back to one of these two source sets or the venues KB below.

### OpenStreetMap (primary POI ground truth)

| Source | Endpoint / URL |
|---|---|
| Overpass API (query endpoint used to pull all 5,078 POIs) | https://overpass-api.de/api/interpreter |
| OpenStreetMap copyright/attribution | https://www.openstreetmap.org/copyright |

Every schedulable stop in the app resolves to a real OSM node/way via its `osm_id` — restaurants, markets, monuments, museums, temples, mosques, churches, gurdwaras, parks, hospitals, pharmacies, and metro stations.

### Wikidata (enrichment layer)

SPARQL endpoint queried for supplementary metadata (website, image, QID) on top of the OSM extract: https://query.wikidata.org/sparql

Sample real entries (same landmarks as the Wikipedia list above, cross-linked to their Wikidata items):

| Venue | Wikidata URL |
|---|---|
| Red Fort | https://www.wikidata.org/wiki/Q45957 |
| India Gate | https://www.wikidata.org/wiki/Q245347 |
| Humayun's Tomb | https://www.wikidata.org/wiki/Q189648 |
| Qutb Minar (Jama Masjid area) | https://www.wikidata.org/wiki/Q233678 |
| Lotus Temple | https://www.wikidata.org/wiki/Q940843 |
| Swaminarayan Akshardham | https://www.wikidata.org/wiki/Q1849858 |
| Chandni Chowk | https://www.wikidata.org/wiki/Q3236763 |

CC0-licensed — safe to reuse without attribution requirements, unlike the Wikipedia/Wikivoyage text (CC BY-SA).

---

## Internal repository references

Everything below lives in this repo and is generated from the external sources above — no external link exists for these, they're the project's own processed output.

| Reference | Path | What it is |
|---|---|---|
| Full POI dataset | `phase1/data/pois.json` | 5,078 POIs pulled from the Overpass API, the grounding key (`osm_id`) every scheduled stop must resolve to |
| Citation index | `phase1/data/citation_index.json` | 197 entries (147 Wikipedia/Wikivoyage + 50 venues-KB) — every citation the app attaches is checked against this for authenticity |
| Vector store | `phase1/data/chroma/` | ChromaDB corpus of the same 197 chunks, embedded via `paraphrase-multilingual-MiniLM-L12-v2` |
| Hand-curated venue KB | `delhi_tourist_venues_kb.md` | 50 venues with entry fee / best time to visit / suitability — enriches matching POIs with `kb_*` fields and is itself a citable RAG source |
| Golden itinerary set (edit QA) | `phase7_qa/results/itinerary_01.json` … `itinerary_20.json` | The 20 fixed reference itineraries, real app output, reused unmodified across every QA round |
| Golden itinerary set (question QA) | `phase7_qa/results/phase2_itinerary_01.json` … `phase2_itinerary_20.json` | The same 20 itineraries' question/explain QA transcripts |
| Post-fix recheck log | `phase7_qa/results/_recheck_log.json` | Fresh, differently-phrased re-verification of every prior fix against the same golden set |
| Full QA findings | `Itinerary edit commands QA.md` | Complete write-up — severity, root cause, evidence, fix, verification — for every finding across both QA phases |
| Sample fixture for Phase 5 | `phase5/sample_itinerary.json` | Standalone 2-day fixture used by Phase 5's own CLI eval runs |

---

*Compiled from the real, live data pipeline (`phase1/data/pois.json`, `phase1/data/citation_index.json`) and this project's own scraping/enrichment scripts (`phase1/scraper.py`, `phase1/overpass_client.py`, `phase1/wikidata_client.py`) — every link above was verified present in the actual dataset, not reconstructed from memory.*
