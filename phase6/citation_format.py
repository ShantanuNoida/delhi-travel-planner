"""Shared citation display formatting — used by app.py and docx_generator.py."""

SOURCE_DISPLAY_NAMES = {
    "wikivoyage": "Wikivoyage",
    "wikipedia": "Wikipedia",
    "delhi_tourist_venues_kb": "Delhi Tourist Venues KB",
}


def format_citation_label(citation: dict) -> str:
    """'Delhi/New Delhi' + source 'wikivoyage' -> 'Delhi/New Delhi (Wikivoyage)'."""
    title = citation.get("source_title", "?")
    source = citation.get("source", "")
    display_source = SOURCE_DISPLAY_NAMES.get(source, source.title() if source else "")
    return f"{title} ({display_source})" if display_source else title
