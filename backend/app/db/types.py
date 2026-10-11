"""Portable column types."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.timeutil import as_utc


class UTCDateTime(TypeDecorator[datetime]):
    """``DateTime(timezone=True)`` that always hands back aware UTC datetimes.

    SQLite drops the zone and returns naive values; the application only ever stores UTC,
    so a naive value read back is UTC. On write, aware values are converted to UTC first
    and naive ones are taken as UTC.
    """

    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else as_utc(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        return None if value is None else as_utc(value)
