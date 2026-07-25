"""
Tool 3 (Bonus): Travel Time Estimator MCP
Heuristic travel time between two coordinate pairs in Delhi.
No external API — pure geometry + Delhi traffic model.
"""

import math
from mcp.server.fastmcp import FastMCP

# Delhi metro lines run at ~35 km/h effective speed (incl. station time)
# Auto-rickshaws and cars average ~15 km/h in Delhi traffic
# Walking: ~5 km/h

ROAD_FACTOR = 1.4          # road distance vs straight-line distance in Delhi
CAR_SPEED_KMH = 15.0
METRO_SPEED_KMH = 35.0
WALK_SPEED_KMH = 5.0
METRO_OVERHEAD_MIN = 10    # station access + wait time


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def travel_time_logic(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict:
    straight_km = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
    road_km = straight_km * ROAD_FACTOR

    if road_km < 1.5:
        mode = "walk"
        minutes = int((road_km / WALK_SPEED_KMH) * 60)
    elif road_km < 4.0:
        mode = "auto"
        minutes = int((road_km / CAR_SPEED_KMH) * 60)
    else:
        # Compare auto vs metro and pick the faster one
        auto_min = int((road_km / CAR_SPEED_KMH) * 60)
        metro_min = int((road_km / METRO_SPEED_KMH) * 60) + METRO_OVERHEAD_MIN
        if metro_min < auto_min:
            mode = "metro"
            minutes = metro_min
        else:
            mode = "auto"
            minutes = auto_min

    return {
        "estimated_minutes": max(minutes, 5),
        "distance_km": round(road_km, 2),
        "mode": mode,
    }


mcp = FastMCP("travel-time-estimator")


@mcp.tool()
def travel_time_estimator(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> dict:
    """
    Estimate travel time between two coordinates in Delhi.
    Returns estimated minutes, road distance, and suggested transport mode.
    """
    return travel_time_logic(origin_lat, origin_lon, dest_lat, dest_lon)


if __name__ == "__main__":
    mcp.run()
