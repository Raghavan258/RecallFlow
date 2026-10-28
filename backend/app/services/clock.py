"""Clock injection point and UTC normalization for stored timestamps."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Convert a provided timestamp to UTC. Missing values stay missing.

    Naive values are treated as UTC. Aware values keep the same instant, so a
    +05:30 offset is stored as the corresponding UTC clock time.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: datetime | None) -> str | None:
    """Serialize a timestamp as ISO-8601 UTC with a Z suffix, or None when absent."""
    normalized = ensure_utc(value)
    if normalized is None:
        return None
    return normalized.isoformat().replace("+00:00", "Z")
