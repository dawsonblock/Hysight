"""Centralized timestamp generation and parsing."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Convert a datetime to an ISO 8601 string in UTC."""
    return ensure_utc(dt).isoformat()


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 string into a timezone-aware UTC datetime.

    Naive timestamps are treated explicitly as UTC.
    """
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return ensure_utc(datetime.fromisoformat(normalized))
