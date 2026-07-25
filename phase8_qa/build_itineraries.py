"""
Team Waypoint -- Round 3
Agent 1 (Itinerary Generator): builds the 20 real itineraries from the specs
in itinerary_specs.py, via the REAL app code (phase2/poi_search.py +
phase2/itinerary_builder.py) -- no mocked data. Saves each as
results/base_itinerary_NN.json so Agent 2 (edits) and Agent 3 (questions)
can each start from the same, unedited state.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
for sub in ("phase2",):
    sys.path.insert(0, os.path.join(_ROOT, sub))

from itinerary_specs import ITINERARY_SPECS, CITY  # noqa: E402
from poi_search import poi_search_logic  # noqa: E402
from itinerary_builder import itinerary_builder_logic  # noqa: E402

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def build_itinerary(spec: dict) -> dict:
    pois = poi_search_logic(CITY, spec["interests"], constraints={"pace": spec["pace"]}, top_n=30)
    return itinerary_builder_logic(pois, days=spec["days"], pace=spec["pace"])


def main():
    for spec in ITINERARY_SPECS:
        out_path = os.path.join(RESULTS_DIR, f"base_itinerary_{spec['id']:02d}.json")
        if os.path.exists(out_path):
            print(f"Skipping {spec['id']:02d} (already built)")
            continue
        itin = build_itinerary(spec)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"spec": spec, "itinerary": itin}, f, indent=2, ensure_ascii=False)
        day_summary = ", ".join(
            f"{k}={itin[k]['total_hours']}h" for k in sorted(itin, key=lambda k: int(k.split("_")[1]))
        )
        print(f"Built {spec['id']:02d}: {spec['label']} ({spec['days']}d/{spec['pace']}) -> {day_summary}")


if __name__ == "__main__":
    main()
