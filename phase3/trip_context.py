"""
TripContext — structured parameters collected during conversation.

Required fields: city, num_days, interests (at least one), pace
Optional fields: travel_dates, group_size, constraints
"""

from dataclasses import dataclass, field
from typing import Any

VALID_PACES = {"relaxed", "moderate", "intensive"}
DAILY_HOURS = {"relaxed": 6, "moderate": 8, "intensive": 10}
DEFAULT_PACE = "moderate"
DEFAULT_DAYS = 2
DEFAULT_GROUP = 1
DEFAULT_CITY = "New Delhi"


@dataclass
class TripContext:
    city: str = DEFAULT_CITY
    num_days: int | None = None
    travel_dates: str | None = None
    interests: list[str] = field(default_factory=list)
    pace: str | None = None
    group_size: int | None = None
    constraints: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Validation helpers

    def required_missing(self) -> list[str]:
        """Return list of required field names that are still unset."""
        missing = []
        if not self.num_days:
            missing.append("num_days")
        if not self.interests:
            missing.append("interests")
        if not self.pace:
            missing.append("pace")
        return missing

    def is_complete(self) -> bool:
        return len(self.required_missing()) == 0

    def fill_defaults(self) -> None:
        """Fill remaining required fields with sensible defaults."""
        if not self.num_days:
            self.num_days = DEFAULT_DAYS
        if not self.pace:
            self.pace = DEFAULT_PACE
        if not self.interests:
            self.interests = ["culture", "food"]
        if not self.group_size:
            self.group_size = DEFAULT_GROUP

    def daily_hours(self) -> int:
        return DAILY_HOURS.get(self.pace or DEFAULT_PACE, 8)

    # ------------------------------------------------------------------ #
    # Merging

    def merge(self, other: "TripContext") -> None:
        """Update fields from another TripContext, preserving existing non-None values."""
        if other.city and other.city != DEFAULT_CITY:
            self.city = other.city
        if other.num_days:
            self.num_days = other.num_days
        if other.travel_dates:
            self.travel_dates = other.travel_dates
        if other.interests:
            existing = set(self.interests)
            for i in other.interests:
                if i not in existing:
                    self.interests.append(i)
        if other.pace and other.pace in VALID_PACES:
            self.pace = other.pace
        if other.group_size:
            self.group_size = other.group_size
        if other.constraints:
            self.constraints.update(other.constraints)

    # ------------------------------------------------------------------ #
    # Display

    def summary(self) -> str:
        lines = [f"City: {self.city}"]
        if self.num_days:
            lines.append(f"Duration: {self.num_days} day{'s' if self.num_days > 1 else ''}")
        if self.travel_dates:
            lines.append(f"Dates: {self.travel_dates}")
        if self.interests:
            lines.append(f"Interests: {', '.join(self.interests)}")
        if self.pace:
            lines.append(f"Pace: {self.pace}")
        if self.group_size:
            lines.append(f"Group size: {self.group_size}")
        if self.constraints:
            lines.append(f"Constraints: {self.constraints}")
        # Markdown hard line break ("  \n", two trailing spaces) rather than
        # a bare "\n" — Streamlit's st.markdown() collapses single newlines
        # into a run-on line otherwise (UX-15/R-16). Invisible/harmless to
        # TTS, which just reads through whitespace, so spoken output is
        # unaffected — only the displayed transcript bubble is.
        return "  \n".join(lines)

    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "num_days": self.num_days,
            "travel_dates": self.travel_dates,
            "interests": self.interests,
            "pace": self.pace,
            "group_size": self.group_size,
            "constraints": self.constraints,
        }
