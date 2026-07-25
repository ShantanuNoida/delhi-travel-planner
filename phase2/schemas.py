"""
Input/output JSON schemas for all Phase 2 MCP tools.
These are registered with the MCP server so the agent knows exactly
what each tool accepts and returns.
"""

POI_SEARCH_INPUT = {
    "type": "object",
    "properties": {
        "city": {"type": "string", "description": "City name. Must be 'New Delhi'."},
        "interests": {
            "type": "array",
            "items": {"type": "string"},
            "description": "User interests e.g. ['food', 'culture', 'history']",
        },
        "constraints": {
            "type": "object",
            "description": "Optional filters: travel_dates, pace, accessibility, dietary",
            "properties": {
                "travel_dates": {"type": "array", "items": {"type": "string"}, "description": "ISO date strings e.g. ['2024-12-20', '2024-12-21']"},
                "pace": {"type": "string", "enum": ["relaxed", "moderate", "intensive"]},
                "accessibility": {"type": "boolean"},
                "dietary": {"type": "string"},
            },
        },
        "top_n": {"type": "integer", "description": "Max POIs to return. Default 20.", "default": 20},
    },
    "required": ["city", "interests"],
}

POI_SEARCH_OUTPUT = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "osm_id": {"type": "string"},
            "name": {"type": "string"},
            "category": {"type": "string"},
            "lat": {"type": "number"},
            "lon": {"type": "number"},
            "opening_hours": {"type": "string"},
            "visit_duration_min": {"type": "integer", "description": "Estimated visit duration in minutes"},
            "relevance_score": {"type": "number", "description": "0.0–1.0"},
            "fallback": {"type": "boolean", "description": "True if returned via interest fallback (EC-2.1)"},
        },
    },
}

ITINERARY_BUILDER_INPUT = {
    "type": "object",
    "properties": {
        "pois": {
            "type": "array",
            "description": "POIs returned by POI Search MCP",
            "items": {"type": "object"},
        },
        "days": {"type": "integer", "description": "Number of trip days (1–4)"},
        "pace": {"type": "string", "enum": ["relaxed", "moderate", "intensive"]},
        "daily_hours": {"type": "number", "description": "Available hours per day. Overrides pace default if provided."},
        "travel_dates": {"type": "array", "items": {"type": "string"}, "description": "ISO date strings, one per day"},
    },
    "required": ["pois", "days", "pace"],
}

ITINERARY_BUILDER_OUTPUT = {
    "type": "object",
    "description": "day_1, day_2, ... each with morning/afternoon/evening slots",
    "additionalProperties": {
        "type": "object",
        "properties": {
            "morning":   {"type": "array", "items": {"type": "object"}},
            "afternoon": {"type": "array", "items": {"type": "object"}},
            "evening":   {"type": "array", "items": {"type": "object"}},
            "total_hours": {"type": "number"},
            "date": {"type": "string"},
        },
    },
}

TRAVEL_TIME_INPUT = {
    "type": "object",
    "properties": {
        "origin_lat":  {"type": "number"},
        "origin_lon":  {"type": "number"},
        "dest_lat":    {"type": "number"},
        "dest_lon":    {"type": "number"},
    },
    "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon"],
}

TRAVEL_TIME_OUTPUT = {
    "type": "object",
    "properties": {
        "estimated_minutes": {"type": "integer"},
        "distance_km":       {"type": "number"},
        "mode":              {"type": "string", "enum": ["walk", "auto", "metro"]},
    },
}

WEATHER_INPUT = {
    "type": "object",
    "properties": {
        "city":       {"type": "string"},
        "date_range": {"type": "array", "items": {"type": "string"}, "description": "ISO date strings"},
    },
    "required": ["city", "date_range"],
}

WEATHER_OUTPUT = {
    "type": "object",
    "properties": {
        "forecast": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date":             {"type": "string"},
                    "max_temp_c":       {"type": "number"},
                    "min_temp_c":       {"type": "number"},
                    "precipitation_mm": {"type": "number"},
                    "description":      {"type": "string"},
                    "outdoor_risk":     {"type": "boolean"},
                },
            },
        },
        "outdoor_risk_flag": {"type": "boolean", "description": "True if any day has outdoor risk"},
        "source": {"type": "string"},
    },
}
