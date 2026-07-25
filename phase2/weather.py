"""
Tool 4 (Bonus): Weather Adjustment MCP
Fetches forecasts from Open-Meteo (free, no API key required).
Flags outdoor-risk days: heavy rain, extreme heat, or cold.
"""

import requests
from mcp.server.fastmcp import FastMCP

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# New Delhi coordinates
DELHI_LAT = 28.6139
DELHI_LON = 77.2090

# Risk thresholds
RAIN_RISK_MM = 5.0
HEAT_RISK_C  = 40.0
COLD_RISK_C  = 10.0


def _wmo_description(code: int) -> str:
    """Map WMO weather interpretation code to human-readable string."""
    mapping = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    }
    return mapping.get(code, f"Weather code {code}")


def weather_logic(city: str, date_range: list[str]) -> dict:
    if not date_range:
        raise ValueError("date_range must contain at least one ISO date string.")

    start_date = min(date_range)
    end_date = max(date_range)

    params = {
        "latitude":         DELHI_LAT,
        "longitude":        DELHI_LON,
        "daily":            "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "start_date":       start_date,
        "end_date":         end_date,
        "timezone":         "Asia/Kolkata",
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("daily", {})
    except Exception as e:
        return {
            "forecast": [],
            "outdoor_risk_flag": False,
            "source": "open-meteo (unavailable)",
            "error": str(e),
        }

    dates       = data.get("time", [])
    max_temps   = data.get("temperature_2m_max", [])
    min_temps   = data.get("temperature_2m_min", [])
    precips     = data.get("precipitation_sum", [])
    codes       = data.get("weathercode", [])

    forecast = []
    any_risk = False

    for i, date in enumerate(dates):
        if date not in date_range:
            continue
        max_t  = max_temps[i] if i < len(max_temps) else None
        min_t  = min_temps[i] if i < len(min_temps) else None
        precip = precips[i]   if i < len(precips)   else 0.0
        code   = codes[i]     if i < len(codes)      else 0

        outdoor_risk = bool(
            (precip is not None and precip >= RAIN_RISK_MM)
            or (max_t  is not None and max_t  >= HEAT_RISK_C)
            or (min_t  is not None and min_t  <= COLD_RISK_C)
        )
        if outdoor_risk:
            any_risk = True

        forecast.append({
            "date":             date,
            "max_temp_c":       max_t,
            "min_temp_c":       min_t,
            "precipitation_mm": precip,
            "description":      _wmo_description(code),
            "outdoor_risk":     outdoor_risk,
        })

    return {
        "forecast":           forecast,
        "outdoor_risk_flag":  any_risk,
        "source":             "open-meteo.com",
    }


mcp = FastMCP("weather-adjustment")


@mcp.tool()
def weather_adjustment(city: str, date_range: list[str]) -> dict:
    """
    Fetch weather forecast for the trip dates in Delhi.
    Returns daily forecast and flags days with outdoor risk
    (heavy rain, extreme heat > 40°C, or cold < 10°C).
    """
    return weather_logic(city, date_range)


if __name__ == "__main__":
    mcp.run()
