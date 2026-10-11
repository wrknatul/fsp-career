"""Time helpers: the codebase works with aware UTC datetimes only."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import overload


def utcnow() -> datetime:
    """Current moment as an aware UTC datetime."""
    return datetime.now(UTC)


@overload
def as_utc(value: datetime) -> datetime: ...


@overload
def as_utc(value: None) -> None: ...


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime to aware UTC.

    SQLite returns naive datetimes (the stored value is already UTC), so a naive
    input is interpreted as UTC. Aware inputs in other zones are converted.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
